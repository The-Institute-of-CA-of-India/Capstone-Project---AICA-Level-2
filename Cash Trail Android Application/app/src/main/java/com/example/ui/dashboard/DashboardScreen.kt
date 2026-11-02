package com.example.ui.dashboard

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CompareArrows
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.NorthEast
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Savings
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.SouthWest
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.ui.settings.AppPreferences
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
import com.example.ui.theme.PastelAmberBg
import com.example.ui.theme.PastelAmberBorder
import com.example.ui.theme.PastelAmberText
import com.example.ui.theme.PastelTransferBg
import com.example.ui.theme.PastelTransferBorder
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import com.example.ui.theme.Slate800
import com.example.ui.theme.Slate900
import com.example.ui.util.CurrencyUtils
import com.example.ui.util.CreditCardStatementCalculator
import com.example.ui.util.InvoiceUtils
import com.example.ui.util.onEntryClickAndLongPress1s
import com.example.ui.util.onEntryClickAndLongPress2s

@Composable
fun DashboardScreen(
    summary: FinancialSummary,
    preferences: AppPreferences,
    accountsState: UiState<List<Account>>,
    transactionsState: UiState<List<Transaction>>,
    categoryBreakdown: List<CategoryBreakdownItem>,
    selectedPeriod: DashboardPeriod,
    periodDateRange: PeriodDateRange,
    onSelectPeriod: (DashboardPeriod) -> Unit,
    onOpenTransactionSheet: (TransactionType) -> Unit,
    onOpenInvestmentSheet: () -> Unit,
    onOpenAddAccountDialog: () -> Unit,
    onOpenCustomizer: () -> Unit,
    onNavigateToTransactions: () -> Unit,
    onNavigateToAccounts: () -> Unit,
    onNavigateToInvestments: () -> Unit,
    onEditTransaction: ((Transaction) -> Unit)? = null,
    onDeleteTransaction: ((Transaction) -> Unit)? = null
) {
    val cfg = preferences.widgetConfig
    val itemSpacing = if (preferences.compactSpacing) 10.dp else 14.dp
    var showPeriodDropdown by remember { mutableStateOf(false) }
    var transactionToDelete by remember { mutableStateOf<Transaction?>(null) }
    var isCreditCardsExpanded by remember { mutableStateOf(false) }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        floatingActionButton = {
            FloatingActionButton(
                onClick = {
                    val defaultType = try {
                        TransactionType.valueOf(preferences.defaultEntryType)
                    } catch (e: Exception) {
                        TransactionType.EXPENSE
                    }
                    onOpenTransactionSheet(defaultType)
                },
                containerColor = Slate900,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.testTag("fab_dashboard_add_transaction")
            ) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Add Transaction")
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp)
                .animateContentSize(animationSpec = spring(stiffness = Spring.StiffnessMediumLow)),
            contentPadding = PaddingValues(top = 16.dp, bottom = 80.dp),
            verticalArrangement = Arrangement.spacedBy(itemSpacing)
        ) {
            // Sticky/top header with Custom Period Dropdown
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "FINANCIAL DASHBOARD",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp
                )

                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = Slate100,
                    modifier = Modifier
                        .clickable { onOpenCustomizer() }
                        .testTag("dashboard_edit_widgets_chip")
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Tune,
                            contentDescription = null,
                            tint = Slate700,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Customize",
                            style = MaterialTheme.typography.labelSmall,
                            color = Slate700,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Period Selector Dropdown Pill
            Box(modifier = Modifier.fillMaxWidth()) {
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = Color.White,
                    border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showPeriodDropdown = true }
                        .testTag("dashboard_period_dropdown_button")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.weight(1f)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(34.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFFE8EFEA)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.CalendarMonth,
                                    contentDescription = null,
                                    tint = Color(0xFF2E654E),
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(10.dp))
                            Column(modifier = Modifier.weight(1f, fill = false)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = selectedPeriod.title,
                                        style = MaterialTheme.typography.titleSmall,
                                        color = Slate900,
                                        fontWeight = FontWeight.Bold,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Icon(
                                        imageVector = Icons.Default.ArrowDropDown,
                                        contentDescription = "Open period selector",
                                        tint = Slate600,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                                Text(
                                    text = periodDateRange.formattedLabel,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate500,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }

                        Spacer(modifier = Modifier.width(8.dp))

                        // Right badge for period type (shows days until pay count in salary cycle box)
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = if (selectedPeriod == DashboardPeriod.SALARY_CYCLE) PastelIncomeBg else Slate100
                        ) {
                            val badgeText = if (selectedPeriod == DashboardPeriod.SALARY_CYCLE) {
                                val days = periodDateRange.daysRemaining
                                when {
                                    days <= 0 -> "Payday today!"
                                    days == 1 -> "1 day until pay"
                                    else -> "$days days until pay"
                                }
                            } else {
                                selectedPeriod.shortLabel
                            }
                            Text(
                                text = badgeText,
                                style = MaterialTheme.typography.labelSmall,
                                color = if (selectedPeriod == DashboardPeriod.SALARY_CYCLE) PastelIncomeText else Slate700,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1,
                                softWrap = false,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                }

                // Dropdown Menu options
                DropdownMenu(
                    expanded = showPeriodDropdown,
                    onDismissRequest = { showPeriodDropdown = false }
                ) {
                    DashboardPeriod.entries.forEach { period ->
                        val isSelected = selectedPeriod == period
                        DropdownMenuItem(
                            text = {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = period.title,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            color = if (isSelected) Slate900 else Slate700
                                        )
                                        if (period == DashboardPeriod.SALARY_CYCLE) {
                                            Text(
                                                text = "Cycle day: ${preferences.salaryCycleStartDay}th of each month",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Slate400,
                                                fontSize = 11.sp
                                            )
                                        }
                                    }
                                    if (isSelected) {
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = null,
                                            tint = Color(0xFF10B981),
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
                                }
                            },
                            onClick = {
                                onSelectPeriod(period)
                                showPeriodDropdown = false
                            }
                        )
                    }
                }
            }

            // Credit Card Bill Reminder Card (if any card has upcoming due date or balance)
            val creditCards = (accountsState as? UiState.Success)?.data?.filter {
                it.type == AccountType.CREDIT_CARD.name && (it.dueDay > 0 || it.balance > 0)
            } ?: emptyList()

            if (creditCards.isNotEmpty()) {
                val now = java.util.Calendar.getInstance()
                val today = now.get(java.util.Calendar.DAY_OF_MONTH)
                val daysInMonth = now.getActualMaximum(java.util.Calendar.DAY_OF_MONTH)

                val allTransactions = (transactionsState as? UiState.Success)?.data ?: emptyList()

                // Sort cards by urgency: cards with upcoming dues first, then highest balance
                val sortedCards = remember(creditCards, allTransactions, today, daysInMonth) {
                    creditCards.sortedWith(
                        compareBy<Account> { card ->
                            if (card.dueDay > 0) {
                                if (card.dueDay >= today) card.dueDay - today else (daysInMonth - today) + card.dueDay
                            } else 999
                        }.thenByDescending { card ->
                            val s = CreditCardStatementCalculator.calculateStatementSummary(card, allTransactions, now)
                            s.statementDueAmount
                        }
                    )
                }

                val maxInitialDisplay = 2
                val hasMoreCards = sortedCards.size > maxInitialDisplay
                val displayedCards = if (isCreditCardsExpanded || !hasMoreCards) {
                    sortedCards
                } else {
                    sortedCards.take(maxInitialDisplay)
                }

                Spacer(modifier = Modifier.height(10.dp))
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = PastelAmberBg,
                    border = androidx.compose.foundation.BorderStroke(1.dp, PastelAmberBorder),
                    modifier = Modifier
                        .fillMaxWidth()
                        .animateContentSize()
                        .testTag("dashboard_credit_card_reminders_card")
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f, fill = false)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.CreditCard,
                                    contentDescription = null,
                                    tint = PastelAmberText,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "CREDIT CARD BILLING REMINDERS (${sortedCards.size})",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PastelAmberText,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 0.8.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }

                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Text(
                                    text = "Accounts",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PastelAmberText,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier
                                        .clickable { onNavigateToAccounts() }
                                        .testTag("credit_card_reminders_nav_accounts")
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        displayedCards.forEachIndexed { index, card ->
                            if (index > 0) {
                                HorizontalDivider(
                                    color = Color(0xFFFDE68A).copy(alpha = 0.5f),
                                    thickness = 1.dp,
                                    modifier = Modifier.padding(vertical = 4.dp)
                                )
                            }

                            val stmtSummary = remember(card, allTransactions, today) {
                                CreditCardStatementCalculator.calculateStatementSummary(card, allTransactions, now)
                            }
                            val dueDay = card.dueDay
                            val daysUntilDue = if (dueDay > 0) {
                                if (dueDay >= today) dueDay - today else (daysInMonth - today) + dueDay
                            } else null

                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f, fill = false)) {
                                    Text(
                                        text = card.name,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Slate900,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        if (card.statementDay > 0) {
                                            Text(
                                                text = "Stmt: ${stmtSummary.formattedStatementDate} • ",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Slate500,
                                                fontSize = 11.sp
                                            )
                                        }
                                        if (dueDay > 0) {
                                            Text(
                                                text = "Due: ${stmtSummary.formattedDueDate}",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Slate700,
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }
                                    if (stmtSummary.unbilledAmount > 0) {
                                        Text(
                                            text = "Total O/S: ${CurrencyUtils.formatAmount(stmtSummary.totalOutstanding, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances)} • Unbilled: ${CurrencyUtils.formatAmount(stmtSummary.unbilledAmount, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances)}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate600,
                                            fontSize = 10.sp
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.width(8.dp))

                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Column(horizontalAlignment = Alignment.End) {
                                        val displayDue = if (stmtSummary.statementDueAmount > 0) {
                                            stmtSummary.statementDueAmount
                                        } else {
                                            stmtSummary.totalOutstanding
                                        }
                                        Text(
                                            text = CurrencyUtils.formatAmount(displayDue, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances),
                                            style = MaterialTheme.typography.bodySmall,
                                            fontWeight = FontWeight.Bold,
                                            color = if (displayDue > 0) Color(0xFFDC2626) else Slate900
                                        )
                                        Text(
                                            text = if (stmtSummary.statementDueAmount > 0) {
                                                "Statement Due"
                                            } else if (stmtSummary.totalOutstanding > 0) {
                                                "Unbilled Only"
                                            } else {
                                                "Paid"
                                            },
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (stmtSummary.statementDueAmount > 0) Color(0xFFDC2626) else Slate500,
                                            fontSize = 9.5.sp,
                                            fontWeight = FontWeight.SemiBold
                                        )
                                        daysUntilDue?.let { days ->
                                            Spacer(modifier = Modifier.height(2.dp))
                                            Surface(
                                                shape = RoundedCornerShape(6.dp),
                                                color = if (days <= 5) Color(0xFFFFE4E6) else Color(0xFFFEF3C7)
                                            ) {
                                                Text(
                                                    text = if (days == 0) "Due Today" else "in $days days",
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = if (days <= 5) Color(0xFFE11D48) else Color(0xFFD97706),
                                                    fontWeight = FontWeight.Bold,
                                                    fontSize = 10.sp,
                                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Show More / Show Less Button if there are more than maxInitialDisplay cards
                        if (hasMoreCards) {
                            Spacer(modifier = Modifier.height(6.dp))
                            HorizontalDivider(
                                color = PastelAmberBorder.copy(alpha = 0.6f),
                                thickness = 1.dp
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = PastelAmberBorder.copy(alpha = 0.4f),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { isCreditCardsExpanded = !isCreditCardsExpanded }
                                    .testTag("credit_cards_reminders_toggle_expand")
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 7.dp, horizontal = 12.dp),
                                    horizontalArrangement = Arrangement.Center,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    val hiddenCount = sortedCards.size - maxInitialDisplay
                                    Text(
                                        text = if (isCreditCardsExpanded) {
                                            "Show Less"
                                        } else {
                                            "Show More (${hiddenCount} other card${if (hiddenCount > 1) "s" else ""})"
                                        },
                                        style = MaterialTheme.typography.labelMedium,
                                        color = PastelAmberText,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Icon(
                                        imageVector = if (isCreditCardsExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                                        contentDescription = if (isCreditCardsExpanded) "Collapse credit card dues" else "Expand credit card dues",
                                        tint = PastelAmberText,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // Render widgets according to user-customized order
        cfg.widgetOrder.forEach { widgetKey ->
            when (widgetKey) {
                DashboardWidgetConfig.WIDGET_NET_WORTH -> {
                    if (cfg.showNetWorthHero) {
                        item(key = "widget_net_worth") {
                            NetWorthHeroWidget(
                                summary = summary,
                                preferences = preferences,
                                size = cfg.netWorthHeroSize
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_CASH_FLOW -> {
                    if (cfg.showMonthlyCashFlow) {
                        item(key = "widget_cash_flow") {
                            MonthlyCashFlowWidget(
                                summary = summary,
                                preferences = preferences,
                                style = cfg.cashFlowStyle
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_QUICK_ACTIONS -> {
                    if (cfg.showQuickActions) {
                        item(key = "widget_quick_actions") {
                            QuickActionShortcutsWidget(
                                cfg = cfg,
                                onOpenTransactionSheet = onOpenTransactionSheet,
                                onOpenInvestmentSheet = onOpenInvestmentSheet
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_ACCOUNTS -> {
                    if (cfg.showAccounts) {
                        item(key = "widget_accounts") {
                            AccountsCarouselWidget(
                                accountsState = accountsState,
                                preferences = preferences,
                                carouselStyle = cfg.accountsCarouselStyle,
                                onOpenAddAccountDialog = onOpenAddAccountDialog,
                                onNavigateToAccounts = onNavigateToAccounts
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_CATEGORIES -> {
                    if (cfg.showCategoryBreakdown && categoryBreakdown.isNotEmpty()) {
                        item(key = "widget_categories") {
                            CategoryBreakdownWidget(
                                categoryBreakdown = categoryBreakdown,
                                preferences = preferences,
                                sizeStyle = cfg.categoryBreakdownSize
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_INVESTMENT -> {
                    if (cfg.showInvestmentSummary) {
                        item(key = "widget_investment") {
                            InvestmentSummaryWidget(
                                summary = summary,
                                preferences = preferences,
                                cardSize = cfg.investmentCardSize,
                                onNavigateToInvestments = onNavigateToInvestments
                            )
                        }
                    }
                }

                DashboardWidgetConfig.WIDGET_TRANSACTIONS -> {
                    if (cfg.showRecentTransactions) {
                        item(key = "widget_transactions_header") {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "RECENT TRANSACTIONS",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 1.sp
                                )
                                Text(
                                    text = "See All",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = Slate700,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.clickable { onNavigateToTransactions() }
                                )
                            }
                        }

                        when (transactionsState) {
                            is UiState.Loading -> {
                                item(key = "transactions_loading") {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .height(80.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Slate800)
                                    }
                                }
                            }
                            is UiState.Error -> {
                                item(key = "transactions_error") {
                                    Text(text = "Failed to load transactions", color = PastelExpenseText)
                                }
                            }
                            is UiState.Success -> {
                                val transactions = transactionsState.data.take(cfg.recentTransactionsCount)
                                if (transactions.isEmpty()) {
                                    item(key = "transactions_empty") {
                                        Card(
                                            shape = RoundedCornerShape(14.dp),
                                            colors = CardDefaults.cardColors(containerColor = Color.White),
                                            border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                                            modifier = Modifier.fillMaxWidth()
                                        ) {
                                            Column(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .padding(18.dp),
                                                horizontalAlignment = Alignment.CenterHorizontally
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.ReceiptLong,
                                                    contentDescription = null,
                                                    tint = Slate400,
                                                    modifier = Modifier.size(32.dp)
                                                )
                                                Spacer(modifier = Modifier.height(6.dp))
                                                Text(
                                                    "No entries recorded yet",
                                                    style = MaterialTheme.typography.titleSmall,
                                                    color = Slate700
                                                )
                                            }
                                        }
                                    }
                                } else {
                                    items(transactions, key = { it.id }) { tx ->
                                        TransactionRowItem(
                                            transaction = tx,
                                            preferences = preferences,
                                            isCompact = cfg.transactionsCardSize == "COMPACT" || preferences.compactSpacing,
                                            onClick = { onEditTransaction?.invoke(tx) },
                                            onLongClick = { transactionToDelete = tx }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        item {
            Spacer(modifier = Modifier.height(70.dp))
        }
    }
}

    transactionToDelete?.let { tx ->
        AlertDialog(
            onDismissRequest = { transactionToDelete = null },
            title = {
                Text(
                    text = "Delete Transaction Entry?",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = "Remove ${tx.category} entry of ${CurrencyUtils.formatRupee(tx.amount)} from your records?\n\n(This action was unlocked by holding the entry for 1 second to prevent accidental touches.)",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Slate700
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteTransaction?.invoke(tx)
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

// ---------------------------------------------------------------------------
// SUB-WIDGET IMPLEMENTATIONS
// ---------------------------------------------------------------------------

@Composable
private fun NetWorthHeroWidget(
    summary: FinancialSummary,
    preferences: AppPreferences,
    size: String
) {
    val isCompact = size == "COMPACT"
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Slate900),
        modifier = Modifier
            .fillMaxWidth()
            .testTag("net_balance_hero_card")
    ) {
        Column(
            modifier = Modifier.padding(if (isCompact) 14.dp else 18.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "ESTIMATED NET WORTH",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 1.sp
                )
                if (preferences.maskBalances) {
                    Text(
                        text = "PRIVATE",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFA7F3D0),
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = CurrencyUtils.formatAmount(
                    summary.netWorth,
                    preferences.currencySymbol,
                    preferences.showDecimals,
                    preferences.maskBalances
                ),
                style = if (isCompact) MaterialTheme.typography.headlineMedium else MaterialTheme.typography.headlineLarge,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                letterSpacing = (-0.5).sp
            )

            if (!isCompact) {
                Spacer(modifier = Modifier.height(14.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text(
                            text = "Liquid Cash",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate400
                        )
                        Text(
                            text = CurrencyUtils.formatAmount(
                                summary.totalLiquidCash,
                                preferences.currencySymbol,
                                preferences.showDecimals,
                                preferences.maskBalances
                            ),
                            style = MaterialTheme.typography.titleSmall,
                            color = Color.White,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Column {
                        Text(
                            text = "Net Invested",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate400
                        )
                        Text(
                            text = CurrencyUtils.formatAmount(
                                summary.totalInvestedCapital,
                                preferences.currencySymbol,
                                preferences.showDecimals,
                                preferences.maskBalances
                            ),
                            style = MaterialTheme.typography.titleSmall,
                            color = Color(0xFFD8B4FE),
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Column {
                        Text(
                            text = "Credit Used",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate400
                        )
                        Text(
                            text = CurrencyUtils.formatAmount(
                                summary.totalCreditDebt,
                                preferences.currencySymbol,
                                preferences.showDecimals,
                                preferences.maskBalances
                            ),
                            style = MaterialTheme.typography.titleSmall,
                            color = Color(0xFFFCA5A5),
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MonthlyCashFlowWidget(
    summary: FinancialSummary,
    preferences: AppPreferences,
    style: String
) {
    if (style == "COMPACT") {
        Card(
            shape = RoundedCornerShape(14.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White),
            border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(24.dp)
                            .clip(CircleShape)
                            .background(PastelIncomeBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(imageVector = Icons.Default.SouthWest, contentDescription = null, tint = PastelIncomeText, modifier = Modifier.size(14.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Column {
                        Text("Income", style = MaterialTheme.typography.labelSmall, color = Slate500)
                        Text(
                            CurrencyUtils.formatAmount(summary.monthlyIncome, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances),
                            style = MaterialTheme.typography.titleSmall,
                            color = PastelIncomeText,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(24.dp)
                            .clip(CircleShape)
                            .background(PastelExpenseBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(imageVector = Icons.Default.NorthEast, contentDescription = null, tint = PastelExpenseText, modifier = Modifier.size(14.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Column {
                        Text("Expenses", style = MaterialTheme.typography.labelSmall, color = Slate500)
                        Text(
                            CurrencyUtils.formatAmount(summary.monthlyExpense, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances),
                            style = MaterialTheme.typography.titleSmall,
                            color = PastelExpenseText,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    } else {
        // Side by side cards
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = PastelIncomeBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, PastelIncomeBorder),
                modifier = Modifier.weight(1f)
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(imageVector = Icons.Default.SouthWest, contentDescription = null, tint = PastelIncomeText, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Income", style = MaterialTheme.typography.labelMedium, color = PastelIncomeText, fontWeight = FontWeight.Bold)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        CurrencyUtils.formatAmount(summary.monthlyIncome, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances),
                        style = MaterialTheme.typography.titleMedium,
                        color = PastelIncomeText,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Surface(
                shape = RoundedCornerShape(16.dp),
                color = PastelExpenseBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, PastelExpenseBorder),
                modifier = Modifier.weight(1f)
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(imageVector = Icons.Default.NorthEast, contentDescription = null, tint = PastelExpenseText, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Expenses", style = MaterialTheme.typography.labelMedium, color = PastelExpenseText, fontWeight = FontWeight.Bold)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        CurrencyUtils.formatAmount(summary.monthlyExpense, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances),
                        style = MaterialTheme.typography.titleMedium,
                        color = PastelExpenseText,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun QuickActionShortcutsWidget(
    cfg: DashboardWidgetConfig,
    onOpenTransactionSheet: (TransactionType) -> Unit,
    onOpenInvestmentSheet: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (cfg.enableExpenseShortcut) {
            ActionChip(
                title = "+ Expense",
                bg = PastelExpenseBg,
                border = PastelExpenseBorder,
                textColor = PastelExpenseText,
                icon = Icons.Default.NorthEast,
                tag = "quick_add_expense",
                onClick = { onOpenTransactionSheet(TransactionType.EXPENSE) }
            )
        }

        if (cfg.enableIncomeShortcut) {
            ActionChip(
                title = "+ Income",
                bg = PastelIncomeBg,
                border = PastelIncomeBorder,
                textColor = PastelIncomeText,
                icon = Icons.Default.SouthWest,
                tag = "quick_add_income",
                onClick = { onOpenTransactionSheet(TransactionType.INCOME) }
            )
        }

        if (cfg.enableTransferShortcut) {
            ActionChip(
                title = "⇄ Transfer",
                bg = PastelTransferBg,
                border = PastelTransferBorder,
                textColor = PastelTransferText,
                icon = Icons.Default.CompareArrows,
                tag = "quick_transfer",
                onClick = { onOpenTransactionSheet(TransactionType.TRANSFER) }
            )
        }

        if (cfg.enableInvestmentShortcut) {
            ActionChip(
                title = "+ Invest",
                bg = PastelInvestmentBg,
                border = PastelInvestmentBorder,
                textColor = PastelInvestmentText,
                icon = Icons.Default.TrendingUp,
                tag = "quick_investment",
                onClick = onOpenInvestmentSheet
            )
        }
    }
}

@Composable
private fun AccountsCarouselWidget(
    accountsState: UiState<List<Account>>,
    preferences: AppPreferences,
    carouselStyle: String,
    onOpenAddAccountDialog: () -> Unit,
    onNavigateToAccounts: () -> Unit
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "ACCOUNTS & MODES OF CASH",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Text(
                text = "Manage",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.clickable { onNavigateToAccounts() }
            )
        }
        Spacer(modifier = Modifier.height(4.dp))

        when (accountsState) {
            is UiState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(80.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Slate800)
                }
            }
            is UiState.Error -> {
                Text(text = "Failed to load accounts", color = PastelExpenseText)
            }
            is UiState.Success -> {
                val accounts = accountsState.data
                val isCompact = carouselStyle == "COMPACT_LIST"

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    accounts.forEach { acc ->
                        AccountCard(
                            account = acc,
                            preferences = preferences,
                            isCompact = isCompact
                        )
                    }
                    // Quick Add Account Card
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = Slate100,
                        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                        modifier = Modifier
                            .width(if (isCompact) 110.dp else 130.dp)
                            .height(if (isCompact) 75.dp else 95.dp)
                            .clickable { onOpenAddAccountDialog() }
                            .testTag("add_account_carousel_card")
                    ) {
                        Column(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.Center,
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(imageVector = Icons.Default.Add, contentDescription = "Add", tint = Slate700, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                "Add Account",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate700,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CategoryBreakdownWidget(
    categoryBreakdown: List<CategoryBreakdownItem>,
    preferences: AppPreferences,
    sizeStyle: String
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(
                text = "EXPENSE BREAKDOWN BY CATEGORY",
                style = MaterialTheme.typography.labelSmall,
                color = Slate500,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(10.dp))

            if (sizeStyle == "COMPACT") {
                // Compact tag/chip list for space optimization
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    categoryBreakdown.take(5).forEach { item ->
                        Surface(
                            shape = RoundedCornerShape(10.dp),
                            color = PastelExpenseBg,
                            border = androidx.compose.foundation.BorderStroke(1.dp, PastelExpenseBorder),
                            modifier = Modifier.padding(vertical = 2.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    item.category,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PastelExpenseText,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "${CurrencyUtils.formatAmount(item.amount, preferences.currencySymbol, false, preferences.maskBalances)} (${(item.percentage * 100).toInt()}%)",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate600
                                )
                            }
                        }
                    }
                }
            } else {
                // Detailed progress bars
                categoryBreakdown.take(4).forEach { item ->
                    Column(modifier = Modifier.padding(vertical = 4.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                item.category,
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate800,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                "${CurrencyUtils.formatAmount(item.amount, preferences.currencySymbol, preferences.showDecimals, preferences.maskBalances)} (${(item.percentage * 100).toInt()}%)",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate600
                            )
                        }
                        Spacer(modifier = Modifier.height(3.dp))
                        LinearProgressIndicator(
                            progress = { item.percentage },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(5.dp)
                                .clip(RoundedCornerShape(3.dp)),
                            color = PastelExpenseText,
                            trackColor = Slate100
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InvestmentSummaryWidget(
    summary: FinancialSummary,
    preferences: AppPreferences,
    cardSize: String,
    onNavigateToInvestments: () -> Unit
) {
    val isCompact = cardSize == "COMPACT"
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = PastelInvestmentBg,
        border = androidx.compose.foundation.BorderStroke(1.dp, PastelInvestmentBorder),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onNavigateToInvestments() }
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(if (isCompact) 10.dp else 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(if (isCompact) 30.dp else 36.dp)
                        .clip(CircleShape)
                        .background(PastelInvestmentBorder),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Savings,
                        contentDescription = null,
                        tint = PastelInvestmentText,
                        modifier = Modifier.size(if (isCompact) 16.dp else 20.dp)
                    )
                }
                Spacer(modifier = Modifier.width(10.dp))
                Column {
                    Text("Invested Capital", style = MaterialTheme.typography.labelSmall, color = Slate600)
                    Text(
                        CurrencyUtils.formatAmount(
                            summary.totalInvestedCapital,
                            preferences.currencySymbol,
                            preferences.showDecimals,
                            preferences.maskBalances
                        ),
                        style = if (isCompact) MaterialTheme.typography.titleSmall else MaterialTheme.typography.titleMedium,
                        color = PastelInvestmentText,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "View Ledger",
                    style = MaterialTheme.typography.labelSmall,
                    color = PastelInvestmentText,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(2.dp))
                Icon(
                    imageVector = Icons.Default.ArrowForward,
                    contentDescription = null,
                    tint = PastelInvestmentText,
                    modifier = Modifier.size(12.dp)
                )
            }
        }
    }
}

@Composable
private fun ActionChip(
    title: String,
    bg: Color,
    border: Color,
    textColor: Color,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    tag: String,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = bg,
        border = androidx.compose.foundation.BorderStroke(1.dp, border),
        modifier = Modifier
            .clickable { onClick() }
            .testTag(tag)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = textColor, modifier = Modifier.size(15.dp))
            Spacer(modifier = Modifier.width(5.dp))
            Text(text = title, style = MaterialTheme.typography.labelMedium, color = textColor, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun AccountCard(
    account: Account,
    preferences: AppPreferences,
    isCompact: Boolean = false
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
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .width(if (isCompact) 140.dp else 160.dp)
            .height(if (isCompact) 80.dp else 100.dp)
            .testTag("account_card_${account.id}")
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(if (isCompact) 10.dp else 12.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(if (isCompact) 20.dp else 24.dp)
                        .clip(CircleShape)
                        .background(chipColor.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = chipColor,
                        modifier = Modifier.size(if (isCompact) 12.dp else 14.dp)
                    )
                }
                Text(
                    text = if (account.type == AccountType.CREDIT_CARD.name && account.dueDay > 0) "Due: ${account.dueDay}th" else account.institution.ifBlank { account.type },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (account.type == AccountType.CREDIT_CARD.name && account.dueDay > 0) Color(0xFFB45309) else Slate500,
                    fontWeight = if (account.type == AccountType.CREDIT_CARD.name && account.dueDay > 0) FontWeight.Bold else FontWeight.Medium
                )
            }

            Column {
                Text(
                    text = account.name,
                    style = MaterialTheme.typography.titleSmall,
                    color = Slate900,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1
                )
                Text(
                    text = CurrencyUtils.formatAmount(
                        account.balance,
                        preferences.currencySymbol,
                        preferences.showDecimals,
                        preferences.maskBalances
                    ),
                    style = MaterialTheme.typography.titleMedium,
                    color = if (account.type == AccountType.CREDIT_CARD.name) PastelExpenseText else Slate900,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
fun TransactionRowItem(
    transaction: Transaction,
    preferences: AppPreferences? = null,
    isCompact: Boolean = false,
    onClick: (() -> Unit)? = null,
    onLongClick: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    var showInvoiceDialog by remember { mutableStateOf(false) }

    val isExpense = transaction.type == TransactionType.EXPENSE.name
    val isIncome = transaction.type == TransactionType.INCOME.name
    val isTransfer = transaction.type == TransactionType.TRANSFER.name

    val badgeBg = when {
        isExpense -> PastelExpenseBg
        isIncome -> PastelIncomeBg
        else -> PastelTransferBg
    }
    val badgeBorder = when {
        isExpense -> PastelExpenseBorder
        isIncome -> PastelIncomeBorder
        else -> PastelTransferBorder
    }
    val badgeText = when {
        isExpense -> PastelExpenseText
        isIncome -> PastelIncomeText
        else -> PastelTransferText
    }

    val icon = when {
        isExpense -> Icons.Default.NorthEast
        isIncome -> Icons.Default.SouthWest
        else -> Icons.Default.CompareArrows
    }

    val amountPrefix = when {
        isExpense -> "- "
        isIncome -> "+ "
        else -> "⇄ "
    }

    val sym = preferences?.currencySymbol ?: "₹"
    val showDecimals = preferences?.showDecimals ?: true
    val mask = preferences?.maskBalances ?: false

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .fillMaxWidth()
            .testTag("transaction_item_${transaction.id}")
            .onEntryClickAndLongPress1s(
                hapticFeedback = haptic,
                onClick = onClick,
                onLongPress1s = onLongClick
            )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = if (isCompact) 8.dp else 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = badgeBg,
                    border = androidx.compose.foundation.BorderStroke(1.dp, badgeBorder),
                    modifier = Modifier.size(if (isCompact) 28.dp else 32.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = icon,
                            contentDescription = null,
                            tint = badgeText,
                            modifier = Modifier.size(if (isCompact) 14.dp else 16.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.width(10.dp))

                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = if (isTransfer) "Inter-Account Transfer" else transaction.category,
                            style = MaterialTheme.typography.titleSmall,
                            color = Slate900,
                            fontWeight = FontWeight.SemiBold
                        )
                        if (transaction.invoiceFileName.isNotBlank()) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Surface(
                                shape = RoundedCornerShape(6.dp),
                                color = Color(0xFFDCFCE7),
                                modifier = Modifier
                                    .clickable { showInvoiceDialog = true }
                                    .testTag("invoice_badge_${transaction.id}")
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Receipt,
                                        contentDescription = "Invoice attached",
                                        tint = Color(0xFF15803D),
                                        modifier = Modifier.size(10.dp)
                                    )
                                    Spacer(modifier = Modifier.width(3.dp))
                                    Text(
                                        text = "Invoice",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Color(0xFF15803D),
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.width(2.dp))
                                    Icon(
                                        imageVector = Icons.Default.Download,
                                        contentDescription = "Download invoice",
                                        tint = Color(0xFF15803D),
                                        modifier = Modifier.size(10.dp)
                                    )
                                }
                            }
                        }
                    }
                    Text(
                        text = transaction.note.ifBlank { CurrencyUtils.formatDate(transaction.date ?: transaction.createdAt) },
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500,
                        maxLines = 1
                    )
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "$amountPrefix${CurrencyUtils.formatAmount(transaction.amount, sym, showDecimals, mask)}",
                    style = MaterialTheme.typography.titleSmall,
                    color = badgeText,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = CurrencyUtils.formatDate(transaction.date ?: transaction.createdAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400
                )
            }
        }
    }

    if (showInvoiceDialog) {
        AlertDialog(
            onDismissRequest = { showInvoiceDialog = false },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Receipt,
                        contentDescription = null,
                        tint = Color(0xFF15803D),
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Invoice Document",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            },
            text = {
                Column {
                    Text(
                        text = transaction.invoiceFileName,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = Slate900
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "Attached to ${transaction.category} (${CurrencyUtils.formatRupee(transaction.amount)})",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate600
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = "You can download this invoice directly to your device's Downloads folder or open it with your document viewer.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        InvoiceUtils.downloadInvoice(
                            context = context,
                            fileName = transaction.invoiceFileName,
                            fileUriString = transaction.invoiceUri,
                            category = transaction.category,
                            amount = transaction.amount,
                            note = transaction.note
                        )
                        showInvoiceDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF166534)),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(imageVector = Icons.Default.Download, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Download Invoice")
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = {
                        InvoiceUtils.openOrShareInvoice(
                            context = context,
                            fileName = transaction.invoiceFileName,
                            fileUriString = transaction.invoiceUri,
                            category = transaction.category,
                            amount = transaction.amount,
                            note = transaction.note
                        )
                        showInvoiceDialog = false
                    },
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(imageVector = Icons.Default.OpenInNew, contentDescription = null, modifier = Modifier.size(16.dp), tint = Slate700)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("View / Share", color = Slate700)
                }
            },
            containerColor = Color.White,
            shape = RoundedCornerShape(18.dp)
        )
    }
}
