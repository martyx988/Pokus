package com.pokus.stockalert.worker

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.pokus.stockalert.StockAlertApp
import com.pokus.stockalert.alerts.NotificationHelper
import com.pokus.stockalert.data.AlertType

class PriceRefreshWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as StockAlertApp
        val repo = app.container.repo
        val alerts = repo.enabledAlerts()

        alerts.groupBy { it.symbol }.forEach { (symbol, symbolAlerts) ->
            repo.refreshIntraday(symbol)
            val latest = repo.latestPrice(symbol) ?: return@forEach

            symbolAlerts.forEach { alert ->
                val triggered = when (alert.type) {
                    AlertType.DROPS_BELOW -> latest < alert.value
                    AlertType.RISES_ABOVE -> latest > alert.value
                    AlertType.PERCENT_CHANGE_FROM_CURRENT -> {
                        val baseline = alert.baselinePrice ?: latest
                        kotlin.math.abs((latest - baseline) / baseline) >= alert.value
                    }
                }
                if (triggered) {
                    NotificationHelper.notify(
                        applicationContext,
                        alert.id.toInt(),
                        "$symbol alert triggered",
                        "Current price: $latest"
                    )
                }
            }
        }
        return Result.success()
    }
}
