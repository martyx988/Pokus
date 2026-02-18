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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
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
import com.pokus.stockalert.data.StockEntity
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
    val searchResults: List<StockEntity> = emptyList(),
    val intraday: List<PricePoint> = emptyList(),
    val daily: List<PricePoint> = emptyList(),
    val alerts: List<AlertEntity> = emptyList()
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
                onAttribution = { nav.navigate("attribution") }
            )
        }
        composable("detail/{symbol}") { backStack ->
            val symbol = backStack.arguments?.getString("symbol") ?: return@composable
            LaunchedEffect(symbol) { vm.loadSymbol(symbol) }
            DetailScreen(symbol = symbol, state = state, onAddAlert = vm::addAlert)
        }
        composable("attribution") {
            AttributionScreen()
        }
    }
}

@Composable
fun SearchScreen(
    state: AppState,
    onQuery: (String) -> Unit,
    onOpen: (String) -> Unit,
    onAttribution: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("NYSE Stock Monitor", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Button(onClick = onAttribution) { Text("Attribution") }
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
                        Text(stock.name)
                    }
                }
            }
        }
    }
}

enum class ChartMode { D1, M1, Y1, Y5, ALL }

@Composable
fun DetailScreen(symbol: String, state: AppState, onAddAlert: (String, AlertType, Double, Boolean) -> Unit) {
    var mode by remember { mutableStateOf(ChartMode.D1) }
    var alertType by remember { mutableStateOf(AlertType.PERCENT_CHANGE_FROM_PREVIOUS) }
    var alertValueText by remember { mutableStateOf("") }
    var deleteOnTrigger by remember { mutableStateOf(true) }

    val points = when (mode) {
        ChartMode.D1 -> state.intraday
        ChartMode.M1 -> state.daily.takeLast(22)
        ChartMode.Y1 -> state.daily.takeLast(252)
        ChartMode.Y5 -> state.daily.takeLast(252 * 5)
        ChartMode.ALL -> state.daily
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(symbol, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ChartMode.entries.forEach {
                Button(onClick = { mode = it }, modifier = Modifier.height(36.dp)) { Text(it.name) }
            }
        }
        Card(modifier = Modifier.fillMaxWidth().height(220.dp)) { LineChart(points) }

        Text("Add alert", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        AlertTypePicker(alertType = alertType, onSelect = { alertType = it })
        OutlinedTextField(
            value = alertValueText,
            onValueChange = { alertValueText = it },
            label = {
                Text(
                    when (alertType) {
                        AlertType.PERCENT_CHANGE_FROM_PREVIOUS -> "Percent change (e.g., 20)"
                        else -> "Price"
                    }
                )
            }
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = deleteOnTrigger, onCheckedChange = { deleteOnTrigger = it })
            Text("Delete alert after it triggers")
        }
        Button(onClick = {
            alertValueText.toDoubleOrNull()?.let { onAddAlert(symbol, alertType, it, deleteOnTrigger) }
            alertValueText = ""
        }) { Text("Save alert") }

        Text("Current alerts", style = MaterialTheme.typography.titleMedium)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.alerts) { alert ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "${alert.type} → ${alert.value} | deleteOnTrigger=${alert.deleteOnTrigger}",
                        modifier = Modifier.padding(10.dp)
                    )
                }
            }
        }
    }
}

@Composable
fun AttributionScreen() {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
            modifier = Modifier.width(320.dp).clickable { expanded = true },
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
        val stepX = size.width / (points.size - 1).coerceAtLeast(1)
        for (i in 0 until points.lastIndex) {
            val p1 = points[i]
            val p2 = points[i + 1]
            val y1 = size.height - (((p1.price - min) / span).toFloat() * size.height)
            val y2 = size.height - (((p2.price - min) / span).toFloat() * size.height)
            drawLine(
                color = Color(0xFF62D2A2),
                start = Offset(i * stepX, y1),
                end = Offset((i + 1) * stepX, y2),
                strokeWidth = 4f
            )
        }
    }
}
