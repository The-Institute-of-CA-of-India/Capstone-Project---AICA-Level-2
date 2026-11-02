package com.example.data.backup

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.core.content.FileProvider
import com.example.data.model.Account
import com.example.data.model.Investment
import com.example.data.model.PersonalDocument
import com.example.data.model.Transaction
import com.example.ui.settings.AppPreferences
import java.io.BufferedReader
import java.io.File
import java.io.FileOutputStream
import java.io.InputStreamReader
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object LocalBackupManager {
    private const val TAG = "LocalBackupManager"
    private const val PREFS_NAME = "cashtrail_backup_prefs"
    private const val KEY_LAST_BACKUP_DATE = "last_daily_backup_date"
    private const val KEY_LAST_BACKUP_TIMESTAMP = "last_daily_backup_timestamp"
    private const val KEY_LAST_BACKUP_RECORDS = "last_daily_backup_records"
    private const val KEY_LAST_BACKUP_FILE_NAME = "last_daily_backup_file_name"
    private const val MAX_BACKUPS_RETAINED = 14

    private fun getBackupsDir(context: Context): File {
        val dir = File(context.filesDir, "backups")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        return dir
    }

    fun buildBackupData(
        accounts: List<Account>,
        transactions: List<Transaction>,
        investments: List<Investment>,
        documents: List<PersonalDocument>,
        preferences: AppPreferences,
        userEmail: String
    ): CashTrailBackupData {
        val stats = BackupStats(
            totalAccounts = accounts.size,
            totalTransactions = transactions.size,
            totalInvestments = investments.size,
            totalDocuments = documents.size,
            totalNetBalance = accounts.sumOf { it.balance },
            totalInvestedCapital = investments.sumOf { it.amount }
        )
        return CashTrailBackupData(
            backupVersion = 1,
            appVersion = "5.0",
            exportedAt = System.currentTimeMillis(),
            exportDateString = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date()),
            userEmail = userEmail,
            stats = stats,
            accounts = accounts,
            transactions = transactions,
            investments = investments,
            documents = documents,
            preferences = preferences
        )
    }

    /**
     * Checks if a daily backup has already been performed today.
     * If not, writes CashTrail_Daily_Backup_YYYY-MM-DD.json and records metadata.
     */
    fun runDailyBackupIfNeeded(
        context: Context,
        accounts: List<Account>,
        transactions: List<Transaction>,
        investments: List<Investment>,
        documents: List<PersonalDocument>,
        preferences: AppPreferences,
        userEmail: String
    ): DailyBackupRecord? {
        val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        val dir = getBackupsDir(context)
        val dailyFile = File(dir, "CashTrail_Daily_Backup_$todayStr.json")

        // If today's backup file already exists and is not empty, return existing record
        if (dailyFile.exists() && dailyFile.length() > 0) {
            val totalRecords = accounts.size + transactions.size + investments.size + documents.size
            return DailyBackupRecord(
                fileName = dailyFile.name,
                dateString = todayStr,
                timestamp = dailyFile.lastModified(),
                fileSizeBytes = dailyFile.length(),
                totalRecords = totalRecords,
                filePath = dailyFile.absolutePath,
                isAutoDaily = true
            )
        }

        // Perform today's backup
        return try {
            val backupData = buildBackupData(accounts, transactions, investments, documents, preferences, userEmail)
            val jsonString = backupData.toJsonString(indent = 2)
            dailyFile.writeText(jsonString)

            val totalRecords = accounts.size + transactions.size + investments.size + documents.size
            val record = DailyBackupRecord(
                fileName = dailyFile.name,
                dateString = todayStr,
                timestamp = System.currentTimeMillis(),
                fileSizeBytes = dailyFile.length(),
                totalRecords = totalRecords,
                filePath = dailyFile.absolutePath,
                isAutoDaily = true
            )

            // Save to prefs
            val sp = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            sp.edit()
                .putString(KEY_LAST_BACKUP_DATE, todayStr)
                .putLong(KEY_LAST_BACKUP_TIMESTAMP, record.timestamp)
                .putInt(KEY_LAST_BACKUP_RECORDS, totalRecords)
                .putString(KEY_LAST_BACKUP_FILE_NAME, dailyFile.name)
                .apply()

            // Rotate older backups
            cleanupOldBackups(dir)

            Log.i(TAG, "Daily backup created successfully: ${dailyFile.name} (${record.formattedFileSize})")
            record
        } catch (e: Exception) {
            Log.e(TAG, "Failed to run daily backup", e)
            null
        }
    }

    /**
     * Forces creation of an instant backup right now.
     */
    fun createInstantBackup(
        context: Context,
        accounts: List<Account>,
        transactions: List<Transaction>,
        investments: List<Investment>,
        documents: List<PersonalDocument>,
        preferences: AppPreferences,
        userEmail: String
    ): DailyBackupRecord? {
        val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        val timeStampStr = SimpleDateFormat("HHmmss", Locale.US).format(Date())
        val dir = getBackupsDir(context)
        val file = File(dir, "CashTrail_Backup_${todayStr}_$timeStampStr.json")

        return try {
            val backupData = buildBackupData(accounts, transactions, investments, documents, preferences, userEmail)
            val jsonString = backupData.toJsonString(indent = 2)
            file.writeText(jsonString)

            val totalRecords = accounts.size + transactions.size + investments.size + documents.size
            val record = DailyBackupRecord(
                fileName = file.name,
                dateString = todayStr,
                timestamp = System.currentTimeMillis(),
                fileSizeBytes = file.length(),
                totalRecords = totalRecords,
                filePath = file.absolutePath,
                isAutoDaily = false
            )

            // Also update daily file if not present today
            val dailyFile = File(dir, "CashTrail_Daily_Backup_$todayStr.json")
            if (!dailyFile.exists()) {
                dailyFile.writeText(jsonString)
            }

            // Update prefs
            val sp = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            sp.edit()
                .putString(KEY_LAST_BACKUP_DATE, todayStr)
                .putLong(KEY_LAST_BACKUP_TIMESTAMP, record.timestamp)
                .putInt(KEY_LAST_BACKUP_RECORDS, totalRecords)
                .putString(KEY_LAST_BACKUP_FILE_NAME, file.name)
                .apply()

            cleanupOldBackups(dir)
            record
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create instant backup", e)
            null
        }
    }

    /**
     * Returns all local backup files stored on the device, newest first.
     */
    fun listLocalBackups(context: Context): List<DailyBackupRecord> {
        val dir = getBackupsDir(context)
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".json") } ?: return emptyList()

        return files.mapNotNull { file ->
            try {
                // Read summary or estimate
                val datePart = extractDateFromFileName(file.name)
                DailyBackupRecord(
                    fileName = file.name,
                    dateString = datePart,
                    timestamp = file.lastModified(),
                    fileSizeBytes = file.length(),
                    totalRecords = -1, // loaded on demand or cached
                    filePath = file.absolutePath,
                    isAutoDaily = file.name.contains("Daily")
                )
            } catch (e: Exception) {
                null
            }
        }.sortedByDescending { it.timestamp }
    }

    private fun extractDateFromFileName(name: String): String {
        return try {
            val regex = Regex("\\d{4}-\\d{2}-\\d{2}")
            val match = regex.find(name)
            match?.value ?: SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        } catch (_: Exception) {
            SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        }
    }

    private fun cleanupOldBackups(dir: File) {
        try {
            val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".json") } ?: return
            if (files.size > MAX_BACKUPS_RETAINED) {
                val sorted = files.sortedBy { it.lastModified() }
                val toDeleteCount = files.size - MAX_BACKUPS_RETAINED
                for (i in 0 until toDeleteCount) {
                    sorted[i].delete()
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed during cleanup of old backups", e)
        }
    }

    fun getLastBackupInfo(context: Context): DailyBackupRecord? {
        val sp = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val date = sp.getString(KEY_LAST_BACKUP_DATE, null) ?: return null
        val timestamp = sp.getLong(KEY_LAST_BACKUP_TIMESTAMP, 0L)
        val records = sp.getInt(KEY_LAST_BACKUP_RECORDS, 0)
        val fileName = sp.getString(KEY_LAST_BACKUP_FILE_NAME, "") ?: ""

        val file = File(getBackupsDir(context), fileName)
        val size = if (file.exists()) file.length() else 0L

        return DailyBackupRecord(
            fileName = if (fileName.isNotBlank()) fileName else "CashTrail_Daily_Backup_$date.json",
            dateString = date,
            timestamp = if (timestamp > 0) timestamp else file.lastModified(),
            fileSizeBytes = size,
            totalRecords = records,
            filePath = file.absolutePath,
            isAutoDaily = true
        )
    }

    /**
     * Writes the backup JSON into a user-selected URI (from ACTION_CREATE_DOCUMENT)
     * e.g., when the user selects Google Drive or external Downloads.
     */
    fun writeBackupToUri(context: Context, destinationUri: Uri, backupJson: String): Boolean {
        return try {
            context.contentResolver.openOutputStream(destinationUri)?.use { out ->
                out.write(backupJson.toByteArray(Charsets.UTF_8))
                out.flush()
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed writing backup to URI $destinationUri", e)
            false
        }
    }

    /**
     * Reads backup JSON from a user-selected URI (from ACTION_OPEN_DOCUMENT)
     */
    fun readBackupFromUri(context: Context, sourceUri: Uri): String? {
        return try {
            context.contentResolver.openInputStream(sourceUri)?.use { stream ->
                BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
                    reader.readText()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed reading backup from URI $sourceUri", e)
            null
        }
    }

    /**
     * Shares a backup file via Android Share Sheet so user can choose "Save to Drive"
     */
    fun shareBackupFile(context: Context, filePath: String): Boolean {
        val file = File(filePath)
        if (!file.exists()) return false

        return try {
            val contentUri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                file
            )
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "application/json"
                putExtra(Intent.EXTRA_STREAM, contentUri)
                putExtra(Intent.EXTRA_SUBJECT, "CashTrail Backup - ${file.name}")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            val chooser = Intent.createChooser(intent, "Save or Send Backup to Google Drive")
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(chooser)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to share backup file", e)
            false
        }
    }
}
