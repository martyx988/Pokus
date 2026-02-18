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
import com.pokus.stockalert.network.AlphaVantageService
import com.pokus.stockalert.network.TwelveDataService
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.URL
import java.time.LocalDate

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
    private val twelveApi: TwelveDataService,
    private val alphaApi: AlphaVantageService,
    private val stockDao: StockDao,
    private val priceDao: PriceDao,
    private val alertDao: AlertDao
) {
    private val alphaKey: String get() = BuildConfig.ALPHA_VANTAGE_API_KEY
    private val twelveKey: String get() = BuildConfig.TWELVE_DATA_API_KEY

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
        if (entities.isEmpty()) return 0
        stockDao.upsertTickers(entities)
        return entities.size
    }

    suspend fun developerLoadLastWeekPricesForAllTickers(batchSize: Int = 50): String {
        if (stockDao.countTickers() == 0) refreshNyseTickers()

        val symbols = stockDao.allSymbols()
        if (symbols.isEmpty()) return "No tickers available."

        var ok = 0
        var failed = 0
        symbols.chunked(batchSize).forEach { batch ->
            for (symbol in batch) {
                val loaded = loadWeeklyForSymbol(symbol)
                if (loaded) ok++ else failed++
                delay(150L)
            }
        }
        return "Loaded last-week prices for $ok tickers. Failed: $failed"
    }

    private suspend fun loadWeeklyForSymbol(symbol: String): Boolean {
        if (twelveKey.isBlank()) return false
        val response = retryApi { twelveApi.timeSeries(symbol, "1day", twelveKey, outputSize = 7) } ?: return false
        val values = response.values ?: return false
        val historical = values.mapNotNull { row ->
            val date = row["datetime"]?.take(10) ?: return@mapNotNull null
            val open = row["open"]?.toDoubleOrNull() ?: return@mapNotNull null
            val high = row["high"]?.toDoubleOrNull() ?: return@mapNotNull null
            val low = row["low"]?.toDoubleOrNull() ?: return@mapNotNull null
            val close = row["close"]?.toDoubleOrNull() ?: return@mapNotNull null
            val volume = row["volume"]?.toLongOrNull() ?: 0L
            HistoricalPriceEntity(symbol, date, open, high, low, close, volume)
        }
        if (historical.isEmpty()) return false
        priceDao.upsertHistorical(historical)
        priceDao.upsertDailyOpenings(historical.map { DailyOpeningPriceEntity(it.symbol, it.date, it.open, it.provider) })
        return true
    }

    suspend fun populateNyseUniverseAndDailyHistory(
        maxSymbolsPerRun: Int = 25,
        symbolPageSize: Int = 1000,
        maxSymbolPages: Int = 10
    ): NyseBootstrapResult {
        val inserted = refreshNyseTickers()
        val targets = priceDao.symbolsWithoutHistorical(maxSymbolsPerRun)
        var hydrated = 0
        targets.forEach {
            if (loadWeeklyForSymbol(it)) hydrated++
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
    }
}
