package com.example.data.repository

import com.example.base.FirestoreEmulatorTestBase
import com.example.data.model.Account
import com.example.data.model.AccountType
import com.example.data.model.Transaction
import com.example.data.model.TransactionType
import com.google.firebase.firestore.FirebaseFirestoreException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class FinancialRepositoryRuleTest : FirestoreEmulatorTestBase() {

    @Test
    fun createAccount_validPayload_createsDocumentAndReturnsId() = runBlocking {
        val uid = signInTestUser(ALICE_EMAIL)
        val repository = FinancialRepository(firestore)

        val account = Account(
            name = "Test Savings",
            type = AccountType.BANK.name,
            balance = 15000.0,
            creditLimit = 0.0,
            colorHex = "#2E7D32"
        )

        val result = withTimeout(DEFAULT_TIMEOUT_MS) {
            repository.createAccount(uid, account)
        }
        assertTrue(result.isSuccess)
        val accountId = result.getOrThrow()
        assertTrue(accountId.isNotEmpty())

        val fetched = withTimeout(DEFAULT_TIMEOUT_MS) {
            repository.getAccount(uid, accountId)
        }
        assertNotNull(fetched)
        assertEquals("Test Savings", fetched?.name)
    }

    @Test
    fun addTransaction_validPayload_createsTransaction() = runBlocking {
        val uid = signInTestUser(ALICE_EMAIL)
        val repository = FinancialRepository(firestore)

        val tx = Transaction(
            type = TransactionType.EXPENSE.name,
            amount = 350.0,
            accountId = "acc_test",
            category = "Food & Dining",
            note = "Dinner"
        )

        val result = withTimeout(DEFAULT_TIMEOUT_MS) {
            repository.addTransaction(uid, tx)
        }
        assertTrue(result.isSuccess)
        val txId = result.getOrThrow()
        assertTrue(txId.isNotEmpty())
    }

    @Test
    fun observeAccounts_unauthenticatedUser_failsWithPermissionDenied() = runBlocking {
        auth.signOut()
        val repository = FinancialRepository(firestore)

        try {
            withTimeout(DEFAULT_TIMEOUT_MS) {
                repository.observeAccounts("unauth_user").first()
            }
            fail("Expected permission denied exception but succeeded")
        } catch (e: Exception) {
            val firestoreException = generateSequence(e as Throwable) { it.cause }
                .firstOrNull { it is FirebaseFirestoreException } as? FirebaseFirestoreException
            assertNotNull("Expected FirebaseFirestoreException in cause chain", firestoreException)
            assertEquals(FirebaseFirestoreException.Code.PERMISSION_DENIED, firestoreException?.code)
        }
    }

    private companion object {
        const val ALICE_EMAIL = "alice@test.com"
        const val DEFAULT_TIMEOUT_MS = 5000L
    }
}
