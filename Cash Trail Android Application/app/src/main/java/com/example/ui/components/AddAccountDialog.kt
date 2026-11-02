package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material3.Icon
import androidx.compose.ui.text.style.TextOverflow
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.SuggestedAccount
import com.example.ui.theme.PastelAmberBg
import com.example.ui.theme.PastelAmberBorder
import com.example.ui.theme.PastelAmberText
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeBorder
import com.example.ui.theme.PastelIncomeText
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900

private val colorChoices = listOf(
    "#2E7D32", // Green
    "#1E88E5", // Blue
    "#C62828", // Red
    "#6A1B9A", // Purple
    "#EF6C00", // Orange
    "#00838F", // Cyan
    "#37474F"  // Slate
)

@Composable
fun AddAccountDialog(
    existingAccount: Account? = null,
    suggestedAccounts: List<SuggestedAccount> = emptyList(),
    initialSuggestedAccount: SuggestedAccount? = null,
    onDismiss: () -> Unit,
    onSubmit: (
        name: String,
        type: AccountType,
        balance: Double,
        creditLimit: Double,
        colorHex: String,
        institution: String,
        notes: String,
        statementDay: Int,
        dueDay: Int
    ) -> Unit
) {
    var name by remember {
        mutableStateOf(existingAccount?.name ?: initialSuggestedAccount?.name ?: "")
    }
    var selectedType by remember {
        mutableStateOf(
            existingAccount?.let {
                try { AccountType.valueOf(it.type) } catch (e: Exception) { AccountType.BANK }
            } ?: initialSuggestedAccount?.type ?: AccountType.BANK
        )
    }
    var balanceText by remember {
        mutableStateOf(
            existingAccount?.let { if (it.balance == 0.0) "" else it.balance.toString() } ?: ""
        )
    }
    var creditLimitText by remember {
        mutableStateOf(
            existingAccount?.let { if (it.creditLimit == 0.0) "" else it.creditLimit.toString() }
                ?: if (initialSuggestedAccount?.type == AccountType.CREDIT_CARD) "50000" else ""
        )
    }
    var statementDayText by remember {
        mutableStateOf(
            existingAccount?.let { if (it.statementDay > 0) it.statementDay.toString() else "15" } ?: "15"
        )
    }
    var dueDayText by remember {
        mutableStateOf(
            existingAccount?.let { if (it.dueDay > 0) it.dueDay.toString() else "5" } ?: "5"
        )
    }
    var institution by remember {
        mutableStateOf(existingAccount?.institution ?: initialSuggestedAccount?.institution ?: "")
    }
    var notes by remember {
        mutableStateOf(existingAccount?.notes ?: initialSuggestedAccount?.reason ?: "")
    }
    var selectedColor by remember {
        mutableStateOf(
            existingAccount?.colorHex?.takeIf { it.isNotBlank() }
                ?: if (initialSuggestedAccount?.type == AccountType.CREDIT_CARD) "#C62828" else colorChoices.first()
        )
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                if (existingAccount != null) "Edit Account" else "Add Financial Account",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Slate900
            )
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
            ) {
                // If there are suggested accounts detected from messages and not editing existing
                if (existingAccount == null && suggestedAccounts.isNotEmpty()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 16.dp)
                            .background(PastelAmberBg, RoundedCornerShape(16.dp))
                            .border(1.dp, PastelAmberBorder, RoundedCornerShape(16.dp))
                            .padding(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = PastelAmberBorder,
                                modifier = Modifier.size(24.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.ElectricBolt,
                                        contentDescription = null,
                                        tint = PastelAmberText,
                                        modifier = Modifier.size(13.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "SUGGESTED FROM MESSAGES",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = PastelAmberText,
                                    letterSpacing = 0.8.sp,
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = "Tap to auto-fill account details",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate600,
                                    fontSize = 11.sp
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        // Horizontally scrollable row with proper spacing and chips
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            suggestedAccounts.forEach { sa ->
                                val isSelected = name == sa.name
                                val isCard = sa.type == AccountType.CREDIT_CARD
                                val chipBorder = if (isSelected) PastelIncomeBorder else Slate200
                                val chipBg = if (isSelected) PastelIncomeBg else Color.White
                                val chipTextColor = if (isSelected) PastelIncomeText else Slate900
                                val chipIconColor = if (isSelected) PastelIncomeText else (if (isCard) PastelExpenseText else PastelTransferText)

                                Surface(
                                    shape = RoundedCornerShape(10.dp),
                                    color = chipBg,
                                    border = BorderStroke(1.dp, chipBorder),
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(10.dp))
                                        .clickable {
                                            name = sa.name
                                            selectedType = sa.type
                                            institution = sa.institution
                                            notes = sa.reason
                                            if (sa.type == AccountType.CREDIT_CARD && creditLimitText.isBlank()) {
                                                creditLimitText = "50000"
                                            }
                                        }
                                        .testTag("apply_suggested_chip_${sa.id}")
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(
                                            imageVector = if (isSelected) {
                                                Icons.Default.CheckCircle
                                            } else if (isCard) {
                                                Icons.Default.CreditCard
                                            } else {
                                                Icons.Default.AccountBalance
                                            },
                                            contentDescription = null,
                                            tint = chipIconColor,
                                            modifier = Modifier.size(15.dp)
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Column {
                                            Text(
                                                text = sa.name,
                                                style = MaterialTheme.typography.labelSmall,
                                                fontWeight = FontWeight.Bold,
                                                color = chipTextColor,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis,
                                                fontSize = 12.sp
                                            )
                                            if (sa.institution.isNotBlank()) {
                                                Text(
                                                    text = sa.institution,
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = if (isSelected) PastelIncomeText else Slate500,
                                                    fontSize = 10.sp,
                                                    maxLines = 1
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                // Type selector
                Text(
                    "Account Type",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    AccountType.entries.forEach { type ->
                        val isSelected = selectedType == type
                        Surface(
                            shape = RoundedCornerShape(10.dp),
                            color = if (isSelected) Slate900 else Slate100,
                            modifier = Modifier
                                .weight(1f)
                                .clickable { selectedType = type }
                                .padding(vertical = 2.dp)
                                .testTag("account_type_pill_${type.name.lowercase()}")
                        ) {
                            Text(
                                text = when (type) {
                                    AccountType.BANK -> "Bank"
                                    AccountType.CREDIT_CARD -> "Card"
                                    AccountType.DIGITAL_WALLET -> "Wallet"
                                    AccountType.CASH -> "Cash"
                                    AccountType.PERSONAL -> "Personal"
                                },
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) Color.White else Slate700,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                modifier = Modifier.padding(vertical = 8.dp, horizontal = 2.dp),
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                                maxLines = 1
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Account Name
                Text(
                    if (selectedType == AccountType.PERSONAL) "Personal Account Name" else "Account Label",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    placeholder = {
                        Text(
                            when (selectedType) {
                                AccountType.PERSONAL -> "e.g. My Personal Fund, Emergency Stash"
                                AccountType.CREDIT_CARD -> "e.g. Amex Platinum, Millennia Card"
                                AccountType.CASH -> "e.g. Petty Cash, Home Vault"
                                AccountType.DIGITAL_WALLET -> "e.g. PayTM, Apple Pay, PhonePe"
                                AccountType.BANK -> "e.g. Salary A/c, Savings"
                            },
                            color = Slate400
                        )
                    },
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate200
                    ),
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("account_name_input")
                )

                Spacer(modifier = Modifier.height(12.dp))

                // Institution / Holder
                Text(
                    if (selectedType == AccountType.PERSONAL) "Account Holder / Purpose" else "Bank / Provider",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = institution,
                    onValueChange = { institution = it },
                    placeholder = {
                        Text(
                            if (selectedType == AccountType.PERSONAL) "e.g. Self, Joint, Personal Savings" else "e.g. HDFC, SBI, PayTM, Cash",
                            color = Slate400
                        )
                    },
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate200
                    ),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(12.dp))

                // Balance
                Text(
                    if (selectedType == AccountType.CREDIT_CARD) "Current Outstanding Balance (₹)" else "Starting Balance (₹)",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = balanceText,
                    onValueChange = { input ->
                        if (input.isEmpty() || input.matches(Regex("^\\d*(\\.\\d{0,2})?$"))) {
                            balanceText = input
                        }
                    },
                    placeholder = { Text("0.00", color = Slate400) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate200
                    ),
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("account_balance_input")
                )

                if (selectedType == AccountType.CREDIT_CARD) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        "Credit Limit (₹)",
                        style = MaterialTheme.typography.labelMedium,
                        color = Slate700,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    OutlinedTextField(
                        value = creditLimitText,
                        onValueChange = { input ->
                            if (input.isEmpty() || input.matches(Regex("^\\d*(\\.\\d{0,2})?$"))) {
                                creditLimitText = input
                            }
                        },
                        placeholder = { Text("e.g. 100000", color = Slate400) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        shape = RoundedCornerShape(10.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Slate900,
                            unfocusedBorderColor = Slate200
                        ),
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                "Statement Day",
                                style = MaterialTheme.typography.labelMedium,
                                color = Slate700,
                                fontWeight = FontWeight.SemiBold
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = statementDayText,
                                onValueChange = { input ->
                                    if (input.isEmpty() || (input.toIntOrNull() != null && input.toInt() in 1..31)) {
                                        statementDayText = input
                                    }
                                },
                                placeholder = { Text("15th", color = Slate400) },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = Slate900,
                                    unfocusedBorderColor = Slate200
                                ),
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                            Text(
                                "e.g. 15th monthly",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate400,
                                fontSize = 10.sp
                            )
                        }

                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                "Payment Due Day",
                                style = MaterialTheme.typography.labelMedium,
                                color = Slate700,
                                fontWeight = FontWeight.SemiBold
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = dueDayText,
                                onValueChange = { input ->
                                    if (input.isEmpty() || (input.toIntOrNull() != null && input.toInt() in 1..31)) {
                                        dueDayText = input
                                    }
                                },
                                placeholder = { Text("5th", color = Slate400) },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = Slate900,
                                    unfocusedBorderColor = Slate200
                                ),
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                            Text(
                                "e.g. 5th monthly",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate400,
                                fontSize = 10.sp
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // Color accent picker
                Text(
                    "Badge Color",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    colorChoices.forEach { hex ->
                        val isColorSelected = selectedColor == hex
                        val color = Color(android.graphics.Color.parseColor(hex))
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(CircleShape)
                                .background(color)
                                .clickable { selectedColor = hex }
                                .then(
                                    if (isColorSelected) Modifier.border(2.dp, Slate900, CircleShape) else Modifier
                                )
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val bal = balanceText.toDoubleOrNull() ?: 0.0
                    val limit = creditLimitText.toDoubleOrNull() ?: 0.0
                    if (name.isNotBlank()) {
                        val stmtDay = if (selectedType == AccountType.CREDIT_CARD) (statementDayText.toIntOrNull() ?: 15) else 0
                        val dueDay = if (selectedType == AccountType.CREDIT_CARD) (dueDayText.toIntOrNull() ?: 5) else 0
                        onSubmit(
                            name.trim(),
                            selectedType,
                            bal,
                            limit,
                            selectedColor,
                            institution.trim(),
                            notes.trim(),
                            stmtDay,
                            dueDay
                        )
                        onDismiss()
                    }
                },
                enabled = name.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                modifier = Modifier.testTag("confirm_create_account_button")
            ) {
                Text(if (existingAccount != null) "Save Changes" else "Create Account")
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) {
                Text("Cancel", color = Slate700)
            }
        },
        shape = RoundedCornerShape(20.dp),
        containerColor = Color.White
    )
}
