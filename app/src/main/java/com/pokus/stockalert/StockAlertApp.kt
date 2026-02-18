package com.pokus.stockalert

import android.app.Application
import androidx.room.Room
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.pokus.stockalert.alerts.NotificationHelper
import com.pokus.stockalert.db.AppDatabase
import com.pokus.stockalert.repo.StockRepository
import com.pokus.stockalert.worker.PriceRefreshWorker
import java.util.concurrent.TimeUnit

class StockAlertApp : Application() {
    lateinit var container: AppContainer

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.createChannel(this)

        val db = Room.databaseBuilder(this, AppDatabase::class.java, "stock-alert-db")
            .fallbackToDestructiveMigration()
            .build()
        container = AppContainer(
            repo = StockRepository(
                stockDao = db.stockDao(),
                priceDao = db.priceDao(),
                alertDao = db.alertDao()
            )
        )

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<PriceRefreshWorker>(20, TimeUnit.MINUTES)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "price_refresh_20min",
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )




    }
}

data class AppContainer(
    val repo: StockRepository
)
