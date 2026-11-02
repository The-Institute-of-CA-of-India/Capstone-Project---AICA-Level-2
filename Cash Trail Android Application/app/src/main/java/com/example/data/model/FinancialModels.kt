package com.example.data.model

import com.google.firebase.Timestamp
import com.google.firebase.firestore.DocumentId
import com.google.firebase.firestore.IgnoreExtraProperties
import com.google.firebase.firestore.ServerTimestamp

enum class AccountType(val displayName: String) {
    BANK("Bank Account"),
    CREDIT_CARD("Credit Card"),
    DIGITAL_WALLET("Digital Wallet"),
    CASH("Cash in Hand"),
    PERSONAL("Personal Account")
}

@IgnoreExtraProperties
data class Account(
    @DocumentId val id: String = "",
    val userId: String = "",
    val name: String = "",
    val type: String = AccountType.BANK.name,
    val balance: Double = 0.0,
    val creditLimit: Double = 0.0,
    val statementDay: Int = 0,
    val dueDay: Int = 0,
    val colorHex: String = "#1E88E5",
    val institution: String = "",
    val notes: String = "",
    @ServerTimestamp val createdAt: Timestamp? = null,
    @ServerTimestamp val updatedAt: Timestamp? = null
)

enum class TransactionType(val displayName: String) {
    EXPENSE("Expense"),
    INCOME("Income"),
    TRANSFER("Transfer")
}

@IgnoreExtraProperties
data class Transaction(
    @DocumentId val id: String = "",
    val userId: String = "",
    val type: String = TransactionType.EXPENSE.name,
    val amount: Double = 0.0,
    val accountId: String = "",
    val destinationAccountId: String? = null,
    val category: String = "General",
    val note: String = "",
    val invoiceFileName: String = "",
    val invoiceUri: String = "",
    val date: Timestamp? = null,
    @ServerTimestamp val createdAt: Timestamp? = null,
    @ServerTimestamp val updatedAt: Timestamp? = null
)

enum class InvestmentAssetType(val displayName: String) {
    MUTUAL_FUNDS("Mutual Funds"),
    STOCKS("Stocks & Equity"),
    FIXED_DEPOSIT("Fixed Deposit"),
    GOLD("Gold & Precious Metals"),
    CRYPTO("Crypto"),
    RETIREMENT("Retirement / PF"),
    REAL_ESTATE("Real Estate"),
    OTHER("Other")
}

enum class InvestmentAction(val displayName: String) {
    CONTRIBUTION("Contribution"),
    WITHDRAWAL("Withdrawal")
}

@IgnoreExtraProperties
data class Investment(
    @DocumentId val id: String = "",
    val userId: String = "",
    val assetName: String = "",
    val assetType: String = InvestmentAssetType.MUTUAL_FUNDS.name,
    val action: String = InvestmentAction.CONTRIBUTION.name,
    val amount: Double = 0.0,
    val sourceAccountId: String? = null,
    val note: String = "",
    val date: Timestamp? = null,
    @ServerTimestamp val createdAt: Timestamp? = null,
    @ServerTimestamp val updatedAt: Timestamp? = null
)
