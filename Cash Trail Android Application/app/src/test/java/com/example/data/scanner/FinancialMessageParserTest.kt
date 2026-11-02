package com.example.data.scanner

import com.example.data.model.NotificationSource
import com.example.data.model.NotificationType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FinancialMessageParserTest {

    @Test
    fun parseMessage_debitSms_extractsAmountAndMerchant() {
        val body = "Dear Customer, INR 480.00 debited from A/c ending 8912 at Swiggy UPI on 17-Oct-26. Info: UPI/389102/Swiggy. Bal: INR 24,120.00."
        val notif = FinancialMessageParser.parseMessage(
            rawBody = body,
            sender = "VM-HDFCBK",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = "₹"
        )

        assertNotNull(notif)
        assertEquals(NotificationType.DEBIT, notif?.type)
        assertEquals(480.0, notif?.amount ?: 0.0, 0.001)
        assertEquals("8912", notif?.accountSuffix)
        assertEquals("Food & Dining", notif?.suggestedCategory)
    }

    @Test
    fun parseMessage_creditSalaryMessage_extractsCreditDetails() {
        val body = "Dear Customer, Salary credited with INR 82,500.00 to your A/c ending in 8912 on 14-Oct-2026 by TECH CORP INFOTECH PVT LTD."
        val notif = FinancialMessageParser.parseMessage(
            rawBody = body,
            sender = "AD-ICICIB",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = "₹"
        )

        assertNotNull(notif)
        assertEquals(NotificationType.CREDIT, notif?.type)
        assertEquals(82500.0, notif?.amount ?: 0.0, 0.001)
        assertEquals("8912", notif?.accountSuffix)
        assertEquals("Salary", notif?.suggestedCategory)
    }

    @Test
    fun parseBillAlert_creditCardStatement_extractsTotalDueAndDueDate() {
        val body = "Your HDFC Credit Card statement for Card ending xx4102 has been generated. Total Amount Due: INR 14,350.00. Payment Due Date: 21st Oct 2026."
        val bill = FinancialMessageParser.parseBillAlert(
            rawBody = body,
            sender = "VM-HDFCBK",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS
        )

        assertNotNull(bill)
        assertEquals("4102", bill?.lastFourDigits)
        assertEquals(14350.0, bill?.totalDue ?: 0.0, 0.001)
        assertTrue((bill?.dueDate ?: 0L) > System.currentTimeMillis())
    }

    @Test
    fun parseMessage_uncommaSeparatedAmounts_extractsFullAmountCorrectly() {
        // Test Rs. 3500 (the exact bug reported by user)
        val body1 = "Dear Customer, Rs. 3500 debited from A/c ending in 8912 at Amazon on 17-Oct-26."
        val notif1 = FinancialMessageParser.parseMessage(
            rawBody = body1,
            sender = "HDFCBK",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = "₹"
        )
        assertNotNull(notif1)
        assertEquals(3500.0, notif1?.amount ?: 0.0, 0.001)

        // Test Rs. 3,500 (with comma)
        val body2 = "Dear Customer, Rs. 3,500 debited from A/c ending in 8912 at Amazon on 17-Oct-26."
        val notif2 = FinancialMessageParser.parseMessage(
            rawBody = body2,
            sender = "HDFCBK",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = "₹"
        )
        assertNotNull(notif2)
        assertEquals(3500.0, notif2?.amount ?: 0.0, 0.001)

        // Test fallback format with 3500 debited
        val body3 = "Your account xx4102 has 3500 debited towards Grocery Mart."
        val notif3 = FinancialMessageParser.parseMessage(
            rawBody = body3,
            sender = "ICICIB",
            timestamp = System.currentTimeMillis(),
            source = NotificationSource.SMS,
            currencySymbol = "₹"
        )
        assertNotNull(notif3)
        assertEquals(3500.0, notif3?.amount ?: 0.0, 0.001)
    }
}
