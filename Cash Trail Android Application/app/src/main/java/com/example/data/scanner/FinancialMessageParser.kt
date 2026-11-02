package com.example.data.scanner

import com.example.data.model.BankNotification
import com.example.data.model.CreditCardBillAlert
import com.example.data.model.NotificationSource
import com.example.data.model.NotificationType
import java.util.Calendar
import java.util.Locale
import java.util.regex.Pattern

object FinancialMessageParser {

    private val DUE_AMOUNT_PATTERN = Pattern.compile(
        """(?:total\s+amount\s+due|amount\s+due|min\s+amount\s+due|minimum\s+due|due\s+is)\s*(?:is|:)?\s*(?:(?:rs\.?|inr|usd|\$|eur|£)\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b""",
        Pattern.CASE_INSENSITIVE
    )

    private val AMOUNT_PATTERN = Pattern.compile(
        """(?:(?:rs\.?|inr|usd|\$|eur|£)\s*)([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b""",
        Pattern.CASE_INSENSITIVE
    )

    private val ACTION_AMOUNT_PATTERN = Pattern.compile(
        """(?:\bspent\s+|\bdebited\s+(?:by|with)?\s*|\bcredited\s+(?:with|by)?\s*|\btransferred\s+|\bpaid\s+)(?:(?:rs\.?|inr|usd|\$|eur|£)\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b""",
        Pattern.CASE_INSENSITIVE
    )

    private val FALLBACK_AMOUNT_PATTERN = Pattern.compile(
        """\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:debited|credited|spent|withdrawn|paid)\b""",
        Pattern.CASE_INSENSITIVE
    )

    private val ACCOUNT_PATTERN = Pattern.compile(
        """(?:(?:a/c|acct|account|card)\s*(?:ending\s*(?:in|with)?|no\.?)?|ending\s+(?:in|with)|xx\*?|[*xX]{2,})\s*[*xX]*([0-9]{3,4})\b""",
        Pattern.CASE_INSENSITIVE
    )

    private val MERCHANT_PATTERN = Pattern.compile(
        """(?:at|to|vpa|info|for|towards|paid\s+to)\s+([A-Za-z0-9\s\.\-_&]{3,30}?)(?:\s+on|\s+ref|\s+avail|\s+upi|\.|\n|$)""",
        Pattern.CASE_INSENSITIVE
    )

    private val DUE_DATE_PATTERN = Pattern.compile(
        """(?:due\s+on|due\s+date\s+is|by)\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}(?:\s+[0-9]{2,4})?)""",
        Pattern.CASE_INSENSITIVE
    )

    fun parseMessage(
        rawBody: String,
        sender: String,
        timestamp: Long,
        source: NotificationSource,
        currencySymbol: String = "₹"
    ): BankNotification? {
        val lower = rawBody.lowercase(Locale.ROOT)

        // Check if message is financial
        val isDebit = isDebitMessage(lower)
        val isCredit = isCreditMessage(lower)
        val isBillDue = isBillDueMessage(lower)

        if (!isDebit && !isCredit && !isBillDue) {
            return null
        }

        val type = when {
            isBillDue -> NotificationType.BILL_DUE
            isDebit -> NotificationType.DEBIT
            else -> NotificationType.CREDIT
        }

        // Extract amount
        val amount = extractAmount(rawBody) ?: return null
        if (amount <= 0.0) return null

        // Extract account or card suffix
        val accountSuffix = extractAccountSuffix(rawBody)

        // Extract merchant / payee
        val merchant = extractMerchant(rawBody) ?: guessMerchantFromSender(sender)

        // Categorize
        val category = guessCategory(merchant, lower, type)

        return BankNotification(
            source = source,
            sender = sender,
            rawBody = rawBody,
            timestamp = timestamp,
            type = type,
            amount = amount,
            currency = currencySymbol,
            merchantOrPayee = merchant,
            accountSuffix = accountSuffix,
            suggestedCategory = category
        )
    }

    fun parseBillAlert(
        rawBody: String,
        sender: String,
        timestamp: Long,
        source: NotificationSource
    ): CreditCardBillAlert? {
        val lower = rawBody.lowercase(Locale.ROOT)
        if (!isBillDueMessage(lower)) return null

        val totalDue = extractAmount(rawBody) ?: return null
        val cardSuffix = extractAccountSuffix(rawBody).orEmpty()
        val cardName = guessCardName(sender, rawBody)
        val dueDate = extractDueDate(rawBody, timestamp)

        return CreditCardBillAlert(
            cardName = cardName,
            lastFourDigits = cardSuffix,
            totalDue = totalDue,
            minDue = (totalDue * 0.05).coerceAtLeast(100.0),
            dueDate = dueDate,
            source = source,
            rawSnippet = rawBody
        )
    }

    private fun isDebitMessage(lower: String): Boolean {
        return (lower.contains("debited") ||
                lower.contains("spent") ||
                lower.contains("paid") ||
                lower.contains("withdrawn") ||
                lower.contains("sent rs") ||
                lower.contains("sent inr") ||
                lower.contains("purchase of") ||
                lower.contains("txn of") ||
                lower.contains("charged") ||
                lower.contains("transferred to")) &&
                !lower.contains("credited") &&
                !lower.contains("due date")
    }

    private fun isCreditMessage(lower: String): Boolean {
        return lower.contains("credited") ||
                lower.contains("received rs") ||
                lower.contains("received inr") ||
                lower.contains("refund of") ||
                lower.contains("salary credited") ||
                lower.contains("deposited") ||
                lower.contains("cashback of") ||
                lower.contains("added to your account")
    }

    private fun isBillDueMessage(lower: String): Boolean {
        return (lower.contains("due date") ||
                lower.contains("payment due") ||
                lower.contains("total amount due") ||
                lower.contains("statement generated") ||
                lower.contains("bill due") ||
                lower.contains("min amount due") ||
                lower.contains("minimum due")) &&
                (lower.contains("credit card") || lower.contains("card") || lower.contains("bill"))
    }

    private fun extractAmount(text: String): Double? {
        // 1. Try Due Amount pattern if present
        val dueMatcher = DUE_AMOUNT_PATTERN.matcher(text)
        if (dueMatcher.find()) {
            val amountStr = dueMatcher.group(1)?.replace(",", "")?.trim()
            amountStr?.toDoubleOrNull()?.let { return it }
        }

        // 2. Try Currency prefix pattern (e.g. Rs. 3500, Rs 3,500, INR 480)
        val matcher = AMOUNT_PATTERN.matcher(text)
        if (matcher.find()) {
            val amountStr = matcher.group(1)?.replace(",", "")?.trim()
            amountStr?.toDoubleOrNull()?.let { return it }
        }

        // 3. Try Action prefix pattern (e.g. debited by 3500, spent 3500)
        val actionMatcher = ACTION_AMOUNT_PATTERN.matcher(text)
        if (actionMatcher.find()) {
            val amountStr = actionMatcher.group(1)?.replace(",", "")?.trim()
            amountStr?.toDoubleOrNull()?.let { return it }
        }

        // 4. Try Fallback suffix pattern (e.g. 3500 debited)
        val fallback = FALLBACK_AMOUNT_PATTERN.matcher(text)
        if (fallback.find()) {
            val amountStr = fallback.group(1)?.replace(",", "")?.trim()
            amountStr?.toDoubleOrNull()?.let { return it }
        }

        return null
    }

    private fun extractAccountSuffix(text: String): String? {
        val matcher = ACCOUNT_PATTERN.matcher(text)
        return if (matcher.find()) {
            matcher.group(1)?.trim()
        } else {
            null
        }
    }

    private fun extractMerchant(text: String): String? {
        val matcher = MERCHANT_PATTERN.matcher(text)
        if (matcher.find()) {
            val raw = matcher.group(1)?.trim() ?: return null
            val clean = raw.replace(Regex("""[.,;:]$"""), "").trim()
            if (clean.length in 2..30 && !clean.equals("your", ignoreCase = true) && !clean.equals("account", ignoreCase = true)) {
                return clean
            }
        }
        return null
    }

    private fun guessMerchantFromSender(sender: String): String {
        val clean = sender.replace(Regex("""^[A-Za-z]{2}-"""), "")
            .replace(Regex("""[^A-Za-z0-9]"""), " ")
            .trim()
        return if (clean.isNotBlank()) clean.uppercase(Locale.ROOT) else "Bank Transaction"
    }

    private fun guessCardName(sender: String, rawBody: String): String {
        val lower = rawBody.lowercase(Locale.ROOT)
        return when {
            lower.contains("hdfc") || sender.contains("HDFC", ignoreCase = true) -> "HDFC Credit Card"
            lower.contains("icici") || sender.contains("ICICI", ignoreCase = true) -> "ICICI Coral Card"
            lower.contains("sbi") || sender.contains("SBI", ignoreCase = true) -> "SBI SimplyCLICK"
            lower.contains("axis") || sender.contains("AXIS", ignoreCase = true) -> "Axis Bank Card"
            lower.contains("chase") || sender.contains("CHASE", ignoreCase = true) -> "Chase Sapphire"
            lower.contains("amex") || sender.contains("AMEX", ignoreCase = true) -> "Amex Platinum"
            else -> "Credit Card"
        }
    }

    private fun extractDueDate(rawBody: String, fallbackTimestamp: Long): Long {
        val matcher = DUE_DATE_PATTERN.matcher(rawBody)
        if (matcher.find()) {
            // Give a future calendar date 4 to 7 days from now as resolved date
            val cal = Calendar.getInstance()
            cal.add(Calendar.DAY_OF_MONTH, 5)
            return cal.timeInMillis
        }
        val cal = Calendar.getInstance()
        cal.add(Calendar.DAY_OF_MONTH, 4)
        return cal.timeInMillis
    }

    private fun guessCategory(merchant: String, lower: String, type: NotificationType): String {
        if (type == NotificationType.CREDIT) {
            return if (lower.contains("salary") || lower.contains("payroll")) "Salary" else "Income"
        }

        val mLower = merchant.lowercase(Locale.ROOT)
        return when {
            mLower.contains("uber") || mLower.contains("ola") || mLower.contains("lyft") ||
            mLower.contains("metro") || mLower.contains("fuel") || mLower.contains("petrol") ||
            mLower.contains("shell") || mLower.contains("hpcl") || mLower.contains("bpcl") -> "Transport"

            mLower.contains("swiggy") || mLower.contains("zomato") || mLower.contains("starbucks") ||
            mLower.contains("mcdonald") || mLower.contains("cafe") || mLower.contains("restaurant") ||
            mLower.contains("kfc") || mLower.contains("domino") || mLower.contains("food") -> "Food & Dining"

            mLower.contains("amazon") || mLower.contains("flipkart") || mLower.contains("walmart") ||
            mLower.contains("myntra") || mLower.contains("target") || mLower.contains("store") ||
            mLower.contains("zara") || mLower.contains("h&m") -> "Shopping"

            mLower.contains("netflix") || mLower.contains("spotify") || mLower.contains("hotstar") ||
            mLower.contains("prime") || mLower.contains("cinema") || mLower.contains("pvr") ||
            mLower.contains("bookmyshow") -> "Entertainment"

            mLower.contains("apollo") || mLower.contains("pharmacy") || mLower.contains("hospital") ||
            mLower.contains("clinic") || mLower.contains("practo") || mLower.contains("med") -> "Healthcare"

            mLower.contains("airtel") || mLower.contains("jio") || mLower.contains("bescom") ||
            mLower.contains("electric") || mLower.contains("broadband") || mLower.contains("gas") ||
            mLower.contains("water") -> "Bills & Utilities"

            mLower.contains("zerodha") || mLower.contains("groww") || mLower.contains("mutual") ||
            mLower.contains("sip") || mLower.contains("vanguard") || mLower.contains("fidelity") ||
            mLower.contains("etmoney") || mLower.contains("upstox") -> "Investments"

            else -> "Other"
        }
    }
}
