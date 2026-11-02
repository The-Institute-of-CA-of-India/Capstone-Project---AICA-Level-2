package com.example.data.scanner

import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.BankNotification
import com.example.data.model.CreditCardBillAlert
import com.example.data.model.NotificationType
import com.example.data.model.SuggestedAccount
import java.util.Locale

object SuggestedAccountDetector {

    /**
     * Known banks and card issuers pattern matcher
     */
    private val KNOWN_INSTITUTIONS = listOf(
        Pair(listOf("axis", "utib", "axisbk"), "Axis Bank"),
        Pair(listOf("hdfc", "hdfcbk"), "HDFC Bank"),
        Pair(listOf("icici", "icicib"), "ICICI Bank"),
        Pair(listOf("sbi", "sbin", "state bank"), "SBI"),
        Pair(listOf("kotak", "kotakb"), "Kotak Mahindra Bank"),
        Pair(listOf("bob", "baroda"), "Bank of Baroda"),
        Pair(listOf("pnb", "punjab"), "Punjab National Bank"),
        Pair(listOf("canara"), "Canara Bank"),
        Pair(listOf("indus", "indusb", "indusind"), "IndusInd Bank"),
        Pair(listOf("union", "ubi"), "Union Bank"),
        Pair(listOf("idfc", "idfcfirst", "idfcb"), "IDFC FIRST Bank"),
        Pair(listOf("yes", "yesbk", "yes bank"), "YES Bank"),
        Pair(listOf("rbl", "ratnakar"), "RBL Bank"),
        Pair(listOf("fed", "fedbk", "federal"), "Federal Bank"),
        Pair(listOf("amex", "american express"), "American Express"),
        Pair(listOf("scb", "standard chartered", "stanc"), "Standard Chartered"),
        Pair(listOf("citi", "citibank"), "Citibank"),
        Pair(listOf("chase", "jpmorgan"), "Chase"),
        Pair(listOf("boa", "bank of america"), "Bank of America"),
        Pair(listOf("wellsfargo", "wells fargo", "wf"), "Wells Fargo"),
        Pair(listOf("hsbc"), "HSBC")
    )

    fun detectSuggestions(
        notifications: List<BankNotification>,
        bills: List<CreditCardBillAlert>,
        existingAccounts: List<Account>,
        dismissedKeys: Set<String> = emptySet()
    ): List<SuggestedAccount> {
        val detected = mutableListOf<SuggestedAccount>()

        // 1. Process Bank Notifications (debits, credits, etc.)
        for (notif in notifications) {
            val text = notif.rawBody
            val lower = text.lowercase(Locale.ROOT)
            val senderLower = notif.sender.lowercase(Locale.ROOT)

            val institution = detectInstitution(senderLower, lower) ?: continue
            // Must be a recognized institution, not generic "Bank"
            if (institution.equals("Bank", ignoreCase = true)) continue

            // Must have a real 3-5 digit account/card suffix to prevent vague duplicate entries
            val suffix = notif.accountSuffix?.trim().orEmpty()
            if (suffix.isBlank() || suffix.length !in 3..5 || !suffix.all { it.isDigit() }) {
                continue
            }

            val isCreditCard = isCreditCardTransaction(lower, senderLower)
            val type = if (isCreditCard) AccountType.CREDIT_CARD else AccountType.BANK
            val accountName = buildAccountName(institution, type, suffix)

            // Deduplication key: institution + type + suffix
            val key = "${institution.lowercase(Locale.ROOT)}_${type.name}_$suffix"
            if (dismissedKeys.contains(key)) continue

            // Check if user already added this account
            if (isAccountAlreadyAdded(existingAccounts, institution, type, suffix)) {
                continue
            }

            val reason = when {
                notif.type == NotificationType.BILL_DUE && notif.amount > 0 ->
                    "Detected from card bill alert of ₹${String.format(Locale.US, "%,.0f", notif.amount)}"
                notif.type == NotificationType.DEBIT && notif.amount > 0 ->
                    "Detected from recent debit of ₹${String.format(Locale.US, "%,.0f", notif.amount)}"
                notif.type == NotificationType.CREDIT && notif.amount > 0 ->
                    "Detected from recent credit of ₹${String.format(Locale.US, "%,.0f", notif.amount)}"
                notif.type == NotificationType.DEBIT -> "Detected from debit transaction"
                notif.type == NotificationType.CREDIT -> "Detected from credit transaction"
                else -> "Detected from card statement alert"
            }

            detected.add(
                SuggestedAccount(
                    id = key,
                    name = accountName,
                    institution = institution,
                    type = type,
                    accountSuffix = suffix,
                    reason = reason,
                    lastDetectedAmount = notif.amount,
                    lastDetectedDate = notif.timestamp,
                    rawSnippet = text.take(120)
                )
            )
        }

        // 2. Process Credit Card Bill Alerts
        for (bill in bills) {
            val senderLower = bill.cardName.lowercase(Locale.ROOT)
            val bodyLower = bill.rawSnippet.lowercase(Locale.ROOT)
            val institution = detectInstitution(senderLower, bodyLower) ?: continue
            if (institution.equals("Bank", ignoreCase = true)) continue

            val suffix = bill.lastFourDigits.trim()
            if (suffix.isBlank() || suffix.length !in 3..5 || !suffix.all { it.isDigit() }) {
                continue
            }

            val type = AccountType.CREDIT_CARD
            val accountName = buildAccountName(institution, type, suffix)

            val key = "${institution.lowercase(Locale.ROOT)}_${type.name}_$suffix"
            if (dismissedKeys.contains(key)) continue

            if (isAccountAlreadyAdded(existingAccounts, institution, type, suffix)) {
                continue
            }

            val reason = if (bill.totalDue > 0) {
                "Detected from bill due alert of ₹${String.format(Locale.US, "%,.0f", bill.totalDue)}"
            } else {
                "Detected from card bill statement"
            }

            detected.add(
                SuggestedAccount(
                    id = key,
                    name = accountName,
                    institution = institution,
                    type = type,
                    accountSuffix = suffix,
                    reason = reason,
                    lastDetectedAmount = bill.totalDue,
                    lastDetectedDate = bill.dueDate,
                    rawSnippet = bill.rawSnippet.take(120)
                )
            )
        }

        // Distinct by key, pick the entry with latest activity, sort by date
        return detected
            .groupBy { it.id }
            .map { (_, list) -> list.maxByOrNull { it.lastDetectedDate } ?: list.first() }
            .sortedByDescending { it.lastDetectedDate }
            .take(6)
    }

    private fun detectInstitution(sender: String, body: String): String? {
        val combined = "$sender $body"
        for ((aliases, name) in KNOWN_INSTITUTIONS) {
            if (aliases.any { combined.contains(it) }) {
                return name
            }
        }

        // Fallback: Check if sender has bank format like AD-AXISBK or VM-HDFCBK
        val cleanSender = sender.replace(Regex("""^[a-z]{2}-"""), "").trim()
        if (cleanSender.endsWith("bk") || cleanSender.endsWith("bank")) {
            val rawName = cleanSender.removeSuffix("bk").removeSuffix("bank").trim()
            if (rawName.length >= 3 && !rawName.equals("bank", ignoreCase = true)) {
                return rawName.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() } + " Bank"
            }
        }
        return null
    }

    private fun isCreditCardTransaction(lower: String, senderLower: String): Boolean {
        return lower.contains("credit card") ||
                lower.contains("creditcard") ||
                lower.contains("card ending") ||
                lower.contains("card no") ||
                lower.contains("card xx") ||
                lower.contains("spent on card") ||
                lower.contains("card statement") ||
                senderLower.contains("card") ||
                lower.contains("cc ending")
    }

    private fun buildAccountName(institution: String, type: AccountType, suffix: String): String {
        val clean = institution.trim()
        return if (type == AccountType.CREDIT_CARD) {
            if (clean.equals("SBI", ignoreCase = true)) {
                "SBI Card ...$suffix"
            } else if (clean.endsWith("Bank", ignoreCase = true)) {
                "$clean Card ...$suffix"
            } else {
                "$clean Card ...$suffix"
            }
        } else {
            if (clean.endsWith("Bank", ignoreCase = true)) {
                "$clean A/c ...$suffix"
            } else {
                "$clean Bank A/c ...$suffix"
            }
        }
    }

    private fun isAccountAlreadyAdded(
        existingAccounts: List<Account>,
        institution: String,
        type: AccountType,
        suffix: String
    ): Boolean {
        val instLower = institution.lowercase(Locale.ROOT)
        val suffixLower = suffix.lowercase(Locale.ROOT)

        return existingAccounts.any { acc ->
            val accNameLower = acc.name.lowercase(Locale.ROOT)
            val accInstLower = acc.institution.lowercase(Locale.ROOT)
            val accNotesLower = acc.notes.lowercase(Locale.ROOT)

            // If suffix matches existing account name or notes
            val suffixMatches = suffixLower.isNotBlank() && (
                accNameLower.contains(suffixLower) ||
                accNotesLower.contains(suffixLower)
            )

            // If institution matches
            val institutionMatches = accInstLower.contains(instLower) || accNameLower.contains(instLower)

            (suffixMatches && institutionMatches) || (suffixMatches && acc.type == type.name)
        }
    }
}
