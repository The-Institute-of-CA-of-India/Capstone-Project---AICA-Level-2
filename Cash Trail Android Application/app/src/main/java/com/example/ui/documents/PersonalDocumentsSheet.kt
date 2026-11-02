package com.example.ui.documents

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Gavel
import androidx.compose.material.icons.filled.HealthAndSafety
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.example.data.model.DocumentCategory
import com.example.data.model.PersonalDocument
import com.example.ui.dashboard.UiState
import com.example.ui.theme.Slate50
import com.example.ui.theme.PastelExpenseBg
import com.example.ui.theme.PastelExpenseText
import com.example.ui.theme.PastelTransferBg
import com.example.ui.theme.PastelTransferText
import com.example.ui.theme.Slate100
import com.example.ui.theme.Slate200
import com.example.ui.theme.Slate300
import com.example.ui.theme.Slate400
import com.example.ui.theme.Slate500
import com.example.ui.theme.Slate600
import com.example.ui.theme.Slate700
import com.example.ui.theme.Slate800
import com.example.ui.theme.Slate900
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object DocumentFileUtils {

    fun saveAttachedFileToInternal(
        context: Context,
        sourceUri: Uri,
        originalName: String
    ): Pair<String, String> {
        val docsDir = File(context.filesDir, "documents").apply { mkdirs() }
        val cleanName = originalName.replace("[^a-zA-Z0-9._-]".toRegex(), "_")
        val timestamp = System.currentTimeMillis()
        val destFile = File(docsDir, "${timestamp}_$cleanName")

        try {
            if (sourceUri.scheme == "content") {
                try {
                    context.contentResolver.takePersistableUriPermission(
                        sourceUri,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION
                    )
                } catch (ignored: Exception) {}
            }
            context.contentResolver.openInputStream(sourceUri)?.use { input ->
                FileOutputStream(destFile).use { output ->
                    input.copyTo(output)
                }
            }
            if (destFile.exists() && destFile.length() > 0) {
                return Pair(originalName, Uri.fromFile(destFile).toString())
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return Pair(originalName, sourceUri.toString())
    }

    private fun getFileFromUri(context: Context, fileUriString: String): File? {
        if (fileUriString.isBlank()) return null
        return try {
            val uri = Uri.parse(fileUriString)
            if (uri.scheme == "file") {
                File(uri.path ?: return null)
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    fun shareDocument(context: Context, document: PersonalDocument) {
        try {
            val file = getFileFromUri(context, document.fileUri)
            val shareUri = if (file != null && file.exists()) {
                FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            } else if (document.fileUri.isNotBlank()) {
                Uri.parse(document.fileUri)
            } else {
                Toast.makeText(context, "Document file not available", Toast.LENGTH_SHORT).show()
                return
            }

            val mimeType = when {
                document.fileName.endsWith(".pdf", ignoreCase = true) -> "application/pdf"
                document.fileName.endsWith(".png", ignoreCase = true) -> "image/png"
                document.fileName.endsWith(".jpg", ignoreCase = true) || document.fileName.endsWith(".jpeg", ignoreCase = true) -> "image/jpeg"
                else -> "*/*"
            }

            val intent = Intent(Intent.ACTION_SEND).apply {
                type = mimeType
                putExtra(Intent.EXTRA_STREAM, shareUri)
                putExtra(Intent.EXTRA_SUBJECT, document.name)
                putExtra(Intent.EXTRA_TEXT, "Document: ${document.name}")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(intent, "Share ${document.name}"))
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(context, "Could not share file: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    fun downloadDocument(context: Context, document: PersonalDocument) {
        try {
            val sourceFile = getFileFromUri(context, document.fileUri)
            val input = if (sourceFile != null && sourceFile.exists()) {
                sourceFile.inputStream()
            } else if (document.fileUri.isNotBlank()) {
                context.contentResolver.openInputStream(Uri.parse(document.fileUri))
            } else {
                Toast.makeText(context, "File not found", Toast.LENGTH_SHORT).show()
                return
            }

            if (input == null) {
                Toast.makeText(context, "Cannot read file", Toast.LENGTH_SHORT).show()
                return
            }

            val ext = when {
                document.fileName.contains(".") -> ".${document.fileName.substringAfterLast(".")}"
                else -> ".pdf"
            }
            val cleanDocName = document.name.replace("[^a-zA-Z0-9_-]".toRegex(), "_")
            val targetFileName = "${cleanDocName}_${System.currentTimeMillis()}$ext"

            val mimeType = when {
                ext.equals(".pdf", ignoreCase = true) -> "application/pdf"
                ext.equals(".png", ignoreCase = true) -> "image/png"
                ext.equals(".jpg", ignoreCase = true) || ext.equals(".jpeg", ignoreCase = true) -> "image/jpeg"
                else -> "application/octet-stream"
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, targetFileName)
                    put(MediaStore.MediaColumns.MIME_TYPE, mimeType)
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                if (uri != null) {
                    context.contentResolver.openOutputStream(uri)?.use { output ->
                        input.copyTo(output)
                    }
                    Toast.makeText(context, "Saved to phone's Downloads folder", Toast.LENGTH_LONG).show()
                } else {
                    Toast.makeText(context, "Failed to create file in Downloads", Toast.LENGTH_SHORT).show()
                }
            } else {
                val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                downloadsDir.mkdirs()
                val targetFile = File(downloadsDir, targetFileName)
                targetFile.outputStream().use { output ->
                    input.copyTo(output)
                }
                Toast.makeText(context, "Saved to ${targetFile.absolutePath}", Toast.LENGTH_LONG).show()
            }
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(context, "Download failed: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    fun openDocument(context: Context, document: PersonalDocument, onOpenImagePreview: (String) -> Unit) {
        val isImage = document.fileName.endsWith(".jpg", ignoreCase = true) ||
                document.fileName.endsWith(".jpeg", ignoreCase = true) ||
                document.fileName.endsWith(".png", ignoreCase = true)

        if (isImage) {
            onOpenImagePreview(document.fileUri)
            return
        }

        try {
            val file = getFileFromUri(context, document.fileUri)
            val uri = if (file != null && file.exists()) {
                FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            } else {
                Uri.parse(document.fileUri)
            }

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/pdf")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "No app available to open PDF. Use Share or Download option.", Toast.LENGTH_SHORT).show()
        }
    }

    fun extractFileName(context: Context, uri: Uri): String {
        var result: String? = null
        if (uri.scheme == "content") {
            try {
                context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) {
                        val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (nameIndex != -1) {
                            result = cursor.getString(nameIndex)
                        }
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
        if (result == null) {
            result = uri.path
            val cut = result?.lastIndexOf('/') ?: -1
            if (cut != -1) {
                result = result?.substring(cut + 1)
            }
        }
        return result ?: "document_${System.currentTimeMillis()}"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PersonalDocumentsSheet(
    documentsState: UiState<List<PersonalDocument>>,
    onDismiss: () -> Unit,
    onAddDocument: (
        name: String,
        category: String,
        documentNumber: String,
        issuer: String,
        expiryDate: String,
        issueDate: String,
        notes: String,
        fileUri: String,
        fileName: String,
        colorHex: String
    ) -> Unit,
    onUpdateDocument: (PersonalDocument) -> Unit,
    onDeleteDocument: (documentId: String, name: String) -> Unit,
    onToggleFavorite: (documentId: String, currentFavorite: Boolean) -> Unit
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val context = LocalContext.current

    var searchQuery by remember { mutableStateOf("") }
    var selectedCategoryFilter by remember { mutableStateOf<DocumentCategory?>(null) }
    var showUploadDialog by remember { mutableStateOf(false) }
    var documentToDelete by remember { mutableStateOf<PersonalDocument?>(null) }
    var previewImageUri by remember { mutableStateOf<String?>(null) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Slate50,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        modifier = Modifier.testTag("personal_documents_bottom_sheet")
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.92f)
                .padding(horizontal = 16.dp)
        ) {
            // Top Header Row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Slate900),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Description,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = "Personal Documents",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = Slate900
                        )
                        Text(
                            text = "PDF, JPEG & PNG Vault",
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate500
                        )
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(
                        onClick = { showUploadDialog = true },
                        colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                        shape = RoundedCornerShape(12.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        modifier = Modifier.testTag("add_document_primary_button")
                    ) {
                        Icon(imageVector = Icons.Default.UploadFile, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Upload", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    }

                    Spacer(modifier = Modifier.width(6.dp))

                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.testTag("close_documents_sheet_button")
                    ) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Slate700)
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Search Bar
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("Search documents by name or category...", color = Slate400, fontSize = 13.sp) },
                leadingIcon = {
                    Icon(imageVector = Icons.Default.Search, contentDescription = null, tint = Slate400)
                },
                trailingIcon = {
                    if (searchQuery.isNotBlank()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(imageVector = Icons.Default.Close, contentDescription = "Clear", tint = Slate500)
                        }
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Slate900,
                    unfocusedBorderColor = Slate200,
                    focusedContainerColor = Color.White,
                    unfocusedContainerColor = Color.White
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("documents_search_input")
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Category Filter Pills
            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                item {
                    FilterChip(
                        selected = selectedCategoryFilter == null,
                        onClick = { selectedCategoryFilter = null },
                        label = { Text("All Docs") },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Slate900,
                            selectedLabelColor = Color.White
                        ),
                        modifier = Modifier.testTag("filter_all_docs")
                    )
                }
                items(DocumentCategory.entries.toTypedArray()) { cat ->
                    FilterChip(
                        selected = selectedCategoryFilter == cat,
                        onClick = { selectedCategoryFilter = if (selectedCategoryFilter == cat) null else cat },
                        label = { Text(cat.displayName) },
                        leadingIcon = {
                            Icon(
                                imageVector = getCategoryIcon(cat),
                                contentDescription = null,
                                modifier = Modifier.size(14.dp)
                            )
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Slate900,
                            selectedLabelColor = Color.White
                        ),
                        modifier = Modifier.testTag("filter_doc_category_${cat.name.lowercase(Locale.ROOT)}")
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Documents Content Area
            when (documentsState) {
                is UiState.Loading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Slate900)
                    }
                }
                is UiState.Error -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            text = "Error: ${documentsState.message}",
                            color = Color(0xFFDC2626),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
                is UiState.Success -> {
                    val allDocs = documentsState.data
                    val filteredDocs = allDocs.filter { doc ->
                        val matchesSearch = searchQuery.isBlank() ||
                                doc.name.contains(searchQuery, ignoreCase = true) ||
                                doc.category.contains(searchQuery, ignoreCase = true) ||
                                doc.fileName.contains(searchQuery, ignoreCase = true)

                        val matchesCategory = selectedCategoryFilter == null ||
                                doc.category.equals(selectedCategoryFilter?.name, ignoreCase = true)

                        matchesSearch && matchesCategory
                    }

                    if (filteredDocs.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier.padding(24.dp)
                            ) {
                                Surface(
                                    shape = CircleShape,
                                    color = Slate200,
                                    modifier = Modifier.size(64.dp)
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Icon(
                                            imageVector = Icons.Default.Description,
                                            contentDescription = null,
                                            tint = Slate500,
                                            modifier = Modifier.size(32.dp)
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(14.dp))
                                Text(
                                    text = if (searchQuery.isNotBlank() || selectedCategoryFilter != null) {
                                        "No matching documents found"
                                    } else {
                                        "No documents uploaded yet"
                                    },
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "Upload your personal documents (PDF, JPEG, PNG) to keep them organized and easily accessible.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Slate500,
                                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Button(
                                    onClick = { showUploadDialog = true },
                                    colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                                    shape = RoundedCornerShape(12.dp)
                                ) {
                                    Icon(Icons.Default.UploadFile, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text("Upload Document")
                                }
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            contentPadding = PaddingValues(bottom = 24.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(filteredDocs, key = { it.id }) { doc ->
                                DocumentListItemCard(
                                    document = doc,
                                    onView = {
                                        DocumentFileUtils.openDocument(context, doc) { imageUri ->
                                            previewImageUri = imageUri
                                        }
                                    },
                                    onShare = {
                                        DocumentFileUtils.shareDocument(context, doc)
                                    },
                                    onDownload = {
                                        DocumentFileUtils.downloadDocument(context, doc)
                                    },
                                    onDelete = {
                                        documentToDelete = doc
                                    }
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    // Upload Document Dialog
    if (showUploadDialog) {
        SimpleDocumentUploadDialog(
            onDismiss = { showUploadDialog = false },
            onSave = { name, category, documentNumber, notes, fileUri, fileName ->
                onAddDocument(
                    name,
                    category,
                    documentNumber,
                    "",
                    "",
                    "",
                    notes,
                    fileUri,
                    fileName,
                    "#1E88E5"
                )
                showUploadDialog = false
            }
        )
    }

    // Delete confirmation dialog
    documentToDelete?.let { doc ->
        AlertDialog(
            onDismissRequest = { documentToDelete = null },
            title = { Text("Delete Document?", fontWeight = FontWeight.Bold, color = Slate900) },
            text = { Text("Are you sure you want to delete \"${doc.name}\"? This action cannot be undone.") },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteDocument(doc.id, doc.name)
                        documentToDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                ) {
                    Text("Delete", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { documentToDelete = null }) {
                    Text("Cancel", color = Slate700)
                }
            }
        )
    }

    // Fullscreen Image Preview Dialog
    previewImageUri?.let { uri ->
        Dialog(onDismissRequest = { previewImageUri = null }) {
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Document Preview",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Slate900
                        )
                        IconButton(onClick = { previewImageUri = null }) {
                            Icon(Icons.Default.Close, contentDescription = "Close", tint = Slate700)
                        }
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(350.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Slate100),
                        contentAlignment = Alignment.Center
                    ) {
                        AsyncImage(
                            model = uri,
                            contentDescription = "Document image",
                            contentScale = ContentScale.Fit,
                            modifier = Modifier.fillMaxSize()
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun DocumentListItemCard(
    document: PersonalDocument,
    onView: () -> Unit,
    onShare: () -> Unit,
    onDownload: () -> Unit,
    onDelete: () -> Unit
) {
    val isPdf = document.fileName.endsWith(".pdf", ignoreCase = true)
    val categoryEnum = try {
        DocumentCategory.valueOf(document.category)
    } catch (e: Exception) {
        DocumentCategory.OTHER
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Slate200),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onView() }
            .testTag("document_card_${document.id}")
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                // File Type Avatar (Pastel Peach-Rose for PDF, Pastel Glacial Blue for Image)
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (isPdf) PastelExpenseBg else PastelTransferBg),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = if (isPdf) Icons.Default.PictureAsPdf else Icons.Default.Image,
                        contentDescription = null,
                        tint = if (isPdf) PastelExpenseText else PastelTransferText,
                        modifier = Modifier.size(22.dp)
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = document.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Slate900,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (document.documentNumber.isNotBlank()) {
                        Text(
                            text = "No: ${document.documentNumber}",
                            style = MaterialTheme.typography.labelSmall,
                            color = Slate600,
                            fontWeight = FontWeight.Medium
                        )
                    }
                    Spacer(modifier = Modifier.height(3.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = Slate100
                        ) {
                            Text(
                                text = categoryEnum.displayName,
                                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                color = Slate700,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }

                        val hasFile = document.fileUri.isNotBlank()
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = when {
                                !hasFile -> Slate100
                                isPdf -> PastelExpenseBg
                                else -> PastelTransferBg
                            }
                        ) {
                            Text(
                                text = when {
                                    !hasFile -> "RECORD"
                                    isPdf -> "PDF"
                                    else -> "IMAGE"
                                },
                                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                color = when {
                                    !hasFile -> Slate600
                                    isPdf -> PastelExpenseText
                                    else -> PastelTransferText
                                },
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.width(6.dp))

            // Action Buttons: Share, Download, View, Delete
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                if (document.fileUri.isNotBlank()) {
                    IconButton(
                        onClick = onShare,
                        modifier = Modifier
                            .size(36.dp)
                            .testTag("share_document_${document.id}")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Share,
                            contentDescription = "Share Document",
                            tint = Slate700,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    IconButton(
                        onClick = onDownload,
                        modifier = Modifier
                            .size(36.dp)
                            .testTag("download_document_${document.id}")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Download,
                            contentDescription = "Download to Phone",
                            tint = Color(0xFF16A34A),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }

                IconButton(
                    onClick = onDelete,
                    modifier = Modifier
                        .size(36.dp)
                        .testTag("delete_document_${document.id}")
                ) {
                    Icon(
                        imageVector = Icons.Default.Delete,
                        contentDescription = "Delete Document",
                        tint = Color(0xFFDC2626),
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}

/**
 * Simple, streamlined document upload dialog:
 * 1. Attach PDF, JPEG, or PNG (Optional)
 * 2. Name the document
 * 3. Document / ID number (Optional)
 * 4. Choose category
 * 5. Notes (Optional)
 * 6. Save
 */
@Composable
fun SimpleDocumentUploadDialog(
    onDismiss: () -> Unit,
    onSave: (name: String, category: String, documentNumber: String, notes: String, fileUri: String, fileName: String) -> Unit
) {
    val context = LocalContext.current
    var name by remember { mutableStateOf("") }
    var documentNumber by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf(DocumentCategory.IDENTITY) }
    var fileUri by remember { mutableStateOf("") }
    var fileName by remember { mutableStateOf("") }
    var isSaving by remember { mutableStateOf(false) }

    fun processSelectedUri(uri: Uri?) {
        if (uri != null) {
            val originalName = DocumentFileUtils.extractFileName(context, uri)
            val (savedName, savedUri) = DocumentFileUtils.saveAttachedFileToInternal(context, uri, originalName)
            fileName = savedName
            fileUri = savedUri

            // Auto-populate document name if empty
            if (name.isBlank()) {
                val clean = originalName.substringBeforeLast(".")
                    .replace("_", " ")
                    .replace("-", " ")
                    .trim()
                if (clean.isNotBlank()) {
                    name = clean.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
                }
            }
        }
    }

    // Photo picker for images (zero-permission, highly reliable)
    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        processSelectedUri(uri)
    }

    // Universal document/file picker for PDFs and all files
    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        processSelectedUri(uri)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                text = "Save Document / Record",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Slate900
            )
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // 1. File Upload Area (Optional)
                Text(
                    text = "1. ATTACH FILE (OPTIONAL - PDF OR IMAGE)",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 0.5.sp
                )

                if (fileUri.isBlank()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFFF1F5F9),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Slate300),
                            modifier = Modifier
                                .weight(1f)
                                .clickable {
                                    filePickerLauncher.launch("*/*")
                                }
                                .testTag("upload_file_button")
                        ) {
                            Column(
                                modifier = Modifier.padding(14.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Icon(
                                    imageVector = Icons.Default.PictureAsPdf,
                                    contentDescription = null,
                                    tint = PastelExpenseText,
                                    modifier = Modifier.size(24.dp)
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = "Choose PDF / File",
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                Text(
                                    text = "Browse files",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500
                                )
                            }
                        }

                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFFF1F5F9),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Slate300),
                            modifier = Modifier
                                .weight(1f)
                                .clickable {
                                    photoPickerLauncher.launch(
                                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                                    )
                                }
                                .testTag("upload_photo_button")
                        ) {
                            Column(
                                modifier = Modifier.padding(14.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Image,
                                    contentDescription = null,
                                    tint = PastelTransferText,
                                    modifier = Modifier.size(24.dp)
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = "Choose Photo",
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Slate900
                                )
                                Text(
                                    text = "From gallery",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Slate500
                                )
                            }
                        }
                    }
                } else {
                    val isPdf = fileName.endsWith(".pdf", ignoreCase = true)
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = if (isPdf) Color(0xFFFEF2F2) else Color(0xFFF0FDF4),
                        border = androidx.compose.foundation.BorderStroke(
                            1.5.dp,
                            if (isPdf) Color(0xFFDC2626) else Color(0xFF16A34A)
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(
                                    imageVector = if (isPdf) Icons.Default.PictureAsPdf else Icons.Default.Image,
                                    contentDescription = null,
                                    tint = if (isPdf) Color(0xFFDC2626) else Color(0xFF16A34A),
                                    modifier = Modifier.size(24.dp)
                                )
                                Spacer(modifier = Modifier.width(10.dp))
                                Column {
                                    Text(
                                        text = fileName,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = Slate900,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = if (isPdf) "PDF Attached" else "Image Attached",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = if (isPdf) Color(0xFFDC2626) else Color(0xFF16A34A),
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }

                            Row(verticalAlignment = Alignment.CenterVertically) {
                                TextButton(
                                    onClick = {
                                        filePickerLauncher.launch("*/*")
                                    }
                                ) {
                                    Text("Change", style = MaterialTheme.typography.labelSmall, color = Slate700)
                                }
                                IconButton(
                                    onClick = {
                                        fileUri = ""
                                        fileName = ""
                                    },
                                    modifier = Modifier.size(32.dp)
                                ) {
                                    Icon(
                                        Icons.Default.Close,
                                        contentDescription = "Remove file",
                                        tint = Slate500,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                        }
                    }
                }

                // 2. Document Name
                Text(
                    text = "2. DOCUMENT NAME *",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 0.5.sp
                )

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    placeholder = { Text("e.g. Passport, Electricity Bill, PAN Card", color = Slate400) },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate300
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("upload_document_name_input")
                )

                // 3. Document / ID Number (Optional)
                Text(
                    text = "3. DOCUMENT / ID NUMBER (OPTIONAL)",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 0.5.sp
                )

                OutlinedTextField(
                    value = documentNumber,
                    onValueChange = { documentNumber = it },
                    placeholder = { Text("e.g. ABCDE1234F or 1234-5678-9012", color = Slate400) },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate300
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                // 4. Category
                Text(
                    text = "4. CATEGORY",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 0.5.sp
                )

                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    val categories = DocumentCategory.entries.toTypedArray()
                    val chunked = categories.toList().chunked(3)
                    chunked.forEach { rowCategories ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            rowCategories.forEach { cat ->
                                val isSelected = selectedCategory == cat
                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = if (isSelected) Slate900 else Slate100,
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { selectedCategory = cat }
                                        .testTag("upload_cat_${cat.name.lowercase(Locale.ROOT)}")
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.Center
                                    ) {
                                        Text(
                                            text = cat.displayName.substringBefore(" &"),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = if (isSelected) Color.White else Slate700,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                            maxLines = 1
                                        )
                                    }
                                }
                            }
                        }
                    }
                }

                // 5. Notes / Details (Optional)
                Text(
                    text = "5. NOTES / DETAILS (OPTIONAL)",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Slate500,
                    letterSpacing = 0.5.sp
                )

                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    placeholder = { Text("e.g. Physical copy in locker, expires 2030", color = Slate400) },
                    singleLine = false,
                    maxLines = 3,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Slate900,
                        unfocusedBorderColor = Slate300
                    ),
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            val canSave = name.isNotBlank() && !isSaving
            Button(
                onClick = {
                    if (canSave) {
                        isSaving = true
                        onSave(name.trim(), selectedCategory.name, documentNumber.trim(), notes.trim(), fileUri, fileName)
                    }
                },
                enabled = canSave,
                colors = ButtonDefaults.buttonColors(containerColor = Slate900),
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.testTag("save_upload_document_button")
            ) {
                Text(if (isSaving) "Saving..." else "Save Document", color = Color.White, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                shape = RoundedCornerShape(10.dp)
            ) {
                Text("Cancel", color = Slate700)
            }
        }
    )
}

private fun getCategoryIcon(cat: DocumentCategory): ImageVector {
    return when (cat) {
        DocumentCategory.IDENTITY -> Icons.Default.Badge
        DocumentCategory.FINANCIAL -> Icons.Default.AccountBalance
        DocumentCategory.INSURANCE -> Icons.Default.HealthAndSafety
        DocumentCategory.TAX_LEGAL -> Icons.Default.Gavel
        DocumentCategory.VEHICLE -> Icons.Default.Description
        DocumentCategory.BILLS -> Icons.Default.Receipt
        DocumentCategory.OTHER -> Icons.Default.Description
    }
}
