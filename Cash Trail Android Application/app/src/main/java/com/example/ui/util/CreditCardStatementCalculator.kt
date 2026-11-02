package com.example.ui.util

import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

data class CreditCardStatementSummary(
    val accountId: String,
    val cardName: String,
    val institution: String,
    val totalOutstanding: Double,
    val statementDueAmount: Double,
    val unbilledAmount: Double,
    val statementDay: Int,
    val dueDay: Int,
    val statementDateMillis: Long,
    val dueDateMillis: Long,
    val daysUntilDue: Int,
    val isDueWithinWeek: Boolean,
    val isOverdue: Boolean,
    val isPaid: Boolean
) {
    val formattedStatementDate: String
        get() = if (statementDateMillis > 0) {
            SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(statementDateMillis))
        } else if (statementDay > 0) {
            "${statementDay}th"
        } else "Not Set"

    val formattedDueDate: String
        get() = if (dueDateMillis > 0) {
            SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(dueDateMillis))
        } else if (dueDay > 0) {
            "${dueDay}th"
        } else "Not Set"
}

object CreditCardStatementCalculator {

    /**
     * Determines the active statement cutoff date and target due date for a credit card.
     */
    fun getStatementAndDueDate(
        statementDay: Int,
        dueDay: Int,
        now: Calendar = Calendar.getInstance()
    ): Pair<Calendar, Calendar> {
        val todayDay = now.get(Calendar.DAY_OF_MONTH)
        val todayMonth = now.get(Calendar.MONTH)
        val todayYear = now.get(Calendar.YEAR)

        val targetDueDate = Calendar.getInstance().apply {
            set(Calendar.YEAR, todayYear)
            set(Calendar.MONTH, todayMonth)
            val maxDays = getActualMaximum(Calendar.DAY_OF_MONTH)
            set(Calendar.DAY_OF_MONTH, dueDay.coerceIn(1, maxDays))
            set(Calendar.HOUR_OF_DAY, 23)
            set(Calendar.MINUTE, 59)
            set(Calendar.SECOND, 59)
            set(Calendar.MILLISECOND, 999)
        }

        if (dueDay > statementDay) {
            // Statement was generated in the same month as the due date (e.g., Stmt 12th, Due 30th)
            if (todayDay > dueDay) {
                targetDueDate.add(Calendar.MONTH, 1)
                val maxDays = targetDueDate.getActualMaximum(Calendar.DAY_OF_MONTH)
                targetDueDate.set(Calendar.DAY_OF_MONTH, dueDay.coerceIn(1, maxDays))
            }
            val statementDate = Calendar.getInstance().apply {
                set(Calendar.YEAR, targetDueDate.get(Calendar.YEAR))
                set(Calendar.MONTH, targetDueDate.get(Calendar.MONTH))
                val maxDays = getActualMaximum(Calendar.DAY_OF_MONTH)
                set(Calendar.DAY_OF_MONTH, statementDay.coerceIn(1, maxDays))
                set(Calendar.HOUR_OF_DAY, 23)
                set(Calendar.MINUTE, 59)
                set(Calendar.SECOND, 59)
                set(Calendar.MILLISECOND, 999)
            }
            return Pair(statementDate, targetDueDate)
        } else {
            // Due date is early in the following month (e.g., Stmt 20th, Due 5th next month)
            if (todayDay > dueDay && todayDay < statementDay) {
                // Between 5th and 20th -> target is next month's 5th
                targetDueDate.add(Calendar.MONTH, 1)
                val maxDays = targetDueDate.getActualMaximum(Calendar.DAY_OF_MONTH)
                targetDueDate.set(Calendar.DAY_OF_MONTH, dueDay.coerceIn(1, maxDays))
            } else if (todayDay >= statementDay) {
                // Past 20th -> target is next month's 5th
                targetDueDate.add(Calendar.MONTH, 1)
                val maxDays = targetDueDate.getActualMaximum(Calendar.DAY_OF_MONTH)
                targetDueDate.set(Calendar.DAY_OF_MONTH, dueDay.coerceIn(1, maxDays))
            }

            // Statement was in the previous month relative to targetDueDate
            val statementDate = Calendar.getInstance().apply {
                set(Calendar.YEAR, targetDueDate.get(Calendar.YEAR))
                set(Calendar.MONTH, targetDueDate.get(Calendar.MONTH))
                add(Calendar.MONTH, -1)
                val maxDays = getActualMaximum(Calendar.DAY_OF_MONTH)
                set(Calendar.DAY_OF_MONTH, statementDay.coerceIn(1, maxDays))
                set(Calendar.HOUR_OF_DAY, 23)
                set(Calendar.MINUTE, 59)
                set(Calendar.SECOND, 59)
                set(Calendar.MILLISECOND, 999)
            }
            return Pair(statementDate, targetDueDate)
        }
    }

    /**
     * Calculates the Total Outstanding, Statement Due (Statement O/S), and Unbilled amount.
     *
     * Example:
     * 200rs transaction made on 10/12
     * Statement date is 12/12
     * 500rs transaction made on 13/12
     * Due date is 30/12
     *
     * Result:
     * Total O/S = 700rs
     * Statement O/S = 200rs (only transactions up to statement cutoff 12/12)
     * Unbilled = 500rs
     */
    fun calculateStatementSummary(
        card: Account,
        transactions: List<Transaction>,
        now: Calendar = Calendar.getInstance()
    ): CreditCardStatementSummary {
        val totalOS = card.balance.coerceAtLeast(0.0)
        val statementDay = card.statementDay
        val dueDay = card.dueDay

        if (totalOS <= 0.0) {
            return CreditCardStatementSummary(
                accountId = card.id,
                cardName = card.name,
                institution = card.institution,
                totalOutstanding = 0.0,
                statementDueAmount = 0.0,
                unbilledAmount = 0.0,
                statementDay = statementDay,
                dueDay = dueDay,
                statementDateMillis = 0L,
                dueDateMillis = 0L,
                daysUntilDue = 0,
                isDueWithinWeek = false,
                isOverdue = false,
                isPaid = true
            )
        }

        if (statementDay <= 0 || dueDay <= 0) {
            return CreditCardStatementSummary(
                accountId = card.id,
                cardName = card.name,
                institution = card.institution,
                totalOutstanding = totalOS,
                statementDueAmount = totalOS,
                unbilledAmount = 0.0,
                statementDay = statementDay,
                dueDay = dueDay,
                statementDateMillis = 0L,
                dueDateMillis = 0L,
                daysUntilDue = 0,
                isDueWithinWeek = totalOS > 0,
                isOverdue = false,
                isPaid = false
            )
        }

        val (statementCal, dueCal) = getStatementAndDueDate(statementDay, dueDay, now)
        val cutoffMillis = statementCal.timeInMillis
        val dueMillis = dueCal.timeInMillis

        // Calculate unbilled transactions (expenses made strictly AFTER statement cutoff)
        val unbilledExpenses = transactions.filter { tx ->
            val isCardExpense = (tx.type == TransactionType.EXPENSE.name && tx.accountId == card.id) ||
                    (tx.type == TransactionType.TRANSFER.name && tx.accountId == card.id)
            if (!isCardExpense) return@filter false

            val txMillis = tx.date?.toDate()?.time ?: (tx.createdAt?.toDate()?.time ?: 0L)
            txMillis > cutoffMillis
        }.sumOf { it.amount }

        // Statement O/S is total outstanding minus unbilled expenses (payments automatically reduce statement balance first)
        val statementOS = (totalOS - unbilledExpenses).coerceIn(0.0, totalOS)
        val unbilledOS = (totalOS - statementOS).coerceAtLeast(0.0)

        // Days calculation
        val today = now.get(Calendar.DAY_OF_MONTH)
        val daysInMonth = now.getActualMaximum(Calendar.DAY_OF_MONTH)
        val isPaid = statementOS <= 0.0 && totalOS <= 0.0

        val (daysUntilDue, isOverdue) = if (dueDay >= today) {
            Pair(dueDay - today, false)
        } else {
            val pastDays = today - dueDay
            if (!isPaid && pastDays in 1..7) {
                Pair(0, true)
            } else {
                Pair((daysInMonth - today) + dueDay, false)
            }
        }

        val isDueWithinWeek = (!isPaid && (daysUntilDue <= 7 || isOverdue))

        return CreditCardStatementSummary(
            accountId = card.id,
            cardName = card.name,
            institution = card.institution,
            totalOutstanding = totalOS,
            statementDueAmount = statementOS,
            unbilledAmount = unbilledOS,
            statementDay = statementDay,
            dueDay = dueDay,
            statementDateMillis = cutoffMillis,
            dueDateMillis = dueMillis,
            daysUntilDue = daysUntilDue,
            isDueWithinWeek = isDueWithinWeek,
            isOverdue = isOverdue,
            isPaid = isPaid
        )
    }

    fun calculateAllSummaries(
        cards: List<Account>,
        transactions: List<Transaction>,
        now: Calendar = Calendar.getInstance()
    ): List<CreditCardStatementSummary> {
        return cards
            .filter { it.type == AccountType.CREDIT_CARD.name }
            .map { calculateStatementSummary(it, transactions, now) }
    }
}
