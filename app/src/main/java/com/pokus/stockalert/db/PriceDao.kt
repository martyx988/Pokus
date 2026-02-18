package com.pokus.stockalert.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.pokus.stockalert.data.DailyOpeningPriceEntity
import com.pokus.stockalert.data.HistoricalPriceEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PriceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertHistorical(prices: List<HistoricalPriceEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertDailyOpenings(prices: List<DailyOpeningPriceEntity>)

    @Query("SELECT * FROM historical_prices WHERE symbol = :symbol ORDER BY date ASC")
    fun observeHistorical(symbol: String): Flow<List<HistoricalPriceEntity>>

    @Query("SELECT * FROM daily_opening_prices WHERE symbol = :symbol ORDER BY date DESC LIMIT 1")
    suspend fun latestDailyOpening(symbol: String): DailyOpeningPriceEntity?

    @Query("SELECT * FROM daily_opening_prices WHERE symbol = :symbol ORDER BY date DESC LIMIT 1 OFFSET 1")
    suspend fun previousDailyOpening(symbol: String): DailyOpeningPriceEntity?

    @Query("SELECT * FROM historical_prices WHERE symbol = :symbol ORDER BY date DESC LIMIT 1")
    suspend fun latestHistorical(symbol: String): HistoricalPriceEntity?

    @Query("SELECT * FROM historical_prices WHERE symbol = :symbol AND date < :date ORDER BY date DESC LIMIT 1")
    suspend fun previousHistoricalBefore(symbol: String, date: String): HistoricalPriceEntity?

    @Query("DELETE FROM daily_opening_prices WHERE date < :minDate")
    suspend fun trimOpeningsBefore(minDate: String)

    @Query("DELETE FROM historical_prices WHERE date < :minDate")
    suspend fun trimHistoricalBefore(minDate: String)

    @Query("SELECT t.symbol FROM tickers t LEFT JOIN historical_prices h ON h.symbol = t.symbol WHERE h.symbol IS NULL ORDER BY t.symbol LIMIT :limit")
    suspend fun symbolsWithoutHistorical(limit: Int): List<String>

    @Query("SELECT COUNT(*) FROM tickers t LEFT JOIN historical_prices h ON h.symbol = t.symbol WHERE h.symbol IS NULL")
    suspend fun countSymbolsWithoutHistorical(): Int
}
