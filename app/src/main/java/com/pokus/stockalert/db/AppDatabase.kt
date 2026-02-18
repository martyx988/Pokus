package com.pokus.stockalert.db

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.pokus.stockalert.data.AlertEntity
import com.pokus.stockalert.data.DailyPriceEntity
import com.pokus.stockalert.data.IntradayPriceEntity
import com.pokus.stockalert.data.StockEntity

@Database(
    entities = [StockEntity::class, DailyPriceEntity::class, IntradayPriceEntity::class, AlertEntity::class],
    version = 1,
    exportSchema = false
)
@TypeConverters(RoomConverters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun stockDao(): StockDao
    abstract fun priceDao(): PriceDao
    abstract fun alertDao(): AlertDao
}
