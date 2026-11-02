package com.example.data.backup

import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Investment
import com.example.data.model.PersonalDocument
import com.example.data.model.Transaction
import com.example.ui.settings.AppPreferences
import com.google.firebase.Timestamp
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class BackupStats(
    val totalAccounts: Int = 0,
    val totalTransactions: Int = 0,
    val totalInvestments: Int = 0,
    val totalDocuments: Int = 0,
    val totalNetBalance: Double = 0.0,
    val totalInvestedCapital: Double = 0.0
)

data class DailyBackupRecord(
    val fileName: String,
    val dateString: String,
    val timestamp: Long,
    val fileSizeBytes: Long,
    val totalRecords: Int,
    val filePath: String,
    val isAutoDaily: Boolean = true
) {
    val formattedFileSize: String
        get() = when {
            fileSizeBytes < 1024 -> "$fileSizeBytes B"
            fileSizeBytes < 1024 * 1024 -> String.format(Locale.US, "%.1f KB", fileSizeBytes / 1024.0)
            else -> String.format(Locale.US, "%.2f MB", fileSizeBytes / (1024.0 * 1024.0))
        }

    val formattedDate: String
        get() = try {
            val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.US)
            val d = sdf.parse(dateString)
            if (d != null) {
                val outFormat = SimpleDateFormat("dd MMM yyyy", Locale.getDefault())
                outFormat.format(d)
            } else dateString
        } catch (_: Exception) {
            dateString
        }

    val formattedTime: String
        get() = SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date(timestamp))
}

data class CashTrailBackupData(
    val backupVersion: Int = 1,
    val appVersion: String = "5.0",
    val exportedAt: Long = System.currentTimeMillis(),
    val exportDateString: String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date()),
    val userEmail: String = "",
    val stats: BackupStats = BackupStats(),
    val accounts: List<Account> = emptyList(),
    val transactions: List<Transaction> = emptyList(),
    val investments: List<Investment> = emptyList(),
    val documents: List<PersonalDocument> = emptyList(),
    val preferences: AppPreferences = AppPreferences()
) {
    fun toJsonString(indent: Int = 2): String {
        val root = JSONObject()
        root.put("backupVersion", backupVersion)
        root.put("appVersion", appVersion)
        root.put("appName", "CashTrail")
        root.put("exportedAt", exportedAt)
        root.put("exportDateString", exportDateString)
        root.put("userEmail", userEmail)

        // Stats
        val statsObj = JSONObject()
        statsObj.put("totalAccounts", accounts.size)
        statsObj.put("totalTransactions", transactions.size)
        statsObj.put("totalInvestments", investments.size)
        statsObj.put("totalDocuments", documents.size)
        statsObj.put("totalNetBalance", accounts.sumOf { it.balance })
        statsObj.put("totalInvestedCapital", investments.sumOf { it.amount })
        root.put("stats", statsObj)

        // Preferences
        val prefsObj = JSONObject()
        prefsObj.put("currencySymbol", preferences.currencySymbol)
        prefsObj.put("showDecimals", preferences.showDecimals)
        prefsObj.put("maskBalances", preferences.maskBalances)
        prefsObj.put("pastelStyle", preferences.pastelStyle)
        prefsObj.put("compactSpacing", preferences.compactSpacing)
        prefsObj.put("salaryCycleStartDay", preferences.salaryCycleStartDay)
        prefsObj.put("defaultEntryType", preferences.defaultEntryType)
        prefsObj.put("messageTrackingEnabled", preferences.messageTrackingEnabled)
        prefsObj.put("messageTrackingDays", preferences.messageTrackingDays)
        root.put("preferences", prefsObj)

        // Accounts
        val accArray = JSONArray()
        for (acc in accounts) {
            val o = JSONObject()
            o.put("id", acc.id)
            o.put("name", acc.name)
            o.put("type", acc.type)
            o.put("balance", acc.balance)
            o.put("creditLimit", acc.creditLimit)
            o.put("statementDay", acc.statementDay)
            o.put("dueDay", acc.dueDay)
            o.put("colorHex", acc.colorHex)
            o.put("institution", acc.institution)
            o.put("notes", acc.notes)
            accArray.put(o)
        }
        root.put("accounts", accArray)

        // Transactions
        val txArray = JSONArray()
        for (tx in transactions) {
            val o = JSONObject()
            o.put("id", tx.id)
            o.put("type", tx.type)
            o.put("amount", tx.amount)
            o.put("accountId", tx.accountId)
            o.put("destinationAccountId", tx.destinationAccountId ?: "")
            o.put("category", tx.category)
            o.put("note", tx.note)
            o.put("invoiceFileName", tx.invoiceFileName)
            o.put("invoiceUri", tx.invoiceUri)
            o.put("dateTimestampSec", tx.date?.seconds ?: (System.currentTimeMillis() / 1000))
            txArray.put(o)
        }
        root.put("transactions", txArray)

        // Investments
        val invArray = JSONArray()
        for (inv in investments) {
            val o = JSONObject()
            o.put("id", inv.id)
            o.put("assetName", inv.assetName)
            o.put("assetType", inv.assetType)
            o.put("action", inv.action)
            o.put("amount", inv.amount)
            o.put("sourceAccountId", inv.sourceAccountId ?: "")
            o.put("note", inv.note)
            o.put("dateTimestampSec", inv.date?.seconds ?: (System.currentTimeMillis() / 1000))
            invArray.put(o)
        }
        root.put("investments", invArray)

        // Documents
        val docArray = JSONArray()
        for (doc in documents) {
            val o = JSONObject()
            o.put("id", doc.id)
            o.put("name", doc.name)
            o.put("category", doc.category)
            o.put("documentNumber", doc.documentNumber)
            o.put("issuer", doc.issuer)
            o.put("expiryDate", doc.expiryDate)
            o.put("issueDate", doc.issueDate)
            o.put("notes", doc.notes)
            o.put("fileUri", doc.fileUri)
            o.put("fileName", doc.fileName)
            o.put("colorHex", doc.colorHex)
            o.put("isFavorite", doc.isFavorite)
            docArray.put(o)
        }
        root.put("documents", docArray)

        return if (indent > 0) root.toString(indent) else root.toString()
    }

    companion object {
        fun fromJsonString(jsonString: String): CashTrailBackupData {
            val root = JSONObject(jsonString)
            val backupVersion = root.optInt("backupVersion", 1)
            val appVersion = root.optString("appVersion", "5.0")
            val exportedAt = root.optLong("exportedAt", System.currentTimeMillis())
            val exportDateString = root.optString("exportDateString", "")
            val userEmail = root.optString("userEmail", "")

            val parsedAccounts = mutableListOf<Account>()
            val accArray = root.optJSONArray("accounts")
            if (accArray != null) {
                for (i in 0 until accArray.length()) {
                    val o = accArray.getJSONObject(i)
                    parsedAccounts.add(
                        Account(
                            id = o.optString("id", ""),
                            userId = userEmail,
                            name = o.optString("name", "Account"),
                            type = o.optString("type", AccountType.BANK.name),
                            balance = o.optDouble("balance", 0.0),
                            creditLimit = o.optDouble("creditLimit", 0.0),
                            statementDay = o.optInt("statementDay", 0),
                            dueDay = o.optInt("dueDay", 0),
                            colorHex = o.optString("colorHex", "#1E88E5"),
                            institution = o.optString("institution", ""),
                            notes = o.optString("notes", "")
                        )
                    )
                }
            }

            val parsedTransactions = mutableListOf<Transaction>()
            val txArray = root.optJSONArray("transactions")
            if (txArray != null) {
                for (i in 0 until txArray.length()) {
                    val o = txArray.getJSONObject(i)
                    val sec = o.optLong("dateTimestampSec", System.currentTimeMillis() / 1000)
                    parsedTransactions.add(
                        Transaction(
                            id = o.optString("id", ""),
                            userId = userEmail,
                            type = o.optString("type", "EXPENSE"),
                            amount = o.optDouble("amount", 0.0),
                            accountId = o.optString("accountId", ""),
                            destinationAccountId = o.optString("destinationAccountId", "").takeIf { it.isNotBlank() },
                            category = o.optString("category", "General"),
                            note = o.optString("note", ""),
                            invoiceFileName = o.optString("invoiceFileName", ""),
                            invoiceUri = o.optString("invoiceUri", ""),
                            date = Timestamp(sec, 0)
                        )
                    )
                }
            }

            val parsedInvestments = mutableListOf<Investment>()
            val invArray = root.optJSONArray("investments")
            if (invArray != null) {
                for (i in 0 until invArray.length()) {
                    val o = invArray.getJSONObject(i)
                    val sec = o.optLong("dateTimestampSec", System.currentTimeMillis() / 1000)
                    parsedInvestments.add(
                        Investment(
                            id = o.optString("id", ""),
                            userId = userEmail,
                            assetName = o.optString("assetName", "Investment"),
                            assetType = o.optString("assetType", "MUTUAL_FUNDS"),
                            action = o.optString("action", "CONTRIBUTION"),
                            amount = o.optDouble("amount", 0.0),
                            sourceAccountId = o.optString("sourceAccountId", "").takeIf { it.isNotBlank() },
                            note = o.optString("note", ""),
                            date = Timestamp(sec, 0)
                        )
                    )
                }
            }

            val parsedDocuments = mutableListOf<PersonalDocument>()
            val docArray = root.optJSONArray("documents")
            if (docArray != null) {
                for (i in 0 until docArray.length()) {
                    val o = docArray.getJSONObject(i)
                    parsedDocuments.add(
                        PersonalDocument(
                            id = o.optString("id", ""),
                            userId = userEmail,
                            name = o.optString("name", "Document"),
                            category = o.optString("category", "IDENTITY"),
                            documentNumber = o.optString("documentNumber", ""),
                            issuer = o.optString("issuer", ""),
                            expiryDate = o.optString("expiryDate", ""),
                            issueDate = o.optString("issueDate", ""),
                            notes = o.optString("notes", ""),
                            fileUri = o.optString("fileUri", ""),
                            fileName = o.optString("fileName", ""),
                            colorHex = o.optString("colorHex", "#1E88E5"),
                            isFavorite = o.optBoolean("isFavorite", false)
                        )
                    )
                }
            }

            val prefsObj = root.optJSONObject("preferences")
            val parsedPrefs = if (prefsObj != null) {
                AppPreferences(
                    currencySymbol = prefsObj.optString("currencySymbol", "₹"),
                    showDecimals = prefsObj.optBoolean("showDecimals", true),
                    maskBalances = prefsObj.optBoolean("maskBalances", false),
                    pastelStyle = prefsObj.optString("pastelStyle", "SOFT"),
                    compactSpacing = prefsObj.optBoolean("compactSpacing", false),
                    salaryCycleStartDay = prefsObj.optInt("salaryCycleStartDay", 1),
                    defaultEntryType = prefsObj.optString("defaultEntryType", "EXPENSE"),
                    messageTrackingEnabled = prefsObj.optBoolean("messageTrackingEnabled", true),
                    messageTrackingDays = prefsObj.optInt("messageTrackingDays", 15)
                )
            } else AppPreferences()

            val stats = BackupStats(
                totalAccounts = parsedAccounts.size,
                totalTransactions = parsedTransactions.size,
                totalInvestments = parsedInvestments.size,
                totalDocuments = parsedDocuments.size,
                totalNetBalance = parsedAccounts.sumOf { it.balance },
                totalInvestedCapital = parsedInvestments.sumOf { it.amount }
            )

            return CashTrailBackupData(
                backupVersion = backupVersion,
                appVersion = appVersion,
                exportedAt = exportedAt,
                exportDateString = exportDateString,
                userEmail = userEmail,
                stats = stats,
                accounts = parsedAccounts,
                transactions = parsedTransactions,
                investments = parsedInvestments,
                documents = parsedDocuments,
                preferences = parsedPrefs
            )
        }
    }
}
