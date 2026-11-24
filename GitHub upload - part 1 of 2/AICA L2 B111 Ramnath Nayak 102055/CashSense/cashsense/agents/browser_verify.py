"""Offline browser agent: verifies IFSC codes and beneficiary accounts by operating the
verification web pages in a real (headless) browser, the way a person would - type, click,
read the result - and saves a screenshot as audit evidence.

Uses Playwright with the Microsoft Edge already installed on Windows (no browser download).
The pages are local files, so everything works offline.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import config


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", re.sub(r"\(SAMPLE\)", "", (name or "").upper())).split("PVT")[0].strip()


def names_match(a: str, b: str) -> bool:
    x, y = _norm(a), _norm(b)
    return bool(x) and bool(y) and (x == y or x.startswith(y) or y.startswith(x))


class BankVerifier:
    def __init__(self, registry_dir: Path | None = None, evidence_dir: Path | None = None, headless: bool = True):
        self.registry = Path(registry_dir or config.DATA_DIR / "phase3" / "registry")
        self.evidence = Path(evidence_dir or config.DATA_DIR / "phase3" / "evidence")
        self.headless = headless
        self._pw = self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(channel="msedge", headless=self.headless)
        except Exception:  # Edge missing: fall back to Playwright's own Chromium if installed
            self._browser = self._pw.chromium.launch(headless=self.headless)
        self.evidence.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _read(self, page) -> dict:
        return {el.get_attribute("data-field"): el.inner_text() for el in page.query_selector_all("td[data-field]")}

    def lookup_ifsc(self, ifsc: str) -> dict:
        page = self._browser.new_page()
        try:
            page.goto((self.registry / "ifsc_lookup.html").as_uri())
            page.fill("#ifsc", ifsc)
            page.click("#search")
            status = page.inner_text("#status")
            data = self._read(page)
            return {"ifsc": ifsc, "found": status == "FOUND", "bank": data.get("Bank", ""),
                    "branch": data.get("Branch", ""), "city": data.get("City", "")}
        finally:
            page.close()

    def verify_account(self, ifsc: str, account_no: str, expected_name: str, evidence_name: str) -> dict:
        page = self._browser.new_page(viewport={"width": 900, "height": 640})
        try:
            page.goto((self.registry / "account_verify.html").as_uri())
            page.fill("#ifsc", ifsc)
            page.fill("#acct", account_no)
            page.click("#search")
            status = page.inner_text("#status")
            holder = self._read(page).get("Account holder", "")
            shot = self.evidence / f"{evidence_name}.png"
            page.screenshot(path=str(shot))
            found = status == "ACCOUNT ACTIVE"
            return {"ifsc": ifsc, "account_last4": account_no[-4:], "account_found": found, "holder": holder,
                    "expected": expected_name, "name_match": found and names_match(holder, expected_name),
                    "screenshot": str(shot.relative_to(config.ROOT)) if shot.is_relative_to(config.ROOT) else str(shot)}
        finally:
            page.close()
