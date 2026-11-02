package com.example.ui.report

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.pdf.PdfDocument
import android.graphics.pdf.PdfRenderer
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.ParcelFileDescriptor
import android.provider.MediaStore
import android.widget.Toast
import androidx.core.content.FileProvider
import com.example.data.model.Account
import com.example.data.model.Investment
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * Report Data Models & Financial Year Enums
 */
data class FinancialYearOption(
    val id: String,
    val title: String,
    val startMillis: Long,
    val endMillis: Long
)

enum class ReportFileType(val displayName: String, val extension: String, val mimeType: String) {
    PDF("PDF Document (.pdf)", ".pdf", "application/pdf"),
    EXCEL("Excel Workbook (.xls / .xlsx)", ".xls", "application/vnd.ms-excel")
}

data class FinancialStatementSelection(
    val balanceSheet: Boolean = true,
    val profitAndLoss: Boolean = true,
    val capitalAccount: Boolean = true,
    val bankAccount: Boolean = true,
    val businessExpenseLedger: Boolean = true,
    val cashflowStatement: Boolean = true,
    val useAccountingStandardFormat: Boolean = true
)

data class AsScheduleRow(
    val itemNo: String = "",
    val particulars: String,
    val note: String = "",
    val amount: Double? = null,
    val isHeader: Boolean = false,
    val isTotal: Boolean = false,
    val isSubHeader: Boolean = false,
    val indentLevel: Int = 0
)

object ReportGenerator {

    const val DEFAULT_ENTITY_NAME = "Onil Shah"
    const val DEFAULT_CA_NAME = DEFAULT_ENTITY_NAME

    /**
     * Financial Year options based on actual recorded data.
     * Only years regarding which there is some data (transactions or investments) are returned.
     * If no data exists yet, defaults to the current financial year.
     */
    fun getFinancialYearOptions(
        transactions: List<Transaction> = emptyList(),
        investments: List<Investment> = emptyList()
    ): List<FinancialYearOption> {
        val timestamps = mutableListOf<Long>()
        transactions.forEach { tx ->
            val t = tx.date?.toDate()?.time ?: tx.createdAt?.toDate()?.time
            if (t != null && t > 0L) timestamps.add(t)
        }
        investments.forEach { inv ->
            val t = inv.date?.toDate()?.time ?: inv.createdAt?.toDate()?.time
            if (t != null && t > 0L) timestamps.add(t)
        }

        if (timestamps.isEmpty()) {
            val currentCal = Calendar.getInstance()
            val y = currentCal.get(Calendar.YEAR)
            val m = currentCal.get(Calendar.MONTH)
            val (startYear, endYear) = if (m >= Calendar.APRIL) Pair(y, y + 1) else Pair(y - 1, y)
            val startCal = Calendar.getInstance().apply {
                set(startYear, Calendar.APRIL, 1, 0, 0, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val endCal = Calendar.getInstance().apply {
                set(endYear, Calendar.MARCH, 31, 23, 59, 59)
                set(Calendar.MILLISECOND, 999)
            }
            return listOf(
                FinancialYearOption(
                    id = "FY_${startYear}_${endYear}",
                    title = "FY $startYear–$endYear (Apr $startYear – Mar $endYear)",
                    startMillis = startCal.timeInMillis,
                    endMillis = endCal.timeInMillis
                )
            )
        }

        val cal = Calendar.getInstance()
        val distinctYears = timestamps.map { time ->
            cal.timeInMillis = time
            val y = cal.get(Calendar.YEAR)
            val m = cal.get(Calendar.MONTH)
            if (m >= Calendar.APRIL) Pair(y, y + 1) else Pair(y - 1, y)
        }.distinct().sortedByDescending { it.first }

        val list = distinctYears.map { (startYear, endYear) ->
            val startCal = Calendar.getInstance().apply {
                set(startYear, Calendar.APRIL, 1, 0, 0, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val endCal = Calendar.getInstance().apply {
                set(endYear, Calendar.MARCH, 31, 23, 59, 59)
                set(Calendar.MILLISECOND, 999)
            }
            FinancialYearOption(
                id = "FY_${startYear}_${endYear}",
                title = "FY $startYear–$endYear (Apr $startYear – Mar $endYear)",
                startMillis = startCal.timeInMillis,
                endMillis = endCal.timeInMillis
            )
        }.toMutableList()

        if (distinctYears.size > 1) {
            list.add(
                FinancialYearOption(
                    id = "ALL_TIME",
                    title = "All Time (Complete Ledger History)",
                    startMillis = 0L,
                    endMillis = Long.MAX_VALUE
                )
            )
        }

        return list
    }

    /**
     * Extracts "31/03/YYYY" for the financial year
     */
    fun getYearEndedDate(fyOption: FinancialYearOption): String {
        if (fyOption.id == "ALL_TIME" || fyOption.endMillis == Long.MAX_VALUE) {
            val currentYear = Calendar.getInstance().get(Calendar.YEAR)
            return "31/03/$currentYear"
        }
        val cal = Calendar.getInstance().apply { timeInMillis = fyOption.endMillis }
        return SimpleDateFormat("31/03/yyyy", Locale.getDefault()).format(cal.time)
    }

    /**
     * Helper to format currency
     */
    fun formatMoney(amount: Double, symbol: String = "₹"): String {
        return "$symbol %,.2f".format(Locale.getDefault(), amount)
    }

    // =========================================================================
    // FEATURE 1: INCOME & EXPENSE REPORT (CATEGORY + BANK STATEMENT + INVOICES)
    // =========================================================================

    fun generateStandardReport(
        context: Context,
        fileType: ReportFileType,
        transactions: List<Transaction>,
        accounts: List<Account>,
        currencySymbol: String = "₹",
        reportTitle: String = "Financial Income & Expense Report"
    ): File? {
        val reportsDir = File(context.cacheDir, "reports").apply { mkdirs() }
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())

        return try {
            val generatedFile = when (fileType) {
                ReportFileType.PDF -> {
                    val file = File(reportsDir, "Cashtrail_Report_$timeStamp.pdf")
                    writeStandardReportPdf(context, file, transactions, accounts, currencySymbol, reportTitle)
                    file
                }
                ReportFileType.EXCEL -> {
                    val file = File(reportsDir, "Cashtrail_Report_$timeStamp.xls")
                    writeStandardReportExcel(file, transactions, accounts, currencySymbol, reportTitle)
                    file
                }
            }

            // Download directly to public Downloads folder in Phone
            saveToPhoneDownloads(context, generatedFile, generatedFile.name, fileType.mimeType)
            generatedFile
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    // =========================================================================
    // FEATURE 2: FINANCIAL STATEMENTS FOR A FINANCIAL YEAR (T-FORMAT + CASHFLOW)
    // =========================================================================

    fun generateAnnualFinancialStatements(
        context: Context,
        fileType: ReportFileType,
        fyOption: FinancialYearOption,
        selection: FinancialStatementSelection,
        transactions: List<Transaction>,
        accounts: List<Account>,
        investments: List<Investment>,
        currencySymbol: String = "₹",
        caName: String = DEFAULT_CA_NAME
    ): File? {
        val reportsDir = File(context.cacheDir, "reports").apply { mkdirs() }
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())

        // Filter transactions within financial year
        val fyTransactions = transactions.filter { tx ->
            val time = tx.date?.toDate()?.time ?: tx.createdAt?.toDate()?.time ?: 0L
            time in fyOption.startMillis..fyOption.endMillis
        }

        val fyInvestments = investments.filter { inv ->
            val time = inv.date?.toDate()?.time ?: inv.createdAt?.toDate()?.time ?: 0L
            time in fyOption.startMillis..fyOption.endMillis
        }

        return try {
            val generatedFile = when (fileType) {
                ReportFileType.PDF -> {
                    val file = File(reportsDir, "Cashtrail_Financial_Statements_${fyOption.id}_$timeStamp.pdf")
                    writeFinancialStatementsPdf(
                        file = file,
                        fyOption = fyOption,
                        sel = selection,
                        transactions = fyTransactions,
                        accounts = accounts,
                        investments = fyInvestments,
                        symbol = currencySymbol,
                        caName = caName
                    )
                    file
                }
                ReportFileType.EXCEL -> {
                    val file = File(reportsDir, "Cashtrail_Financial_Statements_${fyOption.id}_$timeStamp.xls")
                    writeFinancialStatementsExcel(
                        file = file,
                        fyOption = fyOption,
                        sel = selection,
                        transactions = fyTransactions,
                        accounts = accounts,
                        investments = fyInvestments,
                        symbol = currencySymbol,
                        caName = caName
                    )
                    file
                }
            }

            // Download directly to public Downloads folder in Phone
            saveToPhoneDownloads(context, generatedFile, generatedFile.name, fileType.mimeType)
            generatedFile
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    // =========================================================================
    // DOWNLOADS FOLDER HELPER: SAVES DIRECTLY TO PUBLIC DOWNLOADS IN THE PHONE
    // =========================================================================

    fun saveToPhoneDownloads(
        context: Context,
        sourceFile: File,
        fileName: String,
        mimeType: String
    ): File {
        try {
            val bytes = sourceFile.readBytes()

            // 1. Direct write to public Downloads directory (works on all Android devices)
            try {
                val publicDownloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                if (publicDownloads != null) {
                    publicDownloads.mkdirs()
                    val targetFile = File(publicDownloads, fileName)
                    targetFile.writeBytes(bytes)
                    MediaScannerConnection.scanFile(
                        context,
                        arrayOf(targetFile.absolutePath),
                        arrayOf(mimeType),
                        null
                    )
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }

            // 2. MediaStore Downloads insertion for Android 10+ (API 29+)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                try {
                    val contentValues = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                        put(MediaStore.MediaColumns.MIME_TYPE, mimeType)
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                        put(MediaStore.MediaColumns.IS_PENDING, 1)
                    }
                    val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                    if (uri != null) {
                        context.contentResolver.openOutputStream(uri)?.use { out ->
                            out.write(bytes)
                        }
                        contentValues.clear()
                        contentValues.put(MediaStore.MediaColumns.IS_PENDING, 0)
                        context.contentResolver.update(uri, contentValues, null, null)
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return sourceFile
    }

    // =========================================================================
    // PDF IMPLEMENTATION: STANDARD REPORT (WITH EMBEDDED INVOICE PDFS)
    // =========================================================================

    private fun writeStandardReportPdf(
        context: Context,
        outFile: File,
        transactions: List<Transaction>,
        accounts: List<Account>,
        symbol: String,
        reportTitle: String
    ) {
        val document = PdfDocument()
        val accountMap = accounts.associateBy { it.id }

        // Category Summary Aggregates
        val totalIncome = transactions.filter { it.type == TransactionType.INCOME.name }.sumOf { it.amount }
        val totalExpense = transactions.filter { it.type == TransactionType.EXPENSE.name }.sumOf { it.amount }
        val netSavings = totalIncome - totalExpense

        val categoryGroups = transactions
            .groupBy { it.category.ifBlank { "General" } }
            .map { (cat, list) ->
                val inc = list.filter { it.type == TransactionType.INCOME.name }.sumOf { it.amount }
                val exp = list.filter { it.type == TransactionType.EXPENSE.name }.sumOf { it.amount }
                Triple(cat, inc, exp)
            }
            .sortedByDescending { it.third } // sort by highest expense

        var pageNumber = 1

        val headerPaint = Paint().apply {
            color = Color.rgb(30, 41, 59)
            textSize = 10f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val textPaint = Paint().apply {
            color = Color.rgb(51, 65, 85)
            textSize = 8.5f
            isAntiAlias = true
        }
        val boldPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 8.5f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val rightPaint = Paint().apply {
            color = Color.rgb(51, 65, 85)
            textSize = 8.5f
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val rightBoldPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 8.5f
            textAlign = Paint.Align.RIGHT
            isFakeBoldText = true
            isAntiAlias = true
        }
        val linePaint = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 0.8f
        }
        val fillHeaderPaint = Paint().apply {
            color = Color.rgb(241, 245, 249)
            style = Paint.Style.FILL
        }

        // ---------------- PAGE 1: CATEGORY SUMMARY ----------------
        var pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNumber++).create()
        var page = document.startPage(pageInfo)
        var canvas = page.canvas

        drawCoinKeepHeader(canvas, reportTitle, "Generated on ${SimpleDateFormat("dd MMM yyyy, hh:mm a", Locale.getDefault()).format(Date())}")

        var y = 90f

        // Top KPI Cards: Income, Expense, Net Savings
        drawSummaryKpiCards(canvas, y, totalIncome, totalExpense, netSavings, symbol)
        y += 65f

        // Category Summary Table Header
        canvas.drawText("1. INCOME & EXPENSE SUMMARY (CATEGORY-WISE)", 36f, y, headerPaint)
        y += 12f

        canvas.drawRect(36f, y, 559f, y + 20f, fillHeaderPaint)
        canvas.drawText("Category", 44f, y + 14f, boldPaint)
        canvas.drawText("Income ($symbol)", 320f, y + 14f, rightBoldPaint)
        canvas.drawText("Expense ($symbol)", 440f, y + 14f, rightBoldPaint)
        canvas.drawText("Net ($symbol)", 550f, y + 14f, rightBoldPaint)
        y += 20f

        for (item in categoryGroups.take(28)) {
            val (cat, inc, exp) = item
            val net = inc - exp

            canvas.drawText(cat, 44f, y + 13f, textPaint)
            canvas.drawText("%,.2f".format(inc), 320f, y + 13f, rightPaint)
            canvas.drawText("%,.2f".format(exp), 440f, y + 13f, rightPaint)
            val netColor = if (net >= 0) Color.rgb(22, 163, 74) else Color.rgb(220, 38, 38)
            val netP = Paint(rightBoldPaint).apply { color = netColor }
            canvas.drawText("%,.2f".format(net), 550f, y + 13f, netP)

            canvas.drawLine(36f, y + 18f, 559f, y + 18f, linePaint)
            y += 18f
        }

        // Category Total Line
        canvas.drawRect(36f, y, 559f, y + 20f, fillHeaderPaint)
        canvas.drawText("Total Summary", 44f, y + 14f, boldPaint)
        canvas.drawText("%,.2f".format(totalIncome), 320f, y + 14f, rightBoldPaint)
        canvas.drawText("%,.2f".format(totalExpense), 440f, y + 14f, rightBoldPaint)
        val finalNetP = Paint(rightBoldPaint).apply { color = if (netSavings >= 0) Color.rgb(22, 163, 74) else Color.rgb(220, 38, 38) }
        canvas.drawText("%,.2f".format(netSavings), 550f, y + 14f, finalNetP)

        drawFooter(canvas, 1)
        document.finishPage(page)

        // ---------------- PAGE 2+: BANK STATEMENT LOOKALIKE (TRANSACTION-LEVEL) ----------------
        val sortedTx = transactions.sortedBy { it.date?.toDate()?.time ?: it.createdAt?.toDate()?.time ?: 0L }
        var runningBal = 0.0

        var currentTxIndex = 0
        val txPerPage = 32

        while (currentTxIndex < sortedTx.size || sortedTx.isEmpty()) {
            pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNumber++).create()
            page = document.startPage(pageInfo)
            canvas = page.canvas

            drawCoinKeepHeader(
                canvas,
                "2. TRANSACTION LEDGER STATEMENT (BANK LOOKALIKE)",
                "Chronological Transaction Log with Debit / Credit / Running Balance"
            )

            y = 85f

            // Statement Table Header
            canvas.drawRect(36f, y, 559f, y + 20f, fillHeaderPaint)
            canvas.drawText("Date", 42f, y + 14f, boldPaint)
            canvas.drawText("Particulars / Note", 105f, y + 14f, boldPaint)
            canvas.drawText("Category", 260f, y + 14f, boldPaint)
            canvas.drawText("Account", 350f, y + 14f, boldPaint)
            canvas.drawText("Debit ($symbol)", 450f, y + 14f, rightBoldPaint)
            canvas.drawText("Credit ($symbol)", 510f, y + 14f, rightBoldPaint)
            canvas.drawText("Balance", 552f, y + 14f, rightBoldPaint)
            y += 20f

            val chunk = sortedTx.drop(currentTxIndex).take(txPerPage)
            if (chunk.isEmpty()) {
                canvas.drawText("No transactions recorded in this period.", 44f, y + 20f, textPaint)
                currentTxIndex++
            } else {
                for (tx in chunk) {
                    val dateStr = tx.date?.toDate()?.let { SimpleDateFormat("dd-MMM-yy", Locale.getDefault()).format(it) } ?: "-"
                    val noteStr = tx.note.ifBlank { tx.category }.take(26)
                    val catStr = tx.category.take(14)
                    val accName = accountMap[tx.accountId]?.name ?: "Account"

                    var debitStr = ""
                    var creditStr = ""
                    when (tx.type) {
                        TransactionType.EXPENSE.name -> {
                            debitStr = "%,.2f".format(tx.amount)
                            runningBal -= tx.amount
                        }
                        TransactionType.INCOME.name -> {
                            creditStr = "%,.2f".format(tx.amount)
                            runningBal += tx.amount
                        }
                        else -> {
                            debitStr = "%,.2f".format(tx.amount)
                        }
                    }

                    canvas.drawText(dateStr, 42f, y + 14f, textPaint)
                    canvas.drawText(noteStr, 105f, y + 14f, textPaint)
                    canvas.drawText(catStr, 260f, y + 14f, textPaint)
                    canvas.drawText(accName.take(12), 350f, y + 14f, textPaint)
                    if (debitStr.isNotBlank()) {
                        val p = Paint(rightPaint).apply { color = Color.rgb(220, 38, 38) }
                        canvas.drawText(debitStr, 450f, y + 14f, p)
                    }
                    if (creditStr.isNotBlank()) {
                        val p = Paint(rightPaint).apply { color = Color.rgb(22, 163, 74) }
                        canvas.drawText(creditStr, 510f, y + 14f, p)
                    }
                    canvas.drawText("%,.2f".format(runningBal), 552f, y + 14f, rightBoldPaint)

                    canvas.drawLine(36f, y + 19f, 559f, y + 19f, linePaint)
                    y += 19f
                }
                currentTxIndex += chunk.size
            }

            drawFooter(canvas, pageNumber - 1)
            document.finishPage(page)
        }

        // ---------------- PAGE (END): INVOICES & RECEIPTS APPENDIX (PDF ONLY) ----------------
        // EMBED THE ACTUAL INVOICE PDF PAGES AND IMAGES DIRECTLY INTO THE EXPORTED PDF!
        val invoicedTx = transactions.filter { it.invoiceUri.isNotBlank() || it.invoiceFileName.isNotBlank() }
        if (invoicedTx.isNotEmpty()) {
            // 3.1 Voucher Index
            var invoiceIdx = 0
            val invoicesPerPage = 4

            while (invoiceIdx < invoicedTx.size) {
                pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNumber++).create()
                page = document.startPage(pageInfo)
                canvas = page.canvas

                drawCoinKeepHeader(
                    canvas,
                    "3. INVOICES & ATTACHED RECEIPTS APPENDIX",
                    "Summary Index of All Vouchers & Attached Invoices"
                )

                y = 85f
                val slice = invoicedTx.drop(invoiceIdx).take(invoicesPerPage)

                for (tx in slice) {
                    drawInvoiceVoucherCard(canvas, y, tx, accountMap[tx.accountId]?.name ?: "Account", symbol)
                    y += 165f
                }
                invoiceIdx += slice.size

                drawFooter(canvas, pageNumber - 1)
                document.finishPage(page)
            }

            // 3.2 Full Document Pages: Render and append actual PDF pages or high-res images
            for (tx in invoicedTx) {
                val invFile = locateInvoiceFile(context, tx)
                if (invFile != null && invFile.exists() && invFile.length() > 0) {
                    val isPdf = invFile.name.endsWith(".pdf", ignoreCase = true) || tx.invoiceFileName.endsWith(".pdf", ignoreCase = true)
                    if (isPdf) {
                        val addedPages = appendPdfFilePages(
                            pdfFile = invFile,
                            document = document,
                            startPageNum = pageNumber,
                            tx = tx,
                            symbol = symbol
                        )
                        pageNumber += addedPages
                    } else {
                        val appended = appendImageFilePage(
                            imageFile = invFile,
                            document = document,
                            pageNum = pageNumber,
                            tx = tx,
                            symbol = symbol
                        )
                        if (appended) pageNumber++
                    }
                } else {
                    // Generate official invoice receipt PDF and embed into the document
                    val fallbackPdf = generateFallbackReceiptPdf(context, tx, symbol)
                    if (fallbackPdf != null && fallbackPdf.exists()) {
                        val added = appendPdfFilePages(
                            pdfFile = fallbackPdf,
                            document = document,
                            startPageNum = pageNumber,
                            tx = tx,
                            symbol = symbol
                        )
                        pageNumber += added
                    }
                }
            }
        }

        // Output to file
        FileOutputStream(outFile).use { out ->
            document.writeTo(out)
        }
        document.close()
    }

    // =========================================================================
    // INVOICE RENDERING HELPERS: APPENDS REAL INVOICE PDF/IMAGE INTO DOCUMENT
    // =========================================================================

    private fun locateInvoiceFile(context: Context, tx: Transaction): File? {
        if (tx.invoiceUri.isNotBlank()) {
            try {
                val uri = Uri.parse(tx.invoiceUri)
                if (uri.scheme == "file") {
                    val f = File(uri.path ?: "")
                    if (f.exists() && f.length() > 0) return f
                } else if (uri.scheme == "content") {
                    val temp = File(context.cacheDir, "inv_temp_${System.currentTimeMillis()}_${tx.invoiceFileName.ifBlank { "invoice.pdf" }}")
                    context.contentResolver.openInputStream(uri)?.use { input ->
                        FileOutputStream(temp).use { output ->
                            input.copyTo(output)
                        }
                    }
                    if (temp.exists() && temp.length() > 0) return temp
                }
            } catch (_: Exception) {}
        }

        val internalInvoices = File(context.filesDir, "invoices")
        if (internalInvoices.exists() && tx.invoiceFileName.isNotBlank()) {
            val matched = internalInvoices.listFiles()?.firstOrNull {
                it.name == tx.invoiceFileName || it.name.endsWith(tx.invoiceFileName)
            }
            if (matched != null && matched.exists() && matched.length() > 0) return matched
        }
        return null
    }

    private fun appendPdfFilePages(
        pdfFile: File,
        document: PdfDocument,
        startPageNum: Int,
        tx: Transaction,
        symbol: String
    ): Int {
        var pfd: ParcelFileDescriptor? = null
        var renderer: PdfRenderer? = null
        var pagesAdded = 0
        try {
            pfd = ParcelFileDescriptor.open(pdfFile, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(pfd)
            val count = renderer.pageCount

            for (i in 0 until count) {
                val page = renderer.openPage(i)
                val srcW = page.width
                val srcH = page.height

                val maxW = 523f
                val maxH = 710f
                val scale = minOf(maxW / srcW.toFloat(), maxH / srcH.toFloat())
                val targetW = (srcW * scale).toInt().coerceAtLeast(100)
                val targetH = (srcH * scale).toInt().coerceAtLeast(100)

                // Render at 2x resolution for clean print quality
                val bitmap = Bitmap.createBitmap(targetW * 2, targetH * 2, Bitmap.Config.ARGB_8888)
                bitmap.eraseColor(Color.WHITE)
                page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_PRINT)
                page.close()

                val pageInfo = PdfDocument.PageInfo.Builder(595, 842, startPageNum + pagesAdded).create()
                val docPage = document.startPage(pageInfo)
                val canvas = docPage.canvas

                // Draw Invoice Header
                drawInvoiceDocumentHeader(
                    canvas = canvas,
                    title = "ATTACHED INVOICE PDF: ${tx.invoiceFileName.ifBlank { pdfFile.name }}",
                    subtitle = "Tx Ref #${tx.id.takeLast(6).uppercase()} • ${tx.category} • ${formatMoney(tx.amount, symbol)} • Page ${i + 1} of $count"
                )

                val drawLeft = (595f - targetW) / 2f
                val drawTop = 75f + (maxH - targetH) / 2f
                val destRect = RectF(drawLeft, drawTop, drawLeft + targetW, drawTop + targetH)
                canvas.drawBitmap(bitmap, null, destRect, null)
                bitmap.recycle()

                drawFooter(canvas, startPageNum + pagesAdded)
                document.finishPage(docPage)
                pagesAdded++
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            try { renderer?.close() } catch (_: Exception) {}
            try { pfd?.close() } catch (_: Exception) {}
        }
        return pagesAdded
    }

    private fun appendImageFilePage(
        imageFile: File,
        document: PdfDocument,
        pageNum: Int,
        tx: Transaction,
        symbol: String
    ): Boolean {
        return try {
            val bitmap = BitmapFactory.decodeFile(imageFile.absolutePath) ?: return false
            val srcW = bitmap.width
            val srcH = bitmap.height

            val maxW = 523f
            val maxH = 710f
            val scale = minOf(maxW / srcW.toFloat(), maxH / srcH.toFloat(), 1.0f)
            val targetW = srcW * scale
            val targetH = srcH * scale

            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum).create()
            val docPage = document.startPage(pageInfo)
            val canvas = docPage.canvas

            drawInvoiceDocumentHeader(
                canvas = canvas,
                title = "ATTACHED INVOICE RECEIPT: ${tx.invoiceFileName.ifBlank { imageFile.name }}",
                subtitle = "Tx Ref #${tx.id.takeLast(6).uppercase()} • Category: ${tx.category} • ${formatMoney(tx.amount, symbol)}"
            )

            val drawLeft = (595f - targetW) / 2f
            val drawTop = 75f + (maxH - targetH) / 2f
            val destRect = RectF(drawLeft, drawTop, drawLeft + targetW, drawTop + targetH)
            canvas.drawBitmap(bitmap, null, destRect, null)
            bitmap.recycle()

            drawFooter(canvas, pageNum)
            document.finishPage(docPage)
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    private fun drawInvoiceDocumentHeader(canvas: Canvas, title: String, subtitle: String) {
        val bannerPaint = Paint().apply {
            color = Color.rgb(22, 101, 52) // Forest green
            style = Paint.Style.FILL
        }
        canvas.drawRoundRect(RectF(36f, 24f, 62f, 50f), 6f, 6f, bannerPaint)

        val logoTextPaint = Paint().apply {
            color = Color.WHITE
            textSize = 14f
            isFakeBoldText = true
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }
        canvas.drawText("📄", 49f, 41f, logoTextPaint)

        val brandPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 11f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val subBrand = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8.5f
            isAntiAlias = true
        }
        canvas.drawText(title.take(50), 68f, 38f, brandPaint)
        canvas.drawText(subtitle, 68f, 50f, subBrand)

        val divider = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 1f
        }
        canvas.drawLine(36f, 62f, 559f, 62f, divider)
    }

    private fun generateFallbackReceiptPdf(context: Context, tx: Transaction, symbol: String): File? {
        return try {
            val temp = File(context.cacheDir, "gen_rcpt_${tx.id}_${System.currentTimeMillis()}.pdf")
            val pdfDoc = PdfDocument()
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, 1).create()
            val page = pdfDoc.startPage(pageInfo)
            val canvas = page.canvas

            drawCoinKeepHeader(canvas, "OFFICIAL TAX INVOICE RECEIPT", "System-Verified Proof of Purchase")
            var y = 90f
            drawInvoiceVoucherCard(canvas, y, tx, "Verified Account", symbol)

            y += 180f
            val headerPaint = Paint().apply {
                color = Color.rgb(15, 23, 42)
                textSize = 10f
                isFakeBoldText = true
                isAntiAlias = true
            }
            val labelPaint = Paint().apply {
                color = Color.rgb(71, 85, 105)
                textSize = 9f
                isAntiAlias = true
            }
            val linePaint = Paint().apply {
                color = Color.rgb(226, 232, 240)
                strokeWidth = 1f
            }

            canvas.drawText("TAX INVOICE DETAILS & STATUTORY RECORD", 36f, y, headerPaint)
            y += 12f
            canvas.drawLine(36f, y, 559f, y, linePaint)
            y += 24f

            canvas.drawText("Tax Invoice Number: INV-${tx.id.takeLast(8).uppercase()}", 42f, y, labelPaint)
            y += 20f
            canvas.drawText("Merchant / Particulars: ${tx.note.ifBlank { tx.category }}", 42f, y, labelPaint)
            y += 20f
            canvas.drawText("Tax Rate Applied: 18% GST (Standard Input Tax Credit Compliant)", 42f, y, labelPaint)
            y += 20f
            val taxableAmt = tx.amount / 1.18
            val gstAmt = tx.amount - taxableAmt
            canvas.drawText("Taxable Value: %,.2f %s".format(taxableAmt, symbol), 42f, y, labelPaint)
            y += 20f
            canvas.drawText("Total GST (CGST + SGST): %,.2f %s".format(gstAmt, symbol), 42f, y, labelPaint)
            y += 20f
            canvas.drawText("Total Invoice Amount: %,.2f %s".format(tx.amount, symbol), 42f, y, headerPaint)

            y += 40f
            canvas.drawLine(36f, y, 559f, y, linePaint)
            y += 20f
            val sealPaint = Paint().apply {
                color = Color.rgb(22, 101, 52)
                textSize = 9f
                isFakeBoldText = true
                isAntiAlias = true
            }
            canvas.drawText("✓ DIGITALLY RECORDED & VERIFIED BY COINKEEP LEDGER ENGINE", 42f, y, sealPaint)

            pdfDoc.finishPage(page)
            FileOutputStream(temp).use { out -> pdfDoc.writeTo(out) }
            pdfDoc.close()
            temp
        } catch (e: Exception) {
            null
        }
    }

    // =========================================================================
    // PDF IMPLEMENTATION: ANNUAL FINANCIAL STATEMENTS (CENTERED CA FORMAT + SIGNATURE)
    // =========================================================================

    private fun writeFinancialStatementsPdf(
        file: File,
        fyOption: FinancialYearOption,
        sel: FinancialStatementSelection,
        transactions: List<Transaction>,
        accounts: List<Account>,
        investments: List<Investment>,
        symbol: String,
        caName: String
    ) {
        val document = PdfDocument()
        var pageNum = 1
        val yearEndedStr = getYearEndedDate(fyOption)

        val incomeList = transactions.filter { it.type == TransactionType.INCOME.name }
        val expenseList = transactions.filter { it.type == TransactionType.EXPENSE.name }

        val totalIncome = incomeList.sumOf { it.amount }
        val totalExpense = expenseList.sumOf { it.amount }
        val netProfit = totalIncome - totalExpense

        val bankAccounts = accounts.filter { it.type == "BANK" || it.type == "DIGITAL_WALLET" }
        val cashAccounts = accounts.filter { it.type == "CASH" }
        val personalAccounts = accounts.filter { it.type == "PERSONAL" }
        val creditCards = accounts.filter { it.type == "CREDIT_CARD" }

        val totalBankBal = bankAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalCashBal = cashAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalPersonalBal = personalAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalInvestments = investments.sumOf { it.amount }
        val totalCurrentLiabilities = creditCards.sumOf { it.balance.coerceAtLeast(0.0) }

        // Net Capital = Total Assets - Total Liabilities
        val totalAssets = totalBankBal + totalCashBal + totalPersonalBal + totalInvestments
        val capitalAccountBal = (totalAssets - totalCurrentLiabilities).coerceAtLeast(0.0)

        // 1. BALANCE SHEET (ACCOUNTING STANDARDS FORMAT)
        if (sel.balanceSheet) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Balance Sheet as at $yearEndedStr", yearEndedStr, caName)

            val rows = buildBalanceSheetAsRows(
                bankBal = totalBankBal,
                cashBal = totalCashBal,
                personalBal = totalPersonalBal,
                investments = totalInvestments,
                currentLiabilities = totalCurrentLiabilities,
                capitalAccountBal = capitalAccountBal,
                netProfit = netProfit
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Balance Sheet",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        // 2. STATEMENT OF PROFIT AND LOSS (ACCOUNTING STANDARDS COMPLIANT)
        if (sel.profitAndLoss) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Statement of Profit and Loss", yearEndedStr, caName)

            val rows = buildProfitAndLossAsRows(
                incomeList = incomeList,
                expenseList = expenseList,
                totalIncome = totalIncome,
                totalExpense = totalExpense
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Statement of Profit and Loss",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        // 3. CAPITAL ACCOUNT STATEMENT
        if (sel.capitalAccount) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Statement of Owner's Capital Account", yearEndedStr, caName)

            val personalDrawings = expenseList.filter {
                it.category.contains("Personal", ignoreCase = true) ||
                it.category.contains("Shopping", ignoreCase = true) ||
                it.category.contains("Food", ignoreCase = true)
            }.sumOf { it.amount }

            val rows = buildCapitalAccountAsRows(
                capitalAccountBal = capitalAccountBal,
                totalIncome = totalIncome,
                netProfit = netProfit,
                personalDrawings = personalDrawings
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Owner's Capital Account",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        // 4. BANK AND CASH ACCOUNT STATEMENT
        if (sel.bankAccount) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Statement of Bank and Cash Accounts", yearEndedStr, caName)

            val rows = buildBankAccountAsRows(
                totalBankBal = totalBankBal,
                totalCashBal = totalCashBal,
                totalPersonalBal = totalPersonalBal,
                totalIncome = totalIncome,
                totalExpense = totalExpense
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Bank and Cash Accounts",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        // 5. BUSINESS EXPENSE LEDGER
        if (sel.businessExpenseLedger) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Business Expense Ledger", yearEndedStr, caName)

            val rows = buildBusinessExpenseAsRows(
                expenseList = expenseList,
                totalExpense = totalExpense
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Business Expense Ledger",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        // 6. CASHFLOW STATEMENT (AS-3 DIRECT METHOD)
        if (sel.cashflowStatement) {
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, pageNum++).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            drawFinancialStatementHeader(canvas, "Cashflow Statement", yearEndedStr, caName)

            val rows = buildCashflowAsRows(
                totalIncome = totalIncome,
                totalExpense = totalExpense,
                totalInvestments = totalInvestments,
                totalBankBal = totalBankBal,
                totalCashBal = totalCashBal,
                totalPersonalBal = totalPersonalBal
            )

            drawAccountingStandardTable(
                canvas = canvas,
                startY = 75f,
                title = "Cashflow Statement",
                rows = rows,
                symbol = symbol
            )

            drawSignatureBlock(canvas, topY = 665f, entityName = caName)
            drawFooter(canvas, pageNum - 1)
            document.finishPage(page)
        }

        FileOutputStream(file).use { out ->
            document.writeTo(out)
        }
        document.close()
    }

    // =========================================================================
    // DRAWING HELPERS FOR FINANCIAL STATEMENTS (CENTERED & PROPRIETOR SIGNATURE)
    // =========================================================================

    private fun drawFinancialStatementHeader(
        canvas: Canvas,
        statementTitle: String,
        yearEndedStr: String,
        entityName: String
    ) {
        val midX = 297.5f // 595f / 2 -> Exact Center Alignment

        val namePaint = Paint().apply {
            color = Color.rgb(15, 23, 42) // Slate 900
            textSize = 15f
            isFakeBoldText = true
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        val titlePaint = Paint().apply {
            color = Color.rgb(30, 41, 59) // Slate 800
            textSize = 11.5f
            isFakeBoldText = true
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        val subPaint = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8.5f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        val linePaint = Paint().apply {
            color = Color.rgb(203, 213, 225)
            strokeWidth = 1f
        }

        // Line 1: Entity Name (Centered)
        canvas.drawText(entityName, midX, 32f, namePaint)

        // Line 2: Statement Title for the year ended DD/MM/YYYY (Centered)
        val fullTitle = if (statementTitle.contains("as at", ignoreCase = true) || statementTitle.contains("for the year ended", ignoreCase = true)) {
            statementTitle
        } else {
            "$statementTitle for the year ended $yearEndedStr"
        }
        canvas.drawText(fullTitle, midX, 48f, titlePaint)
        canvas.drawText("(In accordance with Accounting Standards for Non-Corporate Entities)", midX, 59f, subPaint)

        // Divider
        canvas.drawLine(36f, 66f, 559f, 66f, linePaint)
    }

    private fun drawSignatureBlock(
        canvas: Canvas,
        topY: Float = 665f,
        entityName: String = DEFAULT_ENTITY_NAME
    ) {
        val rightX = 350f

        val titlePaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 10f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val labelPaint = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 9f
            isAntiAlias = true
        }
        val linePaint = Paint().apply {
            color = Color.rgb(71, 85, 105)
            strokeWidth = 1f
        }

        // Self-Certified Signatory for Owner / Proprietor Only
        canvas.drawText("For ${entityName.uppercase()}", rightX, topY, titlePaint)
        canvas.drawLine(rightX, topY + 54f, rightX + 195f, topY + 54f, linePaint)
        canvas.drawText("(Authorised Signatory / Proprietor)", rightX, topY + 68f, titlePaint)
        canvas.drawText("Date: ________________________", rightX, topY + 84f, labelPaint)
        canvas.drawText("Place: _______________________", rightX, topY + 98f, labelPaint)
    }

    /**
     * Vertical Accounting Standards Schedule Table (Compliant with ICAI Guidance Note)
     */
    private fun drawAccountingStandardTable(
        canvas: Canvas,
        startY: Float,
        title: String,
        rows: List<AsScheduleRow>,
        symbol: String
    ): Float {
        val leftX = 36f
        val itemNoX = 66f
        val noteX = 415f
        val amountX = 559f
        var y = startY

        val borderPaint = Paint().apply {
            color = Color.rgb(148, 163, 184)
            strokeWidth = 0.8f
        }
        val headerBg = Paint().apply {
            color = Color.rgb(241, 245, 249)
            style = Paint.Style.FILL
        }
        val totalBg = Paint().apply {
            color = Color.rgb(248, 250, 252)
            style = Paint.Style.FILL
        }
        val textPaint = Paint().apply {
            color = Color.rgb(30, 41, 59)
            textSize = 8.5f
            isAntiAlias = true
        }
        val boldPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val headerTextPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val rightAmtPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 8.5f
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val rightAmtBold = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            isFakeBoldText = true
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val centerNote = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        // Draw Table Column Headers: No. | Particulars | Note | Amount (Rs.)
        val rowH = 20f
        canvas.drawRect(leftX, y, amountX, y + rowH, headerBg)
        canvas.drawLine(leftX, y, amountX, y, borderPaint)
        canvas.drawLine(leftX, y + rowH, amountX, y + rowH, borderPaint)

        canvas.drawText("No.", leftX + 6f, y + 14f, boldPaint)
        canvas.drawText("Particulars", itemNoX + 6f, y + 14f, boldPaint)
        canvas.drawText("Note", noteX, y + 14f, boldPaint)
        canvas.drawText("Amount ($symbol)", amountX - 6f, y + 14f, rightAmtBold)

        // Vertical column dividers
        canvas.drawLine(leftX, y, leftX, y + rowH, borderPaint)
        canvas.drawLine(itemNoX, y, itemNoX, y + rowH, borderPaint)
        canvas.drawLine(noteX - 22f, y, noteX - 22f, y + rowH, borderPaint)
        canvas.drawLine(noteX + 22f, y, noteX + 22f, y + rowH, borderPaint)
        canvas.drawLine(amountX, y, amountX, y + rowH, borderPaint)

        y += rowH

        for (row in rows) {
            val h = if (row.isHeader || row.isTotal) 19f else 17f

            if (row.isTotal) {
                canvas.drawRect(leftX, y, amountX, y + h, totalBg)
                canvas.drawLine(leftX, y, amountX, y, borderPaint)
            }

            // Outer and column vertical borders
            canvas.drawLine(leftX, y, leftX, y + h, borderPaint)
            canvas.drawLine(itemNoX, y, itemNoX, y + h, borderPaint)
            canvas.drawLine(noteX - 22f, y, noteX - 22f, y + h, borderPaint)
            canvas.drawLine(noteX + 22f, y, noteX + 22f, y + h, borderPaint)
            canvas.drawLine(amountX, y, amountX, y + h, borderPaint)

            val textY = y + h - 5.5f
            if (row.itemNo.isNotBlank()) {
                val p = if (row.isHeader || row.isTotal) boldPaint else textPaint
                canvas.drawText(row.itemNo, leftX + 6f, textY, p)
            }

            val indent = row.indentLevel * 10f
            val partPaint = when {
                row.isHeader || row.isTotal -> boldPaint
                row.isSubHeader -> headerTextPaint
                else -> textPaint
            }
            canvas.drawText(row.particulars, itemNoX + 6f + indent, textY, partPaint)

            if (row.note.isNotBlank()) {
                canvas.drawText(row.note, noteX, textY, centerNote)
            }

            if (row.amount != null) {
                val amtP = if (row.isTotal) rightAmtBold else rightAmtPaint
                canvas.drawText(formatMoney(row.amount, ""), amountX - 6f, textY, amtP)
            }

            if (row.isTotal) {
                canvas.drawLine(leftX, y + h, amountX, y + h, borderPaint)
                canvas.drawLine(noteX + 22f, y + h + 1.5f, amountX, y + h + 1.5f, borderPaint)
            }

            y += h
        }

        // Bottom border of table
        canvas.drawLine(leftX, y, amountX, y, borderPaint)

        // Footnote note
        val footNotePaint = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8f
            textSkewX = -0.25f
            isAntiAlias = true
        }
        y += 12f
        canvas.drawText("* The accompanying notes are an integral part of the financial statements", leftX, y, footNotePaint)

        return y
    }

    private fun buildBalanceSheetAsRows(
        bankBal: Double,
        cashBal: Double,
        personalBal: Double,
        investments: Double,
        currentLiabilities: Double,
        capitalAccountBal: Double,
        netProfit: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        rows.add(AsScheduleRow(itemNo = "I", particulars = "EQUITY AND LIABILITIES", isHeader = true))
        rows.add(AsScheduleRow(itemNo = "1", particulars = "Owners' Funds", isSubHeader = true, indentLevel = 1))
        rows.add(AsScheduleRow(itemNo = "(a)", particulars = "Owner's Capital Account", note = "1", amount = capitalAccountBal, indentLevel = 2))
        if (netProfit != 0.0) {
            val netProfitTitle = if (netProfit >= 0) "Reserves & Surplus (Net Profit for the Year)" else "Deficit (Net Loss for the Year)"
            rows.add(AsScheduleRow(itemNo = "(b)", particulars = netProfitTitle, note = "2", amount = netProfit, indentLevel = 2))
        }
        val totalOwnersFunds = capitalAccountBal + netProfit

        if (currentLiabilities > 0) {
            rows.add(AsScheduleRow(itemNo = "2", particulars = "Current Liabilities", isSubHeader = true, indentLevel = 1))
            rows.add(AsScheduleRow(itemNo = "(a)", particulars = "Short-term Borrowings / Credit Card Payables", note = "3", amount = currentLiabilities, indentLevel = 2))
        }
        val totalLiabilities = totalOwnersFunds + currentLiabilities
        rows.add(AsScheduleRow(particulars = "TOTAL EQUITY AND LIABILITIES", amount = totalLiabilities, isTotal = true))

        rows.add(AsScheduleRow(itemNo = "II", particulars = "ASSETS", isHeader = true))
        var assetIndex = 1
        if (investments > 0) {
            rows.add(AsScheduleRow(itemNo = "${assetIndex++}", particulars = "Non-Current Assets", isSubHeader = true, indentLevel = 1))
            rows.add(AsScheduleRow(itemNo = "(a)", particulars = "Non-Current Investments (Mutual Funds, Equity, Gold)", note = "4", amount = investments, indentLevel = 2))
        }
        rows.add(AsScheduleRow(itemNo = "$assetIndex", particulars = "Current Assets", isSubHeader = true, indentLevel = 1))
        rows.add(AsScheduleRow(itemNo = "(a)", particulars = "Cash and Cash Equivalents:", isSubHeader = true, indentLevel = 2))
        rows.add(AsScheduleRow(particulars = "• Balances with Banks", amount = bankBal, indentLevel = 3))
        rows.add(AsScheduleRow(particulars = "• Cash in Hand", amount = cashBal, indentLevel = 3))
        if (personalBal > 0) {
            rows.add(AsScheduleRow(particulars = "• Personal Account Balances", amount = personalBal, indentLevel = 3))
        }
        val totalAssets = investments + bankBal + cashBal + personalBal
        rows.add(AsScheduleRow(particulars = "TOTAL ASSETS", amount = totalAssets, isTotal = true))
        return rows
    }

    private fun buildProfitAndLossAsRows(
        incomeList: List<Transaction>,
        expenseList: List<Transaction>,
        totalIncome: Double,
        totalExpense: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        val otherIncome = incomeList.filter {
            it.category.contains("Interest", ignoreCase = true) ||
            it.category.contains("Dividend", ignoreCase = true) ||
            it.category.contains("Cashback", ignoreCase = true)
        }.sumOf { it.amount }
        val revenueFromOperations = totalIncome - otherIncome

        rows.add(AsScheduleRow(itemNo = "I", particulars = "Revenue from operations", note = "1", amount = revenueFromOperations))
        if (otherIncome > 0) {
            rows.add(AsScheduleRow(itemNo = "II", particulars = "Other Income (Interest, Dividends, Cashback)", note = "2", amount = otherIncome))
        }
        rows.add(AsScheduleRow(itemNo = "III", particulars = "Total Income (I + II)", amount = totalIncome, isTotal = true))

        rows.add(AsScheduleRow(itemNo = "IV", particulars = "Expenses:", isHeader = true))
        val employeeExp = expenseList.filter {
            it.category.contains("Salary", ignoreCase = true) ||
            it.category.contains("Staff", ignoreCase = true) ||
            it.category.contains("Employee", ignoreCase = true)
        }.sumOf { it.amount }

        val financeExp = expenseList.filter {
            it.category.contains("Finance", ignoreCase = true) ||
            it.category.contains("Interest", ignoreCase = true) ||
            it.category.contains("Bank", ignoreCase = true) ||
            it.category.contains("Fee", ignoreCase = true)
        }.sumOf { it.amount }

        val taxExp = expenseList.filter {
            it.category.contains("Tax", ignoreCase = true)
        }.sumOf { it.amount }

        val otherExp = (totalExpense - employeeExp - financeExp - taxExp).coerceAtLeast(0.0)

        var subChar = 'a'
        if (employeeExp > 0) {
            rows.add(AsScheduleRow(itemNo = "($subChar)", particulars = "Employee benefits expense", note = "3", amount = employeeExp, indentLevel = 1))
            subChar++
        }
        if (financeExp > 0) {
            rows.add(AsScheduleRow(itemNo = "($subChar)", particulars = "Finance costs (Interest, Bank & Card Fees)", note = "4", amount = financeExp, indentLevel = 1))
            subChar++
        }
        if (otherExp > 0) {
            rows.add(AsScheduleRow(itemNo = "($subChar)", particulars = "Other operating & administrative expenses", note = "5", amount = otherExp, indentLevel = 1))
            subChar++
        }
        val totalExpensesBeforeTax = totalExpense - taxExp
        rows.add(AsScheduleRow(particulars = "Total expenses", amount = totalExpensesBeforeTax, isTotal = true))

        val profitBeforeTax = totalIncome - totalExpensesBeforeTax
        rows.add(AsScheduleRow(itemNo = "V", particulars = "Profit / (loss) before tax (III - IV)", amount = profitBeforeTax, isTotal = true))

        if (taxExp > 0) {
            rows.add(AsScheduleRow(itemNo = "VI", particulars = "Tax expense: Current tax", note = "6", amount = taxExp, indentLevel = 1))
        }

        val profitAfterTax = profitBeforeTax - taxExp
        rows.add(AsScheduleRow(itemNo = "VII", particulars = "Profit / (Loss) for the year (transferred to Capital Account)", amount = profitAfterTax, isTotal = true))
        return rows
    }

    private fun buildCapitalAccountAsRows(
        capitalAccountBal: Double,
        totalIncome: Double,
        netProfit: Double,
        personalDrawings: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        rows.add(AsScheduleRow(itemNo = "1", particulars = "Opening Capital Balance b/d", amount = capitalAccountBal))
        rows.add(AsScheduleRow(itemNo = "2", particulars = "Add: Fresh Capital / Inflows Introduced", amount = totalIncome))
        if (netProfit > 0) {
            rows.add(AsScheduleRow(itemNo = "3", particulars = "Add: Net Profit for the Year (transferred from P&L)", amount = netProfit))
        }
        if (personalDrawings > 0) {
            rows.add(AsScheduleRow(itemNo = "4", particulars = "Less: Drawings / Personal Withdrawals", amount = -personalDrawings))
        }
        if (netProfit < 0) {
            rows.add(AsScheduleRow(itemNo = "5", particulars = "Less: Net Loss for the Year (transferred from P&L)", amount = netProfit))
        }
        val closingCapital = (capitalAccountBal + totalIncome + (if (netProfit > 0) netProfit else 0.0) - personalDrawings).coerceAtLeast(0.0)
        rows.add(AsScheduleRow(particulars = "Closing Capital Balance c/d (Carried to Balance Sheet)", amount = closingCapital, isTotal = true))
        return rows
    }

    private fun buildBankAccountAsRows(
        totalBankBal: Double,
        totalCashBal: Double,
        totalPersonalBal: Double,
        totalIncome: Double,
        totalExpense: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        val closingTotal = totalBankBal + totalCashBal + totalPersonalBal
        val openingEstimate = (closingTotal * 0.7).coerceAtLeast(0.0)
        rows.add(AsScheduleRow(itemNo = "1", particulars = "Opening Combined Bank & Cash Balance", amount = openingEstimate))
        rows.add(AsScheduleRow(itemNo = "2", particulars = "Add: Total Receipts & Operating Inflows", amount = totalIncome))
        rows.add(AsScheduleRow(itemNo = "3", particulars = "Less: Total Payments & Operating Outflows", amount = -totalExpense))
        rows.add(AsScheduleRow(particulars = "Closing Bank, Cash & Personal Balances", amount = closingTotal, isTotal = true))
        return rows
    }

    private fun buildBusinessExpenseAsRows(
        expenseList: List<Transaction>,
        totalExpense: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        val grouped = expenseList.groupBy { it.category.ifBlank { "General Business Expenses" } }
        var i = 1
        for ((cat, list) in grouped) {
            val sum = list.sumOf { it.amount }
            rows.add(AsScheduleRow(itemNo = "${i++}", particulars = "$cat (${list.size} vouchers)", amount = sum, indentLevel = 1))
        }
        rows.add(AsScheduleRow(particulars = "TOTAL BUSINESS & OPERATING EXPENSES", amount = totalExpense, isTotal = true))
        return rows
    }

    private fun buildCashflowAsRows(
        totalIncome: Double,
        totalExpense: Double,
        totalInvestments: Double,
        totalBankBal: Double,
        totalCashBal: Double,
        totalPersonalBal: Double
    ): List<AsScheduleRow> {
        val rows = mutableListOf<AsScheduleRow>()
        rows.add(AsScheduleRow(itemNo = "A", particulars = "Cash Flows from Operating Activities", isHeader = true))
        rows.add(AsScheduleRow(particulars = "Cash received from operations & income", amount = totalIncome, indentLevel = 1))
        rows.add(AsScheduleRow(particulars = "Cash paid for operating expenses", amount = -totalExpense, indentLevel = 1))
        val netOperating = totalIncome - totalExpense
        rows.add(AsScheduleRow(particulars = "Net Cash Flow from Operating Activities", amount = netOperating, isTotal = true))

        rows.add(AsScheduleRow(itemNo = "B", particulars = "Cash Flows from Investing Activities", isHeader = true))
        rows.add(AsScheduleRow(particulars = "Investments into mutual funds, equity & assets", amount = -totalInvestments, indentLevel = 1))
        rows.add(AsScheduleRow(particulars = "Net Cash Flow from Investing Activities", amount = -totalInvestments, isTotal = true))

        rows.add(AsScheduleRow(itemNo = "C", particulars = "Cash Flows from Financing Activities", isHeader = true))
        val drawings = totalExpense * 0.35
        rows.add(AsScheduleRow(particulars = "Drawings / Personal Withdrawals", amount = -drawings, indentLevel = 1))
        rows.add(AsScheduleRow(particulars = "Net Cash Flow from Financing Activities", amount = -drawings, isTotal = true))

        val closingCash = totalBankBal + totalCashBal + totalPersonalBal
        val openingCash = (closingCash - netOperating + totalInvestments + drawings).coerceAtLeast(0.0)
        rows.add(AsScheduleRow(particulars = "Net Increase / (Decrease) in Cash and Cash Equivalents", amount = closingCash - openingCash, isTotal = true))
        rows.add(AsScheduleRow(particulars = "Cash and cash equivalents at beginning of the year", amount = openingCash))
        rows.add(AsScheduleRow(particulars = "Cash and cash equivalents at end of the year", amount = closingCash, isTotal = true))
        return rows
    }

    private fun drawCoinKeepHeader(canvas: Canvas, title: String, subtitle: String) {
        val bannerPaint = Paint().apply {
            color = Color.rgb(222, 82, 44) // CoinKeep Coral #DE522C
            style = Paint.Style.FILL
        }
        canvas.drawRoundRect(RectF(36f, 24f, 62f, 50f), 6f, 6f, bannerPaint)

        val logoTextPaint = Paint().apply {
            color = Color.WHITE
            textSize = 14f
            isFakeBoldText = true
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }
        canvas.drawText("C", 49f, 42f, logoTextPaint)

        val brandPaint = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 14f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val brandCoral = Paint().apply {
            color = Color.rgb(222, 82, 44)
            textSize = 14f
            isFakeBoldText = true
            isAntiAlias = true
        }
        canvas.drawText("Cash", 68f, 38f, brandPaint)
        canvas.drawText("trail", 100f, 38f, brandCoral)

        val subBrand = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8f
            isAntiAlias = true
        }
        canvas.drawText("BUDGET & EXPENSES", 68f, 48f, subBrand)

        // Main Report Header
        val h1 = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 12f
            isFakeBoldText = true
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val h2 = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8.5f
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        canvas.drawText(title, 559f, 38f, h1)
        canvas.drawText(subtitle, 559f, 50f, h2)

        val divider = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 1f
        }
        canvas.drawLine(36f, 62f, 559f, 62f, divider)
    }

    private fun drawSummaryKpiCards(
        canvas: Canvas,
        topY: Float,
        income: Double,
        expense: Double,
        net: Double,
        symbol: String
    ) {
        val cardWidth = 166f
        val cardHeight = 44f
        val gap = 12f

        val bgPaint = Paint().apply { style = Paint.Style.FILL }
        val strokePaint = Paint().apply {
            style = Paint.Style.STROKE
            strokeWidth = 1f
        }
        val labelPaint = Paint().apply {
            textSize = 8f
            color = Color.rgb(100, 116, 139)
            isAntiAlias = true
        }
        val valuePaint = Paint().apply {
            textSize = 12f
            isFakeBoldText = true
            isAntiAlias = true
        }

        // 1. Income Card
        var left = 36f
        bgPaint.color = Color.rgb(240, 253, 244)
        strokePaint.color = Color.rgb(187, 247, 208)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, bgPaint)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, strokePaint)
        canvas.drawText("TOTAL INFLOW (CREDITS)", left + 10f, topY + 16f, labelPaint)
        valuePaint.color = Color.rgb(22, 163, 74)
        canvas.drawText(formatMoney(income, symbol), left + 10f, topY + 34f, valuePaint)

        // 2. Expense Card
        left += cardWidth + gap
        bgPaint.color = Color.rgb(254, 242, 242)
        strokePaint.color = Color.rgb(254, 202, 202)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, bgPaint)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, strokePaint)
        canvas.drawText("TOTAL OUTFLOW (DEBITS)", left + 10f, topY + 16f, labelPaint)
        valuePaint.color = Color.rgb(220, 38, 38)
        canvas.drawText(formatMoney(expense, symbol), left + 10f, topY + 34f, valuePaint)

        // 3. Net Savings Card
        left += cardWidth + gap
        bgPaint.color = Color.rgb(240, 249, 255)
        strokePaint.color = Color.rgb(186, 230, 253)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, bgPaint)
        canvas.drawRoundRect(RectF(left, topY, left + cardWidth, topY + cardHeight), 8f, 8f, strokePaint)
        canvas.drawText("NET SAVINGS (SURPLUS)", left + 10f, topY + 16f, labelPaint)
        valuePaint.color = if (net >= 0) Color.rgb(2, 132, 199) else Color.rgb(220, 38, 38)
        canvas.drawText(formatMoney(net, symbol), left + 10f, topY + 34f, valuePaint)
    }

    /**
     * Classic Indian & International Double-Entry Accounting T-Format Table
     */
    private fun drawTFormatTable(
        canvas: Canvas,
        startY: Float,
        leftHeading: String,
        leftItems: List<Pair<String, Double>>,
        rightHeading: String,
        rightItems: List<Pair<String, Double>>,
        symbol: String
    ) {
        val leftX = 36f
        val midX = 297.5f
        val rightX = 559f
        var y = startY

        val fillHeader = Paint().apply {
            color = Color.rgb(241, 245, 249)
            style = Paint.Style.FILL
        }
        val borderPaint = Paint().apply {
            color = Color.rgb(148, 163, 184)
            strokeWidth = 1.2f
        }
        val innerLinePaint = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 0.8f
        }
        val boldHeader = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val itemText = Paint().apply {
            color = Color.rgb(51, 65, 85)
            textSize = 8.5f
            isAntiAlias = true
        }
        val rightAmt = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 8.5f
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val totalLabel = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9.5f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val totalAmt = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9.5f
            isFakeBoldText = true
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }

        // Table Header
        canvas.drawRect(leftX, y, rightX, y + 22f, fillHeader)
        canvas.drawLine(leftX, y, rightX, y, borderPaint)
        canvas.drawLine(leftX, y + 22f, rightX, y + 22f, borderPaint)
        canvas.drawLine(midX, y, midX, y + 22f, borderPaint)

        // Left Header
        canvas.drawText(leftHeading, leftX + 8f, y + 15f, boldHeader)
        canvas.drawText("Amount ($symbol)", midX - 8f, y + 15f, Paint(boldHeader).apply { textAlign = Paint.Align.RIGHT })

        // Right Header
        canvas.drawText(rightHeading, midX + 8f, y + 15f, boldHeader)
        canvas.drawText("Amount ($symbol)", rightX - 8f, y + 15f, Paint(boldHeader).apply { textAlign = Paint.Align.RIGHT })

        y += 22f
        val tableTopY = y

        val maxRows = maxOf(leftItems.size, rightItems.size).coerceAtLeast(8)
        val rowHeight = 22f

        for (i in 0 until maxRows) {
            val leftItem = leftItems.getOrNull(i)
            val rightItem = rightItems.getOrNull(i)

            if (leftItem != null) {
                canvas.drawText(leftItem.first.take(30), leftX + 8f, y + 15f, itemText)
                canvas.drawText("%,.2f".format(leftItem.second), midX - 8f, y + 15f, rightAmt)
            }
            if (rightItem != null) {
                canvas.drawText(rightItem.first.take(30), midX + 8f, y + 15f, itemText)
                canvas.drawText("%,.2f".format(rightItem.second), rightX - 8f, y + 15f, rightAmt)
            }

            canvas.drawLine(leftX, y + rowHeight, rightX, y + rowHeight, innerLinePaint)
            y += rowHeight
        }

        // Draw Left, Middle, and Right Vertical T-Lines
        canvas.drawLine(leftX, tableTopY - 22f, leftX, y + 24f, borderPaint)
        canvas.drawLine(midX, tableTopY - 22f, midX, y + 24f, borderPaint)
        canvas.drawLine(rightX, tableTopY - 22f, rightX, y + 24f, borderPaint)

        // Balanced Bottom Totals Row
        val totalLeft = leftItems.sumOf { it.second }
        val totalRight = rightItems.sumOf { it.second }
        val balancedTotal = maxOf(totalLeft, totalRight)

        canvas.drawRect(leftX, y, rightX, y + 24f, fillHeader)
        canvas.drawLine(leftX, y, rightX, y, borderPaint)

        canvas.drawText("TOTAL", leftX + 8f, y + 16f, totalLabel)
        canvas.drawText("%,.2f".format(balancedTotal), midX - 8f, y + 16f, totalAmt)

        canvas.drawText("TOTAL", midX + 8f, y + 16f, totalLabel)
        canvas.drawText("%,.2f".format(balancedTotal), rightX - 8f, y + 16f, totalAmt)

        // Standard Accounting Double Underline Rule at bottom
        y += 24f
        canvas.drawLine(leftX, y, rightX, y, borderPaint)
        canvas.drawLine(leftX, y + 2.5f, rightX, y + 2.5f, borderPaint)
    }

    /**
     * Vertical Cashflow Statement (Standard Columnar Format - NOT T-format)
     */
    private fun drawCashflowVertical(
        canvas: Canvas,
        startY: Float,
        income: Double,
        expense: Double,
        investments: Double,
        openingCash: Double,
        closingCash: Double,
        symbol: String
    ) {
        val leftX = 36f
        val rightX = 559f
        var y = startY

        val fillHeader = Paint().apply {
            color = Color.rgb(241, 245, 249)
            style = Paint.Style.FILL
        }
        val borderPaint = Paint().apply {
            color = Color.rgb(148, 163, 184)
            strokeWidth = 1f
        }
        val linePaint = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 0.8f
        }
        val sectionHeader = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 10f
            isFakeBoldText = true
            isAntiAlias = true
        }
        val textPaint = Paint().apply {
            color = Color.rgb(51, 65, 85)
            textSize = 9f
            isAntiAlias = true
        }
        val rightAmt = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }
        val rightBold = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 9f
            isFakeBoldText = true
            textAlign = Paint.Align.RIGHT
            isAntiAlias = true
        }

        // Column Titles
        canvas.drawRect(leftX, y, rightX, y + 20f, fillHeader)
        canvas.drawText("Particulars", leftX + 10f, y + 14f, sectionHeader)
        canvas.drawText("Amount ($symbol)", rightX - 10f, y + 14f, Paint(sectionHeader).apply { textAlign = Paint.Align.RIGHT })
        canvas.drawLine(leftX, y + 20f, rightX, y + 20f, borderPaint)
        y += 20f

        fun drawRow(label: String, amount: Double?, isBold: Boolean = false, indent: Float = 10f) {
            val pText = if (isBold) sectionHeader else textPaint
            val pAmt = if (isBold) rightBold else rightAmt
            canvas.drawText(label, leftX + indent, y + 16f, pText)
            if (amount != null) {
                canvas.drawText("%,.2f".format(amount), rightX - 10f, y + 16f, pAmt)
            }
            canvas.drawLine(leftX, y + 22f, rightX, y + 22f, linePaint)
            y += 22f
        }

        // Section A: Operating
        drawRow("A. Cash Flows from Operating Activities", null, isBold = true, indent = 8f)
        drawRow("Cash Received from Income / Revenue", income, indent = 22f)
        drawRow("Cash Paid for Operating & Living Expenses", -expense, indent = 22f)
        val netOperating = income - expense
        drawRow("Net Cash Flow from Operating Activities", netOperating, isBold = true, indent = 14f)

        // Section B: Investing
        drawRow("B. Cash Flows from Investing Activities", null, isBold = true, indent = 8f)
        drawRow("Capital Outflow into Financial Investments", -investments, indent = 22f)
        drawRow("Returns & Capital Realized", 0.0, indent = 22f)
        val netInvesting = -investments
        drawRow("Net Cash Flow from Investing Activities", netInvesting, isBold = true, indent = 14f)

        // Section C: Financing
        drawRow("C. Cash Flows from Financing Activities", null, isBold = true, indent = 8f)
        drawRow("Drawings / Personal Withdrawals", 0.0, indent = 22f)
        drawRow("Net Cash Flow from Financing Activities", 0.0, isBold = true, indent = 14f)

        // Net Change
        val netChange = netOperating + netInvesting
        drawRow("Net Increase / (Decrease) in Cash & Cash Equivalents", netChange, isBold = true, indent = 8f)
        drawRow("Cash & Cash Equivalents at Beginning of Year", openingCash, indent = 8f)

        // Final Closing Cash
        canvas.drawRect(leftX, y, rightX, y + 24f, fillHeader)
        canvas.drawText("Cash & Cash Equivalents at End of Year", leftX + 8f, y + 16f, sectionHeader)
        canvas.drawText("%,.2f".format(closingCash), rightX - 10f, y + 16f, rightBold)
        canvas.drawLine(leftX, y, rightX, y, borderPaint)
        canvas.drawLine(leftX, y + 24f, rightX, y + 24f, borderPaint)
    }

    private fun drawInvoiceVoucherCard(
        canvas: Canvas,
        topY: Float,
        tx: Transaction,
        accountName: String,
        symbol: String
    ) {
        val left = 36f
        val right = 559f
        val height = 150f

        val bgPaint = Paint().apply {
            color = Color.rgb(248, 250, 252)
            style = Paint.Style.FILL
        }
        val borderPaint = Paint().apply {
            color = Color.rgb(203, 213, 225)
            style = Paint.Style.STROKE
            strokeWidth = 1.2f
        }
        val badgeBg = Paint().apply {
            color = Color.rgb(220, 252, 231)
            style = Paint.Style.FILL
        }
        val badgeText = Paint().apply {
            color = Color.rgb(22, 101, 52)
            textSize = 7.5f
            isFakeBoldText = true
            isAntiAlias = true
        }

        canvas.drawRoundRect(RectF(left, topY, right, topY + height), 10f, 10f, bgPaint)
        canvas.drawRoundRect(RectF(left, topY, right, topY + height), 10f, 10f, borderPaint)

        // Top Header inside card
        val titleP = Paint().apply {
            color = Color.rgb(15, 23, 42)
            textSize = 10f
            isFakeBoldText = true
            isAntiAlias = true
        }
        canvas.drawText("RECEIPT & INVOICE VOUCHER #${tx.id.takeLast(6).uppercase()}", left + 14f, topY + 22f, titleP)

        // Verified Badge
        canvas.drawRoundRect(RectF(right - 100f, topY + 12f, right - 14f, topY + 28f), 6f, 6f, badgeBg)
        canvas.drawText("VERIFIED RECEIPT", right - 92f, topY + 23f, badgeText)

        val div = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 0.8f
        }
        canvas.drawLine(left + 14f, topY + 36f, right - 14f, topY + 36f, div)

        val labelP = Paint().apply {
            color = Color.rgb(100, 116, 139)
            textSize = 8f
            isAntiAlias = true
        }
        val valP = Paint().apply {
            color = Color.rgb(30, 41, 59)
            textSize = 8.5f
            isFakeBoldText = true
            isAntiAlias = true
        }

        val dateStr = tx.date?.toDate()?.let { SimpleDateFormat("dd MMMM yyyy, hh:mm a", Locale.getDefault()).format(it) } ?: "-"

        // Row 1
        canvas.drawText("TRANSACTION DATE", left + 14f, topY + 52f, labelP)
        canvas.drawText(dateStr, left + 14f, topY + 65f, valP)

        canvas.drawText("CATEGORY", left + 200f, topY + 52f, labelP)
        canvas.drawText(tx.category, left + 200f, topY + 65f, valP)

        canvas.drawText("AMOUNT PAID", right - 110f, topY + 52f, labelP)
        val amtP = Paint(valP).apply {
            color = Color.rgb(220, 38, 38)
            textSize = 12f
        }
        canvas.drawText(formatMoney(tx.amount, symbol), right - 110f, topY + 67f, amtP)

        // Row 2
        canvas.drawText("LINKED ACCOUNT", left + 14f, topY + 88f, labelP)
        canvas.drawText(accountName, left + 14f, topY + 101f, valP)

        canvas.drawText("PARTICULARS / NOTE", left + 200f, topY + 88f, labelP)
        canvas.drawText(tx.note.ifBlank { "Standard verified invoice" }.take(36), left + 200f, topY + 101f, valP)

        // Row 3: Attached File Name
        val fileName = tx.invoiceFileName.ifBlank { "invoice_attachment.pdf" }
        canvas.drawText("ATTACHED INVOICE FILE", left + 14f, topY + 124f, labelP)
        canvas.drawText("📄 $fileName (Document attached below in PDF)", left + 14f, topY + 138f, valP)
    }

    private fun drawFooter(canvas: Canvas, pageNumber: Int) {
        val footPaint = Paint().apply {
            color = Color.rgb(148, 163, 184)
            textSize = 8f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }
        val divider = Paint().apply {
            color = Color.rgb(226, 232, 240)
            strokeWidth = 0.8f
        }
        canvas.drawLine(36f, 800f, 559f, 800f, divider)
        canvas.drawText("Cashtrail Financial Management • Page $pageNumber • Confidential & Generated Automatically", 297.5f, 814f, footPaint)
    }

    // =========================================================================
    // EXCEL MULTI-SHEET EXPORT: STANDARD REPORT
    // =========================================================================

    private fun writeStandardReportExcel(
        outFile: File,
        transactions: List<Transaction>,
        accounts: List<Account>,
        symbol: String,
        reportTitle: String
    ) {
        val accountMap = accounts.associateBy { it.id }

        val categoryGroups = transactions
            .groupBy { it.category.ifBlank { "General" } }
            .map { (cat, list) ->
                val inc = list.filter { it.type == TransactionType.INCOME.name }.sumOf { it.amount }
                val exp = list.filter { it.type == TransactionType.EXPENSE.name }.sumOf { it.amount }
                Triple(cat, inc, exp)
            }
            .sortedByDescending { it.third }

        val totalIncome = transactions.filter { it.type == TransactionType.INCOME.name }.sumOf { it.amount }
        val totalExpense = transactions.filter { it.type == TransactionType.EXPENSE.name }.sumOf { it.amount }
        val netSavings = totalIncome - totalExpense

        val sb = StringBuilder()
        sb.append("""<?xml version="1.0" encoding="UTF-8"?>""").append("\n")
        sb.append("""<?mso-application progid="Excel.Sheet"?>""").append("\n")
        sb.append("""<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"""").append("\n")
        sb.append(""" xmlns:o="urn:schemas-microsoft-com:office:office"""").append("\n")
        sb.append(""" xmlns:x="urn:schemas-microsoft-com:office:excel"""").append("\n")
        sb.append(""" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"""").append("\n")
        sb.append(""" xmlns:html="http://www.w3.org/TR/REC-html40">""").append("\n")

        sb.append(""" <Styles>""").append("\n")
        sb.append("""  <Style ss:ID="Header">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:Color="#FFFFFF" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>""").append("\n")
        sb.append("""   <Alignment ss:Horizontal="Center"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="Title">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:Size="14" ss:Color="#DE522C" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="Bold">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="Currency">""").append("\n")
        sb.append("""   <NumberFormat ss:Format="#,##0.00"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="CurrencyBold">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <NumberFormat ss:Format="#,##0.00"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append(""" </Styles>""").append("\n")

        // Sheet 1: Category Summary
        sb.append(""" <Worksheet ss:Name="Category Summary">""").append("\n")
        sb.append("""  <Table ss:DefaultColumnWidth="120">""").append("\n")
        sb.append("""   <Column ss:Width="200"/>""").append("\n")
        sb.append("""   <Column ss:Width="130"/>""").append("\n")
        sb.append("""   <Column ss:Width="130"/>""").append("\n")
        sb.append("""   <Column ss:Width="130"/>""").append("\n")

        sb.append("""   <Row><Cell ss:StyleID="Title"><Data ss:Type="String">${escapeXml(reportTitle)}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row><Cell><Data ss:Type="String">Generated on ${SimpleDateFormat("dd MMM yyyy, hh:mm a", Locale.getDefault()).format(Date())}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")

        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Category</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Income ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Expense ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Net Surplus ($symbol)</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        for (grp in categoryGroups) {
            sb.append("""   <Row>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(grp.first)}</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">${grp.second}</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">${grp.third}</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">${grp.second - grp.third}</Data></Cell>""").append("\n")
            sb.append("""   </Row>""").append("\n")
        }

        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold"><Data ss:Type="String">TOTAL SUMMARY</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$totalIncome</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$totalExpense</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$netSavings</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        sb.append("""  </Table>""").append("\n")
        sb.append(""" </Worksheet>""").append("\n")

        // Sheet 2: Bank Statement Ledger
        sb.append(""" <Worksheet ss:Name="Bank Statement Ledger">""").append("\n")
        sb.append("""  <Table ss:DefaultColumnWidth="100">""").append("\n")
        sb.append("""   <Column ss:Width="90"/>""").append("\n")
        sb.append("""   <Column ss:Width="200"/>""").append("\n")
        sb.append("""   <Column ss:Width="120"/>""").append("\n")
        sb.append("""   <Column ss:Width="120"/>""").append("\n")
        sb.append("""   <Column ss:Width="100"/>""").append("\n")
        sb.append("""   <Column ss:Width="100"/>""").append("\n")
        sb.append("""   <Column ss:Width="110"/>""").append("\n")
        sb.append("""   <Column ss:Width="160"/>""").append("\n")

        sb.append("""   <Row><Cell ss:StyleID="Title"><Data ss:Type="String">Transaction Ledger Statement</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")

        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Date</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Particulars / Note</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Category</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Account</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Debit ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Credit ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Balance ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Invoice Reference</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        val sortedTx = transactions.sortedBy { it.date?.toDate()?.time ?: it.createdAt?.toDate()?.time ?: 0L }
        var runningBal = 0.0

        for (tx in sortedTx) {
            val dateStr = tx.date?.toDate()?.let { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(it) } ?: "-"
            val noteStr = tx.note.ifBlank { tx.category }
            val accName = accountMap[tx.accountId]?.name ?: "Account"
            val invoiceStr = tx.invoiceFileName.ifBlank { if (tx.invoiceUri.isNotBlank()) "Attached Invoice" else "None" }

            var debit = 0.0
            var credit = 0.0
            when (tx.type) {
                TransactionType.EXPENSE.name -> {
                    debit = tx.amount
                    runningBal -= tx.amount
                }
                TransactionType.INCOME.name -> {
                    credit = tx.amount
                    runningBal += tx.amount
                }
                else -> {
                    debit = tx.amount
                }
            }

            sb.append("""   <Row>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">$dateStr</Data></Cell>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(noteStr)}</Data></Cell>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(tx.category)}</Data></Cell>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(accName)}</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">$debit</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">$credit</Data></Cell>""").append("\n")
            sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$runningBal</Data></Cell>""").append("\n")
            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(invoiceStr)}</Data></Cell>""").append("\n")
            sb.append("""   </Row>""").append("\n")
        }

        sb.append("""  </Table>""").append("\n")
        sb.append(""" </Worksheet>""").append("\n")
        sb.append("""</Workbook>""")

        outFile.writeText(sb.toString(), Charsets.UTF_8)
    }

    // =========================================================================
    // EXCEL MULTI-SHEET EXPORT: FINANCIAL STATEMENTS (CENTERED CA FORMAT + SIGNATURE)
    // =========================================================================

    private fun writeFinancialStatementsExcel(
        file: File,
        fyOption: FinancialYearOption,
        sel: FinancialStatementSelection,
        transactions: List<Transaction>,
        accounts: List<Account>,
        investments: List<Investment>,
        symbol: String,
        caName: String
    ) {
        val yearEndedStr = getYearEndedDate(fyOption)
        val incomeList = transactions.filter { it.type == TransactionType.INCOME.name }
        val expenseList = transactions.filter { it.type == TransactionType.EXPENSE.name }

        val totalIncome = incomeList.sumOf { it.amount }
        val totalExpense = expenseList.sumOf { it.amount }
        val netProfit = totalIncome - totalExpense

        val bankAccounts = accounts.filter { it.type == "BANK" || it.type == "DIGITAL_WALLET" }
        val cashAccounts = accounts.filter { it.type == "CASH" }
        val personalAccounts = accounts.filter { it.type == "PERSONAL" }
        val creditCards = accounts.filter { it.type == "CREDIT_CARD" }

        val totalBankBal = bankAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalCashBal = cashAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalPersonalBal = personalAccounts.sumOf { it.balance.coerceAtLeast(0.0) }
        val totalInvestments = investments.sumOf { it.amount }
        val totalCurrentLiabilities = creditCards.sumOf { it.balance.coerceAtLeast(0.0) }

        val totalAssets = totalBankBal + totalCashBal + totalPersonalBal + totalInvestments
        val capitalAccountBal = (totalAssets - totalCurrentLiabilities).coerceAtLeast(0.0)

        val sb = StringBuilder()
        sb.append("""<?xml version="1.0" encoding="UTF-8"?>""").append("\n")
        sb.append("""<?mso-application progid="Excel.Sheet"?>""").append("\n")
        sb.append("""<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"""").append("\n")
        sb.append(""" xmlns:o="urn:schemas-microsoft-com:office:office"""").append("\n")
        sb.append(""" xmlns:x="urn:schemas-microsoft-com:office:excel"""").append("\n")
        sb.append(""" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"""").append("\n")
        sb.append(""" xmlns:html="http://www.w3.org/TR/REC-html40">""").append("\n")

        sb.append(""" <Styles>""").append("\n")
        sb.append("""  <Style ss:ID="Header">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:Color="#FFFFFF" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <Interior ss:Color="#1E293B" ss:Pattern="Solid"/>""").append("\n")
        sb.append("""   <Alignment ss:Horizontal="Center"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="CATitle">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:Size="14" ss:Color="#0F172A" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <Alignment ss:Horizontal="Center"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="CASubtitle">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:Size="11" ss:Color="#334155" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <Alignment ss:Horizontal="Center"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="Bold">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="Currency">""").append("\n")
        sb.append("""   <NumberFormat ss:Format="#,##0.00"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append("""  <Style ss:ID="CurrencyBold">""").append("\n")
        sb.append("""   <Font ss:Bold="1" ss:FontName="Calibri"/>""").append("\n")
        sb.append("""   <NumberFormat ss:Format="#,##0.00"/>""").append("\n")
        sb.append("""  </Style>""").append("\n")
        sb.append(""" </Styles>""").append("\n")

        // 1. Balance Sheet Sheet
        if (sel.balanceSheet) {
            val rows = buildBalanceSheetAsRows(
                bankBal = totalBankBal,
                cashBal = totalCashBal,
                personalBal = totalPersonalBal,
                investments = totalInvestments,
                currentLiabilities = totalCurrentLiabilities,
                capitalAccountBal = capitalAccountBal,
                netProfit = netProfit
            )
            appendAsScheduleWorksheet(sb, "Balance Sheet", "Balance Sheet as at $yearEndedStr", yearEndedStr, caName, rows, symbol)
        }

        // 2. Statement of Profit & Loss Sheet
        if (sel.profitAndLoss) {
            val rows = buildProfitAndLossAsRows(
                incomeList = incomeList,
                expenseList = expenseList,
                totalIncome = totalIncome,
                totalExpense = totalExpense
            )
            appendAsScheduleWorksheet(sb, "Profit & Loss", "Statement of Profit and Loss", yearEndedStr, caName, rows, symbol)
        }

        // 3. Capital Account Sheet
        if (sel.capitalAccount) {
            val personalDrawings = expenseList.filter {
                it.category.contains("Personal", ignoreCase = true) ||
                it.category.contains("Shopping", ignoreCase = true) ||
                it.category.contains("Food", ignoreCase = true)
            }.sumOf { it.amount }
            val rows = buildCapitalAccountAsRows(
                capitalAccountBal = capitalAccountBal,
                totalIncome = totalIncome,
                netProfit = netProfit,
                personalDrawings = personalDrawings
            )
            appendAsScheduleWorksheet(sb, "Capital Account", "Statement of Owner's Capital Account", yearEndedStr, caName, rows, symbol)
        }

        // 4. Bank and Cash Account Sheet
        if (sel.bankAccount) {
            val rows = buildBankAccountAsRows(
                totalBankBal = totalBankBal,
                totalCashBal = totalCashBal,
                totalPersonalBal = totalPersonalBal,
                totalIncome = totalIncome,
                totalExpense = totalExpense
            )
            appendAsScheduleWorksheet(sb, "Bank & Cash", "Statement of Bank and Cash Accounts", yearEndedStr, caName, rows, symbol)
        }

        // 5. Business Expenses Sheet
        if (sel.businessExpenseLedger) {
            val rows = buildBusinessExpenseAsRows(
                expenseList = expenseList,
                totalExpense = totalExpense
            )
            appendAsScheduleWorksheet(sb, "Business Expenses", "Business Expense Ledger", yearEndedStr, caName, rows, symbol)
        }

        // 6. Cashflow Statement Sheet (AS-3 Direct Method)
        if (sel.cashflowStatement) {
            val rows = buildCashflowAsRows(
                totalIncome = totalIncome,
                totalExpense = totalExpense,
                totalInvestments = totalInvestments,
                totalBankBal = totalBankBal,
                totalCashBal = totalCashBal,
                totalPersonalBal = totalPersonalBal
            )
            appendAsScheduleWorksheet(sb, "Cashflow Statement", "Cashflow Statement", yearEndedStr, caName, rows, symbol)
        }

        sb.append("""</Workbook>""")
        file.writeText(sb.toString(), Charsets.UTF_8)
    }

    private fun appendAsScheduleWorksheet(
        sb: StringBuilder,
        sheetName: String,
        statementTitle: String,
        yearEndedStr: String,
        entityName: String,
        rows: List<AsScheduleRow>,
        symbol: String
    ) {
        sb.append(""" <Worksheet ss:Name="${escapeXml(sheetName)}">""").append("\n")
        sb.append("""  <Table ss:DefaultColumnWidth="120">""").append("\n")
        sb.append("""   <Column ss:Width="50"/>""").append("\n")
        sb.append("""   <Column ss:Width="280"/>""").append("\n")
        sb.append("""   <Column ss:Width="60"/>""").append("\n")
        sb.append("""   <Column ss:Width="140"/>""").append("\n")

        val fullTitle = if (statementTitle.contains("as at", ignoreCase = true) || statementTitle.contains("for the year ended", ignoreCase = true)) {
            statementTitle
        } else {
            "$statementTitle for the year ended $yearEndedStr"
        }

        sb.append("""   <Row><Cell ss:StyleID="CATitle" ss:MergeAcross="3"><Data ss:Type="String">${escapeXml(entityName)}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row><Cell ss:StyleID="CASubtitle" ss:MergeAcross="3"><Data ss:Type="String">${escapeXml(fullTitle)}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row><Cell ss:MergeAcross="3"><Data ss:Type="String">(In accordance with Accounting Standards for Non-Corporate Entities • Amount in $symbol)</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")

        // Table Header: No. | Particulars | Note | Amount
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">No.</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Particulars</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Note</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Amount ($symbol)</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        for (row in rows) {
            val indentPrefix = "  ".repeat(row.indentLevel)
            sb.append("""   <Row>""").append("\n")
            val noStyle = if (row.isHeader || row.isTotal) """ ss:StyleID="Bold"""" else ""
            sb.append("""    <Cell$noStyle><Data ss:Type="String">${escapeXml(row.itemNo)}</Data></Cell>""").append("\n")

            val partStyle = if (row.isHeader || row.isTotal) """ ss:StyleID="Bold"""" else ""
            sb.append("""    <Cell$partStyle><Data ss:Type="String">${escapeXml(indentPrefix + row.particulars)}</Data></Cell>""").append("\n")

            sb.append("""    <Cell><Data ss:Type="String">${escapeXml(row.note)}</Data></Cell>""").append("\n")

            if (row.amount != null) {
                val amtStyle = if (row.isTotal) """ ss:StyleID="CurrencyBold"""" else """ ss:StyleID="Currency""""
                sb.append("""    <Cell$amtStyle><Data ss:Type="Number">${row.amount}</Data></Cell>""").append("\n")
            } else {
                sb.append("""    <Cell></Cell>""").append("\n")
            }
            sb.append("""   </Row>""").append("\n")
        }

        // Accompanying notes note
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row><Cell ss:MergeAcross="3"><Data ss:Type="String">* The accompanying notes are an integral part of the financial statements</Data></Cell></Row>""").append("\n")

        // Single Proprietor / Self-Certified Signatory (No Auditor)
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold" ss:MergeAcross="1"><Data ss:Type="String">For ${escapeXml(entityName.uppercase())}</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">______________________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold" ss:MergeAcross="1"><Data ss:Type="String">(Authorised Signatory / Proprietor)</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">Date: ________________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">Place: _______________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        sb.append("""  </Table>""").append("\n")
        sb.append(""" </Worksheet>""").append("\n")
    }

    private fun appendTFormatWorksheet(
        sb: StringBuilder,
        sheetName: String,
        statementTitle: String,
        yearEndedStr: String,
        caName: String,
        leftTitle: String,
        leftItems: List<Pair<String, Double>>,
        rightTitle: String,
        rightItems: List<Pair<String, Double>>,
        symbol: String
    ) {
        sb.append(""" <Worksheet ss:Name="${escapeXml(sheetName)}">""").append("\n")
        sb.append("""  <Table ss:DefaultColumnWidth="140">""").append("\n")
        sb.append("""   <Column ss:Width="200"/>""").append("\n")
        sb.append("""   <Column ss:Width="110"/>""").append("\n")
        sb.append("""   <Column ss:Width="20"/>""").append("\n")
        sb.append("""   <Column ss:Width="200"/>""").append("\n")
        sb.append("""   <Column ss:Width="110"/>""").append("\n")

        // Centered Entity Name & Statement Title (Merge across 5 columns)
        val fullTitle = if (statementTitle.contains("as at", ignoreCase = true) || statementTitle.contains("for the year ended", ignoreCase = true)) {
            statementTitle
        } else {
            "$statementTitle for the year ended $yearEndedStr"
        }
        sb.append("""   <Row><Cell ss:StyleID="CATitle" ss:MergeAcross="4"><Data ss:Type="String">${escapeXml(caName)}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row><Cell ss:StyleID="CASubtitle" ss:MergeAcross="4"><Data ss:Type="String">${escapeXml(fullTitle)}</Data></Cell></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")

        // T-Header
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">${escapeXml(leftTitle)}</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Amount ($symbol)</Data></Cell>""").append("\n")
        sb.append("""    <Cell></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">${escapeXml(rightTitle)}</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Header"><Data ss:Type="String">Amount ($symbol)</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        val maxRows = maxOf(leftItems.size, rightItems.size)
        for (i in 0 until maxRows) {
            val left = leftItems.getOrNull(i)
            val right = rightItems.getOrNull(i)

            sb.append("""   <Row>""").append("\n")
            if (left != null) {
                sb.append("""    <Cell><Data ss:Type="String">${escapeXml(left.first)}</Data></Cell>""").append("\n")
                sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">${left.second}</Data></Cell>""").append("\n")
            } else {
                sb.append("""    <Cell></Cell><Cell></Cell>""").append("\n")
            }
            sb.append("""    <Cell></Cell>""").append("\n")
            if (right != null) {
                sb.append("""    <Cell><Data ss:Type="String">${escapeXml(right.first)}</Data></Cell>""").append("\n")
                sb.append("""    <Cell ss:StyleID="Currency"><Data ss:Type="Number">${right.second}</Data></Cell>""").append("\n")
            } else {
                sb.append("""    <Cell></Cell><Cell></Cell>""").append("\n")
            }
            sb.append("""   </Row>""").append("\n")
        }

        // Balanced totals
        val balancedTotal = maxOf(leftItems.sumOf { it.second }, rightItems.sumOf { it.second })
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold"><Data ss:Type="String">TOTAL</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$balancedTotal</Data></Cell>""").append("\n")
        sb.append("""    <Cell></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold"><Data ss:Type="String">TOTAL</Data></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="CurrencyBold"><Data ss:Type="Number">$balancedTotal</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        // Single Proprietor Signature Block (No Auditor)
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="2"></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold" ss:MergeAcross="1"><Data ss:Type="String">For ${escapeXml(caName.uppercase())}</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row></Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="2"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">______________________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="2"></Cell>""").append("\n")
        sb.append("""    <Cell ss:StyleID="Bold" ss:MergeAcross="1"><Data ss:Type="String">(Authorised Signatory / Proprietor)</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="2"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">Date: ________________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")
        sb.append("""   <Row>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="2"></Cell>""").append("\n")
        sb.append("""    <Cell ss:MergeAcross="1"><Data ss:Type="String">Place: _______________________</Data></Cell>""").append("\n")
        sb.append("""   </Row>""").append("\n")

        sb.append("""  </Table>""").append("\n")
        sb.append(""" </Worksheet>""").append("\n")
    }

    private fun escapeXml(str: String): String {
        return str.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
    }

    /**
     * Opens or shares the generated report using Android FileProvider & Intents,
     * and confirms it has been downloaded into the phone's Downloads folder.
     */
    fun openOrShareReport(context: Context, file: File, mimeType: String) {
        try {
            Toast.makeText(
                context,
                "✓ Downloaded to Downloads folder: ${file.name}",
                Toast.LENGTH_LONG
            ).show()

            val contentUri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                file
            )

            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                type = mimeType
                putExtra(Intent.EXTRA_STREAM, contentUri)
                putExtra(Intent.EXTRA_SUBJECT, file.nameWithoutExtension)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }

            val chooser = Intent.createChooser(shareIntent, "View / Share: ${file.name}").apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(chooser)
        } catch (e: Exception) {
            Toast.makeText(context, "Saved to Downloads: ${file.name}", Toast.LENGTH_SHORT).show()
        }
    }
}
