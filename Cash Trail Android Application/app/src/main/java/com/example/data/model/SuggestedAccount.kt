package com.example.data.model

import java.util.UUID

data class SuggestedAccount(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val institution: String,
    val type: AccountType, // Restricted strictly to BANK or CREDIT_CARD
    val accountSuffix: String = "",
    val reason: String = "",
    val lastDetectedAmount: Double? = null,
    val lastDetectedDate: Long = 0L,
    val rawSnippet: String = ""
)
