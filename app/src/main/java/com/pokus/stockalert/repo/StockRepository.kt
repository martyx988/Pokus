package com.pokus.stockalert.repo

import android.content.Context
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
import com.pokus.stockalert.network.TwelveDataService
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.io.IOException
import java.time.LocalDate

data class NyseBootstrapResult(
    val insertedSymbols: Int,
    val hydratedSymbols: Int,
    val symbolsRemainingWithoutDaily: Int
)

class StockRepository(
    private val twelveApi: TwelveDataService,
    private val alphaApi: AlphaVantageService,
    private val stockDao: StockDao,
    private val priceDao: PriceDao,
    private val alertDao: AlertDao
) {
    private val alphaKey: String get() = BuildConfig.ALPHA_VANTAGE_API_KEY
    private val twelveKey: String get() = BuildConfig.TWELVE_DATA_API_KEY

    fun searchLocal(query: String): Flow<List<StockEntity>> = stockDao.searchStocks(query)

    suspend fun refreshSearch(query: String) {
        if (query.isBlank()) return

        val twelveStocks = if (twelveKey.isNotBlank()) {
            retryApi {
                twelveApi.searchSymbols(query, twelveKey)
            }?.data?.mapNotNull { row ->
                val exchange = row.exchange ?: return@mapNotNull null
                val symbol = row.symbol
                val name = row.name ?: symbol
                if (!exchange.contains("NYSE", ignoreCase = true) && !exchange.contains("United States", ignoreCase = true)) return@mapNotNull null
                StockEntity(symbol = symbol, name = name, exchange = exchange, updatedAtEpochMs = System.currentTimeMillis())
            }
        } else {
            emptyList()
        }

        val result = if (!twelveStocks.isNullOrEmpty()) {
            twelveStocks
        } else {
            if (alphaKey.isBlank()) emptyList() else {
                retryApi { alphaApi.searchSymbols(query, alphaKey) }?.bestMatches?.mapNotNull { row ->
                    val exchange = row["4. region"] ?: return@mapNotNull null
                    val name = row["2. name"] ?: return@mapNotNull null
                    val symbol = row["1. symbol"] ?: return@mapNotNull null
                    if (!exchange.contains("United States", ignoreCase = true)) return@mapNotNull null
                    StockEntity(symbol = symbol, name = name, exchange = exchange, updatedAtEpochMs = System.currentTimeMillis())
                } ?: emptyList()
            }
        }

        if (result.isNotEmpty()) stockDao.upsertStocks(result)
    }

    suspend fun preloadDailySnapshotFromAssets(
        context: Context,
        assetPath: String = "bootstrap/nyse_daily_snapshot_2016-12-29_2016-12-30.csv"
    ): Int {
        if (priceDao.countDailyRows() > 0) return 0

        val now = System.currentTimeMillis()
        val stocks = mutableListOf<StockEntity>()
        val prices = mutableListOf<DailyPriceEntity>()

        context.assets.open(assetPath).bufferedReader().use { reader ->
            reader.readLine() // header
            reader.lineSequence().forEach { line ->
                val cols = line.split(',')
                if (cols.size < 7) return@forEach

                val symbol = cols[0].trim()
                val date = cols[1].trim()
                val open = cols[2].toDoubleOrNull() ?: return@forEach
                val high = cols[3].toDoubleOrNull() ?: return@forEach
                val low = cols[4].toDoubleOrNull() ?: return@forEach
                val close = cols[5].toDoubleOrNull() ?: return@forEach
                val volume = cols[6].toLongOrNull() ?: 0L
                if (symbol.isBlank() || date.isBlank()) return@forEach

                stocks += StockEntity(
                    symbol = symbol,
                    name = symbol,
                    exchange = "NYSE",
                    updatedAtEpochMs = now
                )
                prices += DailyPriceEntity(
                    symbol = symbol,
                    date = date,
                    open = open,
                    high = high,
                    low = low,
                    close = close,
                    volume = volume
                )
            }
        }

        if (stocks.isEmpty() || prices.isEmpty()) return 0
        stockDao.upsertStocks(stocks.distinctBy { it.symbol })
        priceDao.upsertDaily(prices)
        return prices.size
    }

    suspend fun developerManualApiLoadForAppleMicrosoft(): String {
        val symbols = listOf("AAPL", "MSFT")
        val now = System.currentTimeMillis()
        stockDao.upsertStocks(symbols.map { symbol ->
            StockEntity(symbol = symbol, name = symbol, exchange = "NYSE", updatedAtEpochMs = now)
        })

        val lines = mutableListOf<String>()
        for (symbol in symbols) {
            val apiOk = refreshTodayOpeningAndRecentDaily(symbol)
            if (!apiOk) refreshDaily(symbol)

            val latest = latestDaily(symbol)
            val previous = latest?.let { previousDailyBefore(symbol, it.date) }
            val points = (if (latest != null) 1 else 0) + (if (previous != null) 1 else 0)

            lines += "$symbol: api=${if (apiOk) "ok" else "fail"}, latest=${latest?.date ?: "-"}, previous=${previous?.date ?: "-"}, points=$points"
        }

        return lines.joinToString("\n")
    }

    suspend fun refreshTodayOpeningAndRecentDaily(symbol: String): Boolean {
        if (twelveKey.isBlank()) return false
        val response = retryApi { twelveApi.timeSeries(symbol, "1day", twelveKey, outputSize = 2) } ?: return false
        val values = response.values ?: return false
        val points = values.mapNotNull { valuesRow ->
            val date = valuesRow["datetime"] ?: return@mapNotNull null
            DailyPriceEntity(
                symbol = symbol,
                date = date.take(10),
                open = valuesRow["open"]?.toDoubleOrNull() ?: return@mapNotNull null,
                high = valuesRow["high"]?.toDoubleOrNull() ?: return@mapNotNull null,
                low = valuesRow["low"]?.toDoubleOrNull() ?: return@mapNotNull null,
                close = valuesRow["close"]?.toDoubleOrNull() ?: return@mapNotNull null,
                volume = valuesRow["volume"]?.toLongOrNull() ?: 0L
            )
        }
        if (points.isEmpty()) return false
        priceDao.upsertDaily(points)
        return true
    }

    suspend fun populateNyseUniverseAndDailyHistory(
        maxSymbolsPerRun: Int = 25,
        symbolPageSize: Int = 1000,
        maxSymbolPages: Int = 10
    ): NyseBootstrapResult {
        if (twelveKey.isBlank()) {
            return NyseBootstrapResult(insertedSymbols = 0, hydratedSymbols = 0, symbolsRemainingWithoutDaily = 0)
        }

        val now = System.currentTimeMillis()
        var insertedSymbols = 0
        var page = 1
        while (page <= maxSymbolPages) {
            val response = retryApi {
                twelveApi.stocks(
                    exchange = "NYSE",
                    country = "United States",
                    apiKey = twelveKey,
                    page = page,
                    outputSize = symbolPageSize
                )
            } ?: break

            val mapped = response.data
                .asSequence()
                .filter { row -> row.symbol.isNotBlank() }
                .map { row ->
                    StockEntity(
                        symbol = row.symbol,
                        name = row.name ?: row.symbol,
                        exchange = row.exchange ?: "NYSE",
                        updatedAtEpochMs = now
                    )
                }
                .toList()

            if (mapped.isEmpty()) break
            stockDao.upsertStocks(mapped)
            insertedSymbols += mapped.size

            val totalPages = response.meta?.totalPages
            if (totalPages != null && page >= totalPages) break
            page++
        }

        var hydrated = 0
        val targets = priceDao.symbolsWithoutDaily(maxSymbolsPerRun)
        for (symbol in targets) {
            val response = retryApi { twelveApi.timeSeries(symbol, "1day", twelveKey, outputSize = 3000) } ?: continue
            val values = response.values ?: continue
            val points = values.mapNotNull { valuesRow ->
                val date = valuesRow["datetime"] ?: return@mapNotNull null
                DailyPriceEntity(
                    symbol = symbol,
                    date = date.take(10),
                    open = valuesRow["open"]?.toDoubleOrNull() ?: return@mapNotNull null,
                    high = valuesRow["high"]?.toDoubleOrNull() ?: return@mapNotNull null,
                    low = valuesRow["low"]?.toDoubleOrNull() ?: return@mapNotNull null,
                    close = valuesRow["close"]?.toDoubleOrNull() ?: return@mapNotNull null,
                    volume = valuesRow["volume"]?.toLongOrNull() ?: 0L
                )
            }
            if (points.isNotEmpty()) {
                priceDao.upsertDaily(points)
                hydrated++
            }
            delay(200L)
        }

        val remaining = priceDao.countSymbolsWithoutDaily()
        return NyseBootstrapResult(
            insertedSymbols = insertedSymbols,
            hydratedSymbols = hydrated,
            symbolsRemainingWithoutDaily = remaining
        )
    }

    suspend fun refreshIntraday(symbol: String) {
        val twelveWorked = if (twelveKey.isNotBlank()) {
            val response = retryApi { twelveApi.timeSeries(symbol, "15min", twelveKey, outputSize = 200) }
            val values = response?.values
            if (!values.isNullOrEmpty()) {
                val points = values.mapNotNull { valuesRow ->
                    val timestamp = valuesRow["datetime"] ?: return@mapNotNull null
                    IntradayPriceEntity(
                        symbol = symbol,
                        timestamp = timestamp,
                        tradingDate = timestamp.take(10),
                        open = valuesRow["open"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        high = valuesRow["high"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        low = valuesRow["low"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        close = valuesRow["close"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        volume = valuesRow["volume"]?.toLongOrNull() ?: 0L
                    )
                }
                if (points.isNotEmpty()) {
                    priceDao.upsertIntraday(points)
                    true
                } else false
            } else false
        } else false

        if (twelveWorked) return
        if (alphaKey.isBlank()) return
        val body = retryApi { alphaApi.intraday(symbol, alphaKey) } ?: return
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
        if (points.isNotEmpty()) priceDao.upsertIntraday(points)
    }

    suspend fun refreshDaily(symbol: String) {
        val twelveWorked = if (twelveKey.isNotBlank()) {
            val response = retryApi { twelveApi.timeSeries(symbol, "1day", twelveKey, outputSize = 3000) }
            val values = response?.values
            if (!values.isNullOrEmpty()) {
                val points = values.mapNotNull { valuesRow ->
                    val date = valuesRow["datetime"] ?: return@mapNotNull null
                    DailyPriceEntity(
                        symbol = symbol,
                        date = date.take(10),
                        open = valuesRow["open"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        high = valuesRow["high"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        low = valuesRow["low"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        close = valuesRow["close"]?.toDoubleOrNull() ?: return@mapNotNull null,
                        volume = valuesRow["volume"]?.toLongOrNull() ?: 0L
                    )
                }
                if (points.isNotEmpty()) {
                    priceDao.upsertDaily(points)
                    true
                } else false
            } else false
        } else false

        if (twelveWorked) return
        if (alphaKey.isBlank()) return
        val body = retryApi { alphaApi.daily(symbol, alphaKey) } ?: return
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
        if (points.isNotEmpty()) priceDao.upsertDaily(points)
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
