package com.example.ui.dashboard

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Investment
import com.example.data.model.InvestmentAction
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.data.repository.FinancialRepository
import com.example.ui.settings.AppPreferences
import com.example.ui.settings.DashboardWidgetConfig
import android.content.Context
import com.example.data.model.BankNotification
import com.example.data.model.CreditCardBillAlert
import com.example.data.model.NotificationSource
import com.example.data.model.PersonalDocument
import com.example.data.model.SuggestedAccount
import com.example.data.scanner.BankMessageScanner
import com.example.data.scanner.FinancialMessageParser
import com.example.data.scanner.SuggestedAccountDetector
import com.example.data.backup.CashTrailBackupData
import com.example.data.backup.DailyBackupRecord
import com.example.data.backup.LocalBackupManager
import com.google.firebase.Timestamp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.Calendar

sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Success<T>(val data: T) : UiState<T>
    data class Error(val message: String) : UiState<Nothing>
}

enum class DashboardPeriod(val title: String, val shortLabel: String) {
    SALARY_CYCLE("Current Salary Cycle", "Salary Cycle"),
    CALENDAR_MONTH("This Month (Calendar)", "Calendar Month"),
    LAST_30_DAYS("Last 30 Days", "30 Days"),
    LAST_7_DAYS("Last 7 Days", "7 Days"),
    THIS_YEAR("This Year", "This Year"),
    ALL_TIME("All Time", "All Time")
}

data class PeriodDateRange(
    val startDate: java.util.Date? = null,
    val endDate: java.util.Date? = null,
    val formattedLabel: String = "",
    val daysElapsed: Int = 0,
    val totalDays: Int = 30,
    val daysRemaining: Int = 0,
    val isSalaryCycle: Boolean = false
)

data class FinancialSummary(
    val netWorth: Double = 0.0,
    val totalLiquidCash: Double = 0.0,
    val totalCreditDebt: Double = 0.0,
    val monthlyIncome: Double = 0.0,
    val monthlyExpense: Double = 0.0,
    val monthlySavings: Double = 0.0,
    val totalInvestedCapital: Double = 0.0,
    val monthlyTransfersCount: Int = 0
)

data class CategoryBreakdownItem(
    val category: String,
    val amount: Double,
    val percentage: Float
)

class FinancialViewModel(
    private val repository: FinancialRepository,
    private val currentUserId: String
) : ViewModel() {

    private val _statusMessage = MutableStateFlow<String?>(null)
    val statusMessage: StateFlow<String?> = _statusMessage.asStateFlow()

    private val _preferences = MutableStateFlow(AppPreferences())
    val preferences: StateFlow<AppPreferences> = _preferences.asStateFlow()

    private val _notifications = MutableStateFlow<List<BankNotification>>(emptyList())
    val notifications: StateFlow<List<BankNotification>> = _notifications.asStateFlow()

    private val _detectedBills = MutableStateFlow<List<CreditCardBillAlert>>(emptyList())
    val detectedBills: StateFlow<List<CreditCardBillAlert>> = _detectedBills.asStateFlow()

    private val _isScanning = MutableStateFlow(false)
    val isScanning: StateFlow<Boolean> = _isScanning.asStateFlow()

    private val _hasSmsPermission = MutableStateFlow(false)
    val hasSmsPermission: StateFlow<Boolean> = _hasSmsPermission.asStateFlow()

    private val _lastDailyBackup = MutableStateFlow<DailyBackupRecord?>(null)
    val lastDailyBackup: StateFlow<DailyBackupRecord?> = _lastDailyBackup.asStateFlow()

    private val _localBackupsList = MutableStateFlow<List<DailyBackupRecord>>(emptyList())
    val localBackupsList: StateFlow<List<DailyBackupRecord>> = _localBackupsList.asStateFlow()

    private val _dismissedNotificationIds = mutableSetOf<String>()
    private val _processedNotificationIds = mutableSetOf<String>()

    init {
        viewModelScope.launch {
            repository.seedDefaultAccountsIfEmpty(currentUserId)
            repository.purgeDummyEntries(currentUserId)
        }
    }


    val accountsState: StateFlow<UiState<List<Account>>> = repository.observeAccounts(currentUserId)
        .map<List<Account>, UiState<List<Account>>> { UiState.Success(it) }
        .catch { error ->
            Log.e(TAG, "Error observing accounts", error)
            emit(UiState.Error(error.localizedMessage ?: "Failed to load accounts"))
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = UiState.Loading
        )

    val transactionsState: StateFlow<UiState<List<Transaction>>> = repository.observeTransactions(currentUserId)
        .map<List<Transaction>, UiState<List<Transaction>>> { UiState.Success(it) }
        .catch { error ->
            Log.e(TAG, "Error observing transactions", error)
            emit(UiState.Error(error.localizedMessage ?: "Failed to load transactions"))
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = UiState.Loading
        )

    val investmentsState: StateFlow<UiState<List<Investment>>> = repository.observeInvestments(currentUserId)
        .map<List<Investment>, UiState<List<Investment>>> { UiState.Success(it) }
        .catch { error ->
            Log.e(TAG, "Error observing investments", error)
            emit(UiState.Error(error.localizedMessage ?: "Failed to load investments"))
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = UiState.Loading
        )

    val personalDocumentsState: StateFlow<UiState<List<PersonalDocument>>> = repository.observePersonalDocuments(currentUserId)
        .map<List<PersonalDocument>, UiState<List<PersonalDocument>>> { UiState.Success(it) }
        .catch { error ->
            Log.e(TAG, "Error observing personal documents", error)
            emit(UiState.Error(error.localizedMessage ?: "Failed to load documents"))
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = UiState.Loading
        )

    private val _dismissedSuggestedAccountKeys = MutableStateFlow<Set<String>>(emptySet())

    val suggestedAccounts: StateFlow<List<SuggestedAccount>> = combine(
        _notifications,
        _detectedBills,
        accountsState,
        _dismissedSuggestedAccountKeys
    ) { notifications, bills, accState, dismissedKeys ->
        val currentAccounts = (accState as? UiState.Success)?.data ?: emptyList()
        SuggestedAccountDetector.detectSuggestions(
            notifications = notifications,
            bills = bills,
            existingAccounts = currentAccounts,
            dismissedKeys = dismissedKeys
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
        initialValue = emptyList()
    )

    private val _selectedPeriod = MutableStateFlow(DashboardPeriod.SALARY_CYCLE)
    val selectedPeriod: StateFlow<DashboardPeriod> = _selectedPeriod.asStateFlow()

    val periodDateRange: StateFlow<PeriodDateRange> = combine(
        _selectedPeriod,
        _preferences
    ) { period, prefs ->
        computePeriodDateRange(period, prefs.salaryCycleStartDay)
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
        initialValue = computePeriodDateRange(DashboardPeriod.SALARY_CYCLE, 1)
    )

    val financialSummary: StateFlow<FinancialSummary> = combine(
        repository.observeAccounts(currentUserId).catch { emit(emptyList()) },
        repository.observeTransactions(currentUserId).catch { emit(emptyList()) },
        repository.observeInvestments(currentUserId).catch { emit(emptyList()) },
        periodDateRange
    ) { accounts, transactions, investments, dateRange ->
        calculateSummary(accounts, transactions, investments, dateRange)
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
        initialValue = FinancialSummary()
    )

    val categoryBreakdown: StateFlow<List<CategoryBreakdownItem>> = combine(
        repository.observeTransactions(currentUserId).catch { emit(emptyList()) },
        periodDateRange
    ) { list, dateRange ->
        val expenses = list.filter { tx ->
            tx.type == TransactionType.EXPENSE.name && isTransactionInDateRange(tx, dateRange)
        }
        val totalExpense = expenses.sumOf { it.amount }
        if (totalExpense <= 0.0) emptyList()
        else {
            expenses.groupBy { it.category }
                .map { (cat, txList) ->
                    val sum = txList.sumOf { it.amount }
                    CategoryBreakdownItem(cat, sum, (sum / totalExpense).toFloat())
                }
                .sortedByDescending { it.amount }
        }
    }
        .catch { emit(emptyList()) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(STOP_TIMEOUT_MILLIS),
            initialValue = emptyList()
        )

    private fun isTransactionInDateRange(tx: Transaction, dateRange: PeriodDateRange): Boolean {
        if (dateRange.startDate == null || dateRange.endDate == null) return true
        val txDate = tx.date?.toDate() ?: tx.createdAt?.toDate() ?: return false
        return txDate.time >= dateRange.startDate.time && txDate.time <= dateRange.endDate.time
    }

    private fun calculateSummary(
        accounts: List<Account>,
        transactions: List<Transaction>,
        investments: List<Investment>,
        dateRange: PeriodDateRange
    ): FinancialSummary {
        var liquid = 0.0
        var creditDebt = 0.0

        for (acc in accounts) {
            if (acc.type == AccountType.CREDIT_CARD.name) {
                creditDebt += acc.balance
            } else {
                liquid += acc.balance
            }
        }

        var mIncome = 0.0
        var mExpense = 0.0
        var mTransfersCount = 0

        for (tx in transactions) {
            if (isTransactionInDateRange(tx, dateRange)) {
                when (tx.type) {
                    TransactionType.INCOME.name -> mIncome += tx.amount
                    TransactionType.EXPENSE.name -> mExpense += tx.amount
                    TransactionType.TRANSFER.name -> mTransfersCount++
                }
            }
        }

        var investedContrib = 0.0
        var investedWithdrawn = 0.0
        for (inv in investments) {
            if (inv.action == InvestmentAction.CONTRIBUTION.name) {
                investedContrib += inv.amount
            } else {
                investedWithdrawn += inv.amount
            }
        }
        val netInvested = (investedContrib - investedWithdrawn).coerceAtLeast(0.0)
        val netWorth = (liquid - creditDebt) + netInvested

        return FinancialSummary(
            netWorth = netWorth,
            totalLiquidCash = liquid,
            totalCreditDebt = creditDebt,
            monthlyIncome = mIncome,
            monthlyExpense = mExpense,
            monthlySavings = (mIncome - mExpense),
            totalInvestedCapital = netInvested,
            monthlyTransfersCount = mTransfersCount
        )
    }

    fun selectPeriod(period: DashboardPeriod) {
        _selectedPeriod.value = period
        _statusMessage.value = "Filtered to: ${period.title}"
    }

    fun setSalaryCycleStartDay(day: Int) {
        _preferences.value = _preferences.value.copy(salaryCycleStartDay = day)
        _statusMessage.value = "Salary cycle updated to ${day}th of month"
    }

    // -------------------------------------------------------------------------
    // PREFERENCES & WIDGET CONFIG ACTIONS
    // -------------------------------------------------------------------------

    fun updateWidgetConfig(newConfig: DashboardWidgetConfig) {
        _preferences.value = _preferences.value.copy(widgetConfig = newConfig)
        _statusMessage.value = "Dashboard widgets customized"
    }

    fun setCurrency(symbol: String) {
        _preferences.value = _preferences.value.copy(currencySymbol = symbol)
        _statusMessage.value = "Currency updated to $symbol"
    }

    fun toggleDecimals() {
        val current = _preferences.value.showDecimals
        _preferences.value = _preferences.value.copy(showDecimals = !current)
        _statusMessage.value = if (!current) "Showing 2 decimal places" else "Showing rounded amounts"
    }

    fun toggleMaskBalances() {
        val current = _preferences.value.maskBalances
        _preferences.value = _preferences.value.copy(maskBalances = !current)
        _statusMessage.value = if (!current) "Privacy Mode Enabled (Amounts Hidden)" else "Amounts Visible"
    }

    fun toggleCompactSpacing() {
        val current = _preferences.value.compactSpacing
        _preferences.value = _preferences.value.copy(compactSpacing = !current)
        _statusMessage.value = if (!current) "Space Optimized View Enabled" else "Comfortable Spacing View Enabled"
    }

    fun resetDashboardWidgets() {
        _preferences.value = _preferences.value.copy(widgetConfig = DashboardWidgetConfig())
        _statusMessage.value = "Dashboard widgets reset to default"
    }

    // -------------------------------------------------------------------------
    // BACKUP & GOOGLE DRIVE INTEGRATION
    // -------------------------------------------------------------------------

    fun refreshBackupRecords(context: Context) {
        viewModelScope.launch {
            _lastDailyBackup.value = LocalBackupManager.getLastBackupInfo(context)
            _localBackupsList.value = LocalBackupManager.listLocalBackups(context)
        }
    }

    fun checkAndRunDailyBackup(context: Context) {
        viewModelScope.launch {
            val accounts = (accountsState.value as? UiState.Success)?.data ?: emptyList()
            val transactions = (transactionsState.value as? UiState.Success)?.data ?: emptyList()
            val investments = (investmentsState.value as? UiState.Success)?.data ?: emptyList()
            val documents = (personalDocumentsState.value as? UiState.Success)?.data ?: emptyList()

            if (accounts.isNotEmpty() || transactions.isNotEmpty() || investments.isNotEmpty()) {
                val record = LocalBackupManager.runDailyBackupIfNeeded(
                    context = context,
                    accounts = accounts,
                    transactions = transactions,
                    investments = investments,
                    documents = documents,
                    preferences = _preferences.value,
                    userEmail = currentUserId
                )
                if (record != null) {
                    _lastDailyBackup.value = record
                }
            }
            refreshBackupRecords(context)
        }
    }

    fun createInstantBackup(context: Context, onComplete: ((DailyBackupRecord?) -> Unit)? = null) {
        viewModelScope.launch {
            val accounts = (accountsState.value as? UiState.Success)?.data ?: emptyList()
            val transactions = (transactionsState.value as? UiState.Success)?.data ?: emptyList()
            val investments = (investmentsState.value as? UiState.Success)?.data ?: emptyList()
            val documents = (personalDocumentsState.value as? UiState.Success)?.data ?: emptyList()

            val record = LocalBackupManager.createInstantBackup(
                context = context,
                accounts = accounts,
                transactions = transactions,
                investments = investments,
                documents = documents,
                preferences = _preferences.value,
                userEmail = currentUserId
            )
            if (record != null) {
                _lastDailyBackup.value = record
                _statusMessage.value = "Backup created: ${record.fileName} (${record.formattedFileSize})"
            } else {
                _statusMessage.value = "Failed to create backup"
            }
            refreshBackupRecords(context)
            onComplete?.invoke(record)
        }
    }

    fun getBackupJsonForExport(): String {
        val accounts = (accountsState.value as? UiState.Success)?.data ?: emptyList()
        val transactions = (transactionsState.value as? UiState.Success)?.data ?: emptyList()
        val investments = (investmentsState.value as? UiState.Success)?.data ?: emptyList()
        val documents = (personalDocumentsState.value as? UiState.Success)?.data ?: emptyList()

        val backupData = LocalBackupManager.buildBackupData(
            accounts = accounts,
            transactions = transactions,
            investments = investments,
            documents = documents,
            preferences = _preferences.value,
            userEmail = currentUserId
        )
        return backupData.toJsonString(indent = 2)
    }

    fun restoreBackupFromJson(
        context: Context,
        jsonString: String,
        onResult: (Boolean, String) -> Unit
    ) {
        viewModelScope.launch {
            try {
                val backupData = CashTrailBackupData.fromJsonString(jsonString)
                val result = repository.restoreFromBackupData(currentUserId, backupData)
                if (result.isSuccess) {
                    val count = result.getOrNull() ?: 0
                    _preferences.value = backupData.preferences
                    _statusMessage.value = "Successfully restored $count items from backup!"
                    refreshBackupRecords(context)
                    onResult(true, "Restored $count records successfully from backup.")
                } else {
                    val msg = result.exceptionOrNull()?.localizedMessage ?: "Unknown restore error"
                    _statusMessage.value = "Restore failed: $msg"
                    onResult(false, msg)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed parsing or restoring backup JSON", e)
                _statusMessage.value = "Invalid backup file: ${e.localizedMessage}"
                onResult(false, "Invalid backup file format: ${e.localizedMessage}")
            }
        }
    }

    // -------------------------------------------------------------------------
    // DATA ACTIONS
    // -------------------------------------------------------------------------

    fun addTransaction(
        type: TransactionType,
        amount: Double,
        accountId: String,
        destinationAccountId: String? = null,
        category: String,
        note: String,
        invoiceFileName: String = "",
        invoiceUri: String = "",
        date: Timestamp = Timestamp.now()
    ) {
        viewModelScope.launch {
            val tx = Transaction(
                userId = currentUserId,
                type = type.name,
                amount = amount,
                accountId = accountId,
                destinationAccountId = destinationAccountId,
                category = category,
                note = note,
                invoiceFileName = invoiceFileName,
                invoiceUri = invoiceUri,
                date = date
            )
            val result = repository.addTransaction(currentUserId, tx)
            if (result.isSuccess) {
                val symbol = _preferences.value.currencySymbol
                _statusMessage.value = when (type) {
                    TransactionType.EXPENSE -> "Expense of $symbol$amount recorded"
                    TransactionType.INCOME -> "Income of $symbol$amount recorded"
                    TransactionType.TRANSFER -> "Inter-account transfer of $symbol$amount completed"
                }
            } else {
                _statusMessage.value = "Failed to record transaction: ${result.exceptionOrNull()?.message}"
            }
        }
    }

    fun deleteTransaction(transaction: Transaction) {
        viewModelScope.launch {
            val result = repository.deleteTransaction(currentUserId, transaction)
            if (result.isSuccess) {
                _statusMessage.value = "Transaction removed & balance restored"
            }
        }
    }

    fun updateTransaction(oldTransaction: Transaction, updatedTransaction: Transaction) {
        viewModelScope.launch {
            val result = repository.updateTransaction(currentUserId, oldTransaction, updatedTransaction)
            if (result.isSuccess) {
                _statusMessage.value = "Transaction updated successfully"
            } else {
                _statusMessage.value = "Failed to update transaction"
            }
        }
    }

    fun addAccount(
        name: String,
        type: AccountType,
        balance: Double,
        creditLimit: Double,
        colorHex: String,
        institution: String,
        notes: String,
        statementDay: Int = 0,
        dueDay: Int = 0
    ) {
        viewModelScope.launch {
            val account = Account(
                userId = currentUserId,
                name = name,
                type = type.name,
                balance = balance,
                creditLimit = creditLimit,
                statementDay = statementDay,
                dueDay = dueDay,
                colorHex = colorHex,
                institution = institution,
                notes = notes
            )
            val result = repository.createAccount(currentUserId, account)
            if (result.isSuccess) {
                _statusMessage.value = "Account '$name' created successfully"
            } else {
                _statusMessage.value = "Failed to create account"
            }
        }
    }

    fun updateAccount(account: Account) {
        viewModelScope.launch {
            val result = repository.updateAccount(currentUserId, account)
            if (result.isSuccess) {
                _statusMessage.value = "Account updated"
            }
        }
    }

    fun deleteAccount(accountId: String) {
        viewModelScope.launch {
            val result = repository.deleteAccount(currentUserId, accountId)
            if (result.isSuccess) {
                _statusMessage.value = "Account deleted"
            }
        }
    }

    fun addInvestment(
        assetName: String,
        assetType: String,
        action: InvestmentAction,
        amount: Double,
        sourceAccountId: String?,
        note: String,
        date: Timestamp = Timestamp.now()
    ) {
        viewModelScope.launch {
            val inv = Investment(
                userId = currentUserId,
                assetName = assetName,
                assetType = assetType,
                action = action.name,
                amount = amount,
                sourceAccountId = sourceAccountId,
                note = note,
                date = date
            )
            val result = repository.addInvestment(currentUserId, inv)
            if (result.isSuccess) {
                val symbol = _preferences.value.currencySymbol
                _statusMessage.value = "${action.displayName} of $symbol$amount in $assetName recorded"
            } else {
                _statusMessage.value = "Failed to record investment"
            }
        }
    }

    fun deleteInvestment(investment: Investment) {
        viewModelScope.launch {
            val result = repository.deleteInvestment(currentUserId, investment)
            if (result.isSuccess) {
                _statusMessage.value = "Investment entry removed"
            }
        }
    }

    fun updateInvestment(oldInvestment: Investment, updatedInvestment: Investment) {
        viewModelScope.launch {
            val result = repository.updateInvestment(currentUserId, oldInvestment, updatedInvestment)
            if (result.isSuccess) {
                _statusMessage.value = "Investment record updated"
            } else {
                _statusMessage.value = "Failed to update investment"
            }
        }
    }

    fun purgeDummyEntries() {
        viewModelScope.launch {
            val result = repository.purgeDummyEntries(currentUserId)
            result.onSuccess { count ->
                _statusMessage.value = if (count > 0) "Removed $count dummy entries" else "No dummy entries found"
            }.onFailure {
                _statusMessage.value = "Failed to purge dummy entries"
            }
        }
    }

    fun clearAllTransactions() {
        viewModelScope.launch {
            val result = repository.clearAllTransactions(currentUserId)
            result.onSuccess {
                _statusMessage.value = "All ledger transactions cleared"
            }.onFailure {
                _statusMessage.value = "Failed to clear transactions"
            }
        }
    }

    fun seedSampleFinancialData() {
        // Obsolete: Clean slate enforced per user request. Triggers dummy purge instead.
        purgeDummyEntries()
    }


    fun clearStatusMessage() {
        _statusMessage.value = null
    }

    // -------------------------------------------------------------------------
    // BANK SMS NOTIFICATION SCANNER (CONFIGURABLE DAYS & ON/OFF TOGGLE)
    // -------------------------------------------------------------------------

    fun setSmsPermissionGranted(granted: Boolean, context: Context? = null) {
        _hasSmsPermission.value = granted
        if (granted && context != null && _preferences.value.messageTrackingEnabled) {
            scanNotifications(context)
        }
    }

    fun setMessageTrackingEnabled(enabled: Boolean, context: Context? = null) {
        _preferences.value = _preferences.value.copy(messageTrackingEnabled = enabled)
        if (enabled) {
            _statusMessage.value = "Message tracking enabled (${_preferences.value.messageTrackingDays} days)"
            if (context != null) {
                scanNotifications(context)
            }
        } else {
            _notifications.value = emptyList()
            _detectedBills.value = emptyList()
            _statusMessage.value = "Message tracking turned OFF"
        }
    }

    fun setMessageTrackingDays(days: Int, context: Context? = null) {
        val validDays = days.coerceIn(1, 365)
        _preferences.value = _preferences.value.copy(messageTrackingDays = validDays)
        _statusMessage.value = "Tracking set to past $validDays days"
        if (_preferences.value.messageTrackingEnabled && context != null) {
            scanNotifications(context)
        }
    }

    fun scanNotifications(context: Context) {
        if (!_preferences.value.messageTrackingEnabled) {
            _notifications.value = emptyList()
            _detectedBills.value = emptyList()
            _statusMessage.value = "Message tracking is currently OFF"
            return
        }
        viewModelScope.launch {
            _isScanning.value = true
            try {
                val symbol = _preferences.value.currencySymbol
                val days = _preferences.value.messageTrackingDays.coerceAtLeast(1)
                val (list, dues) = BankMessageScanner.scanMessages(
                    context = context,
                    daysToTrack = days,
                    currencySymbol = symbol
                )
                val dismissedIds = _dismissedNotificationIds
                val processedIds = _processedNotificationIds
                _notifications.value = list.map { n ->
                    n.copy(
                        isDismissed = dismissedIds.contains(n.id),
                        isProcessed = processedIds.contains(n.id)
                    )
                }
                _detectedBills.value = dues
                _statusMessage.value = "Scanned past $days days: ${list.size} alerts found"
            } catch (e: Exception) {
                Log.e(TAG, "Error scanning messages", e)
                _statusMessage.value = "Failed to scan messages: ${e.localizedMessage}"
            } finally {
                _isScanning.value = false
            }
        }
    }

    fun logNotificationAsExpense(
        notification: BankNotification,
        accountId: String,
        category: String,
        note: String
    ) {
        viewModelScope.launch {
            addTransaction(
                type = TransactionType.EXPENSE,
                amount = notification.amount,
                accountId = accountId,
                category = category,
                note = if (note.isNotBlank()) note else "Bank: ${notification.merchantOrPayee}"
            )
            _processedNotificationIds.add(notification.id)
            _notifications.value = _notifications.value.map {
                if (it.id == notification.id) it.copy(isProcessed = true) else it
            }
        }
    }

    fun logNotificationAsInvestment(
        notification: BankNotification,
        assetName: String,
        assetType: String,
        sourceAccountId: String?
    ) {
        viewModelScope.launch {
            addInvestment(
                assetName = assetName,
                assetType = assetType,
                action = InvestmentAction.CONTRIBUTION,
                amount = notification.amount,
                sourceAccountId = sourceAccountId,
                note = "Detected from ${notification.source}: ${notification.merchantOrPayee}"
            )
            _processedNotificationIds.add(notification.id)
            _notifications.value = _notifications.value.map {
                if (it.id == notification.id) it.copy(isProcessed = true) else it
            }
        }
    }

    fun logNotificationAsIncome(
        notification: BankNotification,
        accountId: String,
        category: String,
        note: String
    ) {
        viewModelScope.launch {
            addTransaction(
                type = TransactionType.INCOME,
                amount = notification.amount,
                accountId = accountId,
                category = category,
                note = if (note.isNotBlank()) note else "Bank: ${notification.merchantOrPayee}"
            )
            _processedNotificationIds.add(notification.id)
            _notifications.value = _notifications.value.map {
                if (it.id == notification.id) it.copy(isProcessed = true) else it
            }
        }
    }

    fun dismissNotification(notificationId: String) {
        _dismissedNotificationIds.add(notificationId)
        _notifications.value = _notifications.value.map {
            if (it.id == notificationId) it.copy(isDismissed = true) else it
        }
        _statusMessage.value = "Notification dismissed"
    }

    fun markNotificationAsProcessed(notificationId: String) {
        _processedNotificationIds.add(notificationId)
        _notifications.value = _notifications.value.map {
            if (it.id == notificationId) it.copy(isProcessed = true) else it
        }
    }

    fun markDetectedBillAsPaid(billId: String, accountId: String? = null) {
        viewModelScope.launch {
            val bill = _detectedBills.value.find { it.id == billId }
            if (bill != null && accountId != null) {
                addTransaction(
                    type = TransactionType.EXPENSE,
                    amount = bill.totalDue,
                    accountId = accountId,
                    category = "Bills & Utilities",
                    note = "Paid ${bill.cardName} bill"
                )
            }
            _detectedBills.value = _detectedBills.value.map {
                if (it.id == billId) it.copy(isPaid = true) else it
            }
            _statusMessage.value = "Bill marked as paid"
        }
    }

    // ----------------------------------------------------
    // SUGGESTED ACCOUNTS (FROM MESSAGE TRACKING)
    // ----------------------------------------------------

    fun dismissSuggestedAccount(suggestionKey: String) {
        _dismissedSuggestedAccountKeys.value = _dismissedSuggestedAccountKeys.value + suggestionKey
        _statusMessage.value = "Suggested account dismissed"
    }

    fun addSuggestedAccount(suggestion: SuggestedAccount) {
        viewModelScope.launch {
            addAccount(
                name = suggestion.name,
                type = suggestion.type,
                balance = 0.0,
                creditLimit = if (suggestion.type == AccountType.CREDIT_CARD) 50000.0 else 0.0,
                colorHex = if (suggestion.type == AccountType.CREDIT_CARD) "#C62828" else "#1E88E5",
                institution = suggestion.institution,
                notes = suggestion.reason,
                statementDay = if (suggestion.type == AccountType.CREDIT_CARD) 15 else 0,
                dueDay = if (suggestion.type == AccountType.CREDIT_CARD) 5 else 0
            )
            _dismissedSuggestedAccountKeys.value = _dismissedSuggestedAccountKeys.value + suggestion.id
            _statusMessage.value = "Added ${suggestion.name} to your accounts"
        }
    }

    fun simulateSampleBankMessage(body: String, sender: String = "VM-AXISBK") {
        val parsed = FinancialMessageParser.parseMessage(
            rawBody = body,
            sender = sender,
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = _preferences.value.currencySymbol
        )
        if (parsed != null) {
            _notifications.value = listOf(parsed) + _notifications.value
            _statusMessage.value = "Tracked message from $sender"
        }
    }

    // ----------------------------------------------------
    // PERSONAL DOCUMENTS MANAGEMENT
    // ----------------------------------------------------

    fun addPersonalDocument(
        name: String,
        category: String,
        documentNumber: String = "",
        issuer: String = "",
        expiryDate: String = "",
        issueDate: String = "",
        notes: String = "",
        fileUri: String = "",
        fileName: String = "",
        colorHex: String = "#1E88E5"
    ) {
        viewModelScope.launch {
            val doc = PersonalDocument(
                name = name,
                category = category,
                documentNumber = documentNumber,
                issuer = issuer,
                expiryDate = expiryDate,
                issueDate = issueDate,
                notes = notes,
                fileUri = fileUri,
                fileName = fileName,
                colorHex = colorHex
            )
            val result = repository.addPersonalDocument(currentUserId, doc)
            if (result.isSuccess) {
                _statusMessage.value = "Saved \"$name\""
            } else {
                _statusMessage.value = "Failed to save: ${result.exceptionOrNull()?.localizedMessage}"
            }
        }
    }

    fun updatePersonalDocument(document: PersonalDocument) {
        viewModelScope.launch {
            val result = repository.updatePersonalDocument(currentUserId, document)
            if (result.isSuccess) {
                _statusMessage.value = "Updated \"${document.name}\""
            } else {
                _statusMessage.value = "Failed to update: ${result.exceptionOrNull()?.localizedMessage}"
            }
        }
    }

    fun deletePersonalDocument(documentId: String, documentName: String = "Document") {
        viewModelScope.launch {
            val result = repository.deletePersonalDocument(currentUserId, documentId)
            if (result.isSuccess) {
                _statusMessage.value = "Deleted \"$documentName\""
            } else {
                _statusMessage.value = "Failed to delete: ${result.exceptionOrNull()?.localizedMessage}"
            }
        }
    }

    fun toggleDocumentFavorite(documentId: String, currentFavorite: Boolean) {
        viewModelScope.launch {
            repository.toggleDocumentFavorite(currentUserId, documentId, currentFavorite)
        }
    }

    companion object {
        private const val TAG = "FinancialVM"
        private const val STOP_TIMEOUT_MILLIS = 5000L

        fun computePeriodDateRange(period: DashboardPeriod, salaryCycleStartDay: Int): PeriodDateRange {
            val now = Calendar.getInstance()
            return when (period) {
                DashboardPeriod.SALARY_CYCLE -> {
                    val cycleDay = salaryCycleStartDay.coerceIn(1, 28)
                    val todayDay = now.get(Calendar.DAY_OF_MONTH)

                    val startCal = Calendar.getInstance().apply {
                        if (todayDay >= cycleDay) {
                            set(Calendar.DAY_OF_MONTH, cycleDay)
                        } else {
                            add(Calendar.MONTH, -1)
                            set(Calendar.DAY_OF_MONTH, cycleDay)
                        }
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                        set(Calendar.MILLISECOND, 0)
                    }

                    val endCal = (startCal.clone() as Calendar).apply {
                        add(Calendar.MONTH, 1)
                        add(Calendar.DAY_OF_MONTH, -1)
                        set(Calendar.HOUR_OF_DAY, 23)
                        set(Calendar.MINUTE, 59)
                        set(Calendar.SECOND, 59)
                        set(Calendar.MILLISECOND, 999)
                    }

                    val totalDays = ((endCal.timeInMillis - startCal.timeInMillis) / (1000 * 60 * 60 * 24)).toInt() + 1
                    val daysElapsed = (((now.timeInMillis - startCal.timeInMillis) / (1000 * 60 * 60 * 24)).toInt() + 1).coerceIn(1, totalDays)
                    val daysRemaining = (totalDays - daysElapsed).coerceAtLeast(0)

                    val monthNames = arrayOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
                    val startMonth = monthNames[startCal.get(Calendar.MONTH)]
                    val endMonth = monthNames[endCal.get(Calendar.MONTH)]
                    val label = "${startCal.get(Calendar.DAY_OF_MONTH)} $startMonth – ${endCal.get(Calendar.DAY_OF_MONTH)} $endMonth"

                    PeriodDateRange(
                        startDate = startCal.time,
                        endDate = endCal.time,
                        formattedLabel = label,
                        daysElapsed = daysElapsed,
                        totalDays = totalDays,
                        daysRemaining = daysRemaining,
                        isSalaryCycle = true
                    )
                }
                DashboardPeriod.CALENDAR_MONTH -> {
                    val startCal = Calendar.getInstance().apply {
                        set(Calendar.DAY_OF_MONTH, 1)
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                        set(Calendar.MILLISECOND, 0)
                    }
                    val endCal = Calendar.getInstance().apply {
                        set(Calendar.DAY_OF_MONTH, getActualMaximum(Calendar.DAY_OF_MONTH))
                        set(Calendar.HOUR_OF_DAY, 23)
                        set(Calendar.MINUTE, 59)
                        set(Calendar.SECOND, 59)
                        set(Calendar.MILLISECOND, 999)
                    }
                    val monthNames = arrayOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
                    val label = "${monthNames[startCal.get(Calendar.MONTH)]} 1 – ${endCal.get(Calendar.DAY_OF_MONTH)}, ${startCal.get(Calendar.YEAR)}"
                    PeriodDateRange(
                        startDate = startCal.time,
                        endDate = endCal.time,
                        formattedLabel = label,
                        daysElapsed = now.get(Calendar.DAY_OF_MONTH),
                        totalDays = endCal.get(Calendar.DAY_OF_MONTH),
                        daysRemaining = (endCal.get(Calendar.DAY_OF_MONTH) - now.get(Calendar.DAY_OF_MONTH)).coerceAtLeast(0),
                        isSalaryCycle = false
                    )
                }
                DashboardPeriod.LAST_30_DAYS -> {
                    val startCal = Calendar.getInstance().apply {
                        add(Calendar.DAY_OF_MONTH, -30)
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                    }
                    PeriodDateRange(
                        startDate = startCal.time,
                        endDate = now.time,
                        formattedLabel = "Past 30 Days",
                        totalDays = 30,
                        daysElapsed = 30,
                        daysRemaining = 0
                    )
                }
                DashboardPeriod.LAST_7_DAYS -> {
                    val startCal = Calendar.getInstance().apply {
                        add(Calendar.DAY_OF_MONTH, -7)
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                    }
                    PeriodDateRange(
                        startDate = startCal.time,
                        endDate = now.time,
                        formattedLabel = "Past 7 Days",
                        totalDays = 7,
                        daysElapsed = 7,
                        daysRemaining = 0
                    )
                }
                DashboardPeriod.THIS_YEAR -> {
                    val startCal = Calendar.getInstance().apply {
                        set(Calendar.DAY_OF_YEAR, 1)
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                    }
                    PeriodDateRange(
                        startDate = startCal.time,
                        endDate = now.time,
                        formattedLabel = "Year ${now.get(Calendar.YEAR)}"
                    )
                }
                DashboardPeriod.ALL_TIME -> {
                    PeriodDateRange(
                        startDate = null,
                        endDate = null,
                        formattedLabel = "All Time"
                    )
                }
            }
        }
    }
}
