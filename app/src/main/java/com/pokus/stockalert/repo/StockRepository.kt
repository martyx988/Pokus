package com.pokus.stockalert.repo

import com.pokus.stockalert.BuildConfig
import com.pokus.stockalert.data.AlertEntity
import com.pokus.stockalert.data.AlertType
import com.pokus.stockalert.data.DailyPriceEntity
import com.pokus.stockalert.data.IntradayPriceEntity
import com.pokus.stockalert.data.PricePoint
import com.pokus.stockalert.data.StockEntity
import com.pokus.stockalert.db.AlertDao
import com.pokus.stockalert.db.PriceDao
import com.pokus.stockalert.db.StockDao
import com.pokus.stockalert.network.AlphaVantageService
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.io.IOException
import java.time.LocalDate

class StockRepository(
    private val api: AlphaVantageService,
    private val stockDao: StockDao,
    private val priceDao: PriceDao,
    private val alertDao: AlertDao
) {
    private val key: String get() = BuildConfig.ALPHA_VANTAGE_API_KEY

    fun searchLocal(query: String): Flow<List<StockEntity>> = stockDao.searchStocks(query)

    suspend fun refreshSearch(query: String) {
        if (key.isBlank() || query.isBlank()) return
        val response = retryApi { api.searchSymbols(query, key) } ?: return
        val stocks = response.bestMatches.mapNotNull { row ->
            val exchange = row["4. region"] ?: return@mapNotNull null
            val name = row["2. name"] ?: return@mapNotNull null
            val symbol = row["1. symbol"] ?: return@mapNotNull null
            if (!exchange.contains("United States", ignoreCase = true)) return@mapNotNull null
            StockEntity(symbol = symbol, name = name, exchange = exchange, updatedAtEpochMs = System.currentTimeMillis())
        }
        if (stocks.isNotEmpty()) stockDao.upsertStocks(stocks)
    }

    suspend fun refreshIntraday(symbol: String) {
        if (key.isBlank()) return
        val body = retryApi { api.intraday(symbol, key) } ?: return
        val series = body["Time Series (15min)"] as? Map<*, *> ?: return
        val points = series.mapNotNull { (ts, valuesAny) ->
            val timestamp = ts.toString()
            val values = valuesAny as? Map<*, *> ?: return@mapNotNull null
            IntradayPriceEntity(
                symbol = symbol,
                timestamp = timestamp,
                tradingDate = timestamp.take(10),
                open = values["1. open"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                high = values["2. high"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                low = values["3. low"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                close = values["4. close"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                volume = values["5. volume"].toString().toLongOrNull() ?: 0L
            )
        }
        priceDao.upsertIntraday(points)
    }

    suspend fun refreshDaily(symbol: String) {
        if (key.isBlank()) return
        val body = retryApi { api.daily(symbol, key) } ?: return
        val series = body["Time Series (Daily)"] as? Map<*, *> ?: return
        val points = series.mapNotNull { (date, valuesAny) ->
            val values = valuesAny as? Map<*, *> ?: return@mapNotNull null
            DailyPriceEntity(
                symbol = symbol,
                date = date.toString(),
                open = values["1. open"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                high = values["2. high"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                low = values["3. low"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                close = values["4. close"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                volume = values["6. volume"].toString().toLongOrNull() ?: 0L
            )
        }
        priceDao.upsertDaily(points)
    }

    suspend fun applyRetention(today: LocalDate) {
        priceDao.clearIntradayOutsideDate(today.toString())
        priceDao.trimDailyBefore(today.minusYears(10).toString())
    }

    fun observeIntraday(symbol: String, tradingDate: String): Flow<List<PricePoint>> =
        priceDao.observeIntradayForDate(symbol, tradingDate)
            .map { rows -> rows.map { PricePoint(it.timestamp.takeLast(5), it.close) } }

    fun observeDaily(symbol: String): Flow<List<PricePoint>> =
        priceDao.observeDaily(symbol).map { rows -> rows.map { PricePoint(it.date, it.close) } }

    suspend fun addAlert(symbol: String, type: AlertType, rawValueInput: Double, deleteOnTrigger: Boolean) {
        val normalized = if (type == AlertType.PERCENT_CHANGE_FROM_PREVIOUS) rawValueInput / 100.0 else rawValueInput
        alertDao.insert(
            AlertEntity(
                symbol = symbol,
                type = type,
                value = normalized,
                deleteOnTrigger = deleteOnTrigger
            )
        )
    }

    fun observeAlerts(symbol: String) = alertDao.observeForSymbol(symbol)

    suspend fun enabledAlerts(): List<AlertEntity> = alertDao.allEnabled()

    suspend fun latestIntraday(symbol: String) = priceDao.latestIntraday(symbol)

    suspend fun previousIntraday(symbol: String) = priceDao.previousIntraday(symbol)

    suspend fun latestDaily(symbol: String) = priceDao.latestDaily(symbol)

    suspend fun previousDailyBefore(symbol: String, date: String) = priceDao.previousDailyBefore(symbol, date)

    suspend fun deleteAlert(alertId: Long) = alertDao.deleteById(alertId)

    suspend fun updateAlertConditionState(alertId: Long, active: Boolean) = alertDao.updateConditionState(alertId, active)

    private suspend fun <T> retryApi(block: suspend () -> T): T? {
        var attempt = 0
        var delayMs = 700L
        while (attempt < 3) {
            try {
                return block()
            } catch (_: IOException) {
                attempt++
                if (attempt >= 3) return null
                delay(delayMs)
                delayMs *= 2
            } catch (_: Exception) {
                return null
            }
        }
        return null
    }
}
