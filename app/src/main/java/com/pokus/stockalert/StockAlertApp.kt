package com.pokus.stockalert

import android.app.Application
import androidx.room.Room
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.pokus.stockalert.alerts.NotificationHelper
import com.pokus.stockalert.db.AppDatabase
import com.pokus.stockalert.network.NetworkModule
import com.pokus.stockalert.repo.StockRepository
import com.pokus.stockalert.worker.PriceRefreshWorker
import java.util.concurrent.TimeUnit

class StockAlertApp : Application() {
    lateinit var container: AppContainer

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.createChannel(this)

        val db = Room.databaseBuilder(this, AppDatabase::class.java, "stock-alert-db").build()
        container = AppContainer(
            repo = StockRepository(
                api = NetworkModule.api,
                stockDao = db.stockDao(),
                priceDao = db.priceDao(),
                alertDao = db.alertDao()
            )
        )

        val request = PeriodicWorkRequestBuilder<PriceRefreshWorker>(15, TimeUnit.MINUTES).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "price_refresh_15min",
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }
}

data class AppContainer(
    val repo: StockRepository
)
