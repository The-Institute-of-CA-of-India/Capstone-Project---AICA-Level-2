package com.example.ui.transactions

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
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
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.ui.dashboard.TransactionRowItem
import com.example.ui.dashboard.UiState
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseBorder
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeBorder
import com.example.ui.theme.PastelIncomeText
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
import com.example.ui.util.CurrencyUtils

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransactionsScreen(
    transactionsState: UiState<List<Transaction>>,
    accounts: List<Account>,
    onAddTransaction: (TransactionType) -> Unit,
    onEditTransaction: (Transaction) -> Unit,
    onDeleteTransaction: (Transaction) -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }
    var selectedTypeFilter by remember { mutableStateOf<TransactionType?>(null) }
    var transactionToDelete by remember { mutableStateOf<Transaction?>(null) }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        floatingActionButton = {
            FloatingActionButton(
                onClick = { onAddTransaction(TransactionType.EXPENSE) },
                containerColor = Slate900,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.testTag("fab_add_transaction")
            ) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Add Transaction")
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp)
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Header
            Text(
                text = "TRANSACTION LEDGER",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.2.sp
            )
            Text(
                text = "Entry by Entry Records",
                style = MaterialTheme.typography.titleLarge,
                color = Slate900,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Search Bar
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("Search by category, note, or account...", color = Slate400) },
                leadingIcon = {
                    Icon(imageVector = Icons.Default.Search, contentDescription = null, tint = Slate400)
                },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(imageVector = Icons.Default.Clear, contentDescription = "Clear", tint = Slate400)
                        }
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate200,
                    focusedContainerColor = Color.White,
                    unfocusedContainerColor = Color.White
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("transaction_search_field")
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Filter Pills (All, Expenses, Incomes, Transfers)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterPill(
                    label = "All Entries",
                    isSelected = selectedTypeFilter == null,
                    bg = Slate900,
                    textColor = Color.White,
                    onClick = { selectedTypeFilter = null }
                )
                FilterPill(
                    label = "Expenses",
                    isSelected = selectedTypeFilter == TransactionType.EXPENSE,
                    bg = PastelExpenseBg,
                    border = PastelExpenseBorder,
                    textColor = PastelExpenseText,
                    onClick = { selectedTypeFilter = TransactionType.EXPENSE }
                )
                FilterPill(
                    label = "Incomes",
                    isSelected = selectedTypeFilter == TransactionType.INCOME,
                    bg = PastelIncomeBg,
                    border = PastelIncomeBorder,
                    textColor = PastelIncomeText,
                    onClick = { selectedTypeFilter = TransactionType.INCOME }
                )
                FilterPill(
                    label = "Transfers",
                    isSelected = selectedTypeFilter == TransactionType.TRANSFER,
                    bg = PastelTransferBg,
                    border = PastelTransferBorder,
                    textColor = PastelTransferText,
                    onClick = { selectedTypeFilter = TransactionType.TRANSFER }
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // List of Transactions
            when (transactionsState) {
                is UiState.Loading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Slate900)
                    }
                }
                is UiState.Error -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(text = "Error loading ledger: ${transactionsState.message}", color = PastelExpenseText)
                    }
                }
                is UiState.Success -> {
                    val allTransactions = transactionsState.data

                    // Filter by type
                    val filteredByType = if (selectedTypeFilter != null) {
                        allTransactions.filter { it.type == selectedTypeFilter!!.name }
                    } else {
                        allTransactions
                    }

                    // Filter by search query
                    val finalFiltered = if (searchQuery.isNotBlank()) {
                        val q = searchQuery.lowercase()
                        filteredByType.filter {
                            it.category.lowercase().contains(q) ||
                                    it.note.lowercase().contains(q) ||
                                    it.amount.toString().contains(q)
                        }
                    } else {
                        filteredByType
                    }

                    if (finalFiltered.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(24.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    imageVector = Icons.Default.ReceiptLong,
                                    contentDescription = null,
                                    tint = Slate400,
                                    modifier = Modifier.size(48.dp)
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = if (searchQuery.isNotEmpty()) "No matching entries found" else "Ledger is currently empty",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = Slate700
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "Tap the + button to record a new transaction",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate500
                                )
                            }
                        }
                    } else {
                        Column {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Tap to edit • Long press (1s) to delete",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500
                                )
                                Text(
                                    text = "${finalFiltered.size} entries",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            LazyColumn(
                                verticalArrangement = Arrangement.spacedBy(10.dp),
                                modifier = Modifier.fillMaxSize()
                            ) {
                                items(finalFiltered, key = { it.id }) { tx ->
                                    TransactionRowItem(
                                        transaction = tx,
                                        onClick = { onEditTransaction(tx) },
                                        onLongClick = { transactionToDelete = tx }
                                    )
                                }
                                item {
                                    Spacer(modifier = Modifier.height(80.dp))
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete Confirmation Dialog (Triggered on 1-second long press)
    transactionToDelete?.let { tx ->
        AlertDialog(
            onDismissRequest = { transactionToDelete = null },
            title = {
                Text(
                    text = "Delete Ledger Entry?",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = "Remove ${tx.category} entry of ${CurrencyUtils.formatRupee(tx.amount)} and restore linked account balances?\n\n(This action was unlocked by holding the entry for 1 second to prevent accidental taps.)",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Slate700
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteTransaction(tx)
                        transactionToDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = PastelExpenseText),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Delete Entry")
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { transactionToDelete = null },
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Cancel", color = Slate700)
                }
            },
            containerColor = Color.White,
            shape = RoundedCornerShape(18.dp)
        )
    }
}

@Composable
private fun FilterPill(
    label: String,
    isSelected: Boolean,
    bg: Color,
    border: Color? = null,
    textColor: Color,
    onClick: () -> Unit
) {
    val currentBg = if (isSelected) bg else Slate100
    val currentText = if (isSelected) textColor else Slate600
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = currentBg,
        border = if (isSelected && border != null) androidx.compose.foundation.BorderStroke(1.dp, border) else null,
        modifier = Modifier
            .clickable { onClick() }
            .testTag("filter_pill_$label")
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = currentText,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp)
        )
    }
}
