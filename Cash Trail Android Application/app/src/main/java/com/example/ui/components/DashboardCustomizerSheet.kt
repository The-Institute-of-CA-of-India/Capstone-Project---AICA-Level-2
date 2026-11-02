package com.example.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Category
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CompareArrows
import androidx.compose.material.icons.filled.NorthEast
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Savings
import androidx.compose.material.icons.filled.SouthWest
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.settings.DashboardWidgetConfig
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseBorder
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeBorder
import com.example.ui.theme.PastelIncomeText
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardCustomizerSheet(
    config: DashboardWidgetConfig,
    onDismiss: () -> Unit,
    onSave: (DashboardWidgetConfig) -> Unit,
    onReset: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var currentConfig by remember { mutableStateOf(config) }

    fun moveWidget(widgetId: String, up: Boolean) {
        val currentList = currentConfig.widgetOrder.toMutableList()
        val index = currentList.indexOf(widgetId)
        if (index != -1) {
            val targetIndex = if (up) index - 1 else index + 1
            if (targetIndex in 0 until currentList.size) {
                currentList.removeAt(index)
                currentList.add(targetIndex, widgetId)
                currentConfig = currentConfig.copy(widgetOrder = currentList)
            }
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
        modifier = Modifier.testTag("dashboard_customizer_sheet")
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(Slate900),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Tune,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Dashboard Customizer",
                            style = MaterialTheme.typography.titleLarge,
                            color = Slate900,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Toggle widgets, adjust sizes & reorder items",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                IconButton(onClick = onDismiss) {
                    Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Slate600)
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // SECTION 1: BUTTON SHORTCUTS CUSTOMIZER
            Text(
                text = "ACTION BUTTON SHORTCUTS",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.2.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Card(
                shape = RoundedCornerShape(14.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        text = "Customize Shortcuts Bar",
                        style = MaterialTheme.typography.titleSmall,
                        color = Slate900,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Toggle which one-tap entry buttons appear at the top of your dashboard",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        FancyShortcutToggle(
                            label = "+ Expense",
                            icon = Icons.Default.NorthEast,
                            checked = currentConfig.enableExpenseShortcut,
                            badgeBg = PastelExpenseBg,
                            badgeBorder = PastelExpenseBorder,
                            badgeText = PastelExpenseText,
                            onToggle = { currentConfig = currentConfig.copy(enableExpenseShortcut = it) }
                        )
                        FancyShortcutToggle(
                            label = "+ Income",
                            icon = Icons.Default.SouthWest,
                            checked = currentConfig.enableIncomeShortcut,
                            badgeBg = PastelIncomeBg,
                            badgeBorder = PastelIncomeBorder,
                            badgeText = PastelIncomeText,
                            onToggle = { currentConfig = currentConfig.copy(enableIncomeShortcut = it) }
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        FancyShortcutToggle(
                            label = "⇄ Transfer",
                            icon = Icons.Default.CompareArrows,
                            checked = currentConfig.enableTransferShortcut,
                            badgeBg = PastelTransferBg,
                            badgeBorder = PastelTransferBorder,
                            badgeText = PastelTransferText,
                            onToggle = { currentConfig = currentConfig.copy(enableTransferShortcut = it) }
                        )
                        FancyShortcutToggle(
                            label = "+ Invest",
                            icon = Icons.Default.TrendingUp,
                            checked = currentConfig.enableInvestmentShortcut,
                            badgeBg = PastelInvestmentBg,
                            badgeBorder = PastelInvestmentBorder,
                            badgeText = PastelInvestmentText,
                            onToggle = { currentConfig = currentConfig.copy(enableInvestmentShortcut = it) }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // SECTION 2: WIDGETS, SIZES & REORDERING
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "WIDGETS & SIZING CONTROLS",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp
                )
                Text(
                    text = "Use ▲▼ to reorder",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500
                )
            }
            Spacer(modifier = Modifier.height(8.dp))

            // Render widgets in their active order
            currentConfig.widgetOrder.forEachIndexed { index, widgetId ->
                val isFirst = index == 0
                val isLast = index == currentConfig.widgetOrder.lastIndex

                when (widgetId) {
                    DashboardWidgetConfig.WIDGET_NET_WORTH -> {
                        ReorderableWidgetCard(
                            title = "Net Worth & Liquid Cash",
                            subtitle = "Hero balance with liquid cash, investments & debt",
                            icon = Icons.Default.AccountBalance,
                            checked = currentConfig.showNetWorthHero,
                            onCheckedChange = { currentConfig = currentConfig.copy(showNetWorthHero = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Text(text = "Card Size:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SizeSelectorPill(
                                    label = "Comfortable (Full Stats)",
                                    isSelected = currentConfig.netWorthHeroSize == "COMFORTABLE",
                                    onClick = { currentConfig = currentConfig.copy(netWorthHeroSize = "COMFORTABLE") }
                                )
                                SizeSelectorPill(
                                    label = "Compact (Space Saver)",
                                    isSelected = currentConfig.netWorthHeroSize == "COMPACT",
                                    onClick = { currentConfig = currentConfig.copy(netWorthHeroSize = "COMPACT") }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_CASH_FLOW -> {
                        ReorderableWidgetCard(
                            title = "Monthly Cash Flow",
                            subtitle = "Income vs expense inflow/outflow tracker",
                            icon = Icons.Default.CompareArrows,
                            checked = currentConfig.showMonthlyCashFlow,
                            onCheckedChange = { currentConfig = currentConfig.copy(showMonthlyCashFlow = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Text(text = "Display Style:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SizeSelectorPill(
                                    label = "Side-by-Side Cards",
                                    isSelected = currentConfig.cashFlowStyle == "CARDS",
                                    onClick = { currentConfig = currentConfig.copy(cashFlowStyle = "CARDS") }
                                )
                                SizeSelectorPill(
                                    label = "Compact Row",
                                    isSelected = currentConfig.cashFlowStyle == "COMPACT",
                                    onClick = { currentConfig = currentConfig.copy(cashFlowStyle = "COMPACT") }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_QUICK_ACTIONS -> {
                        ReorderableWidgetCard(
                            title = "Quick Action Shortcuts Bar",
                            subtitle = "One-tap buttons to record entries quickly",
                            icon = Icons.Default.Tune,
                            checked = currentConfig.showQuickActions,
                            onCheckedChange = { currentConfig = currentConfig.copy(showQuickActions = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_ACCOUNTS -> {
                        ReorderableWidgetCard(
                            title = "Accounts & Cash Carousel",
                            subtitle = "Bank accounts, cards, UPI wallets & cash modes",
                            icon = Icons.Default.AccountBalance,
                            checked = currentConfig.showAccounts,
                            onCheckedChange = { currentConfig = currentConfig.copy(showAccounts = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Text(text = "View Mode:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SizeSelectorPill(
                                    label = "Horizontal Carousel",
                                    isSelected = currentConfig.accountsCarouselStyle == "CAROUSEL",
                                    onClick = { currentConfig = currentConfig.copy(accountsCarouselStyle = "CAROUSEL") }
                                )
                                SizeSelectorPill(
                                    label = "Compact Mini-Cards",
                                    isSelected = currentConfig.accountsCarouselStyle == "COMPACT_LIST",
                                    onClick = { currentConfig = currentConfig.copy(accountsCarouselStyle = "COMPACT_LIST") }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_CATEGORIES -> {
                        ReorderableWidgetCard(
                            title = "Top Expense Categories",
                            subtitle = "Visual distribution of spending by category",
                            icon = Icons.Default.Category,
                            checked = currentConfig.showCategoryBreakdown,
                            onCheckedChange = { currentConfig = currentConfig.copy(showCategoryBreakdown = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Text(text = "Layout Density:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SizeSelectorPill(
                                    label = "Detailed Bars",
                                    isSelected = currentConfig.categoryBreakdownSize == "STANDARD",
                                    onClick = { currentConfig = currentConfig.copy(categoryBreakdownSize = "STANDARD") }
                                )
                                SizeSelectorPill(
                                    label = "Compact Chips",
                                    isSelected = currentConfig.categoryBreakdownSize == "COMPACT",
                                    onClick = { currentConfig = currentConfig.copy(categoryBreakdownSize = "COMPACT") }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_INVESTMENT -> {
                        ReorderableWidgetCard(
                            title = "Investment Portfolio Quick Summary",
                            subtitle = "Net capital deployed & contributions summary",
                            icon = Icons.Default.Savings,
                            checked = currentConfig.showInvestmentSummary,
                            onCheckedChange = { currentConfig = currentConfig.copy(showInvestmentSummary = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Text(text = "Card Size:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SizeSelectorPill(
                                    label = "Standard Card",
                                    isSelected = currentConfig.investmentCardSize == "STANDARD",
                                    onClick = { currentConfig = currentConfig.copy(investmentCardSize = "STANDARD") }
                                )
                                SizeSelectorPill(
                                    label = "Compact Strip",
                                    isSelected = currentConfig.investmentCardSize == "COMPACT",
                                    onClick = { currentConfig = currentConfig.copy(investmentCardSize = "COMPACT") }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    DashboardWidgetConfig.WIDGET_TRANSACTIONS -> {
                        ReorderableWidgetCard(
                            title = "Recent Transactions Feed",
                            subtitle = "Latest ledger entries with pastel mental tags",
                            icon = Icons.Default.ReceiptLong,
                            checked = currentConfig.showRecentTransactions,
                            onCheckedChange = { currentConfig = currentConfig.copy(showRecentTransactions = it) },
                            canMoveUp = !isFirst,
                            canMoveDown = !isLast,
                            onMoveUp = { moveWidget(widgetId, true) },
                            onMoveDown = { moveWidget(widgetId, false) }
                        ) {
                            Column {
                                Text(text = "Number of Items to Show:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                                Spacer(modifier = Modifier.height(6.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    listOf(3, 5, 8, 12).forEach { count ->
                                        SizeSelectorPill(
                                            label = "$count items",
                                            isSelected = currentConfig.recentTransactionsCount == count,
                                            onClick = { currentConfig = currentConfig.copy(recentTransactionsCount = count) }
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(10.dp))
                                Text(text = "Row Size:", style = MaterialTheme.typography.labelSmall, color = Slate600)
                                Spacer(modifier = Modifier.height(6.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    SizeSelectorPill(
                                        label = "Comfortable",
                                        isSelected = currentConfig.transactionsCardSize == "COMFORTABLE",
                                        onClick = { currentConfig = currentConfig.copy(transactionsCardSize = "COMFORTABLE") }
                                    )
                                    SizeSelectorPill(
                                        label = "Compact Spacing",
                                        isSelected = currentConfig.transactionsCardSize == "COMPACT",
                                        onClick = { currentConfig = currentConfig.copy(transactionsCardSize = "COMPACT") }
                                    )
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Action Buttons (Reset + Apply)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        onReset()
                        onDismiss()
                    },
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(imageVector = Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Reset Defaults", color = Slate700)
                }

                Button(
                    onClick = {
                        onSave(currentConfig)
                        onDismiss()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Apply Layout")
                }
            }

            Spacer(modifier = Modifier.height(30.dp))
        }
    }
}

@Composable
private fun ReorderableWidgetCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    content: @Composable (() -> Unit)? = null
) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = if (checked) Color.White else Slate100),
        border = androidx.compose.foundation.BorderStroke(1.dp, if (checked) Slate200 else Color.Transparent),
        modifier = Modifier
            .fillMaxWidth()
            .animateContentSize()
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
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
                            .background(if (checked) Slate900 else Slate200),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = icon,
                            contentDescription = null,
                            tint = if (checked) Color.White else Slate500,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = title,
                            style = MaterialTheme.typography.titleSmall,
                            color = Slate900,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = subtitle,
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Reorder arrows
                    IconButton(
                        onClick = onMoveUp,
                        enabled = canMoveUp,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowUpward,
                            contentDescription = "Move Up",
                            tint = if (canMoveUp) Slate700 else Slate200,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                    IconButton(
                        onClick = onMoveDown,
                        enabled = canMoveDown,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowDownward,
                            contentDescription = "Move Down",
                            tint = if (canMoveDown) Slate700 else Slate200,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    Switch(
                        checked = checked,
                        onCheckedChange = onCheckedChange,
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color.White,
                            checkedTrackColor = Slate900
                        )
                    )
                }
            }

            AnimatedVisibility(visible = checked && content != null) {
                Column {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp), color = Slate100)
                    content?.invoke()
                }
            }
        }
    }
}

@Composable
private fun SizeSelectorPill(
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = if (isSelected) Slate900 else Slate100,
        border = androidx.compose.foundation.BorderStroke(1.dp, if (isSelected) Slate900 else Slate200),
        modifier = Modifier.clickable { onClick() }
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = if (isSelected) Color.White else Slate700,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
        )
    }
}

@Composable
private fun FancyShortcutToggle(
    label: String,
    icon: ImageVector,
    checked: Boolean,
    badgeBg: Color,
    badgeBorder: Color,
    badgeText: Color,
    onToggle: (Boolean) -> Unit
) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = if (checked) badgeBg else Slate100,
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            if (checked) badgeBorder else Slate200
        ),
        modifier = Modifier
            .clickable { onToggle(!checked) }
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (checked) badgeText else Slate400,
                modifier = Modifier.size(14.dp)
            )
            Spacer(modifier = Modifier.width(5.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = if (checked) badgeText else Slate500,
                fontWeight = if (checked) FontWeight.Bold else FontWeight.Medium
            )
        }
    }
}
