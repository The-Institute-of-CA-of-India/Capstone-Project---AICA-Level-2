package com.example.ui.util

import com.google.firebase.Timestamp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CurrencyUtils {

    fun formatAmount(
        amount: Double,
        currencySymbol: String = "₹",
        showDecimals: Boolean = true,
        mask: Boolean = false
    ): String {
        if (mask) return "$currencySymbol••••••"
        return try {
            val formatted = if (showDecimals) {
                "%,.2f".format(Locale.getDefault(), amount)
            } else {
                "%,.0f".format(Locale.getDefault(), amount)
            }
            "$currencySymbol$formatted"
        } catch (e: Exception) {
            "$currencySymbol$amount"
        }
    }

    // Backwards-compatible convenience helper
    fun formatRupee(amount: Double): String {
        return formatAmount(amount, "₹", showDecimals = true, mask = false)
    }

    private val dateFormat = SimpleDateFormat("dd MMM yyyy", Locale.getDefault())
    private val timeFormat = SimpleDateFormat("hh:mm a", Locale.getDefault())
    private val monthYearFormat = SimpleDateFormat("MMMM yyyy", Locale.getDefault())

    fun formatDate(timestamp: Timestamp?): String {
        val date = timestamp?.toDate() ?: Date()
        return dateFormat.format(date)
    }

    fun formatTime(timestamp: Timestamp?): String {
        val date = timestamp?.toDate() ?: Date()
        return timeFormat.format(date)
    }

    fun formatMonthYear(date: Date = Date()): String {
        return monthYearFormat.format(date)
    }
}
