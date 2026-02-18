package com.pokus.stockalert.network

import retrofit2.http.GET
import retrofit2.http.Query

data class SearchResponse(
    val bestMatches: List<Map<String, String>> = emptyList()
)

data class TimeSeriesResponse(
    val metaData: Map<String, String>? = null,
    val timeSeries15Min: Map<String, Map<String, String>>? = null,
    val timeSeriesDaily: Map<String, Map<String, String>>? = null
)

interface AlphaVantageService {
    @GET("query?function=SYMBOL_SEARCH")
    suspend fun searchSymbols(
        @Query("keywords") keywords: String,
        @Query("apikey") apiKey: String
    ): SearchResponse

    @GET("query?function=TIME_SERIES_INTRADAY&interval=15min&outputsize=full")
    suspend fun intraday(
        @Query("symbol") symbol: String,
        @Query("apikey") apiKey: String
    ): Map<String, Any>

    @GET("query?function=TIME_SERIES_DAILY_ADJUSTED&outputsize=full")
    suspend fun daily(
        @Query("symbol") symbol: String,
        @Query("apikey") apiKey: String
    ): Map<String, Any>
}
