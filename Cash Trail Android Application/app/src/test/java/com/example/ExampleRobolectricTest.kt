package com.example

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class ExampleRobolectricTest {

  @Test
  fun `read string from context`() {
    val context = ApplicationProvider.getApplicationContext<Context>()
    val appName = context.getString(R.string.app_name)
    assertEquals("Cashtrail - Budget & Expenses", appName)
  }

  @Test
  fun `verify personal account type exists and functions`() {
    val personalType = com.example.data.model.AccountType.PERSONAL
    assertEquals("Personal Account", personalType.displayName)
    val account = com.example.data.model.Account(
      name = "My Personal Wallet / IOUs",
      type = personalType.name,
      balance = 2500.0
    )
    assertEquals("PERSONAL", account.type)
    assertEquals(2500.0, account.balance, 0.001)
  }

  @Test
  fun `verify financial statements selection and default entity name`() {
    val selection = com.example.ui.report.FinancialStatementSelection()
    assertEquals(true, selection.balanceSheet)
    assertEquals(true, selection.profitAndLoss)
    assertEquals(true, selection.useAccountingStandardFormat)
    assertEquals("Onil Shah", com.example.ui.report.ReportGenerator.DEFAULT_ENTITY_NAME)
  }
}
