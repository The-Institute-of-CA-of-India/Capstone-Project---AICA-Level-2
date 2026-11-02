package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CompareArrows
import androidx.compose.material.icons.filled.SouthWest
import androidx.compose.material.icons.filled.NorthEast
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
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.example.data.model.TransactionType
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseBorder
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeBorder
import com.example.ui.theme.PastelIncomeText
import com.example.ui.theme.PastelTransferBg
import com.example.ui.theme.PastelTransferBorder
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate300
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate900
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.ui.platform.LocalContext
import com.example.data.model.Transaction
import com.example.ui.util.CurrencyUtils
import com.example.ui.util.InvoiceUtils
import com.google.firebase.Timestamp

private val expenseCategories = listOf(
    "Business Expense",
    "Food & Dining",
    "Transport",
    "Utilities",
    "Entertainment",
    "Groceries",
    "Shopping",
    "Healthcare",
    "Education",
    "Travel",
    "Bills & Recharge",
    "General"
)

private val incomeCategories = listOf(
    "Salary",
    "Freelance",
    "Business",
    "Dividend",
    "Rental",
    "Interest",
    "Gift",
    "Refund",
    "Other Income"
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun TransactionEntrySheet(
    accounts: List<Account>,
    initialType: TransactionType = TransactionType.EXPENSE,
    existingTransaction: Transaction? = null,
    onDismiss: () -> Unit,
    onSubmit: (
        type: TransactionType,
        amount: Double,
        accountId: String,
        destinationAccountId: String?,
        category: String,
        note: String,
        invoiceFileName: String,
        invoiceUri: String
    ) -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val isEditMode = existingTransaction != null
    val context = LocalContext.current

    var selectedType by remember {
        mutableStateOf(
            existingTransaction?.let {
                try { TransactionType.valueOf(it.type) } catch (e: Exception) { initialType }
            } ?: initialType
        )
    }
    var amountText by remember {
        mutableStateOf(
            existingTransaction?.let { if (it.amount > 0.0) it.amount.toString() else "" } ?: ""
        )
    }
    var noteText by remember {
        mutableStateOf(existingTransaction?.note ?: "")
    }
    var invoiceFileName by remember {
        mutableStateOf(existingTransaction?.invoiceFileName ?: "")
    }
    var invoiceUri by remember {
        mutableStateOf(existingTransaction?.invoiceUri ?: "")
    }

    val invoiceLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            invoiceUri = uri.toString()
            val resolvedName = try {
                val cursor = context.contentResolver.query(uri, null, null, null, null)
                cursor?.use {
                    if (it.moveToFirst()) {
                        val nameIndex = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (nameIndex != -1) it.getString(nameIndex) else null
                    } else null
                }
            } catch (e: Exception) {
                null
            } ?: "invoice_${System.currentTimeMillis().toString().takeLast(6)}"
            val (savedName, savedUri) = InvoiceUtils.saveAttachedInvoiceToInternal(context, uri, resolvedName)
            invoiceFileName = savedName
            invoiceUri = savedUri
        }
    }

    var selectedAccountId by remember {
        mutableStateOf(existingTransaction?.accountId?.ifBlank { null } ?: accounts.firstOrNull()?.id ?: "")
    }
    var destinationAccountId by remember {
        mutableStateOf(existingTransaction?.destinationAccountId ?: accounts.getOrNull(1)?.id ?: "")
    }

    LaunchedEffect(accounts) {
        if (accounts.isNotEmpty() && accounts.none { it.id == selectedAccountId }) {
            selectedAccountId = accounts.first().id
        }
        if (accounts.size > 1 && (destinationAccountId.isBlank() || destinationAccountId == selectedAccountId)) {
            destinationAccountId = accounts.firstOrNull { it.id != selectedAccountId }?.id ?: ""
        }
    }

    var selectedCategory by remember {
        mutableStateOf(
            existingTransaction?.category?.ifBlank { null }
                ?: if (initialType == TransactionType.INCOME) "Salary" else "Food & Dining"
        )
    }

    val typeColor = when (selectedType) {
        TransactionType.EXPENSE -> PastelExpenseText
        TransactionType.INCOME -> PastelIncomeText
        TransactionType.TRANSFER -> PastelTransferText
    }

    val typeBg = when (selectedType) {
        TransactionType.EXPENSE -> PastelExpenseBg
        TransactionType.INCOME -> PastelIncomeBg
        TransactionType.TRANSFER -> PastelTransferBg
    }

    val typeBorder = when (selectedType) {
        TransactionType.EXPENSE -> PastelExpenseBorder
        TransactionType.INCOME -> PastelIncomeBorder
        TransactionType.TRANSFER -> PastelTransferBorder
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
        modifier = Modifier.testTag("transaction_entry_sheet")
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
                    text = if (isEditMode) "Edit Transaction Entry" else "New Entry",
                    style = MaterialTheme.typography.titleLarge,
                    color = Slate900,
                    fontWeight = FontWeight.Bold
                )
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.testTag("close_sheet_button")
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Slate600
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 3-way Mode Segmented Pill Selector with Mental-Model Pastel Cues
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(Slate100)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                TransactionType.entries.forEach { type ->
                    val isSelected = selectedType == type
                    val tabBg = if (isSelected) {
                        when (type) {
                            TransactionType.EXPENSE -> PastelExpenseBg
                            TransactionType.INCOME -> PastelIncomeBg
                            TransactionType.TRANSFER -> PastelTransferBg
                        }
                    } else Color.Transparent

                    val tabTextColor = if (isSelected) {
                        when (type) {
                            TransactionType.EXPENSE -> PastelExpenseText
                            TransactionType.INCOME -> PastelIncomeText
                            TransactionType.TRANSFER -> PastelTransferText
                        }
                    } else Slate600

                    val icon = when (type) {
                        TransactionType.EXPENSE -> Icons.Default.NorthEast
                        TransactionType.INCOME -> Icons.Default.SouthWest
                        TransactionType.TRANSFER -> Icons.Default.CompareArrows
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(10.dp))
                            .background(tabBg)
                            .clickable {
                                selectedType = type
                                if (type == TransactionType.INCOME && selectedCategory !in incomeCategories) {
                                    selectedCategory = incomeCategories.first()
                                } else if (type == TransactionType.EXPENSE && selectedCategory !in expenseCategories) {
                                    selectedCategory = expenseCategories.first()
                                }
                            }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = icon,
                                contentDescription = null,
                                tint = tabTextColor,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = type.displayName,
                                color = tabTextColor,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Amount Hero Input Box
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = typeBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, typeBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "AMOUNT IN RUPEES",
                        style = MaterialTheme.typography.labelSmall,
                        color = typeColor,
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
                            color = typeColor
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
                                    color = typeColor.copy(alpha = 0.4f)
                                )
                            },
                            textStyle = MaterialTheme.typography.headlineLarge.copy(
                                color = typeColor,
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
                                .testTag("amount_input_field")
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ACCOUNTS SELECTION
            if (selectedType == TransactionType.TRANSFER) {
                // Inter-Account Transfer Selectors (From -> To)
                Text(
                    text = "Source Account (Debit From)",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                AccountChipRow(
                    accounts = accounts,
                    selectedId = selectedAccountId,
                    onSelect = { selectedAccountId = it },
                    tagPrefix = "src_acc"
                )

                Spacer(modifier = Modifier.height(14.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.ArrowForward,
                        contentDescription = "Transfer to",
                        tint = PastelTransferText,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Destination Account (Credit To)",
                        style = MaterialTheme.typography.labelMedium,
                        color = Slate700,
                        fontWeight = FontWeight.SemiBold
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                if (accounts.size < 2) {
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFFFEF3C7),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFFDE68A)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = null,
                                tint = Color(0xFF92400E),
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Inter-account transfers require at least 2 accounts. Add a second account in the Accounts tab to transfer between accounts.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFF92400E)
                            )
                        }
                    }
                } else {
                    AccountChipRow(
                        accounts = accounts.filter { it.id != selectedAccountId },
                        selectedId = destinationAccountId,
                        onSelect = { destinationAccountId = it },
                        tagPrefix = "dest_acc"
                    )
                }
            } else {
                // Expense or Income Account
                Text(
                    text = if (selectedType == TransactionType.EXPENSE) "Paid Using Account" else "Deposited To Account",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                AccountChipRow(
                    accounts = accounts,
                    selectedId = selectedAccountId,
                    onSelect = { selectedAccountId = it },
                    tagPrefix = "acc"
                )
            }

            Spacer(modifier = Modifier.height(18.dp))

            // CATEGORY SELECTOR (For Expense & Income)
            if (selectedType != TransactionType.TRANSFER) {
                Text(
                    text = "Category",
                    style = MaterialTheme.typography.labelMedium,
                    color = Slate700,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                val categories = if (selectedType == TransactionType.EXPENSE) expenseCategories else incomeCategories
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    categories.forEach { category ->
                        val isCatSelected = selectedCategory == category
                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = if (isCatSelected) typeBg else Slate100,
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (isCatSelected) typeBorder else Slate200
                            ),
                            modifier = Modifier
                                .clickable { selectedCategory = category }
                                .testTag("cat_chip_$category")
                        ) {
                            Text(
                                text = category,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isCatSelected) typeColor else Slate700,
                                fontWeight = if (isCatSelected) FontWeight.Bold else FontWeight.Normal,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(18.dp))
            }

            // BUSINESS EXPENSE TAX & INVOICE RECOMMENDATION CARD
            if (selectedType == TransactionType.EXPENSE && selectedCategory == "Business Expense") {
                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFF0FDF4)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFBBF7D0)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("business_expense_recommendation_card")
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Receipt,
                                contentDescription = null,
                                tint = Color(0xFF15803D),
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Business Expense: Invoice Recommended",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF166534)
                            )
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "For business expenses, we recommend uploading a tax invoice or receipt (JPEG, PNG, or PDF) for bookkeeping and GST / tax deduction records. (Recommendation only, not mandatory)",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF14532D),
                            lineHeight = 18.sp
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        if (invoiceFileName.isBlank()) {
                            Button(
                                onClick = {
                                    invoiceLauncher.launch(
                                        arrayOf("image/jpeg", "image/png", "image/webp", "application/pdf", "*/*")
                                    )
                                },
                                shape = RoundedCornerShape(10.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF166534)),
                                modifier = Modifier.testTag("upload_business_invoice_button")
                            ) {
                                Icon(
                                    imageVector = Icons.Default.UploadFile,
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "Attach Invoice (JPEG / PNG / PDF)",
                                    style = MaterialTheme.typography.labelSmall
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(14.dp))
            }

            // Attached Invoice Chip (shown if an invoice is attached)
            if (invoiceFileName.isNotBlank()) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFDCFCE7),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF86EFAC)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                            Icon(
                                imageVector = if (invoiceFileName.endsWith(".pdf", ignoreCase = true)) Icons.Default.Description else Icons.Default.Image,
                                contentDescription = null,
                                tint = Color(0xFF15803D),
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Column {
                                Text(
                                    text = invoiceFileName,
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF166534),
                                    maxLines = 1
                                )
                                Text(
                                    text = "Invoice attached (saved with entry)",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color(0xFF15803D),
                                    fontSize = 11.sp
                                )
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(
                                onClick = {
                                    InvoiceUtils.downloadInvoice(
                                        context = context,
                                        fileName = invoiceFileName,
                                        fileUriString = invoiceUri,
                                        category = selectedCategory,
                                        amount = amountText.toDoubleOrNull(),
                                        note = noteText
                                    )
                                },
                                modifier = Modifier.testTag("download_invoice_chip_button")
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Download,
                                    contentDescription = "Download invoice",
                                    tint = Color(0xFF15803D),
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            IconButton(
                                onClick = {
                                    InvoiceUtils.openOrShareInvoice(
                                        context = context,
                                        fileName = invoiceFileName,
                                        fileUriString = invoiceUri,
                                        category = selectedCategory,
                                        amount = amountText.toDoubleOrNull(),
                                        note = noteText
                                    )
                                },
                                modifier = Modifier.testTag("open_invoice_chip_button")
                            ) {
                                Icon(
                                    imageVector = Icons.Default.OpenInNew,
                                    contentDescription = "View or share invoice",
                                    tint = Color(0xFF15803D),
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            IconButton(
                                onClick = { invoiceFileName = ""; invoiceUri = "" },
                                modifier = Modifier.testTag("remove_invoice_button")
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Close,
                                    contentDescription = "Remove invoice",
                                    tint = Color(0xFF15803D),
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(14.dp))
            }

            // Note / Description Field
            Text(
                text = "Note / Description",
                style = MaterialTheme.typography.labelMedium,
                color = Slate700,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(6.dp))
            OutlinedTextField(
                value = noteText,
                onValueChange = { noteText = it },
                placeholder = {
                    Text(
                        if (selectedType == TransactionType.TRANSFER) "e.g. Card payment, ATM cash withdrawal" else "e.g. Lunch with team, Groceries",
                        color = Slate400,
                        style = MaterialTheme.typography.bodyMedium
                    )
                },
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate200
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("transaction_note_input")
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Submit Button
            val amount = amountText.toDoubleOrNull() ?: 0.0
            val isValid = amount > 0.0 && selectedAccountId.isNotBlank() &&
                    (selectedType != TransactionType.TRANSFER || destinationAccountId.isNotBlank())

            Button(
                onClick = {
                    if (isValid) {
                        val category = if (selectedType == TransactionType.TRANSFER) "Inter-Account Transfer" else selectedCategory
                        val destId = if (selectedType == TransactionType.TRANSFER) destinationAccountId else null
                        onSubmit(selectedType, amount, selectedAccountId, destId, category, noteText, invoiceFileName, invoiceUri)
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
                    .testTag("submit_transaction_button")
            ) {
                Text(
                    text = if (isEditMode) "Save Changes" else when (selectedType) {
                        TransactionType.EXPENSE -> "Record Expense"
                        TransactionType.INCOME -> "Record Income"
                        TransactionType.TRANSFER -> "Execute Transfer Journal"
                    },
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun AccountChipRow(
    accounts: List<Account>,
    selectedId: String,
    onSelect: (String) -> Unit,
    tagPrefix: String
) {
    if (accounts.isEmpty()) {
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = Slate100,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp)
        ) {
            Text(
                text = "No accounts configured. Please add an account in the Accounts tab.",
                style = MaterialTheme.typography.bodySmall,
                color = Slate500,
                modifier = Modifier.padding(12.dp)
            )
        }
        return
    }

    if (accounts.size == 1) {
        // Dynamically scale single account to fill full width beautifully - eliminating empty white patch
        val acc = accounts.first()
        val isSelected = acc.id == selectedId || selectedId.isBlank()
        if (selectedId.isBlank()) {
            onSelect(acc.id)
        }
        val chipColor = try {
            Color(android.graphics.Color.parseColor(acc.colorHex))
        } catch (_: Exception) {
            Slate700
        }

        Card(
            shape = RoundedCornerShape(14.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isSelected) Slate900 else Color(0xFFF8FAFC)
            ),
            border = androidx.compose.foundation.BorderStroke(
                1.5.dp,
                if (isSelected) Slate900 else Slate200
            ),
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp)
                .clickable { onSelect(acc.id) }
                .testTag("${tagPrefix}_chip_${acc.id}")
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .clip(CircleShape)
                            .background(chipColor)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = acc.name,
                            style = MaterialTheme.typography.titleSmall,
                            color = if (isSelected) Color.White else Slate900,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = if (acc.institution.isNotBlank()) "${acc.institution} • ${acc.type}" else acc.type,
                            style = MaterialTheme.typography.labelSmall,
                            color = if (isSelected) Slate300 else Slate500
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = CurrencyUtils.formatRupee(acc.balance),
                        style = MaterialTheme.typography.labelMedium,
                        color = if (isSelected) Color.White else Slate700,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = if (isSelected) Color(0xFF166534) else Slate200
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                        ) {
                            if (isSelected) {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(12.dp)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                            }
                            Text(
                                text = if (isSelected) "Active" else "Select",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) Color.White else Slate700,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    } else if (accounts.size == 2) {
        // Equal-width scaling across the row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            accounts.forEach { acc ->
                val isSelected = acc.id == selectedId
                val chipColor = try {
                    Color(android.graphics.Color.parseColor(acc.colorHex))
                } catch (_: Exception) {
                    Slate700
                }

                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSelected) Slate900 else Color(0xFFF8FAFC)
                    ),
                    border = androidx.compose.foundation.BorderStroke(
                        1.dp,
                        if (isSelected) Slate900 else Slate200
                    ),
                    modifier = Modifier
                        .weight(1f)
                        .clickable { onSelect(acc.id) }
                        .testTag("${tagPrefix}_chip_${acc.id}")
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 10.dp, vertical = 10.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f, fill = false)) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(chipColor)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Column {
                                Text(
                                    text = acc.name,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (isSelected) Color.White else Slate900,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                    maxLines = 1,
                                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                )
                                Text(
                                    text = CurrencyUtils.formatRupee(acc.balance),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isSelected) Slate300 else Slate500,
                                    fontSize = 10.sp
                                )
                            }
                        }
                        if (isSelected) {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                }
            }
        }
    } else if (accounts.size == 3) {
        // 3 accounts: 2 in first row, 3rd in second row spanning cleanly
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                accounts.take(2).forEach { acc ->
                    val isSelected = acc.id == selectedId
                    val chipColor = try {
                        Color(android.graphics.Color.parseColor(acc.colorHex))
                    } catch (_: Exception) {
                        Slate700
                    }

                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (isSelected) Slate900 else Color(0xFFF8FAFC)
                        ),
                        border = androidx.compose.foundation.BorderStroke(
                            1.dp,
                            if (isSelected) Slate900 else Slate200
                        ),
                        modifier = Modifier
                            .weight(1f)
                            .clickable { onSelect(acc.id) }
                            .testTag("${tagPrefix}_chip_${acc.id}")
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 10.dp, vertical = 10.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f, fill = false)) {
                                Box(
                                    modifier = Modifier
                                        .size(8.dp)
                                        .clip(CircleShape)
                                    .background(chipColor)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Column {
                                    Text(
                                        text = acc.name,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = if (isSelected) Color.White else Slate900,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                        maxLines = 1,
                                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = CurrencyUtils.formatRupee(acc.balance),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if (isSelected) Slate300 else Slate500,
                                        fontSize = 10.sp
                                    )
                                }
                            }
                            if (isSelected) {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(14.dp)
                                )
                            }
                        }
                    }
                }
            }

            // 3rd account in second row
            val acc = accounts[2]
            val isSelected = acc.id == selectedId
            val chipColor = try {
                Color(android.graphics.Color.parseColor(acc.colorHex))
            } catch (_: Exception) {
                Slate700
            }
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (isSelected) Slate900 else Color(0xFFF8FAFC)
                ),
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    if (isSelected) Slate900 else Slate200
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect(acc.id) }
                    .testTag("${tagPrefix}_chip_${acc.id}")
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(chipColor)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = acc.name,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isSelected) Color.White else Slate900,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                            )
                            Text(
                                text = "${acc.type} • ${CurrencyUtils.formatRupee(acc.balance)}",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) Slate300 else Slate500,
                                fontSize = 10.sp
                            )
                        }
                    }
                    if (isSelected) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(14.dp)
                        )
                    }
                }
            }
        }
    } else {
        // 4+ accounts: Chunk into rows of 2 (equal-weight distribution)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            accounts.chunked(2).forEach { rowAccounts ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    rowAccounts.forEach { acc ->
                        val isSelected = acc.id == selectedId
                        val chipColor = try {
                            Color(android.graphics.Color.parseColor(acc.colorHex))
                        } catch (_: Exception) {
                            Slate700
                        }

                        Card(
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = if (isSelected) Slate900 else Color(0xFFF8FAFC)
                            ),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (isSelected) Slate900 else Slate200
                            ),
                            modifier = Modifier
                                .weight(1f)
                                .clickable { onSelect(acc.id) }
                                .testTag("${tagPrefix}_chip_${acc.id}")
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 10.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f, fill = false)) {
                                    Box(
                                        modifier = Modifier
                                            .size(8.dp)
                                            .clip(CircleShape)
                                            .background(chipColor)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Column {
                                        Text(
                                            text = acc.name,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = if (isSelected) Color.White else Slate900,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            maxLines = 1,
                                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                        )
                                        Text(
                                            text = CurrencyUtils.formatRupee(acc.balance),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (isSelected) Slate300 else Slate500,
                                            fontSize = 10.sp
                                        )
                                    }
                                }
                                if (isSelected) {
                                    Icon(
                                        imageVector = Icons.Default.Check,
                                        contentDescription = null,
                                        tint = Color.White,
                                        modifier = Modifier.size(14.dp)
                                    )
                                }
                            }
                        }
                    }
                    if (rowAccounts.size == 1) {
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
        }
    }
}
