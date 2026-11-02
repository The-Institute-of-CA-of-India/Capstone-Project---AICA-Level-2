package com.example.ui.accounts

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CompareArrows
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Wallet
import com.example.ui.components.AddAccountDialog
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.SuggestedAccount
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.ui.components.SuggestedAccountsSection
import com.example.ui.dashboard.TransactionRowItem
import com.example.ui.dashboard.UiState
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelTransferBg
import com.example.ui.theme.PastelTransferBorder
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900
import com.example.ui.util.CreditCardStatementCalculator
import com.example.ui.util.CurrencyUtils

@Composable
fun AccountsScreen(
    accountsState: UiState<List<Account>>,
    transactionsState: UiState<List<Transaction>>,
    suggestedAccounts: List<SuggestedAccount> = emptyList(),
    onAddAccount: () -> Unit,
    onAddSuggestedAccount: (SuggestedAccount) -> Unit = {},
    onDismissSuggestedAccount: (String) -> Unit = {},
    onOpenTransferSheet: () -> Unit,
    onDeleteAccount: (String) -> Unit,
    onUpdateAccount: (Account) -> Unit = {}
) {
    val allTransactions = (transactionsState as? UiState.Success)?.data ?: emptyList()
    var accountToDelete by remember { mutableStateOf<Account?>(null) }
    var accountToEdit by remember { mutableStateOf<Account?>(null) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 16.dp),
        contentPadding = PaddingValues(top = 16.dp, bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "ACCOUNTS & MODES OF CASH",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate500,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp
                    )
                    Text(
                        text = "Bank, Wallets, Cards & Cash",
                        style = MaterialTheme.typography.titleLarge,
                        color = Slate900,
                        fontWeight = FontWeight.Bold
                    )
                }

                Button(
                    onClick = onAddAccount,
                    colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.testTag("add_account_top_button")
                ) {
                    Icon(imageVector = Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Add", style = MaterialTheme.typography.labelMedium)
                }
            }
        }

        // Suggested Accounts Section from Message Tracking
        if (suggestedAccounts.isNotEmpty()) {
            item {
                SuggestedAccountsSection(
                    suggestions = suggestedAccounts,
                    onSelectSuggestion = onAddSuggestedAccount,
                    onDismissSuggestion = onDismissSuggestedAccount
                )
            }
        }

        // Journal Inter-Account Transfer Banner Card
        item {
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = PastelTransferBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, PastelTransferBorder),
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onOpenTransferSheet() }
                    .testTag("trigger_transfer_banner")
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(42.dp)
                                .clip(CircleShape)
                                .background(PastelTransferBorder),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.CompareArrows,
                                contentDescription = null,
                                tint = PastelTransferText,
                                modifier = Modifier.size(24.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(14.dp))
                        Column {
                            Text(
                                text = "Inter-Account Journal Transfer",
                                style = MaterialTheme.typography.titleSmall,
                                color = PastelTransferText,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "Move funds between accounts or settle credit card bills seamlessly",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate600
                            )
                        }
                    }

                    Button(
                        onClick = onOpenTransferSheet,
                        colors = ButtonDefaults.buttonColors(containerColor = PastelTransferText),
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text("Transfer", style = MaterialTheme.typography.labelSmall, color = Color.White)
                    }
                }
            }
        }

        // Grouped Accounts List
        when (accountsState) {
            is UiState.Loading -> {
                item {
                    Box(modifier = Modifier.fillMaxWidth().height(150.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Slate900)
                    }
                }
            }
            is UiState.Error -> {
                item {
                    Text(text = "Failed to load accounts", color = PastelExpenseText)
                }
            }
            is UiState.Success -> {
                val accounts = accountsState.data
                AccountType.entries.forEach { type ->
                    val typeAccounts = accounts.filter { it.type == type.name }
                    if (typeAccounts.isNotEmpty()) {
                        item {
                            Text(
                                text = type.displayName.uppercase(),
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate500,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp
                            )
                        }
                        items(typeAccounts, key = { it.id }) { acc ->
                            AccountDetailCard(
                                account = acc,
                                transactions = allTransactions,
                                onEdit = { accountToEdit = acc },
                                onDelete = { accountToDelete = acc }
                            )
                        }
                    }
                }
            }
        }

        // Recent Journal Transfers Section
        item {
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "RECENT INTER-ACCOUNT TRANSFERS",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
        }

        when (transactionsState) {
            is UiState.Loading -> {
                item {
                    Box(modifier = Modifier.fillMaxWidth().height(80.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Slate900, modifier = Modifier.size(20.dp))
                    }
                }
            }
            is UiState.Error -> {}
            is UiState.Success -> {
                val transferTransactions = transactionsState.data.filter { it.type == TransactionType.TRANSFER.name }.take(5)
                if (transferTransactions.isEmpty()) {
                    item {
                        Card(
                            shape = RoundedCornerShape(14.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = "No inter-account transfers made yet.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate500,
                                modifier = Modifier.padding(16.dp)
                            )
                        }
                    }
                } else {
                    items(transferTransactions, key = { it.id }) { tx ->
                        TransactionRowItem(transaction = tx)
                    }
                }
            }
        }

        item {
            Spacer(modifier = Modifier.height(80.dp))
        }
    }

    // Account Delete Dialog
    accountToDelete?.let { acc ->
        AlertDialog(
            onDismissRequest = { accountToDelete = null },
            title = {
                Text(
                    text = "Delete Account '${acc.name}'?",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = "This will remove the account record. Existing transactions previously linked will remain in your transaction history.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Slate700
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteAccount(acc.id)
                        accountToDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = PastelExpenseText),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { accountToDelete = null },
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Cancel", color = Slate700)
                }
            },
            containerColor = Color.White,
            shape = RoundedCornerShape(18.dp)
        )
    }

    // Account Edit Dialog
    accountToEdit?.let { acc ->
        AddAccountDialog(
            existingAccount = acc,
            onDismiss = { accountToEdit = null },
            onSubmit = { name, type, bal, limit, colorHex, institution, notes, statementDay, dueDay ->
                onUpdateAccount(
                    acc.copy(
                        name = name,
                        type = type.name,
                        balance = bal,
                        creditLimit = limit,
                        colorHex = colorHex,
                        institution = institution,
                        notes = notes,
                        statementDay = statementDay,
                        dueDay = dueDay
                    )
                )
                accountToEdit = null
            }
        )
    }
}

@Composable
fun AccountDetailCard(
    account: Account,
    transactions: List<Transaction> = emptyList(),
    onEdit: () -> Unit = {},
    onDelete: () -> Unit
) {
    val chipColor = try {
        Color(android.graphics.Color.parseColor(account.colorHex))
    } catch (e: Exception) {
        Slate700
    }

    val icon = when (account.type) {
        AccountType.BANK.name -> Icons.Default.AccountBalance
        AccountType.CREDIT_CARD.name -> Icons.Default.CreditCard
        AccountType.DIGITAL_WALLET.name -> Icons.Default.Wallet
        AccountType.CASH.name -> Icons.Default.Payments
        AccountType.PERSONAL.name -> Icons.Default.Person
        else -> Icons.Default.AccountBalance
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .fillMaxWidth()
            .testTag("account_detail_card_${account.id}")
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(chipColor.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(imageVector = icon, contentDescription = null, tint = chipColor, modifier = Modifier.size(20.dp))
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = account.name,
                            style = MaterialTheme.typography.titleSmall,
                            color = Slate900,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = if (account.institution.isNotBlank()) account.institution else account.type,
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = CurrencyUtils.formatRupee(account.balance),
                            style = MaterialTheme.typography.titleMedium,
                            color = if (account.type == AccountType.CREDIT_CARD.name) PastelExpenseText else Slate900,
                            fontWeight = FontWeight.Bold
                        )
                        if (account.type == AccountType.CREDIT_CARD.name) {
                            Text(
                                text = "Total O/S",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate400,
                                fontSize = 10.sp
                            )
                        }
                        if (account.type == AccountType.CREDIT_CARD.name && account.creditLimit > 0) {
                            Text(
                                text = "Limit: ${CurrencyUtils.formatRupee(account.creditLimit)}",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate400
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    IconButton(
                        onClick = onEdit,
                        modifier = Modifier.testTag("account_edit_button_${account.id}")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Edit,
                            contentDescription = "Edit account",
                            tint = Slate600,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    IconButton(onClick = onDelete) {
                        Icon(
                            imageVector = Icons.Default.Delete,
                            contentDescription = "Delete account",
                            tint = Slate400,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            // Credit utilization bar for credit cards
            if (account.type == AccountType.CREDIT_CARD.name && account.creditLimit > 0) {
                Spacer(modifier = Modifier.height(12.dp))
                val ratio = (account.balance / account.creditLimit).toFloat().coerceIn(0f, 1f)
                LinearProgressIndicator(
                    progress = { ratio },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp)),
                    color = if (ratio > 0.5f) PastelExpenseText else PastelTransferText,
                    trackColor = Slate100
                )
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Utilization: ${(ratio * 100).toInt()}%",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate500
                    )
                    Text(
                        text = "Available: ${CurrencyUtils.formatRupee((account.creditLimit - account.balance).coerceAtLeast(0.0))}",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate500
                    )
                }
            }

            // Credit Card Statement & Due Date section
            val stmtDay = account.statementDay
            val dueDay = account.dueDay
            if (account.type == AccountType.CREDIT_CARD.name && (stmtDay > 0 || dueDay > 0)) {
                val stmtSummary = CreditCardStatementCalculator.calculateStatementSummary(account, transactions)
                Spacer(modifier = Modifier.height(10.dp))
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Slate100,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                if (stmtDay > 0) {
                                    Text(
                                        text = "Statement Date: ${stmtDay}th monthly",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Slate600,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                                if (dueDay > 0) {
                                    Text(
                                        text = "Payment Due: ${dueDay}th monthly",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Slate900,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }

                            if (dueDay > 0) {
                                val diff = stmtSummary.daysUntilDue
                                val (badgeText, badgeBg, badgeTextCol) = when {
                                    stmtSummary.isOverdue -> Triple("Overdue!", Color(0xFFFFE4E6), Color(0xFFE11D48))
                                    diff == 0 -> Triple("Due Today", Color(0xFFFFE4E6), Color(0xFFE11D48))
                                    diff in 1..3 -> Triple("Due in $diff days!", Color(0xFFFFE4E6), Color(0xFFE11D48))
                                    diff in 4..7 -> Triple("Due in $diff days", Color(0xFFFEF3C7), Color(0xFFD97706))
                                    else -> Triple("Due in $diff days", Color(0xFFDCFCE7), Color(0xFF16A34A))
                                }

                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = badgeBg,
                                    modifier = Modifier.padding(start = 8.dp)
                                ) {
                                    Text(
                                        text = badgeText,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = badgeTextCol,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }

                        // Outstanding Breakdown (Statement O/S vs Unbilled O/S)
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(Color.White.copy(alpha = 0.85f), RoundedCornerShape(8.dp))
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    text = "Statement Due",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = CurrencyUtils.formatRupee(stmtSummary.statementDueAmount),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (stmtSummary.statementDueAmount > 0) PastelExpenseText else Slate900,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    text = "Unbilled O/S",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = CurrencyUtils.formatRupee(stmtSummary.unbilledAmount),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = Slate700,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    text = "Total O/S",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = CurrencyUtils.formatRupee(stmtSummary.totalOutstanding),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = Slate900,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
