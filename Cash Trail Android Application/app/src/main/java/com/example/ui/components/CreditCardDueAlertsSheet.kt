package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Payment
import androidx.compose.material.icons.filled.Sms
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.Account
import com.example.data.model.Transaction
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900
import com.example.ui.util.CurrencyUtils
import com.example.ui.util.CreditCardStatementCalculator
import com.example.ui.util.CreditCardStatementSummary
import java.util.Calendar

data class CardDueInfo(
    val account: Account,
    val statementSummary: CreditCardStatementSummary,
    val dueDay: Int,
    val daysUntilDue: Int,
    val isDueWithinWeek: Boolean,
    val isOverdue: Boolean,
    val isPaid: Boolean
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreditCardDueAlertsSheet(
    creditCardAccounts: List<Account>,
    transactions: List<Transaction> = emptyList(),
    detectedBills: List<com.example.data.model.CreditCardBillAlert> = emptyList(),
    currencySymbol: String = "₹",
    onDismiss: () -> Unit,
    onPayCard: (Account) -> Unit,
    onPayDetectedBill: ((com.example.data.model.CreditCardBillAlert) -> Unit)? = null
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    val now = Calendar.getInstance()
    val today = now.get(Calendar.DAY_OF_MONTH)
    val daysInMonth = now.getActualMaximum(Calendar.DAY_OF_MONTH)

    val cardDueList: List<CardDueInfo> = creditCardAccounts
        .filter { it.dueDay > 0 || it.balance > 0 }
        .map { card ->
            val stmtSummary = CreditCardStatementCalculator.calculateStatementSummary(card, transactions, now)
            val dueDay = if (card.dueDay > 0) card.dueDay else stmtSummary.dueDay
            val isPaid = stmtSummary.statementDueAmount <= 0.0 && stmtSummary.totalOutstanding <= 0.0
            val (days, isOverdue) = if (dueDay > 0) {
                if (dueDay >= today) {
                    Pair(dueDay - today, false)
                } else {
                    val pastDays = today - dueDay
                    if (!isPaid && pastDays in 1..7) {
                        Pair(0, true)
                    } else {
                        Pair((daysInMonth - today) + dueDay, false)
                    }
                }
            } else {
                Pair(999, false)
            }
            CardDueInfo(
                account = card,
                statementSummary = stmtSummary,
                dueDay = dueDay,
                daysUntilDue = days,
                isDueWithinWeek = !isPaid && (days <= 7 || isOverdue),
                isOverdue = isOverdue,
                isPaid = isPaid
            )
        }
        .sortedWith(compareBy({ !it.isDueWithinWeek }, { it.isPaid }, { it.daysUntilDue }))

    val dueWithinWeek = cardDueList.filter { it.isDueWithinWeek }
    val dueLater = cardDueList.filter { !it.isDueWithinWeek }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
        modifier = Modifier.testTag("credit_card_due_alerts_sheet")
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(if (dueWithinWeek.isNotEmpty()) Color(0xFFFEE2E2) else Color(0xFFDCFCE7)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (dueWithinWeek.isNotEmpty()) Icons.Default.NotificationsActive else Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = if (dueWithinWeek.isNotEmpty()) Color(0xFFDC2626) else Color(0xFF16A34A),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Card Payment Dues",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = Slate900
                        )
                        Text(
                            text = if (dueWithinWeek.isNotEmpty())
                                "${dueWithinWeek.size} card bill${if (dueWithinWeek.size > 1) "s" else ""} due within 7 days"
                            else
                                "No bills due within a week",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (dueWithinWeek.isNotEmpty()) Color(0xFFDC2626) else Slate500,
                            fontWeight = if (dueWithinWeek.isNotEmpty()) FontWeight.SemiBold else FontWeight.Normal
                        )
                    }
                }

                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.testTag("close_due_alerts_button")
                ) {
                    Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Slate600)
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Explanation callout
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = Color(0xFFF8FAFC),
                border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.CreditCard,
                        contentDescription = null,
                        tint = Slate600,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Alerts are triggered within 7 days of due date so you can check balances only when needed without dashboard clutter.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate600,
                        lineHeight = 16.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Detected Statements & Bills from Bank SMS
            val unPaidDetectedBills = detectedBills.filter { !it.isPaid }
            if (unPaidDetectedBills.isNotEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "DETECTED STATEMENTS & BILLS (SMS)",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFDC2626),
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = Color(0xFFFEE2E2)
                    ) {
                        Text(
                            text = "${unPaidDetectedBills.size} New Statement${if (unPaidDetectedBills.size > 1) "s" else ""}",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFDC2626),
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))

                unPaidDetectedBills.forEach { bill ->
                    val cal = Calendar.getInstance().apply { timeInMillis = bill.dueDate }
                    val monthNames = arrayOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
                    val dueString = "${cal.get(Calendar.DAY_OF_MONTH)} ${monthNames[cal.get(Calendar.MONTH)]}"

                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF7ED)),
                        border = androidx.compose.foundation.BorderStroke(1.5.dp, Color(0xFFFDBA74)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.Sms,
                                        contentDescription = null,
                                        tint = Color(0xFFEA580C),
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            text = bill.cardName,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = Slate900
                                        )
                                        Text(
                                            text = "Card ending in ••${bill.lastFourDigits} • via ${bill.source}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate500
                                        )
                                    }
                                }

                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = Color(0xFFFFEDD5)
                                ) {
                                    Text(
                                        text = "Due $dueString",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Color(0xFFC2410C),
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "Total Amount Due",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Slate500
                                    )
                                    Text(
                                        text = CurrencyUtils.formatAmount(bill.totalDue, currencySymbol, true, false),
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFFDC2626)
                                    )
                                    bill.minDue?.let { minD ->
                                        Text(
                                            text = "Min Due: ${CurrencyUtils.formatAmount(minD, currencySymbol, true, false)}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate500,
                                            fontSize = 11.sp
                                        )
                                    }
                                }

                                Button(
                                    onClick = {
                                        onDismiss()
                                        onPayDetectedBill?.invoke(bill)
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFEA580C)),
                                    shape = RoundedCornerShape(10.dp),
                                    modifier = Modifier.testTag("pay_detected_bill_${bill.id}")
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Payment,
                                        contentDescription = null,
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text("Pay Statement", style = MaterialTheme.typography.labelSmall)
                                }
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Active Reminders Due Within 7 Days
            if (dueWithinWeek.isNotEmpty()) {
                Text(
                    text = "ACTION REQUIRED • DUE IN ≤ 7 DAYS",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFDC2626),
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(8.dp))

                dueWithinWeek.forEach { item ->
                    val card = item.account
                    val days = item.daysUntilDue

                    val badgeBg = when {
                        item.isOverdue -> Color(0xFFFEE2E2)
                        days == 0 -> Color(0xFFFEE2E2)
                        days == 1 -> Color(0xFFFEF3C7)
                        else -> Color(0xFFFEF9C3)
                    }
                    val badgeText = when {
                        item.isOverdue -> Color(0xFFDC2626)
                        days == 0 -> Color(0xFFDC2626)
                        days == 1 -> Color(0xFFD97706)
                        else -> Color(0xFFB45309)
                    }
                    val badgeLabel = when {
                        item.isOverdue -> "Overdue! (${card.dueDay}th)"
                        days == 0 -> "Due Today!"
                        days == 1 -> "Due Tomorrow!"
                        else -> "Due in $days days (${card.dueDay}th)"
                    }

                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        border = androidx.compose.foundation.BorderStroke(1.5.dp, badgeText.copy(alpha = 0.5f)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.CreditCard,
                                        contentDescription = null,
                                        tint = badgeText,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            text = card.name,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = Slate900
                                        )
                                        if (card.institution.isNotBlank()) {
                                            Text(
                                                text = card.institution,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Slate500
                                            )
                                        }
                                    }
                                }

                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = badgeBg
                                ) {
                                    Text(
                                        text = badgeLabel,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = badgeText,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f, fill = false)) {
                                    val stmt = item.statementSummary
                                    val dueAmt = if (stmt.statementDueAmount > 0) stmt.statementDueAmount else stmt.totalOutstanding
                                    Text(
                                        text = if (stmt.statementDueAmount > 0) "Statement Due (to pay by ${stmt.formattedDueDate})" else "Outstanding Balance",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if (stmt.statementDueAmount > 0) Color(0xFFDC2626) else Slate500,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(
                                        text = CurrencyUtils.formatAmount(dueAmt, currencySymbol, true, false),
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = if (dueAmt > 0) PastelExpenseText else Slate900
                                    )
                                    if (stmt.unbilledAmount > 0) {
                                        Text(
                                            text = "Total O/S: ${CurrencyUtils.formatAmount(stmt.totalOutstanding, currencySymbol, true, false)} • Unbilled: ${CurrencyUtils.formatAmount(stmt.unbilledAmount, currencySymbol, true, false)}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate600,
                                            fontSize = 11.sp
                                        )
                                    }
                                    if (card.statementDay > 0) {
                                        Text(
                                            text = "Statement Cutoff: ${stmt.formattedStatementDate}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Slate500,
                                            fontSize = 10.5.sp
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.width(8.dp))

                                Button(
                                    onClick = {
                                        onDismiss()
                                        onPayCard(card)
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                                    shape = RoundedCornerShape(10.dp),
                                    modifier = Modifier.testTag("pay_card_button_${card.id}")
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Payment,
                                        contentDescription = null,
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    val payLabel = if (item.statementSummary.statementDueAmount > 0) "Pay Bill" else "Pay Card"
                                    Text(payLabel, style = MaterialTheme.typography.labelSmall)
                                }
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            } else {
                // All Clear Banner
                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFF0FDF4)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFBBF7D0)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = Color(0xFF16A34A),
                            modifier = Modifier.size(36.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "No Payments Due This Week",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF15803D)
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "All your credit cards are clear for the next 7 days. You will be alerted right here 1 week prior to any upcoming bill due dates.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF166534),
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Cards Due Later (More than 7 days away)
            if (dueLater.isNotEmpty()) {
                Text(
                    text = "UPCOMING LATER THIS MONTH (> 7 DAYS)",
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate500,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(8.dp))

                dueLater.forEach { item ->
                    val card = item.account
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 14.dp, vertical = 10.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f, fill = false)) {
                                Text(
                                    text = card.name,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Slate900
                                )
                                val stmt = item.statementSummary
                                Text(
                                    text = if (item.isPaid) "Due on ${stmt.formattedDueDate} • Bill Paid" else "Due on ${stmt.formattedDueDate} • in ${item.daysUntilDue} days",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (item.isPaid) Color(0xFF16A34A) else Slate500
                                )
                                if (stmt.unbilledAmount > 0) {
                                    Text(
                                        text = "Total O/S: ${CurrencyUtils.formatAmount(stmt.totalOutstanding, currencySymbol, true, false)} • Unbilled: ${CurrencyUtils.formatAmount(stmt.unbilledAmount, currencySymbol, true, false)}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Slate600,
                                        fontSize = 10.sp
                                    )
                                }
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                val stmt = item.statementSummary
                                val displayAmt = if (stmt.statementDueAmount > 0) stmt.statementDueAmount else stmt.totalOutstanding
                                Text(
                                    text = if (item.isPaid) "₹0.00" else CurrencyUtils.formatAmount(displayAmt, currencySymbol, true, false),
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = if (item.isPaid) Color(0xFF16A34A) else Slate700
                                )
                                if (!item.isPaid && stmt.statementDueAmount > 0) {
                                    Text(
                                        text = "Statement Due",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Color(0xFFDC2626),
                                        fontSize = 9.5.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }
                    }
                }
            }

            if (cardDueList.isEmpty()) {
                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "No Credit Cards Configured",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Slate900
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Add a credit card with a payment due day in Accounts to receive automatic 7-day payment reminders here.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
