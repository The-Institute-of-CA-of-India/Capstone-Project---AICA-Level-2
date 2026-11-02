package com.example.ui.settings

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.material.icons.filled.AutoFixHigh
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Compress
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.Login
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Sms
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Restore
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import com.example.data.backup.DailyBackupRecord
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeText
import com.example.ui.theme.PastelTransferBg
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900

private val currencies = listOf(
    "₹" to "Indian Rupee (INR)",
    "$" to "US Dollar (USD)",
    "€" to "Euro (EUR)",
    "£" to "British Pound (GBP)",
    "¥" to "Japanese Yen (JPY)",
    "A$" to "Australian Dollar (AUD)",
    "C$" to "Canadian Dollar (CAD)",
    "AED" to "UAE Dirham (AED)"
)

@Composable
fun SettingsScreen(
    userEmail: String,
    isGuest: Boolean = false,
    preferences: AppPreferences,
    transactions: List<com.example.data.model.Transaction> = emptyList(),
    accounts: List<com.example.data.model.Account> = emptyList(),
    investments: List<com.example.data.model.Investment> = emptyList(),
    onSetCurrency: (String) -> Unit,
    onToggleDecimals: () -> Unit,
    onToggleMaskBalances: () -> Unit,
    onToggleCompactSpacing: () -> Unit,
    onSetSalaryCycleDay: (Int) -> Unit,
    onOpenCustomizer: () -> Unit,
    onSeedSampleData: () -> Unit,
    onClearAllTransactions: () -> Unit = {},
    onSignOut: () -> Unit,
    onTriggerScan: () -> Unit = {},
    onToggleMessageTracking: (Boolean) -> Unit = {},
    onSetMessageTrackingDays: (Int) -> Unit = {},
    lastDailyBackup: DailyBackupRecord? = null,
    localBackupsList: List<DailyBackupRecord> = emptyList(),
    onSaveToGoogleDrive: () -> Unit = {},
    onTriggerInstantBackup: () -> Unit = {},
    onRestoreBackupRequested: () -> Unit = {},
    onShareBackup: (DailyBackupRecord?) -> Unit = {},
    onRestoreFromRecord: (DailyBackupRecord) -> Unit = {}
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

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasSmsPermission = isGranted
        if (isGranted) {
            onTriggerScan()
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 16.dp)
            .animateContentSize(),
        contentPadding = PaddingValues(top = 16.dp, bottom = 48.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            // Header
            Text(
                text = "APPLICATION SETTINGS",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.2.sp
            )
            Text(
                text = "Preferences & Dashboard Controls",
                style = MaterialTheme.typography.titleLarge,
                color = Slate900,
                fontWeight = FontWeight.Bold
            )
        }

        // Section 1: User Account & Cloud Sync
        item {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Surface(
                                shape = CircleShape,
                                color = if (isGuest) Slate700 else Slate900,
                                modifier = Modifier.size(44.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Text(
                                        text = if (isGuest) "G" else userEmail.take(1).uppercase(),
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color.White,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = if (isGuest) "Guest Mode" else userEmail,
                                    style = MaterialTheme.typography.titleSmall,
                                    color = Slate900,
                                    fontWeight = FontWeight.Bold
                                )
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = if (isGuest) Icons.Default.CloudOff else Icons.Default.CloudDone,
                                        contentDescription = null,
                                        tint = if (isGuest) Slate500 else PastelIncomeText,
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = if (isGuest) "Local Offline Ledger" else "Cloud Sync Active",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if (isGuest) Slate500 else PastelIncomeText,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }

                        OutlinedButton(
                            onClick = onSignOut,
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.testTag("settings_sign_out_button")
                        ) {
                            Icon(
                                imageVector = if (isGuest) Icons.Default.Login else Icons.Default.ExitToApp,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = if (isGuest) Slate900 else Slate700
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = if (isGuest) "Sign In" else "Sign out",
                                color = if (isGuest) Slate900 else Slate700,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = if (isGuest) FontWeight.Bold else FontWeight.Normal
                            )
                        }
                    }

                    if (!isGuest) {
                        Spacer(modifier = Modifier.height(14.dp))
                        HorizontalDivider(color = Slate200, thickness = 1.dp)
                        Spacer(modifier = Modifier.height(10.dp))

                        Row(verticalAlignment = Alignment.Top) {
                            Icon(
                                imageVector = Icons.Default.CloudDone,
                                contentDescription = null,
                                tint = PastelIncomeText,
                                modifier = Modifier
                                    .size(16.dp)
                                    .padding(top = 2.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Column {
                                Text(
                                    text = "Google Account Cloud Sync",
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(
                                    text = "Connected with your personal Google Account ($userEmail). All transactions and ledgers are synchronized in real-time.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate600,
                                    fontSize = 11.5.sp
                                )
                            }
                        }
                    }
                }
            }
        }

        // Section: Personal Google Drive & Daily Local Backup
        item {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("backup_settings_card")
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = PastelIncomeBg,
                                modifier = Modifier.size(38.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.CloudSync,
                                        contentDescription = null,
                                        tint = PastelIncomeText,
                                        modifier = Modifier.size(22.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = "Google Drive & Local Backup",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                Text(
                                    text = "Auto-saves daily snapshot + your personal Drive",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate600,
                                    fontSize = 11.5.sp
                                )
                            }
                        }

                        // Daily Active Badge
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = PastelIncomeBg
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.CheckCircle,
                                    contentDescription = null,
                                    tint = PastelIncomeText,
                                    modifier = Modifier.size(13.dp)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = "Daily Active",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PastelIncomeText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 10.5.sp
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                    HorizontalDivider(color = Slate200, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(12.dp))

                    // Status details box
                    val lastBackup = lastDailyBackup
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Slate100, RoundedCornerShape(12.dp))
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Today,
                            contentDescription = null,
                            tint = Slate700,
                            modifier = Modifier.size(22.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = if (lastBackup != null) "Latest Backup: ${lastBackup.formattedDate} at ${lastBackup.formattedTime}" else "Daily Auto-Backup Scheduled",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = Slate900
                            )
                            Text(
                                text = if (lastBackup != null) "${lastBackup.fileName} (${lastBackup.formattedFileSize}) • Ready to save to Drive" else "Automatic daily snapshot runs every day on launch",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate600,
                                fontSize = 11.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // Primary Action: Save to My Google Drive
                    Button(
                        onClick = onSaveToGoogleDrive,
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Slate900,
                            contentColor = Color.White
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("save_to_drive_button")
                    ) {
                        Icon(
                            imageVector = Icons.Default.CloudUpload,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Save / Sync to My Google Drive",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Instant Backup Now button
                        OutlinedButton(
                            onClick = onTriggerInstantBackup,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .weight(1f)
                                .testTag("backup_now_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.Today,
                                contentDescription = null,
                                modifier = Modifier.size(15.dp),
                                tint = Slate700
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "Backup Now",
                                color = Slate900,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        // Restore from File button
                        OutlinedButton(
                            onClick = onRestoreBackupRequested,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .weight(1f)
                                .testTag("restore_backup_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.Restore,
                                contentDescription = null,
                                modifier = Modifier.size(15.dp),
                                tint = PastelTransferText
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "Restore Backup",
                                color = PastelTransferText,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Share button
                    OutlinedButton(
                        onClick = { onShareBackup(lastBackup) },
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("share_drive_backup_button")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Share,
                            contentDescription = null,
                            modifier = Modifier.size(15.dp),
                            tint = Slate700
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Share / Send Backup File (Save to Drive)",
                            color = Slate700,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }

                    // Recent Daily Snapshots List
                    if (localBackupsList.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(14.dp))
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                imageVector = Icons.Default.History,
                                contentDescription = null,
                                tint = Slate500,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "STORED DAILY BACKUPS (${localBackupsList.size})",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate500,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.8.sp
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))

                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            localBackupsList.take(5).forEach { bRecord ->
                                Surface(
                                    shape = RoundedCornerShape(10.dp),
                                    color = Slate100,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 12.dp, vertical = 8.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = bRecord.fileName,
                                                style = MaterialTheme.typography.bodySmall,
                                                fontWeight = FontWeight.SemiBold,
                                                color = Slate900,
                                                fontSize = 11.5.sp
                                            )
                                            Text(
                                                text = "${bRecord.formattedDate} • ${bRecord.formattedFileSize}",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Slate500,
                                                fontSize = 10.5.sp
                                            )
                                        }
                                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            IconButton(
                                                onClick = { onShareBackup(bRecord) },
                                                modifier = Modifier.size(28.dp)
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.Share,
                                                    contentDescription = "Share to Drive",
                                                    tint = Slate600,
                                                    modifier = Modifier.size(16.dp)
                                                )
                                            }
                                            IconButton(
                                                onClick = { onRestoreFromRecord(bRecord) },
                                                modifier = Modifier.size(28.dp)
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.Restore,
                                                    contentDescription = "Restore this backup",
                                                    tint = PastelTransferText,
                                                    modifier = Modifier.size(16.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Section: Annual Financial Statements Menu (T-Format)
        item {
            Text(
                text = "FINANCIAL STATEMENTS & ANNUAL REPORTS",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            com.example.ui.report.FinancialStatementsSettingsMenu(
                transactions = transactions,
                accounts = accounts,
                investments = investments,
                currencySymbol = preferences.currencySymbol
            )
        }

        // Section 2: Dashboard Layout & Widgets Customization Trigger
        item {
            Text(
                text = "DASHBOARD CUSTOMIZATION & WIDGETS",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpenCustomizer() }
                    .testTag("open_dashboard_customizer_button")
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                        Box(
                            modifier = Modifier
                                .size(40.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .background(PastelTransferBg),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(imageVector = Icons.Default.Tune, contentDescription = null, tint = PastelTransferText, modifier = Modifier.size(20.dp))
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(text = "Customize Dashboard Widgets", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = Slate900)
                            Text(text = "Choose widgets, adjust sizes, reorder & customize button shortcuts", style = MaterialTheme.typography.bodySmall, color = Slate500)
                        }
                    }
                    Button(
                        onClick = onOpenCustomizer,
                        colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("Customize", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }

        // Section: Bank Notifications & Message Sync
        item {
            Text(
                text = "BANK NOTIFICATIONS & AUTO SYNC",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("settings_bank_sync_card")
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    // Main Toggle Row: Message Tracking Switch (ON/OFF)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Box(
                                modifier = Modifier
                                    .size(38.dp)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(if (preferences.messageTrackingEnabled) Color(0xFFDCFCE7) else Slate100),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Sms,
                                    contentDescription = null,
                                    tint = if (preferences.messageTrackingEnabled) Color(0xFF16A34A) else Slate400,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = "SMS Message Tracking",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Slate900
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Surface(
                                        shape = RoundedCornerShape(6.dp),
                                        color = if (preferences.messageTrackingEnabled) Color(0xFFDCFCE7) else Slate200
                                    ) {
                                        Text(
                                            text = if (preferences.messageTrackingEnabled) "ON" else "OFF",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (preferences.messageTrackingEnabled) Color(0xFF15803D) else Slate600,
                                            fontWeight = FontWeight.Bold,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    }
                                }
                                Text(
                                    text = if (preferences.messageTrackingEnabled)
                                        "Scans incoming debit & credit SMS alerts from your device"
                                    else
                                        "Message tracking is turned OFF. No SMS messages will be read or logged.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate500
                                )
                            }
                        }

                        Switch(
                            checked = preferences.messageTrackingEnabled,
                            onCheckedChange = { onToggleMessageTracking(it) },
                            modifier = Modifier.testTag("toggle_message_tracking_switch"),
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = Color.White,
                                checkedTrackColor = Color(0xFF16A34A)
                            )
                        )
                    }

                    if (preferences.messageTrackingEnabled) {
                        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Slate100)

                        // Permission status & grant button
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "SMS Permission",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Slate900
                                )
                                Text(
                                    text = if (hasSmsPermission)
                                        "Permission granted to read device SMS"
                                    else
                                        "Permission required to read incoming bank SMS",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (hasSmsPermission) Color(0xFF16A34A) else Color(0xFFD97706)
                                )
                            }

                            if (!hasSmsPermission) {
                                Button(
                                    onClick = { permissionLauncher.launch(Manifest.permission.READ_SMS) },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFD97706)),
                                    shape = RoundedCornerShape(10.dp),
                                    modifier = Modifier.testTag("settings_grant_sms_button")
                                ) {
                                    Text("Enable", style = MaterialTheme.typography.labelSmall)
                                }
                            } else {
                                OutlinedButton(
                                    onClick = onTriggerScan,
                                    shape = RoundedCornerShape(10.dp),
                                    modifier = Modifier.testTag("settings_rescan_button")
                                ) {
                                    Text("Scan", style = MaterialTheme.typography.labelSmall)
                                }
                            }
                        }

                        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Slate100)

                        // Box to fill number of days to track
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Number of Days to Track",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Slate900
                                )
                                Text(
                                    text = "${preferences.messageTrackingDays} days",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF0284C7)
                                )
                            }

                            var daysInput by remember(preferences.messageTrackingDays) {
                                mutableStateOf(preferences.messageTrackingDays.toString())
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                OutlinedTextField(
                                    value = daysInput,
                                    onValueChange = { newVal ->
                                        val digitsOnly = newVal.filter { it.isDigit() }.take(3)
                                        daysInput = digitsOnly
                                        digitsOnly.toIntOrNull()?.let { d ->
                                            if (d in 1..365) {
                                                onSetMessageTrackingDays(d)
                                            }
                                        }
                                    },
                                    label = { Text("Days to track") },
                                    placeholder = { Text("e.g. 15") },
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                    modifier = Modifier
                                        .weight(1f)
                                        .testTag("message_tracking_days_input"),
                                    shape = RoundedCornerShape(12.dp)
                                )

                                Button(
                                    onClick = {
                                        val d = daysInput.toIntOrNull() ?: preferences.messageTrackingDays
                                        onSetMessageTrackingDays(d.coerceIn(1, 365))
                                        onTriggerScan()
                                    },
                                    shape = RoundedCornerShape(12.dp),
                                    modifier = Modifier.testTag("apply_tracking_days_button")
                                ) {
                                    Text("Apply & Scan", style = MaterialTheme.typography.labelMedium)
                                }
                            }

                            Text(
                                text = "Specifies how many days into the past to scan for bank transactions.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate500
                            )

                            // Quick preset chips
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                listOf(7, 15, 30, 60, 90).forEach { presetDays ->
                                    val isSelected = preferences.messageTrackingDays == presetDays
                                    FilterChip(
                                        selected = isSelected,
                                        onClick = {
                                            daysInput = presetDays.toString()
                                            onSetMessageTrackingDays(presetDays)
                                            onTriggerScan()
                                        },
                                        label = { Text("$presetDays Days") },
                                        shape = RoundedCornerShape(8.dp),
                                        colors = FilterChipDefaults.filterChipColors(
                                            selectedContainerColor = Color(0xFFE0F2FE),
                                            selectedLabelColor = Color(0xFF0369A1)
                                        )
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // Section 3: Space Optimization & Typography / Display
        item {
            Text(
                text = "SPACE & DISPLAY DENSITY",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    // Space Optimization
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Box(
                                modifier = Modifier
                                    .size(32.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(Slate100),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Compress,
                                    contentDescription = null,
                                    tint = Slate700,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text(text = "Compact Space Optimization", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Slate900)
                                Text(text = "Tighter card padding & denser lists for phone screens", style = MaterialTheme.typography.bodySmall, color = Slate500)
                            }
                        }
                        Switch(
                            checked = preferences.compactSpacing,
                            onCheckedChange = { onToggleCompactSpacing() },
                            colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Slate900),
                            modifier = Modifier.testTag("toggle_compact_spacing_switch")
                        )
                    }

                    HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Slate100)

                    // Mask Balances (Privacy Mode)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Box(
                                modifier = Modifier
                                    .size(32.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(Slate100),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = if (preferences.maskBalances) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                    contentDescription = null,
                                    tint = Slate700,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text(text = "Mask Balances (Privacy Mode)", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Slate900)
                                Text(text = "Hide numbers with '••••••' in public", style = MaterialTheme.typography.bodySmall, color = Slate500)
                            }
                        }
                        Switch(
                            checked = preferences.maskBalances,
                            onCheckedChange = { onToggleMaskBalances() },
                            colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Slate900),
                            modifier = Modifier.testTag("toggle_mask_balances_switch")
                        )
                    }

                    HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = Slate100)

                    // Decimals display
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(text = "Show Decimal Places", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Slate900)
                            Text(
                                text = if (preferences.showDecimals) "e.g. ₹12,450.00" else "e.g. ₹12,450 (rounded)",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate500
                            )
                        }
                        Switch(
                            checked = preferences.showDecimals,
                            onCheckedChange = { onToggleDecimals() },
                            colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Slate900),
                            modifier = Modifier.testTag("toggle_decimals_switch")
                        )
                    }
                }
            }
        }

        // Section: Salary Cycle Configuration
        item {
            Text(
                text = "SALARY CYCLE & FINANCIAL PERIOD",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Salary Credit Date (Day of Month)",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = Slate900
                    )
                    Text(
                        text = "Your financial cycle calculates from the ${preferences.salaryCycleStartDay}th of this month to the ${if (preferences.salaryCycleStartDay == 1) 30 else preferences.salaryCycleStartDay - 1}th of next month.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    val presetDays = listOf(1, 5, 10, 15, 20, 25, 28, 30)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        presetDays.forEach { day ->
                            val isSelected = preferences.salaryCycleStartDay == day
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = if (isSelected) Slate900 else Slate100,
                                modifier = Modifier
                                    .clickable { onSetSalaryCycleDay(day) }
                                    .padding(vertical = 2.dp)
                            ) {
                                Text(
                                    text = if (day == 1) "1st (Calendar)" else "${day}th",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isSelected) Color.White else Slate700,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                                )
                            }
                        }
                    }
                }
            }
        }

        // Section 4: Currency Selection
        item {
            Text(
                text = "CURRENCY SYMBOL",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    currencies.forEach { (sym, name) ->
                        val isSelected = preferences.currencySymbol == sym
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .clickable { onSetCurrency(sym) }
                                .background(if (isSelected) Slate100 else Color.Transparent)
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    text = sym,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900,
                                    modifier = Modifier.width(36.dp)
                                )
                                Text(
                                    text = name,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (isSelected) Slate900 else Slate600,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                            if (isSelected) {
                                Surface(
                                    shape = CircleShape,
                                    color = Slate900,
                                    modifier = Modifier.size(8.dp)
                                ) {}
                            }
                        }
                    }
                }
            }
        }

        // Section 5: Data & Ledger Management
        item {
            Text(
                text = "DATA & LEDGER MANAGEMENT",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(text = "Purge Residual Dummy Entries", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = Slate900)
                            Text(text = "Removes any pre-loaded sample payroll, bistro, and test transactions", style = MaterialTheme.typography.bodySmall, color = Slate500)
                        }
                        Button(
                            onClick = onSeedSampleData,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626)),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.testTag("purge_dummy_entries_button")
                        ) {
                            Icon(imageVector = Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Purge", style = MaterialTheme.typography.labelSmall)
                        }
                    }

                    HorizontalDivider(color = Slate200, thickness = 0.8.dp)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(text = "Clear All Ledger Transactions", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = Slate900)
                            Text(text = "Reset transactions to a pristine zero-entry clean slate", style = MaterialTheme.typography.bodySmall, color = Slate500)
                        }
                        OutlinedButton(
                            onClick = onClearAllTransactions,
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Slate900),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.testTag("clear_all_transactions_button")
                        ) {
                            Text("Clear All", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }

        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Slate100.copy(alpha = 0.6f))
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    com.example.ui.components.CoinKeepHorizontalLogo(
                        iconSize = 34.dp,
                        isDark = false,
                        showTagline = true
                    )
                    Text(
                        text = "Version 3.0 • Smart Personal Ledger & Budget Tracker",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500
                    )
                }
            }
        }

        item {
            Spacer(modifier = Modifier.height(80.dp))
        }
    }
}

