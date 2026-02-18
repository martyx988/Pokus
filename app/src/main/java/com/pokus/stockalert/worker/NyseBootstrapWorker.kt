package com.pokus.stockalert.worker

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.pokus.stockalert.StockAlertApp

class NyseBootstrapWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as StockAlertApp
        app.container.repo.preloadDailySnapshotFromAssets(applicationContext)

        val result = app.container.repo.populateNyseUniverseAndDailyHistory(maxSymbolsPerRun = 20)
        return if (result.symbolsRemainingWithoutDaily > 0) Result.retry() else Result.success()
    }
}
