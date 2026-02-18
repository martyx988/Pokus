package com.pokus.stockalert.db

import androidx.room.TypeConverter
import com.pokus.stockalert.data.AlertType

class RoomConverters {
    @TypeConverter
    fun fromAlertType(type: AlertType): String = type.name

    @TypeConverter
    fun toAlertType(raw: String): AlertType = AlertType.valueOf(raw)
}
