package com.pokus.stockalert.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.pokus.stockalert.data.TickerEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface StockDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertTickers(tickers: List<TickerEntity>)

    @Query("SELECT * FROM tickers WHERE symbol LIKE '%' || :query || '%' OR companyName LIKE '%' || :query || '%' ORDER BY symbol LIMIT 50")
    fun searchTickers(query: String): Flow<List<TickerEntity>>

    @Query("SELECT * FROM tickers WHERE symbol = :symbol LIMIT 1")
    suspend fun getTicker(symbol: String): TickerEntity?

    @Query("SELECT symbol FROM tickers ORDER BY symbol")
    suspend fun allSymbols(): List<String>

    @Query("SELECT COUNT(*) FROM tickers")
    suspend fun countTickers(): Int
}
