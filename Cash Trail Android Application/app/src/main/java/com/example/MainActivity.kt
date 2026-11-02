package com.example

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.credentials.CredentialManager
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.compose.material.icons.filled.Description
import com.example.data.model.AccountType
import com.example.data.model.Investment
import com.example.data.model.SuggestedAccount
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.data.repository.FinancialRepository
import com.example.ui.accounts.AccountsScreen
import com.example.ui.auth.AuthScreen
import com.example.ui.auth.signOut
import com.example.ui.components.AddAccountDialog
import com.example.ui.components.CreditCardDueAlertsSheet
import com.example.ui.components.DashboardCustomizerSheet
import com.example.ui.components.InvestmentEntrySheet
import com.example.ui.components.TransactionEntrySheet
import com.example.ui.dashboard.DashboardScreen
import com.example.ui.dashboard.FinancialViewModel
import com.example.ui.dashboard.UiState
import com.example.ui.documents.PersonalDocumentsSheet
import com.example.ui.investments.InvestmentsScreen
import com.example.ui.settings.SettingsScreen
import com.example.ui.theme.FinLedgerTheme
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseBorder
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate800
import com.example.ui.theme.Slate900
import com.example.ui.transactions.TransactionsScreen
import com.example.ui.updates.UpdatesScreen
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore

enum class AppTab(val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    DASHBOARD("Dashboard", Icons.Default.Dashboard),
    LEDGER("Ledger", Icons.Default.ReceiptLong),
    UPDATES("Updates", Icons.Default.NotificationsActive),
    ACCOUNTS("Accounts", Icons.Default.AccountBalance),
    INVESTMENTS("Investments", Icons.Default.TrendingUp),
    SETTINGS("Settings", Icons.Default.Settings)
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            FinLedgerTheme {
                AppRootContent()
            }
        }
    }
}

@Composable
fun AppRootContent() {
    var currentUser by remember { mutableStateOf(FirebaseAuth.getInstance().currentUser) }
    var isGuestMode by rememberSaveable { mutableStateOf(false) }

    DisposableEffect(Unit) {
        val listener = FirebaseAuth.AuthStateListener { auth ->
            currentUser = auth.currentUser
            if (auth.currentUser != null) {
                isGuestMode = false
            }
        }
        FirebaseAuth.getInstance().addAuthStateListener(listener)
        onDispose {
            FirebaseAuth.getInstance().removeAuthStateListener(listener)
        }
    }

    if (currentUser == null && !isGuestMode) {
        AuthScreen(
            onAuthSuccess = {
                currentUser = FirebaseAuth.getInstance().currentUser
                isGuestMode = false
            },
            onSkipLogin = {
                isGuestMode = true
            }
        )
    } else {
        MainAppScaffold(
            currentUserId = currentUser?.uid ?: "guest_user",
            userEmail = if (isGuestMode) "Guest Mode" else (currentUser?.email ?: "User"),
            isGuest = isGuestMode,
            onSignOut = {
                if (isGuestMode) {
                    isGuestMode = false
                } else {
                    currentUser = null
                }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainAppScaffold(
    currentUserId: String,
    userEmail: String,
    isGuest: Boolean = false,
    onSignOut: () -> Unit = {}
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val credentialManager = remember { CredentialManager.create(context) }

    val viewModel: FinancialViewModel = viewModel(
        key = currentUserId,
        factory = viewModelFactory {
            initializer {
                val app = checkNotNull(this[APPLICATION_KEY])
                val databaseId = app.getString(R.string.firestore_database_id)
                val firestore = FirebaseFirestore.getInstance(databaseId)
                FinancialViewModel(
                    repository = FinancialRepository(firestore),
                    currentUserId = currentUserId
                )
            }
        }
    )

    var currentTab by remember { mutableStateOf(AppTab.DASHBOARD) }

    // Dialog & Sheet States
    var showTransactionSheet by remember { mutableStateOf(false) }
    var transactionSheetInitialType by remember { mutableStateOf(TransactionType.EXPENSE) }
    var transactionToEdit by remember { mutableStateOf<Transaction?>(null) }
    var showInvestmentSheet by remember { mutableStateOf(false) }
    var investmentToEdit by remember { mutableStateOf<Investment?>(null) }
    var showAddAccountDialog by remember { mutableStateOf(false) }
    var prefillSuggestedAccount by remember { mutableStateOf<SuggestedAccount?>(null) }
    var showPersonalDocumentsSheet by remember { mutableStateOf(false) }
    var showCustomizerSheet by remember { mutableStateOf(false) }
    var showDueAlertsSheet by remember { mutableStateOf(false) }
    var pendingNotificationIdForEntry by remember { mutableStateOf<String?>(null) }
    var showExportReportDialog by remember { mutableStateOf(false) }

    // Snackbars
    val snackbarHostState = remember { SnackbarHostState() }
    val statusMessage by viewModel.statusMessage.collectAsStateWithLifecycle()

    LaunchedEffect(statusMessage) {
        statusMessage?.let { msg ->
            snackbarHostState.showSnackbar(msg)
            viewModel.clearStatusMessage()
        }
    }

    // Observers
    val summary by viewModel.financialSummary.collectAsStateWithLifecycle()
    val preferences by viewModel.preferences.collectAsStateWithLifecycle()
    val accountsState by viewModel.accountsState.collectAsStateWithLifecycle()
    val transactionsState by viewModel.transactionsState.collectAsStateWithLifecycle()
    val investmentsState by viewModel.investmentsState.collectAsStateWithLifecycle()
    val personalDocumentsState by viewModel.personalDocumentsState.collectAsStateWithLifecycle()
    val suggestedAccounts by viewModel.suggestedAccounts.collectAsStateWithLifecycle()
    val categoryBreakdown by viewModel.categoryBreakdown.collectAsStateWithLifecycle()
    val selectedPeriod by viewModel.selectedPeriod.collectAsStateWithLifecycle()
    val periodDateRange by viewModel.periodDateRange.collectAsStateWithLifecycle()

    val notifications by viewModel.notifications.collectAsStateWithLifecycle()
    val detectedBills by viewModel.detectedBills.collectAsStateWithLifecycle()
    val isScanning by viewModel.isScanning.collectAsStateWithLifecycle()

    val personalDocumentsCount = (personalDocumentsState as? UiState.Success)?.data?.size ?: 0

    LaunchedEffect(Unit) {
        viewModel.scanNotifications(context)
        viewModel.refreshBackupRecords(context)
    }

    val lastDailyBackup by viewModel.lastDailyBackup.collectAsStateWithLifecycle()
    val localBackupsList by viewModel.localBackupsList.collectAsStateWithLifecycle()

    val saveToDriveLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/json")
    ) { uri ->
        if (uri != null) {
            val json = viewModel.getBackupJsonForExport()
            val success = com.example.data.backup.LocalBackupManager.writeBackupToUri(context, uri, json)
            if (success) {
                android.widget.Toast.makeText(context, "Backup saved to Google Drive / Storage successfully!", android.widget.Toast.LENGTH_LONG).show()
                viewModel.refreshBackupRecords(context)
            } else {
                android.widget.Toast.makeText(context, "Failed to write backup file.", android.widget.Toast.LENGTH_SHORT).show()
            }
        }
    }

    val restoreBackupLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            val json = com.example.data.backup.LocalBackupManager.readBackupFromUri(context, uri)
            if (!json.isNullOrBlank()) {
                viewModel.restoreBackupFromJson(context, json) { success, msg ->
                    android.widget.Toast.makeText(context, msg, android.widget.Toast.LENGTH_LONG).show()
                }
            } else {
                android.widget.Toast.makeText(context, "Unable to read selected file.", android.widget.Toast.LENGTH_SHORT).show()
            }
        }
    }

    val unreviewedNotificationsCount = remember(notifications) {
        notifications.count { !it.isDismissed && !it.isProcessed }
    }
    val unpaidDetectedBillsCount = remember(detectedBills) {
        detectedBills.count { !it.isPaid }
    }

    val accountsList = (accountsState as? UiState.Success)?.data ?: emptyList()

    LaunchedEffect(accountsList) {
        if (accountsList.isNotEmpty()) {
            viewModel.checkAndRunDailyBackup(context)
        }
    }

    val currentTransactionsList = (transactionsState as? UiState.Success)?.data ?: emptyList()

    val creditCardAccounts = remember(accountsList) {
        accountsList.filter { it.type == AccountType.CREDIT_CARD.name }
    }
    val cardsDueWithinWeek = remember(creditCardAccounts, currentTransactionsList) {
        val now = java.util.Calendar.getInstance()
        creditCardAccounts.filter { card ->
            val summary = com.example.ui.util.CreditCardStatementCalculator.calculateStatementSummary(card, currentTransactionsList, now)
            summary.isDueWithinWeek
        }
    }

    // Back handling
    if (currentTab != AppTab.DASHBOARD) {
        BackHandler {
            currentTab = AppTab.DASHBOARD
        }
    }

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.background)
                    .statusBarsPadding()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f, fill = false)
                    ) {
                        com.example.ui.components.CoinKeepHorizontalLogo(
                            iconSize = 28.dp,
                            isDark = false
                        )
                        Spacer(modifier = Modifier.width(8.dp))

                        // Doc Logo button right beside the logo to maintain personal documents
                        Surface(
                            shape = RoundedCornerShape(10.dp),
                            color = Slate100,
                            modifier = Modifier
                                .clickable { showPersonalDocumentsSheet = true }
                                .testTag("top_bar_doc_logo_button")
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Description,
                                    contentDescription = "Personal Documents",
                                    tint = Slate800,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(5.dp))
                                Text(
                                    text = if (personalDocumentsCount > 0) "Docs ($personalDocumentsCount)" else "Docs",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate800,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        // Notification / Alerts Chip for Credit Card Dues (shown when dues exist)
                        val totalDuesCount = cardsDueWithinWeek.size + unpaidDetectedBillsCount
                        if (totalDuesCount > 0) {
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = PastelExpenseBg,
                                border = androidx.compose.foundation.BorderStroke(1.dp, PastelExpenseBorder),
                                modifier = Modifier
                                    .clickable { showDueAlertsSheet = true }
                                    .testTag("notifications_alerts_button")
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.NotificationsActive,
                                        contentDescription = "Credit Card Due Alerts",
                                        tint = PastelExpenseText,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(modifier = Modifier.width(5.dp))
                                    Text(
                                        text = "$totalDuesCount Due",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = PastelExpenseText,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }

                    // Top-right section: Export & Settings buttons
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        // Export Report icon button in top bar (export icon)(no text)
                        IconButton(
                            onClick = { showExportReportDialog = true },
                            modifier = Modifier
                                .size(36.dp)
                                .testTag("top_bar_export_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.FileDownload,
                                contentDescription = "Export Report",
                                tint = Slate700,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        // Settings Icon in top-right corner
                        IconButton(
                            onClick = { currentTab = AppTab.SETTINGS },
                            modifier = Modifier
                                .size(36.dp)
                                .testTag("top_bar_settings_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = "Settings",
                                tint = if (currentTab == AppTab.SETTINGS) PastelTransferText else Slate600,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }
                HorizontalDivider(color = Slate200, thickness = 1.dp)
            }
        },
        bottomBar = {
            val bottomNavTabs = listOf(
                AppTab.DASHBOARD,
                AppTab.LEDGER,
                AppTab.UPDATES,
                AppTab.ACCOUNTS,
                AppTab.INVESTMENTS
            )
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.background,
                tonalElevation = 0.dp,
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .testTag("main_navigation_bar")
            ) {
                bottomNavTabs.forEach { tab ->
                    val isSelected = currentTab == tab
                    NavigationBarItem(
                        selected = isSelected,
                        onClick = { currentTab = tab },
                        icon = {
                            if (tab == AppTab.UPDATES && unreviewedNotificationsCount > 0) {
                                BadgedBox(
                                    badge = {
                                        Badge(
                                            containerColor = PastelExpenseText,
                                            contentColor = Color.White
                                        ) {
                                            Text(unreviewedNotificationsCount.toString())
                                        }
                                    }
                                ) {
                                    Icon(
                                        imageVector = tab.icon,
                                        contentDescription = tab.label,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            } else {
                                Icon(
                                    imageVector = tab.icon,
                                    contentDescription = tab.label,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        },
                        label = {
                            Text(
                                text = tab.label,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                            )
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Slate900,
                            selectedTextColor = Slate900,
                            indicatorColor = PastelExpenseBg,
                            unselectedIconColor = Slate400,
                            unselectedTextColor = Slate400
                        ),
                        modifier = Modifier.testTag("nav_item_${tab.name}")
                    )
                }
            }
        },
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (currentTab) {
                AppTab.DASHBOARD -> {
                    DashboardScreen(
                        summary = summary,
                        preferences = preferences,
                        accountsState = accountsState,
                        transactionsState = transactionsState,
                        categoryBreakdown = categoryBreakdown,
                        selectedPeriod = selectedPeriod,
                        periodDateRange = periodDateRange,
                        onSelectPeriod = { viewModel.selectPeriod(it) },
                        onOpenTransactionSheet = { type ->
                            transactionToEdit = null
                            transactionSheetInitialType = type
                            showTransactionSheet = true
                        },
                        onOpenInvestmentSheet = {
                            showInvestmentSheet = true
                        },
                        onOpenAddAccountDialog = {
                            showAddAccountDialog = true
                        },
                        onOpenCustomizer = {
                            showCustomizerSheet = true
                        },
                        onNavigateToTransactions = {
                            currentTab = AppTab.LEDGER
                        },
                        onNavigateToAccounts = {
                            currentTab = AppTab.ACCOUNTS
                        },
                        onNavigateToInvestments = {
                            currentTab = AppTab.INVESTMENTS
                        },
                        onEditTransaction = { tx ->
                            transactionToEdit = tx
                        },
                        onDeleteTransaction = { tx ->
                            viewModel.deleteTransaction(tx)
                        }
                    )
                }
                AppTab.LEDGER -> {
                    TransactionsScreen(
                        transactionsState = transactionsState,
                        accounts = accountsList,
                        onAddTransaction = { type ->
                            transactionToEdit = null
                            transactionSheetInitialType = type
                            showTransactionSheet = true
                        },
                        onEditTransaction = { tx ->
                            transactionToEdit = tx
                        },
                        onDeleteTransaction = { tx ->
                            viewModel.deleteTransaction(tx)
                        }
                    )
                }
                AppTab.UPDATES -> {
                    UpdatesScreen(
                        notifications = notifications,
                        accounts = accountsList,
                        isScanning = isScanning,
                        currencySymbol = preferences.currencySymbol,
                        preferences = preferences,
                        onToggleMessageTracking = { viewModel.setMessageTrackingEnabled(it, context) },
                        onRefreshScan = { viewModel.scanNotifications(context) },
                        onOpenTransactionSheet = { notif, type ->
                            pendingNotificationIdForEntry = notif.id
                            val matchingAccount = if (notif.accountSuffix != null) {
                                accountsList.firstOrNull { it.name.contains(notif.accountSuffix) || it.institution.contains(notif.accountSuffix) }
                                    ?: accountsList.firstOrNull()
                            } else {
                                accountsList.firstOrNull()
                            }
                            transactionToEdit = Transaction(
                                id = "",
                                userId = currentUserId,
                                type = type.name,
                                amount = notif.amount,
                                accountId = matchingAccount?.id ?: "",
                                category = notif.suggestedCategory,
                                note = notif.merchantOrPayee
                            )
                            transactionSheetInitialType = type
                            showTransactionSheet = true
                        },
                        onOpenInvestmentSheet = { notif ->
                            pendingNotificationIdForEntry = notif.id
                            val matchingAccount = if (notif.accountSuffix != null) {
                                accountsList.firstOrNull { it.name.contains(notif.accountSuffix) || it.institution.contains(notif.accountSuffix) }
                                    ?: accountsList.firstOrNull()
                            } else {
                                accountsList.firstOrNull()
                            }
                            investmentToEdit = Investment(
                                id = "",
                                userId = currentUserId,
                                assetName = notif.merchantOrPayee,
                                assetType = "MUTUAL_FUNDS",
                                action = "CONTRIBUTION",
                                amount = notif.amount,
                                sourceAccountId = matchingAccount?.id,
                                note = "From ${notif.source}: ${notif.merchantOrPayee}"
                            )
                            showInvestmentSheet = true
                        },
                        onDismissNotification = { notifId ->
                            viewModel.dismissNotification(notifId)
                        },
                        onSimulateSampleSms = { body, sender ->
                            viewModel.simulateSampleBankMessage(body, sender)
                        }
                    )
                }
                AppTab.ACCOUNTS -> {
                    AccountsScreen(
                        accountsState = accountsState,
                        transactionsState = transactionsState,
                        suggestedAccounts = suggestedAccounts,
                        onAddAccount = {
                            prefillSuggestedAccount = null
                            showAddAccountDialog = true
                        },
                        onAddSuggestedAccount = { sa ->
                            prefillSuggestedAccount = sa
                            showAddAccountDialog = true
                        },
                        onDismissSuggestedAccount = { saId ->
                            viewModel.dismissSuggestedAccount(saId)
                        },
                        onOpenTransferSheet = {
                            transactionSheetInitialType = TransactionType.TRANSFER
                            showTransactionSheet = true
                        },
                        onDeleteAccount = { accId ->
                            viewModel.deleteAccount(accId)
                        },
                        onUpdateAccount = { updatedAcc ->
                            viewModel.updateAccount(updatedAcc)
                        }
                    )
                }
                AppTab.INVESTMENTS -> {
                    InvestmentsScreen(
                        investmentsState = investmentsState,
                        onAddInvestment = {
                            investmentToEdit = null
                            showInvestmentSheet = true
                        },
                        onEditInvestment = { inv ->
                            investmentToEdit = inv
                        },
                        onDeleteInvestment = { inv ->
                            viewModel.deleteInvestment(inv)
                        }
                    )
                }
                AppTab.SETTINGS -> {
                    SettingsScreen(
                        userEmail = userEmail,
                        isGuest = isGuest,
                        preferences = preferences,
                        transactions = (transactionsState as? UiState.Success)?.data ?: emptyList(),
                        accounts = accountsList,
                        investments = (investmentsState as? UiState.Success)?.data ?: emptyList(),
                        onSetCurrency = { viewModel.setCurrency(it) },
                        onToggleDecimals = { viewModel.toggleDecimals() },
                        onToggleMaskBalances = { viewModel.toggleMaskBalances() },
                        onToggleCompactSpacing = { viewModel.toggleCompactSpacing() },
                        onSetSalaryCycleDay = { viewModel.setSalaryCycleStartDay(it) },
                        onOpenCustomizer = { showCustomizerSheet = true },
                        onSeedSampleData = { viewModel.seedSampleFinancialData() },
                        onClearAllTransactions = { viewModel.clearAllTransactions() },
                        onTriggerScan = { viewModel.scanNotifications(context) },
                        onToggleMessageTracking = { viewModel.setMessageTrackingEnabled(it, context) },
                        onSetMessageTrackingDays = { viewModel.setMessageTrackingDays(it, context) },
                        lastDailyBackup = lastDailyBackup,
                        localBackupsList = localBackupsList,
                        onSaveToGoogleDrive = {
                            val todayStr = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US).format(java.util.Date())
                            saveToDriveLauncher.launch("CashTrail_Backup_$todayStr.json")
                        },
                        onTriggerInstantBackup = {
                            viewModel.createInstantBackup(context) { rec ->
                                if (rec != null) {
                                    android.widget.Toast.makeText(context, "Instant backup created: ${rec.fileName}", android.widget.Toast.LENGTH_SHORT).show()
                                }
                            }
                        },
                        onRestoreBackupRequested = {
                            restoreBackupLauncher.launch(arrayOf("application/json", "text/plain", "*/*"))
                        },
                        onShareBackup = { record ->
                            val path = record?.filePath ?: lastDailyBackup?.filePath
                            if (path != null) {
                                com.example.data.backup.LocalBackupManager.shareBackupFile(context, path)
                            } else {
                                viewModel.createInstantBackup(context) { newRec ->
                                    newRec?.filePath?.let { p ->
                                        com.example.data.backup.LocalBackupManager.shareBackupFile(context, p)
                                    }
                                }
                            }
                        },
                        onRestoreFromRecord = { record ->
                            val file = java.io.File(record.filePath)
                            if (file.exists()) {
                                val json = file.readText()
                                viewModel.restoreBackupFromJson(context, json) { success, msg ->
                                    android.widget.Toast.makeText(context, msg, android.widget.Toast.LENGTH_LONG).show()
                                }
                            }
                        },
                        onSignOut = {
                            if (isGuest) {
                                onSignOut()
                            } else {
                                signOut(
                                    context = context,
                                    credentialManager = credentialManager,
                                    onSignOutComplete = {
                                        onSignOut()
                                    },
                                    scope = coroutineScope
                                )
                            }
                        }
                    )
                }
            }
        }
    }

    // Sheets & Dialogs
    val activeEditingTx = transactionToEdit
    if (showTransactionSheet || activeEditingTx != null) {
        TransactionEntrySheet(
            accounts = accountsList,
            initialType = transactionSheetInitialType,
            existingTransaction = activeEditingTx,
            onDismiss = {
                showTransactionSheet = false
                transactionToEdit = null
                pendingNotificationIdForEntry = null
            },
            onSubmit = { type, amount, accountId, destAccountId, category, note, invoiceFileName, invoiceUri ->
                if (activeEditingTx != null && activeEditingTx.id.isNotBlank()) {
                    val updated = activeEditingTx.copy(
                        type = type.name,
                        amount = amount,
                        accountId = accountId,
                        destinationAccountId = destAccountId,
                        category = category,
                        note = note,
                        invoiceFileName = invoiceFileName,
                        invoiceUri = invoiceUri
                    )
                    viewModel.updateTransaction(activeEditingTx, updated)
                    transactionToEdit = null
                } else {
                    viewModel.addTransaction(
                        type = type,
                        amount = amount,
                        accountId = accountId,
                        destinationAccountId = destAccountId,
                        category = category,
                        note = note,
                        invoiceFileName = invoiceFileName,
                        invoiceUri = invoiceUri
                    )
                    showTransactionSheet = false
                    transactionToEdit = null
                    pendingNotificationIdForEntry?.let { notifId ->
                        viewModel.markNotificationAsProcessed(notifId)
                        pendingNotificationIdForEntry = null
                    }
                }
            }
        )
    }

    val activeEditingInv = investmentToEdit
    if (showInvestmentSheet || activeEditingInv != null) {
        InvestmentEntrySheet(
            accounts = accountsList,
            existingInvestment = activeEditingInv,
            onDismiss = {
                showInvestmentSheet = false
                investmentToEdit = null
                pendingNotificationIdForEntry = null
            },
            onSubmit = { assetName, assetType, action, amount, sourceAccountId, note ->
                if (activeEditingInv != null && activeEditingInv.id.isNotBlank()) {
                    val updated = activeEditingInv.copy(
                        assetName = assetName,
                        assetType = assetType,
                        action = action.name,
                        amount = amount,
                        sourceAccountId = sourceAccountId,
                        note = note
                    )
                    viewModel.updateInvestment(activeEditingInv, updated)
                    investmentToEdit = null
                } else {
                    viewModel.addInvestment(
                        assetName = assetName,
                        assetType = assetType,
                        action = action,
                        amount = amount,
                        sourceAccountId = sourceAccountId,
                        note = note
                    )
                    showInvestmentSheet = false
                    investmentToEdit = null
                    pendingNotificationIdForEntry?.let { notifId ->
                        viewModel.markNotificationAsProcessed(notifId)
                        pendingNotificationIdForEntry = null
                    }
                }
            }
        )
    }

    if (showAddAccountDialog) {
        AddAccountDialog(
            suggestedAccounts = suggestedAccounts,
            initialSuggestedAccount = prefillSuggestedAccount,
            onDismiss = {
                showAddAccountDialog = false
                prefillSuggestedAccount = null
            },
            onSubmit = { name, type, balance, creditLimit, colorHex, institution, notes, statementDay, dueDay ->
                viewModel.addAccount(
                    name = name,
                    type = type,
                    balance = balance,
                    creditLimit = creditLimit,
                    colorHex = colorHex,
                    institution = institution,
                    notes = notes,
                    statementDay = statementDay,
                    dueDay = dueDay
                )
                showAddAccountDialog = false
                prefillSuggestedAccount = null
            }
        )
    }

    if (showPersonalDocumentsSheet) {
        PersonalDocumentsSheet(
            documentsState = personalDocumentsState,
            onDismiss = { showPersonalDocumentsSheet = false },
            onAddDocument = { name, category, number, issuer, expiry, issueDate, notes, fileUri, fileName, colorHex ->
                viewModel.addPersonalDocument(name, category, number, issuer, expiry, issueDate, notes, fileUri, fileName, colorHex)
            },
            onUpdateDocument = { doc ->
                viewModel.updatePersonalDocument(doc)
            },
            onDeleteDocument = { docId, name ->
                viewModel.deletePersonalDocument(docId, name)
            },
            onToggleFavorite = { docId, curFav ->
                viewModel.toggleDocumentFavorite(docId, curFav)
            }
        )
    }

    if (showCustomizerSheet) {
        DashboardCustomizerSheet(
            config = preferences.widgetConfig,
            onDismiss = { showCustomizerSheet = false },
            onSave = { newConfig ->
                viewModel.updateWidgetConfig(newConfig)
            },
            onReset = {
                viewModel.resetDashboardWidgets()
            }
        )
    }

    if (showDueAlertsSheet) {
        val currentTransactions = (transactionsState as? UiState.Success)?.data ?: emptyList()
        CreditCardDueAlertsSheet(
            creditCardAccounts = creditCardAccounts,
            transactions = currentTransactions,
            detectedBills = detectedBills,
            currencySymbol = preferences.currencySymbol,
            onDismiss = { showDueAlertsSheet = false },
            onPayCard = { card ->
                showDueAlertsSheet = false
                val stmtSummary = com.example.ui.util.CreditCardStatementCalculator.calculateStatementSummary(card, currentTransactions)
                val payAmount = if (stmtSummary.statementDueAmount > 0) stmtSummary.statementDueAmount else stmtSummary.totalOutstanding
                val bankAccount = accountsList.firstOrNull { it.type == AccountType.BANK.name } ?: accountsList.firstOrNull()
                transactionToEdit = Transaction(
                    id = "",
                    userId = currentUserId,
                    type = TransactionType.TRANSFER.name,
                    amount = payAmount,
                    accountId = bankAccount?.id ?: "",
                    destinationAccountId = card.id,
                    category = "Credit Card Payment",
                    note = "Payment towards ${card.name} (${if (stmtSummary.statementDueAmount > 0) "Statement Bill" else "Outstanding"})"
                )
                transactionSheetInitialType = TransactionType.TRANSFER
                showTransactionSheet = true
            },
            onPayDetectedBill = { bill ->
                val matchingAcc = accountsList.firstOrNull { it.name.contains(bill.lastFourDigits) }
                    ?: accountsList.firstOrNull { it.type == AccountType.BANK.name }
                    ?: accountsList.firstOrNull()
                viewModel.markDetectedBillAsPaid(bill.id, matchingAcc?.id)
            }
        )
    }

    if (showExportReportDialog) {
        val currentTransactions = (transactionsState as? UiState.Success)?.data ?: emptyList()
        com.example.ui.report.ExportReportDialog(
            transactions = currentTransactions,
            accounts = accountsList,
            currencySymbol = preferences.currencySymbol,
            onDismiss = { showExportReportDialog = false }
        )
    }
}
