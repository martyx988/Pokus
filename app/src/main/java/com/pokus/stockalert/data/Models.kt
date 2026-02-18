package com.pokus.stockalert.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "stocks")
data class StockEntity(
    @PrimaryKey val symbol: String,
    val name: String,
    val exchange: String,
    val updatedAtEpochMs: Long
)

@Entity(
    tableName = "daily_prices",
    primaryKeys = ["symbol", "date"],
    foreignKeys = [
        ForeignKey(
            entity = StockEntity::class,
            parentColumns = ["symbol"],
            childColumns = ["symbol"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("symbol")]
)
data class DailyPriceEntity(
    val symbol: String,
    val date: String,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long
)

@Entity(
    tableName = "intraday_prices",
    primaryKeys = ["symbol", "timestamp"],
    foreignKeys = [
        ForeignKey(
            entity = StockEntity::class,
            parentColumns = ["symbol"],
            childColumns = ["symbol"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("symbol")]
)
data class IntradayPriceEntity(
    val symbol: String,
    val timestamp: String,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long
)

enum class AlertType {
    PERCENT_CHANGE_FROM_CURRENT,
    DROPS_BELOW,
    RISES_ABOVE
}

@Entity(
    tableName = "alerts",
    indices = [Index("symbol")],
    foreignKeys = [
        ForeignKey(
            entity = StockEntity::class,
            parentColumns = ["symbol"],
            childColumns = ["symbol"],
            onDelete = ForeignKey.CASCADE
        )
    ]
)
data class AlertEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val symbol: String,
    val type: AlertType,
    val value: Double,
    val baselinePrice: Double?,
    val enabled: Boolean = true,
    val createdAtEpochMs: Long = System.currentTimeMillis()
)

data class PricePoint(
    val label: String,
    val price: Double
)
