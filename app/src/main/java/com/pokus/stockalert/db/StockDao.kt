package com.pokus.stockalert.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.pokus.stockalert.data.StockEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface StockDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertStocks(stocks: List<StockEntity>)

    @Query("SELECT * FROM stocks WHERE symbol LIKE '%' || :query || '%' OR name LIKE '%' || :query || '%' ORDER BY symbol LIMIT 50")
    fun searchStocks(query: String): Flow<List<StockEntity>>

    @Query("SELECT * FROM stocks WHERE symbol = :symbol LIMIT 1")
    suspend fun getStock(symbol: String): StockEntity?
}
