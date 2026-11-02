package com.example.ui.settings

data class DashboardWidgetConfig(
    val showNetWorthHero: Boolean = true,
    val netWorthHeroSize: String = "COMFORTABLE", // "COMFORTABLE", "COMPACT", "MINIMAL"
    val showMonthlyCashFlow: Boolean = true,
    val cashFlowStyle: String = "CARDS", // "CARDS" (side by side), "COMPACT" (single bar), "MINIMAL" (pills)
    val showQuickActions: Boolean = true,
    val quickActionStyle: String = "PILLS", // "PILLS", "COMPACT", "GRID"
    val showAccounts: Boolean = true,
    val accountsCarouselStyle: String = "CAROUSEL", // "CAROUSEL", "COMPACT_LIST", "MINIMAL"
    val showCategoryBreakdown: Boolean = true,
    val categoryBreakdownSize: String = "STANDARD", // "STANDARD" (bars), "COMPACT" (chips)
    val showRecentTransactions: Boolean = true,
    val recentTransactionsCount: Int = 5,
    val transactionsCardSize: String = "COMFORTABLE", // "COMFORTABLE", "COMPACT"
    val showInvestmentSummary: Boolean = true,
    val investmentCardSize: String = "STANDARD", // "STANDARD", "COMPACT"
    // Button shortcuts toggles:
    val enableExpenseShortcut: Boolean = true,
    val enableIncomeShortcut: Boolean = true,
    val enableTransferShortcut: Boolean = true,
    val enableInvestmentShortcut: Boolean = true,
    // Widget reordering priority list (ID keys)
    val widgetOrder: List<String> = listOf(
        WIDGET_NET_WORTH,
        WIDGET_CASH_FLOW,
        WIDGET_QUICK_ACTIONS,
        WIDGET_ACCOUNTS,
        WIDGET_CATEGORIES,
        WIDGET_INVESTMENT,
        WIDGET_TRANSACTIONS
    )
) {
    companion object {
        const val WIDGET_NET_WORTH = "net_worth"
        const val WIDGET_CASH_FLOW = "cash_flow"
        const val WIDGET_QUICK_ACTIONS = "quick_actions"
        const val WIDGET_ACCOUNTS = "accounts"
        const val WIDGET_CATEGORIES = "categories"
        const val WIDGET_INVESTMENT = "investment"
        const val WIDGET_TRANSACTIONS = "transactions"
    }
}

data class AppPreferences(
    val currencySymbol: String = "₹",
    val showDecimals: Boolean = true,
    val maskBalances: Boolean = false,
    val pastelStyle: String = "SOFT", // "SOFT" or "VIBRANT"
    val compactSpacing: Boolean = false, // Space optimization toggle across the app
    val salaryCycleStartDay: Int = 1, // Day of month salary is credited (1 to 31)
    val defaultEntryType: String = "EXPENSE",
    val messageTrackingEnabled: Boolean = true, // Toggle message tracking ON or OFF
    val messageTrackingDays: Int = 15, // Number of days to track messages for transactions
    val widgetConfig: DashboardWidgetConfig = DashboardWidgetConfig()
)
