package com.pokus.stockalert.worker

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.pokus.stockalert.StockAlertApp
import com.pokus.stockalert.alerts.NotificationHelper
import com.pokus.stockalert.data.AlertType
import java.time.DayOfWeek
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import kotlin.math.abs

class PriceRefreshWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as StockAlertApp
        val repo = app.container.repo
        val nowNy = ZonedDateTime.now(ZoneId.of("America/New_York"))
        val today = nowNy.toLocalDate()

        repo.applyRetention(today)
        if (!isNyseMarketOpen(nowNy)) return Result.success()

        val alerts = repo.enabledAlerts()
        alerts.groupBy { it.symbol }.forEach { (symbol, symbolAlerts) ->
            repo.refreshIntraday(symbol)
            repo.refreshDaily(symbol)

            val latest = repo.latestIntraday(symbol) ?: return@forEach
            val previous = repo.previousIntraday(symbol)
            val yesterdayClose = repo.previousDailyBefore(symbol, today.toString())?.close

            symbolAlerts.forEach { alert ->
                val triggered = when (alert.type) {
                    AlertType.PERCENT_CHANGE_FROM_PREVIOUS -> {
                        val reference = previous?.close ?: yesterdayClose
                        reference != null && reference > 0.0 && abs((latest.close - reference) / reference) >= alert.value
                    }

                    AlertType.DROPS_BELOW -> latest.close < alert.value && !alert.conditionActive
                    AlertType.RISES_ABOVE -> latest.close > alert.value && !alert.conditionActive
                }

                val activeNow = when (alert.type) {
                    AlertType.DROPS_BELOW -> latest.close < alert.value
                    AlertType.RISES_ABOVE -> latest.close > alert.value
                    AlertType.PERCENT_CHANGE_FROM_PREVIOUS -> false
                }

                if (triggered) {
                    NotificationHelper.notify(
                        applicationContext,
                        alert.id.toInt(),
                        "$symbol alert triggered",
                        "Current price: ${latest.close}"
                    )
                    if (alert.deleteOnTrigger) {
                        repo.deleteAlert(alert.id)
                    }
                }
                if (!alert.deleteOnTrigger) {
                    repo.updateAlertConditionState(alert.id, activeNow)
                }
            }
        }

        return Result.success()
    }

    private fun isNyseMarketOpen(nowNy: ZonedDateTime): Boolean {
        val day = nowNy.dayOfWeek
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) return false

        val time = nowNy.toLocalTime()
        return time >= LocalTime.of(9, 30) && time <= LocalTime.of(16, 0)
    }
}
