"""Telegram client tests (offline, with a stand-in HTTP session)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from cashsense import config
from cashsense.messaging.telegram import TelegramClient, TelegramError

TOKEN = "123456:SECRET-TOKEN-XYZ"


class Resp:
    def __init__(self, body, code=200):
        self._body, self.status_code = body, code

    def json(self):
        return self._body


class Session:
    def __init__(self, results=None, fail=False):
        self.calls, self.results, self.fail = [], results or {}, fail

    def post(self, url, json, timeout):
        self.calls.append((url, json))
        if self.fail:
            raise requests.ConnectionError(f"failed to reach {url}")
        method = url.rsplit("/", 1)[1]
        res = self.results.get(method, True)
        return Resp(res if isinstance(res, dict) and "ok" in res else {"ok": True, "result": res})


class TelegramTests(unittest.TestCase):
    def test_send_with_buttons(self):
        s = Session({"sendMessage": {"message_id": 7}})
        t = TelegramClient(TOKEN, "999", session=s)
        self.assertEqual(t.send_message("Approve?", [[("Approve", "ok:1"), ("Reject", "no:1")]]), {"message_id": 7})
        url, payload = s.calls[0]
        self.assertTrue(url.endswith("/sendMessage"))
        self.assertEqual(payload["chat_id"], "999")
        self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][1], {"text": "Reject", "callback_data": "no:1"})

    def test_discover_chat_from_start(self):
        updates = [{"update_id": 1, "message": {"chat": {"id": -100, "type": "group"}}},
                   {"update_id": 2, "message": {"chat": {"id": 4242, "type": "private"}, "text": "/start"}}]
        t = TelegramClient(TOKEN, "", session=Session({"getUpdates": updates}))
        self.assertEqual(t.discover_chat_id(), "4242")

    def test_errors_never_reveal_token(self):
        t = TelegramClient(TOKEN, "1", session=Session(fail=True))
        with self.assertRaises(TelegramError) as cm:
            t.get_me()
        self.assertNotIn("SECRET", str(cm.exception))
        refused = Session({"getMe": {"ok": False, "description": "Unauthorized"}})
        with self.assertRaises(TelegramError) as cm:
            TelegramClient(TOKEN, "1", session=refused).get_me()
        self.assertIn("Unauthorized", str(cm.exception))
        self.assertNotIn("SECRET", str(cm.exception))

    def test_needs_token_and_chat(self):
        with self.assertRaises(TelegramError):
            TelegramClient("", "1", session=Session()).get_me()
        with self.assertRaises(TelegramError):
            TelegramClient(TOKEN, "", session=Session()).send_message("hi")

    def test_save_setting_updates_env_in_place(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "ROOT", Path(tmp)):
            (Path(tmp) / ".env").write_text("A=1\nTELEGRAM_CHAT_ID=\nB=2\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {}):
                config.save_setting("TELEGRAM_CHAT_ID", "4242")
                config.save_setting("NEW_KEY", "x")
            self.assertEqual((Path(tmp) / ".env").read_text(encoding="utf-8"),
                             "A=1\nTELEGRAM_CHAT_ID=4242\nB=2\nNEW_KEY=x\n")


if __name__ == "__main__":
    unittest.main()
