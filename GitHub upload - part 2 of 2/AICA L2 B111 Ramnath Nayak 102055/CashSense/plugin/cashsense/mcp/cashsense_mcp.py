"""CashSense MCP server - JSON-RPC 2.0 over stdin/stdout, Python standard library only.

Gives Claude READ-ONLY access to CashSense through the local API (127.0.0.1:8765, X-CashSense-Key).
No tool can approve, post or change anything - approvals stay with the CA in Telegram.

Configuration (environment): CASHSENSE_URL (default http://127.0.0.1:8765) and either CASHSENSE_API_KEY or
CASHSENSE_HOME (the cashsense folder; the key is read from its .env).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROTOCOL = "2025-06-18"
SERVER = {"name": "cashsense", "version": "1.0.0"}

TOOLS = [
    ("cash_position", "get_cash_position", "Bank balances, cash-credit drawn / limit / utilisation and EEFC balance "
     "as at the CashSense as-of date.", {}, []),
    ("forecast", "get_forecast", "13-week cash forecast for a scenario: peak CC drawing and utilisation, 85% alert "
     "weeks, weekly figures.", {"scenario": {"type": "string", "enum": ["base", "late_15", "top_customer_default",
                                                                        "capex_forward"]}}, ["scenario"]),
    ("reconciliation_status", "get_reconciliation_status", "Latest bank reconciliation per account and the "
     "outstanding reconciling items.", {}, []),
    ("risks", "get_risks", "Risk flags (vendor bank changes, unknown payees, split/duplicate payments, MSME 43B(h)...).",
     {"status": {"type": "string", "enum": ["open", "all"]}}, []),
    ("pending_approvals", "get_pending_approvals", "Approvals waiting for the CA in Telegram.", {}, []),
    ("receivables", "get_receivables", "Open customer invoices by customer, with overdue amounts.",
     {"top_n": {"type": "integer"}, "overdue_only": {"type": "boolean"}}, []),
    ("payables", "get_payables", "Open supplier bills, overdue and MSME (sec 43B(h)) totals.",
     {"msme_only": {"type": "boolean"}, "overdue_only": {"type": "boolean"}}, []),
    ("commitments", "get_commitments", "Known future payments/receipts (salary, statutory, rent, EMI, capex, FD).",
     {"from_date": {"type": "string"}, "to_date": {"type": "string"}}, []),
    ("ask", None, "Ask the CashSense assistant (Gemini with the same read-only tools) a question in plain English.",
     {"question": {"type": "string"}}, ["question"]),
]


def api_key() -> str:
    key = os.environ.get("CASHSENSE_API_KEY", "")
    home = os.environ.get("CASHSENSE_HOME", "")
    if not key and home:
        env = Path(home) / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("CASHSENSE_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    return key


def call_api(path: str, payload: dict, timeout: float = 120) -> dict:
    url = os.environ.get("CASHSENSE_URL", "http://127.0.0.1:8765").rstrip("/") + path
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-CashSense-Key": api_key()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300]
        raise RuntimeError(f"CashSense API error {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"CashSense API not reachable at {url} - start it with scripts/start_cashsense.ps1 "
                           f"({exc.reason})") from None


def tool_list() -> list[dict]:
    return [{"name": n, "description": d, "annotations": {"readOnlyHint": True, "openWorldHint": False},
             "inputSchema": {"type": "object", "properties": props, "required": req, "additionalProperties": False}}
            for n, _, d, props, req in TOOLS]


def run_tool(name: str, args: dict) -> dict:
    spec = next((t for t in TOOLS if t[0] == name), None)
    if spec is None:
        raise ValueError(f"Unknown tool {name}")
    if name == "ask":
        return call_api("/api/ask", {"question": str(args.get("question", ""))[:500]})
    return call_api(f"/api/tool/{spec[1]}", {"args": args or {}})


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:                      # notification (e.g. notifications/initialized): no reply
        return None
    try:
        if method == "initialize":
            client_version = (msg.get("params") or {}).get("protocolVersion", PROTOCOL)
            result = {"protocolVersion": client_version, "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": SERVER,
                      "instructions": "Read-only CashSense treasury data (SAMPLE company). Approvals happen in Telegram."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            p = msg.get("params") or {}
            try:
                data = run_tool(p.get("name", ""), p.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=1)}],
                          "isError": False}
            except (RuntimeError, ValueError) as exc:
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as exc:  # never crash the server on one bad request
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(exc)}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
