package com.example.data.model

import java.util.UUID

enum class NotificationType {
    DEBIT,
    CREDIT,
    BILL_DUE
}

enum class NotificationSource {
    SMS,
    GMAIL
}

data class BankNotification(
    val id: String = UUID.randomUUID().toString(),
    val source: NotificationSource,
    val sender: String,
    val rawBody: String,
    val timestamp: Long,
    val type: NotificationType,
    val amount: Double,
    val currency: String = "₹",
    val merchantOrPayee: String,
    val accountSuffix: String? = null,
    val suggestedCategory: String = "Other",
    val suggestedAccountId: String? = null,
    val isDismissed: Boolean = false,
    val isProcessed: Boolean = false
)

data class CreditCardBillAlert(
    val id: String = UUID.randomUUID().toString(),
    val cardName: String,
    val lastFourDigits: String,
    val totalDue: Double,
    val minDue: Double? = null,
    val dueDate: Long,
    val source: NotificationSource,
    val rawSnippet: String = "",
    val isPaid: Boolean = false
)
