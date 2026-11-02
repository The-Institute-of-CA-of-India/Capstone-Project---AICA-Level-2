package com.example.ui.util

import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.PointerInputChange
import androidx.compose.ui.input.pointer.pointerInput

private sealed interface PressResult {
    data class Released(val change: PointerInputChange?) : PressResult
}

/**
 * Custom gesture detector:
 * - Normal tap: calls [onClick] on finger release before 1 second (1000ms)
 * - 1-second press: calls [onLongPress] and fires haptic feedback when held continuously for 1000ms
 * This eliminates accidental delete triggers and fulfills the 1-second hold requirement.
 */
fun Modifier.onEntryClickAndLongPress(
    hapticFeedback: HapticFeedback? = null,
    holdDurationMs: Long = 1000L,
    onClick: (() -> Unit)? = null,
    onLongPress: (() -> Unit)? = null
): Modifier {
    if (onClick == null && onLongPress == null) return this
    return this.pointerInput(onClick, onLongPress, holdDurationMs) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false)
            val result = withTimeoutOrNull(holdDurationMs) {
                PressResult.Released(waitForUpOrCancellation())
            }
            if (result is PressResult.Released) {
                if (result.change != null) {
                    onClick?.invoke()
                }
            } else {
                // Timed out: user held entry for >= 1 second (1000ms)
                hapticFeedback?.performHapticFeedback(HapticFeedbackType.LongPress)
                onLongPress?.invoke()
                waitForUpOrCancellation()
            }
        }
    }
}

/**
 * Backward compatibility alias with 1-second default hold time
 */
fun Modifier.onEntryClickAndLongPress2s(
    hapticFeedback: HapticFeedback? = null,
    onClick: (() -> Unit)? = null,
    onLongPress2s: (() -> Unit)? = null
): Modifier = onEntryClickAndLongPress(
    hapticFeedback = hapticFeedback,
    holdDurationMs = 1000L, // Updated to 1 second as requested
    onClick = onClick,
    onLongPress = onLongPress2s
)

fun Modifier.onEntryClickAndLongPress1s(
    hapticFeedback: HapticFeedback? = null,
    onClick: (() -> Unit)? = null,
    onLongPress1s: (() -> Unit)? = null
): Modifier = onEntryClickAndLongPress(
    hapticFeedback = hapticFeedback,
    holdDurationMs = 1000L,
    onClick = onClick,
    onLongPress = onLongPress1s
)
