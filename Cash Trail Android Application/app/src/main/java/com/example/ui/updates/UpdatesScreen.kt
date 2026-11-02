package com.example.ui.updates

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Payment
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Sms
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.data.model.Account
import com.example.data.model.BankNotification
import com.example.data.model.NotificationSource
import com.example.data.model.NotificationType
import com.example.data.model.TransactionType
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeText
import com.example.ui.theme.PastelInvestmentText
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900
import com.example.ui.util.CurrencyUtils
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class UpdatesFilter {
    ALL,
    DEBITS,
    CREDITS,
    BILL_DUES
}

@Composable
fun UpdatesScreen(
    notifications: List<BankNotification>,
    accounts: List<Account>,
    isScanning: Boolean,
    currencySymbol: String,
    preferences: com.example.ui.settings.AppPreferences? = null,
    onToggleMessageTracking: ((Boolean) -> Unit)? = null,
    onRefreshScan: () -> Unit,
    onOpenTransactionSheet: (notification: BankNotification, type: TransactionType) -> Unit,
    onOpenInvestmentSheet: (notification: BankNotification) -> Unit,
    onDismissNotification: (notificationId: String) -> Unit,
    onSimulateSampleSms: ((String, String) -> Unit)? = null
) {
    val context = LocalContext.current
    var hasSmsPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.READ_SMS
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val sharedPrefs = remember(context) {
        context.getSharedPreferences("finledger_sms_sync", Context.MODE_PRIVATE)
    }
    var hasSeenSmsBanner by remember {
        mutableStateOf(sharedPrefs.getBoolean("has_seen_sms_banner", false))
    }
    val dismissBanner: () -> Unit = {
        hasSeenSmsBanner = true
        sharedPrefs.edit().putBoolean("has_seen_sms_banner", true).apply()
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasSmsPermission = isGranted
        dismissBanner()
        if (isGranted) {
            onRefreshScan()
        }
    }

    var selectedFilter by remember { mutableStateOf(UpdatesFilter.ALL) }

    // Initial scan if list is empty
    LaunchedEffect(Unit) {
        if (notifications.isEmpty() && preferences?.messageTrackingEnabled != false) {
            onRefreshScan()
        }
    }

    val activeNotifications = notifications.filter { !it.isDismissed && !it.isProcessed }
    val filteredList = when (selectedFilter) {
        UpdatesFilter.ALL -> activeNotifications
        UpdatesFilter.DEBITS -> activeNotifications.filter { it.type == NotificationType.DEBIT }
        UpdatesFilter.CREDITS -> activeNotifications.filter { it.type == NotificationType.CREDIT }
        UpdatesFilter.BILL_DUES -> activeNotifications.filter { it.type == NotificationType.BILL_DUE }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp)
            .testTag("updates_screen_list"),
        contentPadding = PaddingValues(top = 16.dp, bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "UPDATES & BANK NOTIFICATIONS",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate500,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp
                    )
                    Text(
                        text = "${preferences?.messageTrackingDays ?: 15}-Day Message Scanner",
                        style = MaterialTheme.typography.titleLarge,
                        color = Slate900,
                        fontWeight = FontWeight.Bold
                    )
                }

                IconButton(
                    onClick = onRefreshScan,
                    modifier = Modifier.testTag("refresh_scan_button")
                ) {
                    if (isScanning) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = Slate700)
                    } else {
                        Icon(imageVector = Icons.Default.Refresh, contentDescription = "Refresh 15-Day Scan", tint = Slate700)
                    }
                }
            }
        }

        // Message Tracking Disabled Banner
        if (preferences?.messageTrackingEnabled == false) {
            item {
                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFEF2F2)),
                    border = BorderStroke(1.dp, Color(0xFFFECACA)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("message_tracking_off_banner")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Message Tracking is OFF",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF991B1B)
                            )
                            Text(
                                text = "Turn message tracking ON to automatically scan and log bank SMS transactions.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFB91C1C)
                            )
                        }
                        if (onToggleMessageTracking != null) {
                            Button(
                                onClick = { onToggleMessageTracking(true) },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626)),
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier.testTag("enable_message_tracking_button")
                            ) {
                                Text("Turn ON", style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
        }

        // Permission Card (First time only if permission not yet granted and not dismissed)
        if (!hasSmsPermission && !hasSeenSmsBanner) {
            item {
                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFEF3C7)),
                    border = BorderStroke(1.dp, Color(0xFFFDE68A)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("sms_permission_first_time_banner")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(
                            modifier = Modifier.weight(1f),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Security,
                                contentDescription = null,
                                tint = Color(0xFFD97706),
                                modifier = Modifier.size(22.dp)
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text(
                                    text = "SMS Reading Permission Required",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF92400E)
                                )
                                Text(
                                    text = "Grant permission to read your incoming bank debits & credits.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color(0xFFB45309)
                                )
                            }
                        }

                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                onClick = { permissionLauncher.launch(Manifest.permission.READ_SMS) },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFD97706)),
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier.testTag("grant_sms_permission_button")
                            ) {
                                Text("Grant", style = MaterialTheme.typography.labelSmall)
                            }
                            Spacer(modifier = Modifier.width(4.dp))
                            IconButton(
                                onClick = dismissBanner,
                                modifier = Modifier
                                    .size(32.dp)
                                    .testTag("dismiss_sms_banner_button")
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Close,
                                    contentDescription = "Dismiss",
                                    tint = Color(0xFF92400E),
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }
                    }
                }
            }
        }

        // Filter Pills
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val debitsCount = activeNotifications.count { it.type == NotificationType.DEBIT }
                val creditsCount = activeNotifications.count { it.type == NotificationType.CREDIT }
                val duesCount = activeNotifications.count { it.type == NotificationType.BILL_DUE }

                FilterChip(
                    selected = selectedFilter == UpdatesFilter.ALL,
                    onClick = { selectedFilter = UpdatesFilter.ALL },
                    label = { Text("All (${activeNotifications.size})") },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Slate900, selectedLabelColor = Color.White),
                    modifier = Modifier.testTag("filter_all")
                )
                FilterChip(
                    selected = selectedFilter == UpdatesFilter.DEBITS,
                    onClick = { selectedFilter = UpdatesFilter.DEBITS },
                    label = { Text("Debits ($debitsCount)") },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = PastelExpenseText, selectedLabelColor = Color.White),
                    modifier = Modifier.testTag("filter_debits")
                )
                FilterChip(
                    selected = selectedFilter == UpdatesFilter.CREDITS,
                    onClick = { selectedFilter = UpdatesFilter.CREDITS },
                    label = { Text("Credits ($creditsCount)") },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = PastelIncomeText, selectedLabelColor = Color.White),
                    modifier = Modifier.testTag("filter_credits")
                )
                FilterChip(
                    selected = selectedFilter == UpdatesFilter.BILL_DUES,
                    onClick = { selectedFilter = UpdatesFilter.BILL_DUES },
                    label = { Text("Dues ($duesCount)") },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Color(0xFFEA580C), selectedLabelColor = Color.White),
                    modifier = Modifier.testTag("filter_dues")
                )
            }
        }

        // Items list or Empty State
        if (filteredList.isEmpty()) {
            item {
                Card(
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    border = BorderStroke(1.dp, Slate200),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 24.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(28.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = Color(0xFF16A34A),
                            modifier = Modifier.size(44.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "All Caught Up!",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Slate900
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "No unreviewed bank notifications found in the past 15 days.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(
                                onClick = onRefreshScan,
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(imageVector = Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(14.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Scan Again")
                            }

                            if (onSimulateSampleSms != null) {
                                Button(
                                    onClick = {
                                        onSimulateSampleSms(
                                            "INR 2,450.00 debited from Axis Bank A/c ending in 4102 on 29-Oct-24 at AMAZON. Avail Bal: INR 35,400",
                                            "VM-AXISBK"
                                        )
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                                    shape = RoundedCornerShape(10.dp),
                                    modifier = Modifier.testTag("simulate_sample_sms_button")
                                ) {
                                    Icon(imageVector = Icons.Default.Sms, contentDescription = null, modifier = Modifier.size(14.dp))
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text("Test Axis Bank SMS")
                                }
                            }
                        }
                    }
                }
            }
        } else {
            items(filteredList, key = { it.id }) { item ->
                NotificationReviewCard(
                    notification = item,
                    accounts = accounts,
                    currencySymbol = currencySymbol,
                    onOpenTransactionSheet = { type ->
                        onOpenTransactionSheet(item, type)
                    },
                    onOpenInvestmentSheet = {
                        onOpenInvestmentSheet(item)
                    },
                    onDismiss = {
                        onDismissNotification(item.id)
                    }
                )
            }
        }

        item {
            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

@Composable
private fun NotificationReviewCard(
    notification: BankNotification,
    accounts: List<Account>,
    currencySymbol: String,
    onOpenTransactionSheet: (type: TransactionType) -> Unit,
    onOpenInvestmentSheet: () -> Unit,
    onDismiss: () -> Unit
) {
    var showRawBody by remember { mutableStateOf(false) }

    // Pre-match account by suffix if possible
    val defaultAccount = remember(accounts, notification.accountSuffix) {
        val suffix = notification.accountSuffix
        if (suffix != null) {
            accounts.firstOrNull { it.name.contains(suffix) || it.institution.contains(suffix) }
                ?: accounts.firstOrNull()
        } else {
            accounts.firstOrNull()
        }
    }

    val dateFormat = remember { SimpleDateFormat("dd MMM, hh:mm a", Locale.getDefault()) }
    val formattedTime = remember(notification.timestamp) {
        dateFormat.format(Date(notification.timestamp))
    }

    val isDebit = notification.type == NotificationType.DEBIT
    val isCredit = notification.type == NotificationType.CREDIT

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize()
            .clickable {
                onOpenTransactionSheet(
                    if (isCredit) TransactionType.INCOME else TransactionType.EXPENSE
                )
            }
            .testTag("notification_card_${notification.id}")
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header: Source + Sender + Time
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = Color(0xFFEFF6FF)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Sms,
                                contentDescription = null,
                                tint = Color(0xFF2563EB),
                                modifier = Modifier.size(12.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "SMS",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF1D4ED8)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = notification.sender,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = Slate700
                    )
                }

                Text(
                    text = formattedTime,
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Body: Merchant & Large Amount
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = notification.merchantOrPayee,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Slate900
                    )
                    notification.accountSuffix?.let { suffix ->
                        Text(
                            text = "A/c / Card ending in ••$suffix",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                Text(
                    text = "${if (isDebit) "-" else "+"}${CurrencyUtils.formatAmount(notification.amount, currencySymbol, true, false)}",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = if (isDebit) PastelExpenseText else PastelIncomeText
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Smart Suggested Information Pill
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = Color(0xFFF8FAFC),
                border = BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.AccountBalance,
                        contentDescription = null,
                        tint = Slate600,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Suggested Category: ${notification.suggestedCategory} • Account: ${defaultAccount?.name ?: "Checking"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate600
                    )
                }
            }

            // Raw message expander
            AnimatedVisibility(visible = showRawBody) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = Color(0xFFF1F5F9),
                    border = BorderStroke(1.dp, Slate200),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp)
                ) {
                    Text(
                        text = notification.rawBody,
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate600,
                        fontSize = 11.sp,
                        modifier = Modifier.padding(8.dp)
                    )
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (showRawBody) "Hide original snippet" else "View original snippet",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500,
                    modifier = Modifier
                        .clickable { showRawBody = !showRawBody }
                        .padding(vertical = 4.dp)
                )

                TextButton(
                    onClick = onDismiss,
                    modifier = Modifier.testTag("dismiss_notification_${notification.id}")
                ) {
                    Icon(imageVector = Icons.Default.Close, contentDescription = null, modifier = Modifier.size(12.dp), tint = Slate500)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Dismiss", style = MaterialTheme.typography.labelSmall, color = Slate500)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Action Buttons: Open in regular transaction window
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (isDebit) {
                    Button(
                        onClick = { onOpenTransactionSheet(TransactionType.EXPENSE) },
                        colors = ButtonDefaults.buttonColors(containerColor = PastelExpenseText),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier
                            .weight(1.3f)
                            .testTag("log_expense_button_${notification.id}")
                    ) {
                        Icon(imageVector = Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Add as Expense", style = MaterialTheme.typography.labelSmall)
                    }

                    OutlinedButton(
                        onClick = onOpenInvestmentSheet,
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = PastelInvestmentText),
                        border = BorderStroke(1.dp, PastelInvestmentText),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier
                            .weight(1f)
                            .testTag("log_invest_button_${notification.id}")
                    ) {
                        Icon(imageVector = Icons.AutoMirrored.Filled.TrendingUp, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Add as Invest", style = MaterialTheme.typography.labelSmall)
                    }
                } else if (isCredit) {
                    Button(
                        onClick = { onOpenTransactionSheet(TransactionType.INCOME) },
                        colors = ButtonDefaults.buttonColors(containerColor = PastelIncomeText),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier
                            .weight(1f)
                            .testTag("log_income_button_${notification.id}")
                    ) {
                        Icon(imageVector = Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Add as Income", style = MaterialTheme.typography.labelSmall)
                    }
                } else {
                    Button(
                        onClick = { onOpenTransactionSheet(TransactionType.EXPENSE) },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFEA580C)),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier
                            .weight(1f)
                            .testTag("log_bill_button_${notification.id}")
                    ) {
                        Icon(imageVector = Icons.Default.Payment, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Pay / Record Expense", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
    }
}
