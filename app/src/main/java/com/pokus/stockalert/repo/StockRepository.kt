package com.pokus.stockalert.repo


import com.pokus.stockalert.BuildConfig
import com.pokus.stockalert.data.AlertEntity
import com.pokus.stockalert.data.AlertType
import com.pokus.stockalert.data.DailyOpeningPriceEntity
import com.pokus.stockalert.data.HistoricalPriceEntity
import com.pokus.stockalert.data.PricePoint
import com.pokus.stockalert.data.TickerEntity
import com.pokus.stockalert.db.AlertDao
import com.pokus.stockalert.db.PriceDao
import com.pokus.stockalert.db.StockDao
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext

import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.io.IOException
import java.net.URL
import java.time.Instant

import java.time.LocalDate
import java.time.ZoneOffset

data class NyseBootstrapResult(
    val insertedSymbols: Int,
    val hydratedSymbols: Int,
    val symbolsRemainingWithoutDaily: Int
)

data class TickerSeedRow(
    val symbol: String,
    val companyName: String,
    val securityType: String
)

class StockRepository(
    private val stockDao: StockDao,
    private val priceDao: PriceDao,
    private val alertDao: AlertDao
) {
    private enum class LoadStatus {
        SUCCESS,
        NO_DATA,
        ERROR
    }

    fun searchLocal(query: String): Flow<List<TickerEntity>> = stockDao.searchTickers(query)

    suspend fun refreshSearch(query: String) {
        if (query.isBlank()) return
        if (stockDao.countTickers() == 0) {
            refreshNyseTickers()
        }
    }

    suspend fun refreshNyseTickers(limit: Int? = null): Int {

        val text = try {
            withContext(Dispatchers.IO) {
                URL("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt").readText()
            }
        } catch (_: Exception) {
            return 0
        }

        val rows = parseNyseTickerRows(text, limit)
        if (rows.isEmpty()) return 0

        val now = System.currentTimeMillis()
        val entities = rows.map {
            TickerEntity(
                symbol = it.symbol,
                companyName = it.companyName,
                securityType = it.securityType,
                exchange = "NYSE",
                updatedAtEpochMs = now
            )
        }

        stockDao.upsertTickers(entities)
        return entities.size
    }


    suspend fun developerLoadLastWeekPricesForAllTickers(
        maxSymbolsPerRun: Int = 300,
        perSymbolTimeoutMs: Long = 15_000L
    ): String {

        if (stockDao.countTickers() == 0) refreshNyseTickers()

        val symbols = stockDao.allSymbols()
        if (symbols.isEmpty()) return "No tickers available."


        val targets = symbols.take(maxSymbolsPerRun)
        var ok = 0
        var failed = 0
        for (symbol in targets) {
            val loaded = withTimeoutOrNull(perSymbolTimeoutMs) {
                loadWeeklyForSymbolDetailed(symbol)
            } ?: LoadStatus.ERROR

            if (loaded == LoadStatus.SUCCESS) ok++ else failed++
            delay(60L)
        }

        val suffix = if (symbols.size > targets.size) {
            " Processed first ${targets.size}/${symbols.size} tickers to keep developer load bounded."
        } else {
            ""
        }
        return "Loaded last-week prices for $ok tickers. Failed: $failed.$suffix"
    }

    private suspend fun loadWeeklyForSymbol(symbol: String): Boolean {
        return loadWeeklyForSymbolDetailed(symbol) == LoadStatus.SUCCESS
    }

    private suspend fun loadWeeklyForSymbolDetailed(symbol: String): LoadStatus {
        val rows = fetchYahooHistorical(symbol)
        if (rows.isEmpty()) return LoadStatus.NO_DATA

        priceDao.upsertHistorical(rows)
        val latest = rows.maxByOrNull { it.date } ?: return LoadStatus.NO_DATA
        priceDao.upsertDailyOpenings(
            listOf(
                DailyOpeningPriceEntity(
                    symbol = latest.symbol,
                    date = latest.date,
                    open = latest.open,
                    provider = latest.provider
                )
            )
        )
        return LoadStatus.SUCCESS
    }

    private suspend fun fetchYahooHistorical(symbol: String): List<HistoricalPriceEntity> {
        val url = "https://query1.finance.yahoo.com/v8/finance/chart/$symbol?range=1mo&interval=1d&events=history&includeAdjustedClose=true"
        val body = retryApi {
            withContext(Dispatchers.IO) { URL(url).readText() }
        } ?: return emptyList()

        return parseYahooChartRows(body, symbol)
            .sortedBy { it.date }
            .takeLast(7)

    }

    suspend fun populateNyseUniverseAndDailyHistory(
        maxSymbolsPerRun: Int = 25,
        symbolPageSize: Int = 1000,
        maxSymbolPages: Int = 10
    ): NyseBootstrapResult {
        val inserted = refreshNyseTickers()
        val targets = priceDao.symbolsWithoutHistorical(maxSymbolsPerRun)
        var hydrated = 0

        targets.forEach { symbol ->
            if (loadWeeklyForSymbol(symbol)) hydrated++

        }
        return NyseBootstrapResult(inserted, hydrated, priceDao.countSymbolsWithoutHistorical())
    }

    suspend fun refreshTodayOpeningAndRecentDaily(symbol: String): Boolean = loadWeeklyForSymbol(symbol)

    suspend fun refreshIntraday(symbol: String) {
        // New schema keeps daily opening + historical prices only.
        loadWeeklyForSymbol(symbol)
    }

    suspend fun refreshDaily(symbol: String): Boolean = loadWeeklyForSymbol(symbol)

    suspend fun refreshDailyCompact(symbol: String): String = if (loadWeeklyForSymbol(symbol)) "ok" else "fail"

    suspend fun applyRetention(today: LocalDate) {
        val minDate = today.minusYears(10).toString()
        priceDao.trimHistoricalBefore(minDate)
        priceDao.trimOpeningsBefore(minDate)
    }

    fun observeIntraday(symbol: String, tradingDate: String): Flow<List<PricePoint>> =
        observeDaily(symbol)

    fun observeDaily(symbol: String): Flow<List<PricePoint>> =
        priceDao.observeHistorical(symbol).map { rows -> rows.map { PricePoint(it.date, it.close) } }

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

    suspend fun latestIntraday(symbol: String) = priceDao.latestDailyOpening(symbol)?.let {
        HistoricalPriceEntity(symbol, it.date, it.open, it.open, it.open, it.open, 0L, it.provider)
    }


    suspend fun previousIntraday(symbol: String) = priceDao.previousDailyOpening(symbol)?.let {
        HistoricalPriceEntity(symbol, it.date, it.open, it.open, it.open, it.open, 0L, it.provider)
    }

    suspend fun latestDaily(symbol: String) = priceDao.latestHistorical(symbol)

    suspend fun previousDailyBefore(symbol: String, date: String) = priceDao.previousHistoricalBefore(symbol, date)


    suspend fun latestDaily(symbol: String) = priceDao.latestHistorical(symbol)
    suspend fun previousDailyBefore(symbol: String, date: String) = priceDao.previousHistoricalBefore(symbol, date)
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

    companion object {
        fun classifySecurityType(etfFlag: String, companyName: String): String {
            val flag = etfFlag.trim().uppercase()
            val upperName = companyName.trim().uppercase()
            if (flag == "Y") {
                return when {
                    Regex("\\bETN\\b|EXCHANGE TRADED NOTE").containsMatchIn(upperName) -> "ETN"
                    Regex("\\bETC\\b|EXCHANGE TRADED COMMODITY").containsMatchIn(upperName) -> "ETC"
                    else -> "ETF"
                }
            }
            return "STOCK"
        }

        fun parseNyseTickerRows(raw: String, limit: Int? = null): List<TickerSeedRow> {
            val lines = raw.lineSequence().filter { it.isNotBlank() }.toList()
            if (lines.size < 2) return emptyList()
            val header = lines.first().split('|')
            val idxExchange = header.indexOf("Exchange")
            val idxTicker = header.indexOf("ACT Symbol")
            val idxName = header.indexOf("Security Name")
            val idxEtf = header.indexOf("ETF")
            if (idxExchange < 0 || idxTicker < 0 || idxName < 0 || idxEtf < 0) return emptyList()

            val out = mutableListOf<TickerSeedRow>()
            for (line in lines.drop(1)) {
                val cols = line.split('|')
                if (cols.size <= maxOf(idxExchange, idxTicker, idxName, idxEtf)) continue
                val exchange = cols[idxExchange].trim().uppercase()
                if (exchange !in setOf("N", "P", "A")) continue
                val symbol = cols[idxTicker].trim()
                if (!symbol.matches(Regex("[A-Za-z]{1,5}"))) continue
                val name = cols[idxName].trim()
                val type = classifySecurityType(cols[idxEtf], name)
                out += TickerSeedRow(symbol, name, type)
                if (limit != null && out.size >= limit) break
            }
            return out.distinctBy { it.symbol }.sortedBy { it.symbol }
        }


        fun parseYahooChartRows(rawJson: String, symbol: String): List<HistoricalPriceEntity> {
            val root = JSONObject(rawJson)
            val chart = root.optJSONObject("chart") ?: return emptyList()
            val resultArray = chart.optJSONArray("result") ?: return emptyList()
            if (resultArray.length() == 0) return emptyList()

            val result = resultArray.optJSONObject(0) ?: return emptyList()
            val timestamps = result.optJSONArray("timestamp") ?: return emptyList()
            val indicators = result.optJSONObject("indicators") ?: return emptyList()
            val quote = indicators.optJSONArray("quote")?.optJSONObject(0) ?: return emptyList()

            val opens = quote.optJSONArray("open") ?: return emptyList()
            val highs = quote.optJSONArray("high") ?: return emptyList()
            val lows = quote.optJSONArray("low") ?: return emptyList()
            val closes = quote.optJSONArray("close") ?: return emptyList()
            val volumes = quote.optJSONArray("volume") ?: return emptyList()

            val count = listOf(
                timestamps.length(),
                opens.length(),
                highs.length(),
                lows.length(),
                closes.length(),
                volumes.length()
            ).minOrNull() ?: 0

            val out = mutableListOf<HistoricalPriceEntity>()
            for (i in 0 until count) {
                if (timestamps.isNull(i) || opens.isNull(i) || highs.isNull(i) || lows.isNull(i) || closes.isNull(i) || volumes.isNull(i)) {
                    continue
                }

                val epoch = timestamps.optLong(i, Long.MIN_VALUE)
                if (epoch == Long.MIN_VALUE) continue

                val open = opens.optDouble(i, Double.NaN)
                val high = highs.optDouble(i, Double.NaN)
                val low = lows.optDouble(i, Double.NaN)
                val close = closes.optDouble(i, Double.NaN)
                if (open.isNaN() || high.isNaN() || low.isNaN() || close.isNaN()) continue

                val volume = volumes.optLong(i, 0L)
                val date = Instant.ofEpochSecond(epoch).atZone(ZoneOffset.UTC).toLocalDate().toString()

                out += HistoricalPriceEntity(
                    symbol = symbol,
                    date = date,
                    open = open,
                    high = high,
                    low = low,
                    close = close,
                    volume = volume,
                    provider = "yfinance"
                )
            }

            return out
                .distinctBy { it.date }
                .sortedBy { it.date }
        }

    }
}
