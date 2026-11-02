package com.example.data.scanner

import android.content.Context
import android.content.pm.PackageManager
import android.provider.Telephony
import android.util.Log
import androidx.core.content.ContextCompat
import com.example.data.model.BankNotification
import com.example.data.model.CreditCardBillAlert
import com.example.data.model.NotificationSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Bank Message (SMS) Scanner
 * Scans SMS messages from the user's device inbox for incoming bank debit,
 * credit, and credit card statement alerts within a configurable number of days.
 * Note: Email tracking has been completely removed as requested.
 */
object BankMessageScanner {
    private const val TAG = "BankMessageScanner"

    suspend fun scanMessages(
        context: Context,
        daysToTrack: Int = 15,
        currencySymbol: String = "₹"
    ): Pair<List<BankNotification>, List<CreditCardBillAlert>> = withContext(Dispatchers.IO) {
        val notifications = mutableListOf<BankNotification>()
        val dueAlerts = mutableListOf<CreditCardBillAlert>()

        val now = System.currentTimeMillis()
        val daysSafe = daysToTrack.coerceAtLeast(1)
        val cutoffMillis = now - (daysSafe.toLong() * 24L * 60L * 60L * 1000L)

        // Read SMS from device inbox if permission is granted
        val hasSmsPermission = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.READ_SMS
        ) == PackageManager.PERMISSION_GRANTED

        var smsCount = 0
        if (hasSmsPermission) {
            try {
                val cursor = context.contentResolver.query(
                    Telephony.Sms.Inbox.CONTENT_URI,
                    arrayOf(
                        Telephony.Sms.Inbox.ADDRESS,
                        Telephony.Sms.Inbox.BODY,
                        Telephony.Sms.Inbox.DATE
                    ),
                    "${Telephony.Sms.Inbox.DATE} >= ?",
                    arrayOf(cutoffMillis.toString()),
                    "${Telephony.Sms.Inbox.DATE} DESC"
                )

                cursor?.use {
                    val addressIdx = it.getColumnIndex(Telephony.Sms.Inbox.ADDRESS)
                    val bodyIdx = it.getColumnIndex(Telephony.Sms.Inbox.BODY)
                    val dateIdx = it.getColumnIndex(Telephony.Sms.Inbox.DATE)

                    while (it.moveToNext()) {
                        val address = if (addressIdx != -1) it.getString(addressIdx) ?: "Bank" else "Bank"
                        val body = if (bodyIdx != -1) it.getString(bodyIdx) ?: "" else ""
                        val date = if (dateIdx != -1) it.getLong(dateIdx) else now

                        val parsedNotification = FinancialMessageParser.parseMessage(
                            rawBody = body,
                            sender = address,
                            timestamp = date,
                            source = NotificationSource.SMS,
                            currencySymbol = currencySymbol
                        )
                        if (parsedNotification != null) {
                            notifications.add(parsedNotification)
                            smsCount++
                        }

                        val parsedBill = FinancialMessageParser.parseBillAlert(
                            rawBody = body,
                            sender = address,
                            timestamp = date,
                            source = NotificationSource.SMS
                        )
                        if (parsedBill != null) {
                            dueAlerts.add(parsedBill)
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error scanning SMS inbox", e)
            }
        }

        val sortedNotifications = notifications.sortedByDescending { it.timestamp }
        val sortedDues = dueAlerts.sortedBy { it.dueDate }

        Pair(sortedNotifications, sortedDues)
    }

    // Backward compatibility helper
    suspend fun scanLast15Days(
        context: Context,
        userEmail: String = "",
        currencySymbol: String = "₹"
    ): Pair<List<BankNotification>, List<CreditCardBillAlert>> {
        return scanMessages(context, daysToTrack = 15, currencySymbol = currencySymbol)
    }
}
