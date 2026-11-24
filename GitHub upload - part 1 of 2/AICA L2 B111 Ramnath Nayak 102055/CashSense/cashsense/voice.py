"""Voice: Telegram voice notes in, spoken answers out.

  speech -> text : Gemini audio understanding (GeminiClient.transcribe)
  answer         : assistant agent (read-only tools)
  text -> speech : Gemini TTS model; fallback: Windows' built-in offline voice (System.Speech)
  encoding       : ffmpeg (bundled with the imageio-ffmpeg package) -> OGG/Opus, the format Telegram plays
"""
from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def to_ogg(audio_path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "voice.ogg"
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(audio_path), "-c:a", "libopus", "-b:a", "32k",
                        "-ac", "1", str(out)], check=True, timeout=60)
        return out.read_bytes()


def pcm_to_ogg(pcm: bytes, rate: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "speech.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        return to_ogg(wav)


def windows_tts_ogg(text: str) -> bytes:
    """Offline fallback: Windows System.Speech -> WAV -> OGG."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "speech.wav"
        txt = Path(tmp) / "speech.txt"
        txt.write_text(text, encoding="utf-8")
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SetOutputToWaveFile('{wav}'); $s.Speak([IO.File]::ReadAllText('{txt}')); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=120,
                       capture_output=True)
        return to_ogg(wav)


def speak(text: str, client=None) -> tuple[bytes, str]:
    """Return (OGG/Opus bytes, engine used)."""
    if client is not None and client.available:
        try:
            pcm, rate = client.speak(text)
            return pcm_to_ogg(pcm, rate), f"Gemini TTS ({client.last_model})"
        except Exception:  # TTS busy or unsupported: fall back to the offline voice
            pass
    return windows_tts_ogg(text), "Windows offline voice"


def answer_voice_note(db, client, audio: bytes, mime_type: str = "audio/ogg") -> dict:
    from .agents.assistant import ask

    transcript = client.transcribe(audio, mime_type)
    if not transcript:
        return {"transcript": "", "answer": "Sorry, I could not hear a question in that voice note.", "voice": None}
    res = ask(db, transcript, client)
    ogg, engine = speak(_plain(res["answer"]), client)
    return {**res, "transcript": transcript, "voice": ogg, "voice_engine": engine}


import re

_RS = re.compile(r"(-?)(?:Rs\.?|₹|INR)\s?(\d[\d,]*)(?:\.(\d{1,2}))?(?!\d)(?!\.\d)"
                 r"(?!\s*(?:lakh|lakhs|crore|crores|cr)\b)", re.I)
_INDIAN = re.compile(r"(?<![\d.])(\d{1,2}(?:,\d{2})+,\d{3})(?:\.\d{1,2})?(?![\d,])")


def indian_words(rupees: int) -> str:
    """12632553 -> '1 crore 26 lakh 32 thousand 553' (the TTS reads the digits; the units are Indian)."""
    if rupees == 0:
        return "0"
    crore, rest = divmod(rupees, 10_000_000)
    lakh, rest = divmod(rest, 100_000)
    thousand, units = divmod(rest, 1_000)
    parts = []
    if crore:
        parts.append(f"{indian_words(crore) if crore >= 100_000 else crore} crore")
    if lakh:
        parts.append(f"{lakh} lakh")
    if thousand:
        parts.append(f"{thousand} thousand")
    if units:
        parts.append(str(units))
    return " ".join(parts)


def _spoken(digits: str, paise: str | None, negative: bool) -> str:
    value = int(digits.replace(",", "")) + (1 if paise and int(paise.ljust(2, "0")) >= 50 else 0)
    return ("minus " if negative else "") + indian_words(value) + " rupees"


def _plain(text: str) -> str:
    """Make amounts sound Indian when read aloud:
    'Rs 1,26,32,553.34' -> '1 crore 26 lakh 32 thousand 553 rupees' (paise rounded),
    a bare '1,26,32,553' -> '1 crore 26 lakh 32 thousand 553'; 'Rs 10.41 lakh' stays as it is."""
    text = _RS.sub(lambda m: _spoken(m.group(2), m.group(3), bool(m.group(1))), text)
    text = _WORDS.sub(lambda m: f"{m.group(1)} {m.group(2).lower()} rupees", text)
    return _INDIAN.sub(lambda m: indian_words(int(m.group(1).replace(",", ""))), text)


_WORDS = re.compile(r"(?:Rs\.?|₹|INR)\s?(\d+(?:\.\d+)?)\s*(lakhs?|crores?)\b", re.I)
