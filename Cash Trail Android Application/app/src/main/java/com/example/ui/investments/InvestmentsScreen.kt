package com.example.ui.investments

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Savings
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.example.data.model.Investment
import com.example.data.model.InvestmentAction
import com.example.data.model.InvestmentAssetType
import com.example.ui.dashboard.UiState
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelInvestmentBg
import com.example.ui.theme.PastelInvestmentBorder
import com.example.ui.theme.PastelInvestmentText
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
import androidx.compose.ui.platform.LocalHapticFeedback
import com.example.ui.util.CurrencyUtils
import com.example.ui.util.onEntryClickAndLongPress1s

@Composable
fun InvestmentsScreen(
    investmentsState: UiState<List<Investment>>,
    onAddInvestment: () -> Unit,
    onEditInvestment: (Investment) -> Unit,
    onDeleteInvestment: (Investment) -> Unit
) {
    val haptic = LocalHapticFeedback.current
    var itemToDelete by remember { mutableStateOf<Investment?>(null) }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        floatingActionButton = {
            FloatingActionButton(
                onClick = onAddInvestment,
                containerColor = PastelInvestmentText,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.testTag("fab_add_investment")
            ) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Add Investment")
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 80.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                // Header
                Text(
                    text = "INVESTMENT PORTFOLIO",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp
                )
                Text(
                    text = "Capital Contribution & Redemptions",
                    style = MaterialTheme.typography.titleLarge,
                    color = Slate900,
                    fontWeight = FontWeight.Bold
                )
            }

            when (investmentsState) {
                is UiState.Loading -> {
                    item {
                        Box(modifier = Modifier.fillMaxWidth().height(150.dp), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(color = PastelInvestmentText)
                        }
                    }
                }
                is UiState.Error -> {
                    item {
                        Text(text = "Failed to load investments", color = PastelExpenseText)
                    }
                }
                is UiState.Success -> {
                    val investments = investmentsState.data

                    var totalContributed = 0.0
                    var totalWithdrawn = 0.0
                    val assetTotals = mutableMapOf<String, Double>()

                    for (inv in investments) {
                        if (inv.action == InvestmentAction.CONTRIBUTION.name) {
                            totalContributed += inv.amount
                            assetTotals[inv.assetType] = (assetTotals[inv.assetType] ?: 0.0) + inv.amount
                        } else {
                            totalWithdrawn += inv.amount
                            assetTotals[inv.assetType] = (assetTotals[inv.assetType] ?: 0.0) - inv.amount
                        }
                    }
                    val netCapital = (totalContributed - totalWithdrawn).coerceAtLeast(0.0)

                    // Hero Net Capital Deployed Card
                    item {
                        Surface(
                            shape = RoundedCornerShape(22.dp),
                            color = PastelInvestmentBg,
                            border = androidx.compose.foundation.BorderStroke(1.dp, PastelInvestmentBorder),
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("investments_hero_card")
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Text(
                                    text = "NET CAPITAL DEPLOYED",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PastelInvestmentText,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 1.sp
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = CurrencyUtils.formatRupee(netCapital),
                                    style = MaterialTheme.typography.headlineLarge,
                                    color = PastelInvestmentText,
                                    fontWeight = FontWeight.Bold
                                )

                                Spacer(modifier = Modifier.height(16.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text(text = "Total Invested", style = MaterialTheme.typography.bodySmall, color = Slate600)
                                        Text(
                                            text = CurrencyUtils.formatRupee(totalContributed),
                                            style = MaterialTheme.typography.titleSmall,
                                            color = PastelInvestmentText,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                    Column {
                                        Text(text = "Total Withdrawn", style = MaterialTheme.typography.bodySmall, color = Slate600)
                                        Text(
                                            text = CurrencyUtils.formatRupee(totalWithdrawn),
                                            style = MaterialTheme.typography.titleSmall,
                                            color = PastelTransferText,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // Asset Class Breakdown Chips
                    if (assetTotals.isNotEmpty()) {
                        item {
                            Text(
                                text = "ASSET ALLOCATION",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate500,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                assetTotals.entries.take(4).forEach { (assetType, amount) ->
                                    val assetName = try {
                                        InvestmentAssetType.valueOf(assetType).displayName
                                    } catch (e: Exception) {
                                        assetType
                                    }
                                    Card(
                                        shape = RoundedCornerShape(12.dp),
                                        colors = CardDefaults.cardColors(containerColor = Color.White),
                                        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200)
                                    ) {
                                        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                                            Text(text = assetName, style = MaterialTheme.typography.labelSmall, color = Slate600)
                                            Text(
                                                text = CurrencyUtils.formatRupee(amount.coerceAtLeast(0.0)),
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = Slate900,
                                                fontWeight = FontWeight.Bold
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Ledger items
                    item {
                        Text(
                            text = "INVESTMENT LEDGER ENTRIES",
                            style = MaterialTheme.typography.labelSmall,
                            color = Slate500,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp
                        )
                    }

                    if (investments.isEmpty()) {
                        item {
                            Card(
                                shape = RoundedCornerShape(16.dp),
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Column(
                                    modifier = Modifier.padding(24.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Icon(imageVector = Icons.Default.Savings, contentDescription = null, tint = Slate400, modifier = Modifier.size(40.dp))
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text("No investment records yet", style = MaterialTheme.typography.titleSmall, color = Slate700)
                                    Text("Log mutual funds, stocks, fixed deposits or gold deposits using the + button.", style = MaterialTheme.typography.bodySmall, color = Slate500)
                                }
                            }
                        }
                    } else {
                        item {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Tap entry to edit • Long press (1s) to delete",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500
                                )
                                Text(
                                    text = "${investments.size} records",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                        items(investments, key = { it.id }) { inv ->
                            val isContribution = inv.action == InvestmentAction.CONTRIBUTION.name
                            Card(
                                shape = RoundedCornerShape(14.dp),
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag("investment_item_${inv.id}")
                                    .onEntryClickAndLongPress1s(
                                        hapticFeedback = haptic,
                                        onClick = { onEditInvestment(inv) },
                                        onLongPress1s = { itemToDelete = inv }
                                    )
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(14.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                                        Box(
                                            modifier = Modifier
                                                .size(36.dp)
                                                .clip(CircleShape)
                                                .background(if (isContribution) PastelInvestmentBg else PastelTransferBg),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Icon(
                                                imageVector = if (isContribution) Icons.Default.TrendingUp else Icons.Default.TrendingDown,
                                                contentDescription = null,
                                                tint = if (isContribution) PastelInvestmentText else PastelTransferText,
                                                modifier = Modifier.size(18.dp)
                                            )
                                        }
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column {
                                            Text(
                                                text = inv.assetName,
                                                style = MaterialTheme.typography.titleSmall,
                                                color = Slate700,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                            val typeLabel = try {
                                                InvestmentAssetType.valueOf(inv.assetType).displayName
                                            } catch (e: Exception) {
                                                inv.assetType
                                            }
                                            Text(
                                                text = "$typeLabel • ${if (isContribution) "Deposit" else "Redemption"}",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = Slate500
                                            )
                                        }
                                    }

                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(
                                            text = "${if (isContribution) "+ " else "- "}${CurrencyUtils.formatRupee(inv.amount)}",
                                            style = MaterialTheme.typography.titleSmall,
                                            color = if (isContribution) PastelInvestmentText else PastelTransferText,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = CurrencyUtils.formatDate(inv.date ?: inv.createdAt),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate400
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(80.dp))
            }
        }
    }

    // Delete confirmation dialog
    itemToDelete?.let { inv ->
        AlertDialog(
            onDismissRequest = { itemToDelete = null },
            title = {
                Text(text = "Delete Investment Record?", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            },
            text = {
                Text(
                    text = "Remove ${inv.assetName} entry of ${CurrencyUtils.formatRupee(inv.amount)} from your investment ledger?\n\n(This action was unlocked by holding the entry for 1 second to prevent accidental taps.)",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Slate700
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteInvestment(inv)
                        itemToDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = PastelExpenseText),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Delete Entry")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { itemToDelete = null }, shape = RoundedCornerShape(10.dp)) {
                    Text("Cancel", color = Slate700)
                }
            },
            containerColor = Color.White,
            shape = RoundedCornerShape(18.dp)
        )
    }
}
