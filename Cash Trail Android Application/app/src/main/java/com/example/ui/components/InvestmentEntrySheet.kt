package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
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
import com.example.data.model.Account
import com.example.data.model.InvestmentAction
import com.example.data.model.InvestmentAssetType
import com.example.ui.theme.PastelInvestmentBg
import com.example.ui.theme.PastelInvestmentBorder
import com.example.ui.theme.PastelInvestmentText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate600
import com.example.data.model.Investment
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun InvestmentEntrySheet(
    accounts: List<Account>,
    existingInvestment: Investment? = null,
    onDismiss: () -> Unit,
    onSubmit: (
        assetName: String,
        assetType: String,
        action: InvestmentAction,
        amount: Double,
        sourceAccountId: String?,
        note: String
    ) -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val isEditMode = existingInvestment != null

    var assetName by remember { mutableStateOf(existingInvestment?.assetName ?: "") }
    var selectedAssetType by remember {
        mutableStateOf(existingInvestment?.assetType ?: InvestmentAssetType.MUTUAL_FUNDS.name)
    }
    var selectedAction by remember {
        mutableStateOf(
            existingInvestment?.let {
                try { InvestmentAction.valueOf(it.action) } catch (e: Exception) { InvestmentAction.CONTRIBUTION }
            } ?: InvestmentAction.CONTRIBUTION
        )
    }
    var amountText by remember {
        mutableStateOf(existingInvestment?.let { if (it.amount > 0) it.amount.toString() else "" } ?: "")
    }
    var selectedAccountId by remember {
        mutableStateOf(existingInvestment?.sourceAccountId ?: accounts.firstOrNull()?.id)
    }
    var noteText by remember { mutableStateOf(existingInvestment?.note ?: "") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
        modifier = Modifier.testTag("investment_entry_sheet")
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
                Text(
                    text = if (isEditMode) "Edit Investment Entry" else "Investment Ledger Entry",
                    style = MaterialTheme.typography.titleLarge,
                    color = Slate900,
                    fontWeight = FontWeight.Bold
                )
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.testTag("close_investment_sheet")
                ) {
                    Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Slate600)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Action Toggle: Contribution vs Withdrawal
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(Slate100)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                InvestmentAction.entries.forEach { action ->
                    val isSelected = selectedAction == action
                    val tabBg = if (isSelected) PastelInvestmentBg else Color.Transparent
                    val tabColor = if (isSelected) PastelInvestmentText else Slate600

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(10.dp))
                            .background(tabBg)
                            .clickable { selectedAction = action }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = if (action == InvestmentAction.CONTRIBUTION) Icons.Default.TrendingUp else Icons.Default.TrendingDown,
                                contentDescription = null,
                                tint = tabColor,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = action.displayName,
                                color = tabColor,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Amount Hero Input
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = PastelInvestmentBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, PastelInvestmentBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "CAPITAL AMOUNT (₹)",
                        style = MaterialTheme.typography.labelSmall,
                        color = PastelInvestmentText,
                        fontWeight = FontWeight.SemiBold,
                        letterSpacing = 1.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = "₹",
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Bold,
                            color = PastelInvestmentText
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        OutlinedTextField(
                            value = amountText,
                            onValueChange = { input ->
                                if (input.isEmpty() || input.matches(Regex("^\\d*(\\.\\d{0,2})?$"))) {
                                    amountText = input
                                }
                            },
                            placeholder = {
                                Text(
                                    "0.00",
                                    fontSize = 32.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = PastelInvestmentText.copy(alpha = 0.4f)
                                )
                            },
                            textStyle = MaterialTheme.typography.headlineLarge.copy(
                                color = PastelInvestmentText,
                                fontWeight = FontWeight.Bold,
                                fontSize = 32.sp
                            ),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Color.Transparent,
                                unfocusedBorderColor = Color.Transparent
                            ),
                            modifier = Modifier
                                .width(220.dp)
                                .testTag("investment_amount_field")
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // Asset Name
            Text(
                text = "Asset / Fund Name",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(6.dp))
            OutlinedTextField(
                value = assetName,
                onValueChange = { assetName = it },
                placeholder = { Text("e.g. Nifty 50 Index, Sovereign Gold, SBI FD", color = Slate400) },
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate200
                ),
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("investment_asset_name_field")
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Asset Type Chips
            Text(
                text = "Asset Class",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                InvestmentAssetType.entries.forEach { type ->
                    val isSelected = selectedAssetType == type.name
                    Surface(
                        shape = RoundedCornerShape(20.dp),
                        color = if (isSelected) PastelInvestmentBg else Slate100,
                        border = androidx.compose.foundation.BorderStroke(
                            1.dp,
                            if (isSelected) PastelInvestmentBorder else Slate200
                        ),
                        modifier = Modifier
                            .clickable { selectedAssetType = type.name }
                            .testTag("asset_type_${type.name}")
                    ) {
                        Text(
                            text = type.displayName,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (isSelected) PastelInvestmentText else Slate700,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Linked Settlement Account
            Text(
                text = if (selectedAction == InvestmentAction.CONTRIBUTION) "Funded From Account (Optional)" else "Credited To Account (Optional)",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))
            val totalAccountOptions = listOf<Account?>(null) + accounts
            if (totalAccountOptions.size <= 3) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    totalAccountOptions.forEach { acc ->
                        val isSelected = selectedAccountId == acc?.id
                        Card(
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = if (isSelected) Slate900 else Slate100),
                            modifier = Modifier
                                .weight(1f)
                                .clickable { selectedAccountId = acc?.id }
                        ) {
                            Text(
                                text = acc?.name ?: "None (External)",
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isSelected) Color.White else Slate900,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                maxLines = 1,
                                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 10.dp)
                            )
                        }
                    }
                }
            } else {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    totalAccountOptions.chunked(2).forEach { rowOptions ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            rowOptions.forEach { acc ->
                                val isSelected = selectedAccountId == acc?.id
                                Card(
                                    shape = RoundedCornerShape(12.dp),
                                    colors = CardDefaults.cardColors(containerColor = if (isSelected) Slate900 else Slate100),
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { selectedAccountId = acc?.id }
                                ) {
                                    Text(
                                        text = acc?.name ?: "None (External)",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = if (isSelected) Color.White else Slate900,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                        maxLines = 1,
                                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 10.dp)
                                    )
                                }
                            }
                            if (rowOptions.size == 1) {
                                Spacer(modifier = Modifier.weight(1f))
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Note
            Text(
                text = "Note / Folio Reference",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(6.dp))
            OutlinedTextField(
                value = noteText,
                onValueChange = { noteText = it },
                placeholder = { Text("e.g. Monthly SIP, Lock-in period 3 yrs", color = Slate400) },
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate200
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("investment_note_field")
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Submit Button
            val amount = amountText.toDoubleOrNull() ?: 0.0
            val isValid = amount > 0.0 && assetName.isNotBlank()

            Button(
                onClick = {
                    if (isValid) {
                        onSubmit(
                            assetName.trim(),
                            selectedAssetType,
                            selectedAction,
                            amount,
                            selectedAccountId,
                            noteText.trim()
                        )
                        onDismiss()
                    }
                },
                enabled = isValid,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Slate900,
                    contentColor = Color.White
                ),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
                    .testTag("submit_investment_button")
            ) {
                Text(
                    text = if (isEditMode) "Save Changes" else "Post to Investment Ledger",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
