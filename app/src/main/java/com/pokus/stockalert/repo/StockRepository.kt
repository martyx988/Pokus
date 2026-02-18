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
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

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
        val response = api.searchSymbols(query, key)
        val stocks = response.bestMatches.mapNotNull { row ->
            val exchange = row["4. region"] ?: return@mapNotNull null
            if (!exchange.contains("United States", ignoreCase = true)) return@mapNotNull null
            StockEntity(
                symbol = row["1. symbol"] ?: return@mapNotNull null,
                name = row["2. name"] ?: return@mapNotNull null,
                exchange = exchange,
                updatedAtEpochMs = System.currentTimeMillis()
            )
        }
        if (stocks.isNotEmpty()) stockDao.upsertStocks(stocks)
    }

    suspend fun refreshIntraday(symbol: String) {
        if (key.isBlank()) return
        val body = api.intraday(symbol, key)
        val series = body["Time Series (15min)"] as? Map<*, *> ?: return
        val points = series.mapNotNull { (ts, valuesAny) ->
            val values = valuesAny as? Map<*, *> ?: return@mapNotNull null
            IntradayPriceEntity(
                symbol = symbol,
                timestamp = ts.toString(),
                open = values["1. open"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                high = values["2. high"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                low = values["3. low"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                close = values["4. close"].toString().toDoubleOrNull() ?: return@mapNotNull null,
                volume = values["5. volume"].toString().toLongOrNull() ?: 0L
            )
        }
        priceDao.clearIntraday(symbol)
        priceDao.upsertIntraday(points)
    }

    suspend fun refreshDaily(symbol: String) {
        if (key.isBlank()) return
        val body = api.daily(symbol, key)
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

    fun observeIntraday(symbol: String): Flow<List<PricePoint>> =
        priceDao.observeIntraday(symbol).map { it.sortedBy { row -> row.timestamp }.map { p -> PricePoint(p.timestamp.takeLast(5), p.close) } }

    fun observeDaily(symbol: String): Flow<List<PricePoint>> =
        priceDao.observeDaily(symbol).map { it.sortedBy { row -> row.date }.map { p -> PricePoint(p.date, p.close) } }

    suspend fun addAlert(symbol: String, type: AlertType, rawValueInput: Double) {
        val latest = priceDao.latestIntradayClose(symbol)
        val normalized = if (type == AlertType.PERCENT_CHANGE_FROM_CURRENT) rawValueInput / 100.0 else rawValueInput
        alertDao.insert(
            AlertEntity(
                symbol = symbol,
                type = type,
                value = normalized,
                baselinePrice = if (type == AlertType.PERCENT_CHANGE_FROM_CURRENT) latest else null
            )
        )
    }

    fun observeAlerts(symbol: String) = alertDao.observeForSymbol(symbol)

    suspend fun enabledAlerts(): List<AlertEntity> = alertDao.allEnabled()

    suspend fun latestPrice(symbol: String): Double? = priceDao.latestIntradayClose(symbol)
}
