package com.example.ui.report

import android.content.Context
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.data.model.Account
import com.example.data.model.Investment
import com.example.data.model.Transaction
import com.example.ui.theme.PastelIncomeBg
import com.example.ui.theme.PastelIncomeText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate300
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate800
import com.example.ui.theme.Slate900
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Dialog shown when tapping the Export icon in the Top Bar.
 * Asks for the File Type (Excel + PDF) and details covered sections:
 * 1. Income Expense summary category-wise
 * 2. Income Expense summary Transaction Level (bank statement lookalike)
 * 3. All available invoices at end of PDF (in case of PDF export only)
 */
@Composable
fun ExportReportDialog(
    transactions: List<Transaction>,
    accounts: List<Account>,
    currencySymbol: String = "₹",
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var selectedFileType by remember { mutableStateOf(ReportFileType.PDF) }
    var isGenerating by remember { mutableStateOf(false) }

    Dialog(onDismissRequest = { if (!isGenerating) onDismiss() }) {
        Card(
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White),
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp)
                .testTag("export_report_dialog")
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(22.dp)
            ) {
                // Header with icon & close
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            shape = CircleShape,
                            color = Slate100,
                            modifier = Modifier.size(42.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.Description,
                                    contentDescription = null,
                                    tint = Slate900,
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = "Export Report",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = Slate900
                            )
                            Text(
                                text = "Generate financial statement",
                                style = MaterialTheme.typography.labelSmall,
                                color = Slate500
                            )
                        }
                    }

                    if (!isGenerating) {
                        IconButton(
                            onClick = onDismiss,
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Close",
                                tint = Slate500,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(18.dp))

                // File Type Selection (Excel + PDF)
                Text(
                    text = "SELECT FILE TYPE",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(10.dp))

                // PDF Option Card
                val isPdfSelected = selectedFileType == ReportFileType.PDF
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (isPdfSelected) Color(0xFFFEF2F2) else Color.White,
                    border = androidx.compose.foundation.BorderStroke(
                        1.5.dp,
                        if (isPdfSelected) Color(0xFFDC2626) else Slate200
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { selectedFileType = ReportFileType.PDF }
                        .testTag("file_type_pdf_option")
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isPdfSelected,
                            onClick = { selectedFileType = ReportFileType.PDF },
                            colors = RadioButtonDefaults.colors(
                                selectedColor = Color(0xFFDC2626),
                                unselectedColor = Slate400
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFDC2626),
                            modifier = Modifier.size(32.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.PictureAsPdf,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = "PDF Document (.pdf)",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = Slate900
                            )
                            Text(
                                text = "With category summary, statement & attached invoices",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate600
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Excel Option Card
                val isExcelSelected = selectedFileType == ReportFileType.EXCEL
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (isExcelSelected) Color(0xFFF0FDF4) else Color.White,
                    border = androidx.compose.foundation.BorderStroke(
                        1.5.dp,
                        if (isExcelSelected) Color(0xFF16A34A) else Slate200
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { selectedFileType = ReportFileType.EXCEL }
                        .testTag("file_type_excel_option")
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isExcelSelected,
                            onClick = { selectedFileType = ReportFileType.EXCEL },
                            colors = RadioButtonDefaults.colors(
                                selectedColor = Color(0xFF16A34A),
                                unselectedColor = Slate400
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFF16A34A),
                            modifier = Modifier.size(32.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.TableChart,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = "Excel Workbook (.xls / .xlsx)",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = Slate900
                            )
                            Text(
                                text = "Multi-sheet workbook with category breakdown & ledger",
                                style = MaterialTheme.typography.bodySmall,
                                color = Slate600
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Report Contents Covered List
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = Slate100,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(
                            text = "SECTIONS INCLUDED IN REPORT",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = Slate600,
                            letterSpacing = 0.5.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        ReportItemRow(
                            number = "1",
                            title = "Income & Expense Summary",
                            subtitle = "Category-wise aggregates and net savings"
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        ReportItemRow(
                            number = "2",
                            title = "Transaction-Level Statement",
                            subtitle = "Bank statement lookalike with debit, credit & balance"
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        ReportItemRow(
                            number = "3",
                            title = "Invoices & Receipts (Embedded in PDF)",
                            subtitle = if (isPdfSelected) {
                                "All attached invoice PDFs & receipts are embedded directly into the exported PDF"
                            } else {
                                "Invoice references linked in Excel; full PDFs in PDF export"
                            },
                            isHighlight = isPdfSelected
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "📁 Downloaded directly to phone's Downloads folder",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF16A34A),
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Action Buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        enabled = !isGenerating,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                    ) {
                        Text("Cancel", color = Slate700)
                    }

                    Button(
                        onClick = {
                            isGenerating = true
                            coroutineScope.launch {
                                val file = withContext(Dispatchers.IO) {
                                    ReportGenerator.generateStandardReport(
                                        context = context,
                                        fileType = selectedFileType,
                                        transactions = transactions,
                                        accounts = accounts,
                                        currencySymbol = currencySymbol
                                    )
                                }
                                isGenerating = false
                                if (file != null && file.exists()) {
                                    onDismiss()
                                    ReportGenerator.openOrShareReport(
                                        context = context,
                                        file = file,
                                        mimeType = selectedFileType.mimeType
                                    )
                                } else {
                                    Toast.makeText(context, "Could not generate report file.", Toast.LENGTH_SHORT).show()
                                }
                            }
                        },
                        enabled = !isGenerating,
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Slate900,
                            contentColor = Color.White
                        ),
                        modifier = Modifier
                            .weight(1.5f)
                            .height(48.dp)
                            .testTag("confirm_export_button")
                    ) {
                        if (isGenerating) {
                            CircularProgressIndicator(
                                color = Color.White,
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Generating...", style = MaterialTheme.typography.labelLarge)
                        } else {
                            Icon(
                                imageVector = Icons.Default.Download,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = if (selectedFileType == ReportFileType.PDF) "Generate PDF" else "Generate Excel",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ReportItemRow(
    number: String,
    title: String,
    subtitle: String,
    isHighlight: Boolean = false
) {
    Row(
        verticalAlignment = Alignment.Top,
        modifier = Modifier.fillMaxWidth()
    ) {
        Surface(
            shape = CircleShape,
            color = if (isHighlight) Color(0xFFDC2626) else Slate700,
            modifier = Modifier.size(18.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = number,
                    color = Color.White,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
        Spacer(modifier = Modifier.width(10.dp))
        Column {
            Text(
                text = title,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = Slate900
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = if (isHighlight) Color(0xFF991B1B) else Slate600,
                fontSize = 11.sp
            )
        }
    }
}

/**
 * Menu / Section in Settings for generating Annual Financial Statements.
 * Covers:
 * 1. Balance Sheet
 * 2. Profit & Loss Statement
 * 3. Capital Account
 * 4. Bank Account
 * 5. Business Expense Ledger
 * 6. Cashflow Statement
 * (All T-format style except for cashflow)
 *
 * Provides checkboxes to:
 * 1. Choose the reports to generate
 * 2. Financial Year
 */
@Composable
fun FinancialStatementsSettingsMenu(
    transactions: List<Transaction>,
    accounts: List<Account>,
    investments: List<Investment>,
    currencySymbol: String = "₹"
) {
    var showSheet by remember { mutableStateOf(false) }

    Card(
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .fillMaxWidth()
            .testTag("financial_statements_menu_card")
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                    Box(
                        modifier = Modifier
                            .size(42.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0xFFEDE9FE)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Assessment,
                            contentDescription = null,
                            tint = Color(0xFF6D28D9),
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Annual Financial Statements",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = Slate900
                        )
                        Text(
                            text = "T-Format Balance Sheet, P&L, Capital, Bank, Expense & Cashflow",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                Button(
                    onClick = { showSheet = true },
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Slate900,
                        contentColor = Color.White
                    ),
                    modifier = Modifier.testTag("open_financial_statements_button")
                ) {
                    Text("Generate", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = Slate100)
            Spacer(modifier = Modifier.height(10.dp))

            // Quick Badges of What's Included
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                StatementTag(text = "Balance Sheet (T)")
                StatementTag(text = "P&L (T)")
                StatementTag(text = "Capital A/c (T)")
                StatementTag(text = "Cashflow")
            }
        }
    }

    if (showSheet) {
        FinancialStatementsModalSheet(
            transactions = transactions,
            accounts = accounts,
            investments = investments,
            currencySymbol = currencySymbol,
            onDismiss = { showSheet = false }
        )
    }
}

@Composable
private fun StatementTag(text: String) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = Slate100,
        modifier = Modifier.padding(vertical = 2.dp)
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = Slate700,
            fontSize = 10.sp,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp)
        )
    }
}

/**
 * Modal Bottom Sheet for Financial Statements configuration:
 * - Checkboxes to choose reports to generate
 * - Checkboxes to choose Financial Year
 * - File type choice (PDF or Excel)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinancialStatementsModalSheet(
    transactions: List<Transaction>,
    accounts: List<Account>,
    investments: List<Investment>,
    currencySymbol: String = "₹",
    onDismiss: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    val fyOptions = remember(transactions, investments) {
        ReportGenerator.getFinancialYearOptions(transactions, investments)
    }
    var selectedFyId by remember(fyOptions) {
        mutableStateOf(fyOptions.firstOrNull()?.id ?: "")
    }
    var isYearDropdownExpanded by remember { mutableStateOf(false) }

    // Checkbox selections for reports
    var selBalanceSheet by remember { mutableStateOf(true) }
    var selProfitAndLoss by remember { mutableStateOf(true) }
    var selCapitalAccount by remember { mutableStateOf(true) }
    var selBankAccount by remember { mutableStateOf(true) }
    var selBusinessExpenseLedger by remember { mutableStateOf(true) }
    var selCashflowStatement by remember { mutableStateOf(true) }

    var entityName by remember { mutableStateOf("Onil Shah") }
    var selectedFileType by remember { mutableStateOf(ReportFileType.PDF) }
    var isGenerating by remember { mutableStateOf(false) }

    ModalBottomSheet(
        onDismissRequest = { if (!isGenerating) onDismiss() },
        sheetState = sheetState,
        containerColor = Color.White
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 8.dp)
                .verticalScroll(rememberScrollState())
                .testTag("financial_statements_modal_sheet")
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Generate Financial Statements",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Slate900
                    )
                    Text(
                        text = "Statutory T-format accounts for accounting & compliance",
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate500
                    )
                }

                IconButton(
                    onClick = { if (!isGenerating) onDismiss() },
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Slate500
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 1. CHOOSE FINANCIAL YEAR (DROPDOWN)
            Text(
                text = "1. CHOOSE FINANCIAL YEAR",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = Slate500,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(8.dp))

            val currentSelectedFy = fyOptions.find { it.id == selectedFyId }
                ?: fyOptions.firstOrNull()
                ?: FinancialYearOption("DEFAULT", "Current FY", 0L, Long.MAX_VALUE)

            Box(modifier = Modifier.fillMaxWidth()) {
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = Color.White,
                    border = androidx.compose.foundation.BorderStroke(
                        1.5.dp,
                        if (isYearDropdownExpanded) Slate900 else Slate300
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .clickable { isYearDropdownExpanded = !isYearDropdownExpanded }
                        .testTag("financial_year_dropdown_trigger")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 13.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.weight(1f)
                        ) {
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = Color(0xFFEDE9FE),
                                modifier = Modifier.size(36.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.DateRange,
                                        contentDescription = null,
                                        tint = Color(0xFF6D28D9),
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = currentSelectedFy.title,
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                val activeCount = transactions.count { tx ->
                                    val time = tx.date?.toDate()?.time ?: tx.createdAt?.toDate()?.time ?: 0L
                                    time in currentSelectedFy.startMillis..currentSelectedFy.endMillis
                                }
                                Text(
                                    text = if (activeCount > 0) "$activeCount transaction(s) recorded" else "Only years with recorded data",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate500,
                                    fontSize = 11.sp
                                )
                            }
                        }

                        Icon(
                            imageVector = if (isYearDropdownExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                            contentDescription = if (isYearDropdownExpanded) "Collapse" else "Expand",
                            tint = Slate700,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }

                DropdownMenu(
                    expanded = isYearDropdownExpanded,
                    onDismissRequest = { isYearDropdownExpanded = false },
                    modifier = Modifier
                        .fillMaxWidth(0.9f)
                        .background(Color.White)
                ) {
                    fyOptions.forEach { fy ->
                        val isSelected = selectedFyId == fy.id
                        DropdownMenuItem(
                            text = {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = fy.title,
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            color = if (isSelected) Slate900 else Slate700
                                        )
                                        val count = transactions.count { tx ->
                                            val time = tx.date?.toDate()?.time ?: tx.createdAt?.toDate()?.time ?: 0L
                                            time in fy.startMillis..fy.endMillis
                                        }
                                        Text(
                                            text = if (count > 0) "$count transaction(s) with data" else "Financial year",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (count > 0) Color(0xFF16A34A) else Slate500
                                        )
                                    }
                                    if (isSelected) {
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = "Selected",
                                            tint = Color(0xFF16A34A),
                                            modifier = Modifier.size(18.dp)
                                        )
                                    }
                                }
                            },
                            onClick = {
                                selectedFyId = fy.id
                                isYearDropdownExpanded = false
                            },
                            modifier = Modifier.testTag("fy_dropdown_item_${fy.id}")
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 2. CHOOSE REPORTS TO GENERATE (CHECKBOXES)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "2. CHOOSE STATEMENTS TO GENERATE",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 1.sp
                )

                // Select / Deselect All
                val allSelected = selBalanceSheet && selProfitAndLoss && selCapitalAccount &&
                        selBankAccount && selBusinessExpenseLedger && selCashflowStatement
                TextButton(
                    onClick = {
                        val target = !allSelected
                        selBalanceSheet = target
                        selProfitAndLoss = target
                        selCapitalAccount = target
                        selBankAccount = target
                        selBusinessExpenseLedger = target
                        selCashflowStatement = target
                    }
                ) {
                    Text(
                        text = if (allSelected) "Deselect All" else "Select All",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate700
                    )
                }
            }

            Card(
                shape = RoundedCornerShape(14.dp),
                colors = CardDefaults.cardColors(containerColor = Slate100),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(8.dp)) {
                    StatementCheckboxRow(
                        title = "1. Balance Sheet",
                        formatNote = "T-Format (Capital & Liabilities vs. Assets)",
                        checked = selBalanceSheet,
                        onCheckedChange = { selBalanceSheet = it },
                        tag = "checkbox_balance_sheet"
                    )
                    HorizontalDivider(color = Slate200, modifier = Modifier.padding(horizontal = 8.dp))

                    StatementCheckboxRow(
                        title = "2. Profit & Loss Statement",
                        formatNote = "T-Format (Expenses / Dr. vs. Income / Cr.)",
                        checked = selProfitAndLoss,
                        onCheckedChange = { selProfitAndLoss = it },
                        tag = "checkbox_profit_loss"
                    )
                    HorizontalDivider(color = Slate200, modifier = Modifier.padding(horizontal = 8.dp))

                    StatementCheckboxRow(
                        title = "3. Capital Account",
                        formatNote = "T-Format (Drawings & Losses vs. Capital & Profit)",
                        checked = selCapitalAccount,
                        onCheckedChange = { selCapitalAccount = it },
                        tag = "checkbox_capital_account"
                    )
                    HorizontalDivider(color = Slate200, modifier = Modifier.padding(horizontal = 8.dp))

                    StatementCheckboxRow(
                        title = "4. Bank Account",
                        formatNote = "T-Format (Receipts / Dr. vs. Payments / Cr.)",
                        checked = selBankAccount,
                        onCheckedChange = { selBankAccount = it },
                        tag = "checkbox_bank_account"
                    )
                    HorizontalDivider(color = Slate200, modifier = Modifier.padding(horizontal = 8.dp))

                    StatementCheckboxRow(
                        title = "5. Business Expense Ledger",
                        formatNote = "T-Format (Itemized Vouchers vs. Recoveries)",
                        checked = selBusinessExpenseLedger,
                        onCheckedChange = { selBusinessExpenseLedger = it },
                        tag = "checkbox_business_expense"
                    )
                    HorizontalDivider(color = Slate200, modifier = Modifier.padding(horizontal = 8.dp))

                    StatementCheckboxRow(
                        title = "6. Cashflow Statement",
                        formatNote = "Columnar / Direct Method (Operating, Investing, Cash)",
                        checked = selCashflowStatement,
                        onCheckedChange = { selCashflowStatement = it },
                        tag = "checkbox_cashflow_statement"
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 3. FILE TYPE (PDF vs EXCEL)
            Text(
                text = "3. SELECT EXPORT FORMAT",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = Slate500,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // PDF Button
                val isPdf = selectedFileType == ReportFileType.PDF
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (isPdf) Color(0xFFFEF2F2) else Color.White,
                    border = androidx.compose.foundation.BorderStroke(1.5.dp, if (isPdf) Color(0xFFDC2626) else Slate200),
                    modifier = Modifier
                        .weight(1f)
                        .clickable { selectedFileType = ReportFileType.PDF }
                        .testTag("statements_format_pdf")
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isPdf,
                            onClick = { selectedFileType = ReportFileType.PDF },
                            colors = RadioButtonDefaults.colors(selectedColor = Color(0xFFDC2626))
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Column {
                            Text("PDF Format", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = Slate900)
                            Text("Formal Print", style = MaterialTheme.typography.bodySmall, color = Slate500, fontSize = 11.sp)
                        }
                    }
                }

                // Excel Button
                val isExcel = selectedFileType == ReportFileType.EXCEL
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (isExcel) Color(0xFFF0FDF4) else Color.White,
                    border = androidx.compose.foundation.BorderStroke(1.5.dp, if (isExcel) Color(0xFF16A34A) else Slate200),
                    modifier = Modifier
                        .weight(1f)
                        .clickable { selectedFileType = ReportFileType.EXCEL }
                        .testTag("statements_format_excel")
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isExcel,
                            onClick = { selectedFileType = ReportFileType.EXCEL },
                            colors = RadioButtonDefaults.colors(selectedColor = Color(0xFF16A34A))
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Column {
                            Text("Excel Format", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = Slate900)
                            Text("Multi-Sheet .xls", style = MaterialTheme.typography.bodySmall, color = Slate500, fontSize = 11.sp)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 4. ENTITY / PROPRIETOR NAME (FOR SIGNATURE & HEADERS)
            Text(
                text = "4. ENTITY / PROPRIETOR NAME",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = Slate500,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = entityName,
                onValueChange = { entityName = it },
                label = { Text("Name of Non-Corporate Entity / Proprietor") },
                placeholder = { Text("e.g. Onil Shah") },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate300
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("entity_proprietor_name_input")
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Accounting Standards Compliant Format Notice & Signatory Box
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = Slate100,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "ACCOUNTING STANDARDS FORMAT PREVIEW",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = Slate500,
                        letterSpacing = 1.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = entityName.ifBlank { "Onil Shah" },
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = Slate900
                    )
                    val activeFy = fyOptions.find { it.id == selectedFyId }
                        ?: fyOptions.firstOrNull()
                        ?: FinancialYearOption("DEFAULT", "Current FY", 0L, Long.MAX_VALUE)
                    Text(
                        text = "Statement of Profit & Loss / Balance Sheet for the year ended ${ReportGenerator.getYearEndedDate(activeFy)}",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.SemiBold,
                        color = Slate700
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "(Compliant with ICAI Guidance Note for Non-Corporate Entities • Applicable items only)",
                        style = MaterialTheme.typography.labelSmall,
                        color = Slate500,
                        fontSize = 10.5.sp
                    )
                    Spacer(modifier = Modifier.height(3.dp))
                    Text(
                        text = "✍️ Self-Certified: Signatory space for Proprietor only (No auditor)",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFF0369A1),
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 11.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "📁 Downloaded directly to phone's Downloads folder",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFF16A34A),
                        fontWeight = FontWeight.Bold,
                        fontSize = 11.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Generate Button
            val hasAnyReport = selBalanceSheet || selProfitAndLoss || selCapitalAccount ||
                    selBankAccount || selBusinessExpenseLedger || selCashflowStatement

            Button(
                onClick = {
                    val fy = fyOptions.find { it.id == selectedFyId }
                        ?: fyOptions.firstOrNull()
                        ?: FinancialYearOption("DEFAULT", "Current FY", 0L, Long.MAX_VALUE)
                    val selection = FinancialStatementSelection(
                        balanceSheet = selBalanceSheet,
                        profitAndLoss = selProfitAndLoss,
                        capitalAccount = selCapitalAccount,
                        bankAccount = selBankAccount,
                        businessExpenseLedger = selBusinessExpenseLedger,
                        cashflowStatement = selCashflowStatement,
                        useAccountingStandardFormat = true
                    )

                    isGenerating = true
                    coroutineScope.launch {
                        val file = withContext(Dispatchers.IO) {
                            ReportGenerator.generateAnnualFinancialStatements(
                                context = context,
                                fileType = selectedFileType,
                                fyOption = fy,
                                selection = selection,
                                transactions = transactions,
                                accounts = accounts,
                                investments = investments,
                                currencySymbol = currencySymbol,
                                caName = entityName.ifBlank { "Onil Shah" }
                            )
                        }
                        isGenerating = false
                        if (file != null && file.exists()) {
                            onDismiss()
                            ReportGenerator.openOrShareReport(
                                context = context,
                                file = file,
                                mimeType = selectedFileType.mimeType
                            )
                        } else {
                            Toast.makeText(context, "Could not generate financial statements.", Toast.LENGTH_SHORT).show()
                        }
                    }
                },
                enabled = hasAnyReport && !isGenerating,
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Slate900,
                    contentColor = Color.White
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp)
                    .testTag("generate_financial_statements_button")
            ) {
                if (isGenerating) {
                    CircularProgressIndicator(
                        color = Color.White,
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text("Compiling Financial Statements...", style = MaterialTheme.typography.labelLarge)
                } else {
                    Icon(imageVector = Icons.Default.Download, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (selectedFileType == ReportFileType.PDF) "Generate PDF Statements" else "Generate Excel Workbook",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun StatementCheckboxRow(
    title: String,
    formatNote: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    tag: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable { onCheckedChange(!checked) }
            .padding(horizontal = 6.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = CheckboxDefaults.colors(
                checkedColor = Slate900,
                uncheckedColor = Slate400
            ),
            modifier = Modifier.testTag(tag)
        )
        Spacer(modifier = Modifier.width(6.dp))
        Column {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = if (checked) FontWeight.Bold else FontWeight.Medium,
                color = if (checked) Slate900 else Slate700
            )
            Text(
                text = formatNote,
                style = MaterialTheme.typography.bodySmall,
                color = Slate500,
                fontSize = 11.sp
            )
        }
    }
}
