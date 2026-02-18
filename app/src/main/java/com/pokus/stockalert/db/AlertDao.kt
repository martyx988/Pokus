package com.pokus.stockalert.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.pokus.stockalert.data.AlertEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface AlertDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(alert: AlertEntity)

    @Query("SELECT * FROM alerts WHERE symbol = :symbol ORDER BY createdAtEpochMs DESC")
    fun observeForSymbol(symbol: String): Flow<List<AlertEntity>>

    @Query("SELECT * FROM alerts WHERE enabled = 1")
    suspend fun allEnabled(): List<AlertEntity>

    @Query("DELETE FROM alerts WHERE id = :alertId")
    suspend fun deleteById(alertId: Long)

    @Query("UPDATE alerts SET conditionActive = :active WHERE id = :alertId")
    suspend fun updateConditionState(alertId: Long, active: Boolean)
}
