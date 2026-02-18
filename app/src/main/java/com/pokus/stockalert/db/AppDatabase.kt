package com.pokus.stockalert.db

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.pokus.stockalert.data.AlertEntity
import com.pokus.stockalert.data.DailyOpeningPriceEntity
import com.pokus.stockalert.data.HistoricalPriceEntity
import com.pokus.stockalert.data.TickerEntity

@Database(
    entities = [TickerEntity::class, HistoricalPriceEntity::class, DailyOpeningPriceEntity::class, AlertEntity::class],
    version = 2,
    exportSchema = false
)
@TypeConverters(RoomConverters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun stockDao(): StockDao
    abstract fun priceDao(): PriceDao
    abstract fun alertDao(): AlertDao
}
