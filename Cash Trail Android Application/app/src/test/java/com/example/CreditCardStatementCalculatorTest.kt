package com.example

import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.ui.util.CreditCardStatementCalculator
import com.google.firebase.Timestamp
import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.Calendar
import java.util.Date

class CreditCardStatementCalculatorTest {

    @Test
    fun testUserScenario_statementCutoffCalculatesCorrectStatementAndUnbilledOS() {
        // User example:
        // 200rs trns made on 10/12
        // Statement date is 12/12
        // 500 trns made on 13/12
        // due date of credit card is 30/12
        // then total o/s will be 700
        // statement o/s will be 200

        // Build calendar for 15/12/2026 (between statement date 12/12 and due date 30/12)
        val nowCal = Calendar.getInstance().apply {
            set(2026, Calendar.DECEMBER, 15, 12, 0, 0)
        }

        val card = Account(
            id = "cc_1",
            userId = "user_1",
            name = "HDFC Regalia",
            type = AccountType.CREDIT_CARD.name,
            balance = 700.0, // total outstanding balance
            creditLimit = 50000.0,
            statementDay = 12,
            dueDay = 30
        )

        val tx1Date = Calendar.getInstance().apply {
            set(2026, Calendar.DECEMBER, 10, 10, 0, 0)
        }.time

        val tx2Date = Calendar.getInstance().apply {
            set(2026, Calendar.DECEMBER, 13, 10, 0, 0)
        }.time

        val transactions = listOf(
            Transaction(
                id = "tx1",
                userId = "user_1",
                type = TransactionType.EXPENSE.name,
                amount = 200.0,
                accountId = "cc_1",
                date = Timestamp(tx1Date),
                category = "Groceries"
            ),
            Transaction(
                id = "tx2",
                userId = "user_1",
                type = TransactionType.EXPENSE.name,
                amount = 500.0,
                accountId = "cc_1",
                date = Timestamp(tx2Date),
                category = "Shopping"
            )
        )

        val summary = CreditCardStatementCalculator.calculateStatementSummary(
            card = card,
            transactions = transactions,
            now = nowCal
        )

        assertEquals(700.0, summary.totalOutstanding, 0.001)
        assertEquals(200.0, summary.statementDueAmount, 0.001)
        assertEquals(500.0, summary.unbilledAmount, 0.001)
        assertEquals(15, summary.daysUntilDue) // from 15th to 30th
    }
}
