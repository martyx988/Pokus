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
}
