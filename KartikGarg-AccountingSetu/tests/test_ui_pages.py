"""Smoke-render every page for every role against the demo dataset (Streamlit AppTest).

Verifies that each page executes without exceptions and without 'Unexpected error' messages.
It does not replace manual UX review.
"""
import datetime as dt
from pathlib import Path

import pytest

from services import ai_service, ocr_service
from services.db import SQLiteDatabase, get_db, set_db
from services.storage_service import LocalStorage, set_storage

HARNESS = str(Path(__file__).with_name("ui_harness.py"))

FIRM_PAGES = ["views.client_workspace:page", "views.dashboard:page", "views.documents:page", "views.accounting:page",
              "views.bank:page", "views.gst:page", "views.reports:page", "views.tally:page", "views.finalization:page",
              "views.assistant:page", "views.clients:page", "views.staff:page", "views.firm_settings:page",
              "views.activity:audit_page", "views.activity:notifications_page", "views.auth_views:change_password_page"]
CLIENT_PAGES = ["views.client_portal:dashboard", "views.client_portal:submit_page", "views.client_portal:my_documents",
                "views.client_portal:reports_page", "views.client_portal:clarifications_page", "views.client_portal:profile_page",
                "views.assistant:page"]
ADMIN_PAGES = ["views.super_admin:overview", "views.super_admin:firms_page", "views.super_admin:plans_page",
               "views.super_admin:settings_page", "views.super_admin:logs_page"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ui")
    db = SQLiteDatabase(tmp / "ui.db")
    db.migrate()
    set_db(db)
    set_storage(LocalStorage(tmp / "storage"))
    ocr_service.set_ocr(ocr_service.OCRProvider())
    ai_service.set_provider(ai_service.LocalRulesProvider())
    from scripts import seed_demo

    seed_demo.seed(quiet=True)
    ids = {r["email"]: r["id"] for r in get_db().fetchall("select id, email from user_profiles")}
    client = get_db().fetchone("select id from clients where name = 'Shree Ganesh Traders'")
    return ids, client["id"]


def _render(user_id, page, client_id=None):
    from streamlit.testing.v1 import AppTest

    today = dt.date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    at = AppTest.from_file(HARNESS, default_timeout=60)
    at.session_state["user_id"] = user_id
    at.session_state["page"] = page
    at.session_state["client_id"] = client_id
    at.session_state["year"], at.session_state["month"] = y, m
    at.session_state["fy"] = f"{y if m >= 4 else y - 1}-{str((y if m >= 4 else y - 1) + 1)[-2:]}"
    at.run()
    return at


def _assert_ok(at, page):
    assert not at.exception, f"{page}: {[e.value for e in at.exception]}"
    errs = [e.value for e in at.error if "Unexpected error" in str(e.value)]
    assert not errs, f"{page}: {errs}"


@pytest.mark.parametrize("page", FIRM_PAGES)
def test_firm_admin_pages(demo, page):
    ids, cid = demo
    _assert_ok(_render(ids["admin@kapoorca.demo"], page, cid), page)


@pytest.mark.parametrize("page", ["views.documents:page", "views.accounting:page", "views.reports:page", "views.dashboard:page"])
def test_accountant_pages(demo, page):
    ids, cid = demo
    _assert_ok(_render(ids["accountant@kapoorca.demo"], page, cid), page)


@pytest.mark.parametrize("page", CLIENT_PAGES)
def test_client_pages(demo, page):
    ids, _ = demo
    _assert_ok(_render(ids["owner@ganeshtraders.demo"], page), page)


@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_super_admin_pages(demo, page):
    ids, _ = demo
    _assert_ok(_render(ids["owner@setu.demo"], page), page)


def test_other_firm_cannot_open_client_pages(demo):
    ids, cid = demo
    at = _render(ids["admin@mehtaca.demo"], "views.accounting:page", cid)
    assert at.exception, "a foreign client id must not render"
