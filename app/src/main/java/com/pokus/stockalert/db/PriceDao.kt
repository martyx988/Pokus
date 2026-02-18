package com.pokus.stockalert.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.pokus.stockalert.data.DailyPriceEntity
import com.pokus.stockalert.data.IntradayPriceEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PriceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertDaily(prices: List<DailyPriceEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertIntraday(prices: List<IntradayPriceEntity>)

    @Query("SELECT * FROM daily_prices WHERE symbol = :symbol ORDER BY date ASC")
    fun observeDaily(symbol: String): Flow<List<DailyPriceEntity>>

    @Query("SELECT * FROM intraday_prices WHERE symbol = :symbol AND tradingDate = :tradingDate ORDER BY timestamp ASC")
    fun observeIntradayForDate(symbol: String, tradingDate: String): Flow<List<IntradayPriceEntity>>

    @Query("SELECT * FROM intraday_prices WHERE symbol = :symbol ORDER BY timestamp DESC LIMIT 1")
    suspend fun latestIntraday(symbol: String): IntradayPriceEntity?

    @Query("SELECT * FROM intraday_prices WHERE symbol = :symbol ORDER BY timestamp DESC LIMIT 1 OFFSET 1")
    suspend fun previousIntraday(symbol: String): IntradayPriceEntity?

    @Query("SELECT * FROM daily_prices WHERE symbol = :symbol ORDER BY date DESC LIMIT 1")
    suspend fun latestDaily(symbol: String): DailyPriceEntity?

    @Query("SELECT * FROM daily_prices WHERE symbol = :symbol AND date < :date ORDER BY date DESC LIMIT 1")
    suspend fun previousDailyBefore(symbol: String, date: String): DailyPriceEntity?

    @Query("DELETE FROM intraday_prices WHERE tradingDate != :tradingDate")
    suspend fun clearIntradayOutsideDate(tradingDate: String)

    @Query("DELETE FROM daily_prices WHERE date < :minDate")
    suspend fun trimDailyBefore(minDate: String)

    @Query("SELECT s.symbol FROM stocks s LEFT JOIN daily_prices d ON d.symbol = s.symbol WHERE d.symbol IS NULL ORDER BY s.symbol LIMIT :limit")
    suspend fun symbolsWithoutDaily(limit: Int): List<String>

    @Query("SELECT COUNT(*) FROM stocks s LEFT JOIN daily_prices d ON d.symbol = s.symbol WHERE d.symbol IS NULL")
    suspend fun countSymbolsWithoutDaily(): Int
}
