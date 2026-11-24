"""Telegram Bot API client (free). The bot token comes from TELEGRAM_BOT_TOKEN and is never
logged: errors are re-raised without the request URL, because the URL contains the token."""
from __future__ import annotations

import requests

from .. import config

API = "https://api.telegram.org"


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, token: str | None = None, chat_id: str | None = None,
                 session: requests.Session | None = None, timeout: float = 20.0):
        self.token = token if token is not None else config.setting("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None else config.setting("TELEGRAM_CHAT_ID")
        self.http = session or requests.Session()
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _call(self, method: str, payload: dict | None = None, timeout: float | None = None) -> dict | list:
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not set in .env")
        try:
            r = self.http.post(f"{API}/bot{self.token}/{method}", json=payload or {}, timeout=timeout or self.timeout)
        except requests.RequestException as exc:
            raise TelegramError(f"Cannot reach Telegram ({type(exc).__name__})") from None
        try:
            body = r.json()
        except ValueError:
            raise TelegramError(f"Telegram returned HTTP {r.status_code}") from None
        if not body.get("ok"):
            raise TelegramError(f"Telegram refused {method}: {body.get('description', r.status_code)}")
        return body["result"]

    # -- basics ---------------------------------------------------------------
    def get_me(self) -> dict:
        return self._call("getMe")

    def get_updates(self, offset: int | None = None, wait: int = 0) -> list[dict]:
        payload = {"timeout": wait, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload, timeout=wait + self.timeout)

    def discover_chat_id(self) -> str | None:
        """Find the private chat of the person who sent /start to the bot."""
        for upd in reversed(self.get_updates()):
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") == "private":
                return str(chat["id"])
        return None

    def send_message(self, text: str, buttons: list[list[tuple[str, str]]] | None = None,
                     chat_id: str | None = None) -> dict:
        """Send text (HTML formatting). buttons: rows of (label, callback_data) for inline buttons."""
        target = chat_id or self.chat_id
        if not target:
            raise TelegramError("No chat ID yet - send /start to the bot, then run telegram-check")
        payload = {"chat_id": target, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row]
                                                           for row in buttons]}
        return self._call("sendMessage", payload)

    def download_file(self, file_id: str) -> tuple[bytes, str]:
        """Download a file the user sent to the bot. Returns (content, file name from Telegram's path)."""
        info = self._call("getFile", {"file_id": file_id})
        try:
            r = self.http.get(f"{API}/file/bot{self.token}/{info['file_path']}", timeout=60)
        except requests.RequestException as exc:
            raise TelegramError(f"Cannot download file ({type(exc).__name__})") from None
        if r.status_code != 200:
            raise TelegramError(f"File download failed (HTTP {r.status_code})")
        return r.content, info["file_path"].rsplit("/", 1)[-1]

    def send_voice(self, ogg: bytes, caption: str = "", chat_id: str | None = None) -> dict:
        """Send an OGG/Opus voice message."""
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not set in .env")
        try:
            r = self.http.post(f"{API}/bot{self.token}/sendVoice",
                               data={"chat_id": chat_id or self.chat_id, "caption": caption[:1000]},
                               files={"voice": ("answer.ogg", ogg, "audio/ogg")}, timeout=60)
        except requests.RequestException as exc:
            raise TelegramError(f"Cannot reach Telegram ({type(exc).__name__})") from None
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not body.get("ok"):
            raise TelegramError(f"Telegram refused sendVoice: {body.get('description', r.status_code)}")
        return body["result"]

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    def edit_message(self, message_id: int, text: str, chat_id: str | None = None) -> None:
        self._call("editMessageText", {"chat_id": chat_id or self.chat_id, "message_id": message_id,
                                       "text": text, "parse_mode": "HTML"})
