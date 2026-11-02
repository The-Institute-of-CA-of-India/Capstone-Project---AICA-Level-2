package com.example.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.cos
import kotlin.math.sin

// Official CoinKeep Brand Colors with Rich Warm Pastel Tones
val CoinKeepCoral = Color(0xFFD95D39)
val CoinKeepCream = Color(0xFFFFF9F2)
val CoinKeepGold = Color(0xFFF7C85C)

/**
 * Official CoinKeep Logo Mark
 * Exact pixel-faithful implementation of the user's uploaded logo:
 * - Warm terracotta/coral squircle container (#DE522C)
 * - Ultra-thick creamy-white open 'C' with smooth rounded caps (#FFF7EE)
 * - Radiant golden coin circle (#FFCC5C) nestled in the center opening
 */
@Composable
fun CoinKeepLogoMark(
    modifier: Modifier = Modifier,
    size: Dp = 40.dp,
    showContainer: Boolean = true
) {
    val cornerRadius = size * 0.225f

    Box(
        modifier = modifier
            .size(size)
            .then(
                if (showContainer) {
                    Modifier
                        .shadow(
                            elevation = 3.dp,
                            shape = RoundedCornerShape(cornerRadius),
                            spotColor = Color(0x40DE522C),
                            ambientColor = Color(0x20000000)
                        )
                        .clip(RoundedCornerShape(cornerRadius))
                        .background(CoinKeepCoral)
                } else Modifier
            ),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.size(size)) {
            val w = this.size.width
            val h = this.size.height

            // Center of the 'C' arc
            val cCenter = Offset(w * 0.462f, h * 0.50f)
            val cRadius = w * 0.265f
            val cStrokeWidth = w * 0.165f

            // Opening angle of 38 degrees
            val cutAngleRad = 38.0 * Math.PI / 180.0
            val startX = cCenter.x + cRadius * cos(cutAngleRad).toFloat()
            val startY = cCenter.y - cRadius * sin(cutAngleRad).toFloat()
            val endX = cCenter.x + cRadius * cos(cutAngleRad).toFloat()
            val endY = cCenter.y + cRadius * sin(cutAngleRad).toFloat()

            // Main 'C' sweeping arc
            val cPath = Path().apply {
                moveTo(startX, startY)
                arcTo(
                    rect = androidx.compose.ui.geometry.Rect(
                        left = cCenter.x - cRadius,
                        top = cCenter.y - cRadius,
                        right = cCenter.x + cRadius,
                        bottom = cCenter.y + cRadius
                    ),
                    startAngleDegrees = -38f,
                    sweepAngleDegrees = -284f,
                    forceMoveTo = false
                )
            }

            drawPath(
                path = cPath,
                color = CoinKeepCream,
                style = Stroke(width = cStrokeWidth, cap = StrokeCap.Round)
            )

            // Golden coin circle in the opening
            val coinCenter = Offset(w * 0.660f, h * 0.50f)
            val coinRadius = w * 0.080f
            drawCircle(
                color = CoinKeepGold,
                radius = coinRadius,
                center = coinCenter
            )
        }
    }
}

/**
 * Backward compatibility alias for FinLedgerLogo
 */
@Composable
fun FinLedgerLogo(
    modifier: Modifier = Modifier,
    size: Dp = 38.dp,
    showContainerBackground: Boolean = true
) {
    CoinKeepLogoMark(
        modifier = modifier,
        size = size,
        showContainer = showContainerBackground
    )
}

/**
 * Horizontal CoinKeep Brand Logo
 * Features the official logo mark alongside the bold "CoinKeep" wordmark.
 */
@Composable
fun CoinKeepHorizontalLogo(
    modifier: Modifier = Modifier,
    iconSize: Dp = 32.dp,
    isDark: Boolean = isSystemInDarkTheme(),
    showTagline: Boolean = false
) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        CoinKeepLogoMark(
            size = iconSize,
            showContainer = true
        )

        Column(verticalArrangement = Arrangement.Center) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "Cash",
                    fontSize = (iconSize.value * 0.62f).sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.5).sp,
                    color = if (isDark) Color.White else Color(0xFF0F172A)
                )
                Text(
                    text = "trail",
                    fontSize = (iconSize.value * 0.62f).sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.5).sp,
                    color = CoinKeepCoral
                )
            }

            if (showTagline) {
                Text(
                    text = "BUDGET & EXPENSES",
                    fontSize = (iconSize.value * 0.22f).coerceAtLeast(9f).sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.5.sp,
                    color = if (isDark) Color(0xFF94A3B8) else Color(0xFF64748B)
                )
            }
        }
    }
}

/**
 * Stacked CoinKeep Brand Logo
 * Centered official logo mark on top with brand wordmark and tagline below.
 */
@Composable
fun CoinKeepStackedLogo(
    modifier: Modifier = Modifier,
    iconSize: Dp = 80.dp,
    isDark: Boolean = isSystemInDarkTheme(),
    showTagline: Boolean = true
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        CoinKeepLogoMark(
            size = iconSize,
            showContainer = true
        )

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "Cash",
                    fontSize = (iconSize.value * 0.38f).coerceIn(24f, 40f).sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.5).sp,
                    color = if (isDark) Color.White else Color(0xFF0F172A)
                )
                Text(
                    text = "trail",
                    fontSize = (iconSize.value * 0.38f).coerceIn(24f, 40f).sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.5).sp,
                    color = CoinKeepCoral
                )
            }

            if (showTagline) {
                Text(
                    text = "BUDGET & EXPENSES",
                    fontSize = (iconSize.value * 0.13f).coerceIn(10f, 13f).sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 2.sp,
                    color = if (isDark) Color(0xFF94A3B8) else Color(0xFF64748B)
                )
            }
        }
    }
}
