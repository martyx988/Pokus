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

    @Query("SELECT * FROM daily_prices WHERE symbol = :symbol ORDER BY date DESC")
    fun observeDaily(symbol: String): Flow<List<DailyPriceEntity>>

    @Query("SELECT * FROM intraday_prices WHERE symbol = :symbol ORDER BY timestamp DESC")
    fun observeIntraday(symbol: String): Flow<List<IntradayPriceEntity>>

    @Query("SELECT close FROM intraday_prices WHERE symbol = :symbol ORDER BY timestamp DESC LIMIT 1")
    suspend fun latestIntradayClose(symbol: String): Double?

    @Query("DELETE FROM intraday_prices WHERE symbol = :symbol")
    suspend fun clearIntraday(symbol: String)
}
