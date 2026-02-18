package com.pokus.stockalert.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

object NetworkModule {
    private val httpClient = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
        .build()

    val api: AlphaVantageService = Retrofit.Builder()
        .baseUrl("https://www.alphavantage.co/")
        .client(httpClient)
        .addConverterFactory(MoshiConverterFactory.create())
        .build()
        .create(AlphaVantageService::class.java)
}
