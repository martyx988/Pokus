package com.pokus.stockalert.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "tickers")
data class TickerEntity(
    @PrimaryKey val symbol: String,
    val companyName: String,
    val securityType: String,
    val exchange: String,
    val updatedAtEpochMs: Long
)

@Entity(
    tableName = "historical_prices",
    primaryKeys = ["symbol", "date"],
    foreignKeys = [
        ForeignKey(
            entity = TickerEntity::class,
            parentColumns = ["symbol"],
            childColumns = ["symbol"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("symbol"), Index("date")]
)
data class HistoricalPriceEntity(
    val symbol: String,
    val date: String,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long,
    val provider: String = "twelve_data"
)

@Entity(
    tableName = "daily_opening_prices",
    primaryKeys = ["symbol", "date"],
    foreignKeys = [
        ForeignKey(
            entity = TickerEntity::class,
            parentColumns = ["symbol"],
            childColumns = ["symbol"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("symbol"), Index("date")]
)
data class DailyOpeningPriceEntity(
    val symbol: String,
    val date: String,
    val open: Double,
    val provider: String = "twelve_data"
)

enum class AlertType {
    PERCENT_CHANGE_FROM_PREVIOUS,
    DROPS_BELOW,
    RISES_ABOVE
}

@Entity(
    tableName = "alerts",
    indices = [Index("symbol")],
    foreignKeys = [
        ForeignKey(
            entity = TickerEntity::class,
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
    val deleteOnTrigger: Boolean,
    val conditionActive: Boolean = false,
    val enabled: Boolean = true,
    val createdAtEpochMs: Long = System.currentTimeMillis()
)

data class PricePoint(
    val label: String,
    val price: Double
)
