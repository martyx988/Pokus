package com.pokus.stockalert

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.IconButton
import androidx.compose.material3.Switch
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pokus.stockalert.data.AlertEntity
import com.pokus.stockalert.data.AlertType
import com.pokus.stockalert.data.PricePoint
import com.pokus.stockalert.data.TickerEntity
import com.pokus.stockalert.repo.StockRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate

data class AppState(
    val query: String = "",
    val searchResults: List<TickerEntity> = emptyList(),
    val intraday: List<PricePoint> = emptyList(),
    val daily: List<PricePoint> = emptyList(),
    val alerts: List<AlertEntity> = emptyList(),
    val developerLoading: Boolean = false,
    val developerStatus: String = ""
)

class MainViewModel(private val repo: StockRepository) : ViewModel() {
    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> = _state.asStateFlow()
    private var searchJob: Job? = null

    fun onQueryChanged(newQuery: String) {
        _state.update { it.copy(query = newQuery) }
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            repo.refreshSearch(newQuery)
            repo.searchLocal(newQuery).collect { list ->
                _state.update { s -> s.copy(searchResults = list) }
            }
        }
    }

    fun loadSymbol(symbol: String) {
        viewModelScope.launch {
            repo.refreshIntraday(symbol)
            repo.refreshTodayOpeningAndRecentDaily(symbol)
            repo.refreshDaily(symbol)
            val today = LocalDate.now().toString()
            launch { repo.observeIntraday(symbol, today).collect { _state.update { s -> s.copy(intraday = it) } } }
            launch { repo.observeDaily(symbol).collect { _state.update { s -> s.copy(daily = it) } } }
            launch { repo.observeAlerts(symbol).collect { _state.update { s -> s.copy(alerts = it) } } }
        }
    }

    fun addAlert(symbol: String, type: AlertType, value: Double, deleteOnTrigger: Boolean) {
        viewModelScope.launch { repo.addAlert(symbol, type, value, deleteOnTrigger) }
    }

    fun deleteAlert(alertId: Long) {
        viewModelScope.launch { repo.deleteAlert(alertId) }
    }

    fun runDeveloperLoadLastWeekPrices() {
        _state.update { it.copy(developerLoading = true, developerStatus = "Loading last-week prices for all tickers...") }
        viewModelScope.launch {
            try {
                val result = repo.developerLoadLastWeekPricesForAllTickers()
                _state.update { it.copy(developerLoading = false, developerStatus = result) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        developerLoading = false,
                        developerStatus = "Developer load failed: ${e.message ?: e::class.java.simpleName}"
                    )
                }
            }
        }
    }
}

class VMFactory(private val repo: StockRepository) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(repo) as T
}

class MainActivity : ComponentActivity() {
    private val notificationsPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    private val vm by viewModels<MainViewModel> {
        VMFactory((application as StockAlertApp).container.repo)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationsPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        setContent {
            val dark = androidx.compose.foundation.isSystemInDarkTheme()
            MaterialTheme(colorScheme = if (dark) darkColorScheme() else lightColorScheme()) {
                val nav = rememberNavController()
                val state by vm.state.collectAsState()
                AppNavHost(nav, state, vm)
            }
        }
    }
}

@Composable
fun AppNavHost(nav: NavHostController, state: AppState, vm: MainViewModel) {
    NavHost(navController = nav, startDestination = "search") {
        composable("search") {
            SearchScreen(
                state = state,
                onQuery = vm::onQueryChanged,
                onOpen = { symbol -> nav.navigate("detail/$symbol") },
                onAttribution = { nav.navigate("attribution") },
                onDeveloper = { nav.navigate("developer") }
            )
        }
        composable("detail/{symbol}") { backStack ->
            val symbol = backStack.arguments?.getString("symbol") ?: return@composable
            LaunchedEffect(symbol) { vm.loadSymbol(symbol) }
            DetailScreen(
                symbol = symbol,
                state = state,
                onAddAlert = vm::addAlert,
                onDeleteAlert = vm::deleteAlert,
                onBack = { nav.popBackStack() }
            )
        }
        composable("attribution") {
            AttributionScreen(onBack = { nav.popBackStack() })
        }
        composable("developer") {
            DeveloperSettingsScreen(
                state = state,
                onBack = { nav.popBackStack() },
                onRunManualApiLoad = { vm.runDeveloperLoadLastWeekPrices() }
            )
        }
    }
}

@Composable
fun SearchScreen(
    state: AppState,
    onQuery: (String) -> Unit,
    onOpen: (String) -> Unit,
    onAttribution: () -> Unit,
    onDeveloper: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("NYSE Stock Monitor", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onDeveloper) { Text("Developer") }
                Button(onClick = onAttribution) { Text("Attribution") }
            }
        }

        OutlinedTextField(
            value = state.query,
            onValueChange = onQuery,
            label = { Text("Search ticker or company") },
            modifier = Modifier.fillMaxWidth()
        )
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.searchResults) { stock ->
                Card(modifier = Modifier.fillMaxWidth().clickable { onOpen(stock.symbol) }) {
                    Column(Modifier.padding(12.dp)) {
                        Text(stock.symbol, fontWeight = FontWeight.SemiBold)
                        Text(stock.companyName)
                    }
                }
            }
        }
    }
}

enum class ChartMode { D1, W1, M1, Y1, ALL }

@Composable
fun DetailScreen(
    symbol: String,
    state: AppState,
    onAddAlert: (String, AlertType, Double, Boolean) -> Unit,
    onDeleteAlert: (Long) -> Unit,
    onBack: () -> Unit
) {
    var mode by remember { mutableStateOf(ChartMode.M1) }
    var alertType by remember { mutableStateOf(AlertType.RISES_ABOVE) }
    var alertValueText by remember { mutableStateOf("") }
    var deleteOnTrigger by remember { mutableStateOf(true) }

    val points = when (mode) {
        ChartMode.D1 -> if (state.intraday.size >= 2) state.intraday else state.daily.takeLast(2)
        ChartMode.W1 -> state.daily.takeLast(5)
        ChartMode.M1 -> state.daily.takeLast(22)
        ChartMode.Y1 -> state.daily.takeLast(252)
        ChartMode.ALL -> state.daily
    }

    val latest = points.lastOrNull()?.price ?: 0.0
    val previous = points.dropLast(1).lastOrNull()?.price
    val dayChangePct = if (previous != null && previous != 0.0) ((latest - previous) / previous) * 100.0 else 0.0

    val bg = Brush.verticalGradient(listOf(Color(0xFF081321), Color(0xFF06101B)))

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(bg)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = onBack, modifier = Modifier.height(36.dp)) { Text("←") }
            Spacer(Modifier.weight(1f))
            Text(symbol, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Color(0xFFEAF1FF))
            Spacer(Modifier.weight(1f))
            Text("★", color = Color(0xFFEAF1FF))
        }

        Text(
            text = "$" + String.format("%.2f", latest),
            style = MaterialTheme.typography.displayMedium,
            fontWeight = FontWeight.Bold,
            color = Color(0xFFF2F7FF)
        )

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Card(shape = RoundedCornerShape(20.dp)) {
                Box(modifier = Modifier.background(Color(0xFF0A3B2E)).padding(horizontal = 14.dp, vertical = 6.dp)) {
                    Text(
                        text = (if (dayChangePct >= 0) "↗" else "↘") + String.format(" %.1f%%", kotlin.math.abs(dayChangePct)),
                        color = if (dayChangePct >= 0) Color(0xFF2DE08E) else Color(0xFFFF6B6B),
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            Text("Today", color = Color(0xFF9AA8C1))
        }

        Card(
            modifier = Modifier.fillMaxWidth().height(250.dp),
            shape = RoundedCornerShape(22.dp)
        ) {
            Box(Modifier.background(Color(0xFF0A1A2F)).padding(12.dp)) {
                LineChart(points)
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().background(Color(0xFF253447), RoundedCornerShape(28.dp)).padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            listOf(
                ChartMode.D1 to "1D",
                ChartMode.W1 to "1W",
                ChartMode.M1 to "1M",
                ChartMode.Y1 to "1Y",
                ChartMode.ALL to "ALL"
            ).forEach { (m, label) ->
                val active = mode == m
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .background(if (active) Color(0xFF2385F0) else Color.Transparent, RoundedCornerShape(24.dp))
                        .clickable { mode = m }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(label, color = if (active) Color.White else Color(0xFF9CAAC0), fontWeight = FontWeight.SemiBold)
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(22.dp)) {
            Column(
                modifier = Modifier.background(Color(0xFF162334)).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("Add Alert", style = MaterialTheme.typography.headlineSmall, color = Color(0xFFEAF1FF), fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Box(Modifier.weight(1f)) { AlertTypePicker(alertType = alertType, onSelect = { alertType = it }) }
                    OutlinedTextField(
                        value = alertValueText,
                        onValueChange = { alertValueText = it },
                        label = { Text("Target Price") },
                        modifier = Modifier.weight(1f)
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("One-time alert", color = Color(0xFFD7E2F4))
                    Spacer(Modifier.weight(1f))
                    Switch(checked = deleteOnTrigger, onCheckedChange = { deleteOnTrigger = it })
                }
                Button(
                    onClick = {
                        alertValueText.toDoubleOrNull()?.let { onAddAlert(symbol, alertType, it, deleteOnTrigger) }
                        alertValueText = ""
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp)
                ) { Text("Create Alert") }
            }
        }

        Text("ACTIVE ALERTS", color = Color(0xFF8C9BB2), fontWeight = FontWeight.Bold)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(state.alerts) { alert ->
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                    Row(
                        modifier = Modifier.background(Color(0xFF162334)).padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .background(
                                    if (alert.type == AlertType.DROPS_BELOW) Color(0xFF3B2230) else Color(0xFF13382F),
                                    CircleShape
                                )
                                .padding(horizontal = 12.dp, vertical = 8.dp)
                        ) {
                            Text(if (alert.type == AlertType.DROPS_BELOW) "↘" else "↗", color = if (alert.type == AlertType.DROPS_BELOW) Color(0xFFFF6B6B) else Color(0xFF2DE08E))
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                text = if (alert.type == AlertType.DROPS_BELOW) "Price drops below" else if (alert.type == AlertType.RISES_ABOVE) "Price rises above" else "Price change",
                                color = Color(0xFFEAF1FF)
                            )
                            Text(
                                text = if (alert.type == AlertType.PERCENT_CHANGE_FROM_PREVIOUS) String.format("%.2f%%", alert.value * 100.0) else "$" + String.format("%.2f", alert.value),
                                color = Color.White,
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        IconButton(onClick = { onDeleteAlert(alert.id) }) { Text("🗑", color = Color(0xFFA6B8D3)) }
                    }
                }
            }
        }
    }
}

@Composable
fun DeveloperSettingsScreen(
    state: AppState,
    onBack: () -> Unit,
    onRunManualApiLoad: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onBack, modifier = Modifier.height(36.dp)) { Text("Back") }
            Text("Developer settings", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        }

        Text("Load all NYSE ticker prices for the last week into historical and opening tables.")

        Button(
            onClick = onRunManualApiLoad,
            enabled = !state.developerLoading
        ) {
            Text(if (state.developerLoading) "Running..." else "Load last-week prices for all tickers")
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = if (state.developerStatus.isBlank()) "No test run yet." else state.developerStatus,
                modifier = Modifier.padding(12.dp)
            )
        }
    }
}

@Composable
fun AttributionScreen(onBack: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = onBack, modifier = Modifier.height(36.dp)) { Text("Back") }
        Text("Data Attribution", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Market data powered by Alpha Vantage.")
        Text("Please review Alpha Vantage terms of service before distributing the app.")
    }
}

@Composable
fun AlertTypePicker(alertType: AlertType, onSelect: (AlertType) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Card(
            modifier = Modifier.fillMaxWidth().clickable { expanded = true },
            shape = RoundedCornerShape(10.dp)
        ) {
            Text(
                when (alertType) {
                    AlertType.PERCENT_CHANGE_FROM_PREVIOUS -> "changes by % from previous reference price"
                    AlertType.DROPS_BELOW -> "drops below"
                    AlertType.RISES_ABOVE -> "rises above"
                },
                modifier = Modifier.padding(12.dp)
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            AlertType.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.name) },
                    onClick = {
                        onSelect(type)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
fun LineChart(points: List<PricePoint>) {
    if (points.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No data yet") }
        return
    }

    val min = points.minOf { it.price }
    val max = points.maxOf { it.price }
    val span = (max - min).coerceAtLeast(0.01)

    Canvas(modifier = Modifier.fillMaxSize().background(Color(0xFF10172A))) {
        val chartColor = Color(0xFF62D2A2)
        val stepX = size.width / (points.size - 1).coerceAtLeast(1)

        if (points.size == 1) {
            drawCircle(
                color = chartColor,
                radius = 8f,
                center = Offset(size.width / 2f, size.height / 2f)
            )
            return@Canvas
        }

        for (i in 0 until points.lastIndex) {
            val p1 = points[i]
            val p2 = points[i + 1]
            val y1 = size.height - (((p1.price - min) / span).toFloat() * size.height)
            val y2 = size.height - (((p2.price - min) / span).toFloat() * size.height)
            drawLine(
                color = chartColor,
                start = Offset(i * stepX, y1),
                end = Offset((i + 1) * stepX, y2),
                strokeWidth = 4f
            )
        }
    }
}
