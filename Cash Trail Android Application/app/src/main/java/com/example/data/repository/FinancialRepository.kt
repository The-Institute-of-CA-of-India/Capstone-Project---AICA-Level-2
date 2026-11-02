package com.example.data.repository

import android.content.Context
import android.util.Log
import com.example.R
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Investment
import com.example.data.model.InvestmentAction
import com.example.data.model.OperationType
import com.example.data.model.PersonalDocument
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.example.data.backup.CashTrailBackupData
import com.example.data.model.handleFirestoreError
import com.google.firebase.Timestamp
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.snapshots
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import java.util.UUID

class FinancialRepository(private val db: FirebaseFirestore) {
    companion object {
        private const val TAG = "FinancialRepository"
    }

    constructor(context: Context) : this(
        FirebaseFirestore.getInstance(
            context.applicationContext.getString(R.string.firestore_database_id)
        )
    )

    private fun isGuest(userId: String): Boolean = userId.startsWith("guest")

    private val guestAccounts = MutableStateFlow<List<Account>>(emptyList())
    private val guestTransactions = MutableStateFlow<List<Transaction>>(emptyList())
    private val guestInvestments = MutableStateFlow<List<Investment>>(emptyList())
    private val guestDocuments = MutableStateFlow<List<PersonalDocument>>(emptyList())

    private fun adjustGuestAccountBalance(accountId: String, delta: Double) {
        guestAccounts.value = guestAccounts.value.map { acc ->
            if (acc.id == accountId) acc.copy(balance = acc.balance + delta) else acc
        }
    }

    // ----------------------------------------------------
    // ACCOUNTS
    // ----------------------------------------------------

    fun observeAccounts(userId: String): Flow<List<Account>> {
        if (isGuest(userId)) return guestAccounts.asStateFlow()
        val path = "users/$userId/accounts"
        return db.collection("users").document(userId).collection("accounts")
            .snapshots()
            .map { snapshot ->
                snapshot.toObjects(Account::class.java).sortedBy { it.name }
            }
            .catch { error ->
                if (error is Exception) {
                    handleFirestoreError(error, OperationType.LIST, path)
                }
                throw error
            }
    }

    suspend fun getAccount(userId: String, accountId: String): Account? {
        if (isGuest(userId)) return guestAccounts.value.firstOrNull { it.id == accountId }
        val docRef = db.collection("users").document(userId).collection("accounts").document(accountId)
        return try {
            docRef.get().await().toObject(Account::class.java)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.GET, docRef.path)
            null
        }
    }

    suspend fun createAccount(userId: String, account: Account): Result<String> {
        val accId = if (account.id.isNotBlank()) account.id else UUID.randomUUID().toString()
        if (isGuest(userId)) {
            val saved = account.copy(id = accId, userId = userId)
            guestAccounts.value = guestAccounts.value + saved
            return Result.success(accId)
        }
        val docRef = db.collection("users").document(userId).collection("accounts").document(accId)
        val payload = hashMapOf<String, Any>(
            "userId" to userId,
            "name" to account.name,
            "type" to account.type,
            "balance" to account.balance,
            "creditLimit" to account.creditLimit,
            "statementDay" to account.statementDay,
            "dueDay" to account.dueDay,
            "colorHex" to account.colorHex,
            "institution" to account.institution,
            "notes" to account.notes,
            "createdAt" to FieldValue.serverTimestamp(),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        return try {
            docRef.set(payload).await()
            Result.success(accId)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.CREATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun updateAccount(userId: String, account: Account): Result<Unit> {
        require(account.id.isNotBlank()) { "Account ID must not be blank" }
        if (isGuest(userId)) {
            guestAccounts.value = guestAccounts.value.map { if (it.id == account.id) account else it }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("accounts").document(account.id)
        val updates = hashMapOf<String, Any>(
            "name" to account.name,
            "type" to account.type,
            "balance" to account.balance,
            "creditLimit" to account.creditLimit,
            "statementDay" to account.statementDay,
            "dueDay" to account.dueDay,
            "colorHex" to account.colorHex,
            "institution" to account.institution,
            "notes" to account.notes,
            "updatedAt" to FieldValue.serverTimestamp()
        )
        return try {
            docRef.update(updates).await()
            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun deleteAccount(userId: String, accountId: String): Result<Unit> {
        if (isGuest(userId)) {
            guestAccounts.value = guestAccounts.value.filter { it.id != accountId }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("accounts").document(accountId)
        return try {
            docRef.delete().await()
            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.DELETE, docRef.path)
            Result.failure(e)
        }
    }

    // ----------------------------------------------------
    // TRANSACTIONS (Expense, Income, Inter-Account Transfer)
    // ----------------------------------------------------

    fun observeTransactions(userId: String): Flow<List<Transaction>> {
        if (isGuest(userId)) return guestTransactions.asStateFlow()
        val path = "users/$userId/transactions"
        return db.collection("users").document(userId).collection("transactions")
            .snapshots()
            .map { snapshot ->
                snapshot.toObjects(Transaction::class.java).sortedByDescending {
                    it.date ?: it.createdAt ?: Timestamp.now()
                }
            }
            .catch { error ->
                if (error is Exception) {
                    handleFirestoreError(error, OperationType.LIST, path)
                }
                throw error
            }
    }

    suspend fun addTransaction(userId: String, transaction: Transaction): Result<String> {
        val txId = if (transaction.id.isNotBlank()) transaction.id else UUID.randomUUID().toString()
        if (isGuest(userId)) {
            val saved = transaction.copy(id = txId, userId = userId)
            guestTransactions.value = listOf(saved) + guestTransactions.value
            when (transaction.type) {
                TransactionType.EXPENSE.name -> {
                    adjustGuestAccountBalance(transaction.accountId, -transaction.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustGuestAccountBalance(transaction.accountId, transaction.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustGuestAccountBalance(transaction.accountId, -transaction.amount)
                    transaction.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) {
                            adjustGuestAccountBalance(destId, transaction.amount)
                        }
                    }
                }
            }
            return Result.success(txId)
        }
        val docRef = db.collection("users").document(userId).collection("transactions").document(txId)

        val payload = hashMapOf<String, Any>(
            "userId" to userId,
            "type" to transaction.type,
            "amount" to transaction.amount,
            "accountId" to transaction.accountId,
            "category" to transaction.category,
            "note" to transaction.note,
            "invoiceFileName" to transaction.invoiceFileName,
            "invoiceUri" to transaction.invoiceUri,
            "date" to (transaction.date ?: Timestamp.now()),
            "createdAt" to FieldValue.serverTimestamp(),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        transaction.destinationAccountId?.let {
            if (it.isNotBlank()) payload["destinationAccountId"] = it
        }

        return try {
            docRef.set(payload).await()

            // Update account balances
            when (transaction.type) {
                TransactionType.EXPENSE.name -> {
                    adjustAccountBalance(userId, transaction.accountId, -transaction.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustAccountBalance(userId, transaction.accountId, transaction.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustAccountBalance(userId, transaction.accountId, -transaction.amount)
                    transaction.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) {
                            adjustAccountBalance(userId, destId, transaction.amount)
                        }
                    }
                }
            }

            Result.success(txId)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.CREATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun updateTransaction(userId: String, oldTx: Transaction, newTx: Transaction): Result<Unit> {
        if (isGuest(userId)) {
            // 1. Revert previous impact on balances
            when (oldTx.type) {
                TransactionType.EXPENSE.name -> {
                    adjustGuestAccountBalance(oldTx.accountId, oldTx.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustGuestAccountBalance(oldTx.accountId, -oldTx.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustGuestAccountBalance(oldTx.accountId, oldTx.amount)
                    oldTx.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) adjustGuestAccountBalance(destId, -oldTx.amount)
                    }
                }
            }

            // 2. Apply new impact on balances
            when (newTx.type) {
                TransactionType.EXPENSE.name -> {
                    adjustGuestAccountBalance(newTx.accountId, -newTx.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustGuestAccountBalance(newTx.accountId, newTx.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustGuestAccountBalance(newTx.accountId, -newTx.amount)
                    newTx.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) adjustGuestAccountBalance(destId, newTx.amount)
                    }
                }
            }

            guestTransactions.value = guestTransactions.value.map { if (it.id == oldTx.id) newTx else it }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("transactions").document(oldTx.id)
        val updates = hashMapOf<String, Any>(
            "type" to newTx.type,
            "amount" to newTx.amount,
            "accountId" to newTx.accountId,
            "category" to newTx.category,
            "note" to newTx.note,
            "invoiceFileName" to newTx.invoiceFileName,
            "invoiceUri" to newTx.invoiceUri,
            "date" to (newTx.date ?: oldTx.date ?: Timestamp.now()),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        if (newTx.destinationAccountId != null) {
            updates["destinationAccountId"] = newTx.destinationAccountId
        }

        return try {
            docRef.update(updates).await()

            // 1. Revert previous impact on balances
            when (oldTx.type) {
                TransactionType.EXPENSE.name -> {
                    adjustAccountBalance(userId, oldTx.accountId, oldTx.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustAccountBalance(userId, oldTx.accountId, -oldTx.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustAccountBalance(userId, oldTx.accountId, oldTx.amount)
                    oldTx.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) adjustAccountBalance(userId, destId, -oldTx.amount)
                    }
                }
            }

            // 2. Apply new impact on balances
            when (newTx.type) {
                TransactionType.EXPENSE.name -> {
                    adjustAccountBalance(userId, newTx.accountId, -newTx.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustAccountBalance(userId, newTx.accountId, newTx.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustAccountBalance(userId, newTx.accountId, -newTx.amount)
                    newTx.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) adjustAccountBalance(userId, destId, newTx.amount)
                    }
                }
            }

            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun deleteTransaction(userId: String, transaction: Transaction): Result<Unit> {
        if (isGuest(userId)) {
            // Revert balance adjustments
            when (transaction.type) {
                TransactionType.EXPENSE.name -> {
                    adjustGuestAccountBalance(transaction.accountId, transaction.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustGuestAccountBalance(transaction.accountId, -transaction.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustGuestAccountBalance(transaction.accountId, transaction.amount)
                    transaction.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) {
                            adjustGuestAccountBalance(destId, -transaction.amount)
                        }
                    }
                }
            }
            guestTransactions.value = guestTransactions.value.filter { it.id != transaction.id }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("transactions").document(transaction.id)
        return try {
            docRef.delete().await()

            // Revert balance adjustments
            when (transaction.type) {
                TransactionType.EXPENSE.name -> {
                    adjustAccountBalance(userId, transaction.accountId, transaction.amount)
                }
                TransactionType.INCOME.name -> {
                    adjustAccountBalance(userId, transaction.accountId, -transaction.amount)
                }
                TransactionType.TRANSFER.name -> {
                    adjustAccountBalance(userId, transaction.accountId, transaction.amount)
                    transaction.destinationAccountId?.let { destId ->
                        if (destId.isNotBlank()) {
                            adjustAccountBalance(userId, destId, -transaction.amount)
                        }
                    }
                }
            }

            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.DELETE, docRef.path)
            Result.failure(e)
        }
    }

    private suspend fun adjustAccountBalance(userId: String, accountId: String, delta: Double) {
        val accRef = db.collection("users").document(userId).collection("accounts").document(accountId)
        try {
            val snapshot = accRef.get().await()
            if (snapshot.exists()) {
                val currentBalance = snapshot.getDouble("balance") ?: 0.0
                accRef.update(
                    mapOf(
                        "balance" to (currentBalance + delta),
                        "updatedAt" to FieldValue.serverTimestamp()
                    )
                ).await()
            }
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, accRef.path)
        }
    }

    // ----------------------------------------------------
    // INVESTMENTS (Ledger of Contributions and Withdrawals)
    // ----------------------------------------------------

    fun observeInvestments(userId: String): Flow<List<Investment>> {
        if (isGuest(userId)) return guestInvestments.asStateFlow()
        val path = "users/$userId/investments"
        return db.collection("users").document(userId).collection("investments")
            .snapshots()
            .map { snapshot ->
                snapshot.toObjects(Investment::class.java).sortedByDescending {
                    it.date ?: it.createdAt ?: Timestamp.now()
                }
            }
            .catch { error ->
                if (error is Exception) {
                    handleFirestoreError(error, OperationType.LIST, path)
                }
                throw error
            }
    }

    suspend fun addInvestment(userId: String, investment: Investment): Result<String> {
        val invId = if (investment.id.isNotBlank()) investment.id else UUID.randomUUID().toString()
        if (isGuest(userId)) {
            val saved = investment.copy(id = invId, userId = userId)
            guestInvestments.value = listOf(saved) + guestInvestments.value
            // If a source account was used, deduct contribution or add withdrawal
            investment.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (investment.action == InvestmentAction.CONTRIBUTION.name) {
                        -investment.amount
                    } else {
                        investment.amount
                    }
                    adjustGuestAccountBalance(srcAccId, delta)
                }
            }
            return Result.success(invId)
        }
        val docRef = db.collection("users").document(userId).collection("investments").document(invId)

        val payload = hashMapOf<String, Any>(
            "userId" to userId,
            "assetName" to investment.assetName,
            "assetType" to investment.assetType,
            "action" to investment.action,
            "amount" to investment.amount,
            "note" to investment.note,
            "date" to (investment.date ?: Timestamp.now()),
            "createdAt" to FieldValue.serverTimestamp(),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        investment.sourceAccountId?.let {
            if (it.isNotBlank()) payload["sourceAccountId"] = it
        }

        return try {
            docRef.set(payload).await()

            // If a source account was used, deduct contribution or add withdrawal
            investment.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (investment.action == InvestmentAction.CONTRIBUTION.name) {
                        -investment.amount
                    } else {
                        investment.amount
                    }
                    adjustAccountBalance(userId, srcAccId, delta)
                }
            }

            Result.success(invId)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.CREATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun deleteInvestment(userId: String, investment: Investment): Result<Unit> {
        if (isGuest(userId)) {
            investment.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (investment.action == InvestmentAction.CONTRIBUTION.name) {
                        investment.amount
                    } else {
                        -investment.amount
                    }
                    adjustGuestAccountBalance(srcAccId, delta)
                }
            }
            guestInvestments.value = guestInvestments.value.filter { it.id != investment.id }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("investments").document(investment.id)
        return try {
            docRef.delete().await()

            // Revert account adjustment if source account was selected
            investment.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (investment.action == InvestmentAction.CONTRIBUTION.name) {
                        investment.amount
                    } else {
                        -investment.amount
                    }
                    adjustAccountBalance(userId, srcAccId, delta)
                }
            }

            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.DELETE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun updateInvestment(userId: String, oldInv: Investment, newInv: Investment): Result<Unit> {
        if (isGuest(userId)) {
            oldInv.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (oldInv.action == InvestmentAction.CONTRIBUTION.name) oldInv.amount else -oldInv.amount
                    adjustGuestAccountBalance(srcAccId, delta)
                }
            }
            newInv.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (newInv.action == InvestmentAction.CONTRIBUTION.name) -newInv.amount else newInv.amount
                    adjustGuestAccountBalance(srcAccId, delta)
                }
            }
            guestInvestments.value = guestInvestments.value.map { if (it.id == oldInv.id) newInv else it }
            return Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("investments").document(oldInv.id)
        val updates = hashMapOf<String, Any>(
            "assetName" to newInv.assetName,
            "assetType" to newInv.assetType,
            "action" to newInv.action,
            "amount" to newInv.amount,
            "note" to newInv.note,
            "date" to (newInv.date ?: oldInv.date ?: Timestamp.now()),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        if (newInv.sourceAccountId != null) {
            updates["sourceAccountId"] = newInv.sourceAccountId
        }

        return try {
            docRef.update(updates).await()

            // 1. Revert previous investment adjustment
            oldInv.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (oldInv.action == InvestmentAction.CONTRIBUTION.name) oldInv.amount else -oldInv.amount
                    adjustAccountBalance(userId, srcAccId, delta)
                }
            }

            // 2. Apply new investment adjustment
            newInv.sourceAccountId?.let { srcAccId ->
                if (srcAccId.isNotBlank()) {
                    val delta = if (newInv.action == InvestmentAction.CONTRIBUTION.name) -newInv.amount else newInv.amount
                    adjustAccountBalance(userId, srcAccId, delta)
                }
            }

            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, docRef.path)
            Result.failure(e)
        }
    }

    // ----------------------------------------------------
    // DUMMY ENTRIES REMOVAL & CLEAN SLATE
    // ----------------------------------------------------

    suspend fun seedDefaultAccountsIfEmpty(userId: String) {
        // Users start with a clean slate. No dummy entries are seeded automatically.
    }

    suspend fun purgeDummyEntries(userId: String): Result<Int> = withContext(Dispatchers.IO) {
        try {
            val dummyNotes = setOf(
                "Corporate Monthly Payroll",
                "Weekly Supermarket Supplies",
                "Dinner & Bistro",
                "Cab rides to office",
                "Digital Wallet Auto-Topup",
                "Monthly Disciplined SIP"
            )

            if (isGuest(userId)) {
                val beforeCount = guestTransactions.value.size + guestInvestments.value.size
                guestTransactions.value = guestTransactions.value.filterNot { dummyNotes.contains(it.note.trim()) }
                guestInvestments.value = guestInvestments.value.filterNot { dummyNotes.contains(it.note.trim()) || it.assetName == "Nifty 50 Index Fund" }
                val afterCount = guestTransactions.value.size + guestInvestments.value.size
                return@withContext Result.success(beforeCount - afterCount)
            }

            val txSnapshot = db.collection("users").document(userId).collection("transactions").get().await()
            var deletedCount = 0

            for (doc in txSnapshot.documents) {
                val tx = doc.toObject(Transaction::class.java)
                if (tx != null && dummyNotes.contains(tx.note.trim())) {
                    deleteTransaction(userId, tx)
                    deletedCount++
                }
            }

            val invSnapshot = db.collection("users").document(userId).collection("investments").get().await()
            for (doc in invSnapshot.documents) {
                val inv = doc.toObject(Investment::class.java)
                if (inv != null && (dummyNotes.contains(inv.note.trim()) || inv.assetName == "Nifty 50 Index Fund")) {
                    deleteInvestment(userId, inv)
                    deletedCount++
                }
            }

            Result.success(deletedCount)
        } catch (e: Exception) {
            Log.e(TAG, "Error purging dummy entries", e)
            Result.failure(e)
        }
    }

    suspend fun clearAllTransactions(userId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (isGuest(userId)) {
                guestTransactions.value = emptyList()
                return@withContext Result.success(Unit)
            }

            val txSnapshot = db.collection("users").document(userId).collection("transactions").get().await()
            for (doc in txSnapshot.documents) {
                val tx = doc.toObject(Transaction::class.java)
                if (tx != null) {
                    deleteTransaction(userId, tx)
                }
            }
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Error clearing transactions", e)
            Result.failure(e)
        }
    }

    // ----------------------------------------------------
    // PERSONAL DOCUMENTS
    // ----------------------------------------------------

    fun observePersonalDocuments(userId: String): Flow<List<PersonalDocument>> {
        if (isGuest(userId)) return guestDocuments.asStateFlow()
        val path = "users/$userId/documents"
        return db.collection("users").document(userId).collection("documents")
            .snapshots()
            .map { snapshot ->
                snapshot.toObjects(PersonalDocument::class.java).sortedWith(
                    compareByDescending<PersonalDocument> { it.isFavorite }
                        .thenBy { it.name.lowercase() }
                )
            }
            .catch { error ->
                if (error is Exception) {
                    handleFirestoreError(error, OperationType.LIST, path)
                }
                throw error
            }
    }

    suspend fun addPersonalDocument(userId: String, document: PersonalDocument): Result<String> = withContext(Dispatchers.IO) {
        val docId = if (document.id.isNotBlank()) document.id else UUID.randomUUID().toString()
        if (isGuest(userId)) {
            val docWithId = document.copy(
                id = docId,
                userId = userId,
                createdAt = document.createdAt ?: Timestamp.now()
            )
            guestDocuments.value = listOf(docWithId) + guestDocuments.value
            return@withContext Result.success(docId)
        }
        val docRef = db.collection("users").document(userId).collection("documents").document(docId)
        val payload = hashMapOf<String, Any>(
            "userId" to userId,
            "name" to document.name,
            "category" to document.category,
            "documentNumber" to document.documentNumber,
            "issuer" to document.issuer,
            "expiryDate" to document.expiryDate,
            "issueDate" to document.issueDate,
            "notes" to document.notes,
            "fileUri" to document.fileUri,
            "fileName" to document.fileName,
            "colorHex" to document.colorHex,
            "isFavorite" to document.isFavorite,
            "createdAt" to FieldValue.serverTimestamp(),
            "updatedAt" to FieldValue.serverTimestamp()
        )
        return@withContext try {
            docRef.set(payload).await()
            Result.success(docId)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.CREATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun updatePersonalDocument(userId: String, document: PersonalDocument): Result<Unit> = withContext(Dispatchers.IO) {
        if (isGuest(userId)) {
            val docWithUpdate = document.copy(
                updatedAt = Timestamp.now()
            )
            guestDocuments.value = guestDocuments.value.map {
                if (it.id == document.id) docWithUpdate else it
            }
            return@withContext Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("documents").document(document.id)
        val updates = hashMapOf<String, Any>(
            "name" to document.name,
            "category" to document.category,
            "documentNumber" to document.documentNumber,
            "issuer" to document.issuer,
            "expiryDate" to document.expiryDate,
            "issueDate" to document.issueDate,
            "notes" to document.notes,
            "fileUri" to document.fileUri,
            "fileName" to document.fileName,
            "colorHex" to document.colorHex,
            "isFavorite" to document.isFavorite,
            "updatedAt" to FieldValue.serverTimestamp()
        )
        return@withContext try {
            docRef.update(updates).await()
            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun deletePersonalDocument(userId: String, documentId: String): Result<Unit> = withContext(Dispatchers.IO) {
        if (isGuest(userId)) {
            guestDocuments.value = guestDocuments.value.filterNot { it.id == documentId }
            return@withContext Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("documents").document(documentId)
        return@withContext try {
            docRef.delete().await()
            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.DELETE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun toggleDocumentFavorite(userId: String, documentId: String, currentFavorite: Boolean): Result<Unit> = withContext(Dispatchers.IO) {
        if (isGuest(userId)) {
            guestDocuments.value = guestDocuments.value.map {
                if (it.id == documentId) it.copy(isFavorite = !currentFavorite) else it
            }
            return@withContext Result.success(Unit)
        }
        val docRef = db.collection("users").document(userId).collection("documents").document(documentId)
        return@withContext try {
            docRef.update("isFavorite", !currentFavorite, "updatedAt", FieldValue.serverTimestamp()).await()
            Result.success(Unit)
        } catch (e: Exception) {
            handleFirestoreError(e, OperationType.UPDATE, docRef.path)
            Result.failure(e)
        }
    }

    suspend fun restoreFromBackupData(userId: String, backup: CashTrailBackupData): Result<Int> = withContext(Dispatchers.IO) {
        var restoredCount = 0
        if (isGuest(userId)) {
            val updatedAccounts = backup.accounts.map { it.copy(userId = userId) }
            val updatedTransactions = backup.transactions.map { it.copy(userId = userId) }
            val updatedInvestments = backup.investments.map { it.copy(userId = userId) }
            val updatedDocs = backup.documents.map { it.copy(userId = userId) }

            guestAccounts.value = updatedAccounts
            guestTransactions.value = updatedTransactions
            guestInvestments.value = updatedInvestments
            guestDocuments.value = updatedDocs

            restoredCount = updatedAccounts.size + updatedTransactions.size + updatedInvestments.size + updatedDocs.size
            return@withContext Result.success(restoredCount)
        }

        try {
            // Restore accounts
            for (account in backup.accounts) {
                val accId = if (account.id.isNotBlank()) account.id else UUID.randomUUID().toString()
                val docRef = db.collection("users").document(userId).collection("accounts").document(accId)
                val payload = hashMapOf<String, Any>(
                    "userId" to userId,
                    "name" to account.name,
                    "type" to account.type,
                    "balance" to account.balance,
                    "creditLimit" to account.creditLimit,
                    "statementDay" to account.statementDay,
                    "dueDay" to account.dueDay,
                    "colorHex" to account.colorHex,
                    "institution" to account.institution,
                    "notes" to account.notes,
                    "updatedAt" to FieldValue.serverTimestamp()
                )
                docRef.set(payload).await()
                restoredCount++
            }

            // Restore transactions
            for (tx in backup.transactions) {
                val txId = if (tx.id.isNotBlank()) tx.id else UUID.randomUUID().toString()
                val docRef = db.collection("users").document(userId).collection("transactions").document(txId)
                val payload = hashMapOf<String, Any>(
                    "userId" to userId,
                    "type" to tx.type,
                    "amount" to tx.amount,
                    "accountId" to tx.accountId,
                    "category" to tx.category,
                    "note" to tx.note,
                    "invoiceFileName" to tx.invoiceFileName,
                    "invoiceUri" to tx.invoiceUri,
                    "date" to (tx.date ?: Timestamp.now()),
                    "updatedAt" to FieldValue.serverTimestamp()
                )
                tx.destinationAccountId?.let { if (it.isNotBlank()) payload["destinationAccountId"] = it }
                docRef.set(payload).await()
                restoredCount++
            }

            // Restore investments
            for (inv in backup.investments) {
                val invId = if (inv.id.isNotBlank()) inv.id else UUID.randomUUID().toString()
                val docRef = db.collection("users").document(userId).collection("investments").document(invId)
                val payload = hashMapOf<String, Any>(
                    "userId" to userId,
                    "assetName" to inv.assetName,
                    "assetType" to inv.assetType,
                    "action" to inv.action,
                    "amount" to inv.amount,
                    "note" to inv.note,
                    "date" to (inv.date ?: Timestamp.now()),
                    "updatedAt" to FieldValue.serverTimestamp()
                )
                inv.sourceAccountId?.let { if (it.isNotBlank()) payload["sourceAccountId"] = it }
                docRef.set(payload).await()
                restoredCount++
            }

            // Restore documents
            for (doc in backup.documents) {
                val docId = if (doc.id.isNotBlank()) doc.id else UUID.randomUUID().toString()
                val docRef = db.collection("users").document(userId).collection("documents").document(docId)
                val payload = hashMapOf<String, Any>(
                    "userId" to userId,
                    "name" to doc.name,
                    "category" to doc.category,
                    "documentNumber" to doc.documentNumber,
                    "issuer" to doc.issuer,
                    "expiryDate" to doc.expiryDate,
                    "issueDate" to doc.issueDate,
                    "notes" to doc.notes,
                    "fileUri" to doc.fileUri,
                    "fileName" to doc.fileName,
                    "colorHex" to doc.colorHex,
                    "isFavorite" to doc.isFavorite,
                    "updatedAt" to FieldValue.serverTimestamp()
                )
                docRef.set(payload).await()
                restoredCount++
            }

            Result.success(restoredCount)
        } catch (e: Exception) {
            Log.e(TAG, "Error restoring from backup", e)
            Result.failure(e)
        }
    }
}


