package com.pokus.stockalert.repo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class StockRepositoryParsingTest {

    @Test
    fun classifySecurityType_detectsEtfEtcEtn() {
        assertEquals("ETF", StockRepository.classifySecurityType("Y", "SPDR S&P 500 ETF"))
        assertEquals("ETN", StockRepository.classifySecurityType("Y", "Some Exchange Traded Note"))
        assertEquals("ETC", StockRepository.classifySecurityType("Y", "Gold Exchange Traded Commodity"))
        assertEquals("STOCK", StockRepository.classifySecurityType("N", "Acme Inc"))
    }

    @Test
    fun parseNyseTickerRows_filtersAndSorts() {
        val raw = """
            ACT Symbol|Security Name|Exchange|ETF
            MSFT|Microsoft Corp|N|N
            SPY|SPDR S&P 500 ETF TRUST|P|Y
            BRK.B|Berkshire|N|N
            GLD|Gold Exchange Traded Commodity|A|Y
            File Creation Time: 123|n/a|n/a|n/a
        """.trimIndent()

        val result = StockRepository.parseNyseTickerRows(raw)

        assertEquals(3, result.size)
        assertEquals(listOf("GLD", "MSFT", "SPY"), result.map { it.symbol })
        assertEquals("STOCK", result.first { it.symbol == "MSFT" }.securityType)
        assertEquals("ETF", result.first { it.symbol == "SPY" }.securityType)
        assertEquals("ETC", result.first { it.symbol == "GLD" }.securityType)
        assertTrue(result.none { it.symbol == "BRK.B" })
    }


    @Test
    fun parseYahooChartRows_mapsToHistoricalFormat() {
        val raw = """
            {
              "chart": {
                "result": [
                  {
                    "timestamp": [1704067200, 1704153600],
                    "indicators": {
                      "quote": [
                        {
                          "open": [100.5, 101.0],
                          "high": [110.0, 111.0],
                          "low": [99.0, 100.0],
                          "close": [109.5, 110.0],
                          "volume": [1000, 2000]
                        }
                      ]
                    }
                  }
                ]
              }
            }
        """.trimIndent()

        val rows = StockRepository.parseYahooChartRows(raw, "MSFT")

        assertEquals(2, rows.size)
        assertEquals("MSFT", rows.first().symbol)
        assertEquals("yfinance", rows.first().provider)
        assertEquals(100.5, rows.first().open, 0.0001)
        assertEquals(109.5, rows.first().close, 0.0001)
    }

}
