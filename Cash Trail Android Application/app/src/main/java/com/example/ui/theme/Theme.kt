package com.example.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Slate900,
    onPrimary = Color.White,
    primaryContainer = PastelIncomeBg,
    onPrimaryContainer = PastelIncomeText,
    secondary = Slate700,
    onSecondary = Color.White,
    secondaryContainer = PastelTransferBg,
    onSecondaryContainer = PastelTransferText,
    tertiary = PastelInvestmentText,
    onTertiary = Color.White,
    tertiaryContainer = PastelInvestmentBg,
    onTertiaryContainer = PastelInvestmentText,
    background = Slate50,
    onBackground = Slate900,
    surface = Color.White,
    onSurface = Slate900,
    surfaceVariant = Slate100,
    onSurfaceVariant = Slate600,
    outline = Slate200,
    outlineVariant = Slate300
)

@Composable
fun FinLedgerTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = Typography,
        content = content
    )
}
