package com.pokus.stockalert.network

import retrofit2.http.GET
import retrofit2.http.Query

data class TwelveDataSymbol(
    val symbol: String,
    val name: String?,
    val exchange: String?
)

data class TwelveDataSearchResponse(
    val data: List<TwelveDataSymbol> = emptyList()
)

data class TwelveDataStock(
    val symbol: String,
    val name: String? = null,
    val exchange: String? = null,
    val country: String? = null,
    val type: String? = null
)

data class TwelveDataStocksMeta(
    val page: Int? = null,
    val totalPages: Int? = null,
    val totalCount: Int? = null
)

data class TwelveDataStocksResponse(
    val data: List<TwelveDataStock> = emptyList(),
    val meta: TwelveDataStocksMeta? = null,
    val status: String? = null,
    val code: Int? = null,
    val message: String? = null
)

data class TwelveDataTimeSeriesResponse(
    val values: List<Map<String, String>>? = null,
    val status: String? = null,
    val code: Int? = null,
    val message: String? = null
)

interface TwelveDataService {
    @GET("symbol_search")
    suspend fun searchSymbols(
        @Query("symbol") query: String,
        @Query("apikey") apiKey: String,
        @Query("outputsize") outputSize: Int = 60
    ): TwelveDataSearchResponse

    @GET("time_series")
    suspend fun timeSeries(
        @Query("symbol") symbol: String,
        @Query("interval") interval: String,
        @Query("apikey") apiKey: String,
        @Query("outputsize") outputSize: Int
    ): TwelveDataTimeSeriesResponse

    @GET("stocks")
    suspend fun stocks(
        @Query("exchange") exchange: String,
        @Query("country") country: String,
        @Query("apikey") apiKey: String,
        @Query("page") page: Int,
        @Query("outputsize") outputSize: Int = 1000
    ): TwelveDataStocksResponse
}
