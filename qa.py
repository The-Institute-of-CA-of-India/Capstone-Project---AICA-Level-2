"""Answers and notes. Rule-based answers use calc.py numbers only.
Optional Gemini call: it receives masked summary numbers (never raw rows, PAN,
Aadhaar, bank or phone numbers) and only explains; it never calculates."""
from __future__ import annotations

import json
import re

import requests

from calc import inr, discount_scenario, can_afford, mask_map

CHIPS = [
    "Who owes me money, and since when?",
    "Is my profit up or down compared to last month, and why?",
    "Can I afford to pay salaries and GST this month?",
    "Which expense grew the most?",
    "How many weeks of cash do I have?",
    "What if I give a 5% discount to my top customer?",
    "What GST will I probably owe this quarter?",
    "Am I on track for my target this month?",
    "Which customer gives me the most sales?",
    "Who do I need to pay in the next 15 days?",
]
DISCLAIMER = ("Based on the data uploaded by your CA. Estimates only. Not tax or legal advice. "
              "Please confirm with your CA before acting.")


def _r(a, w, n):
    return dict(answer=a, why=w, next=n)


def rule_answer(q: str, m: dict):
    t = q.lower()
    if "discount" in t:
        d = discount_scenario(m, 5)
        return _r(f"A 5% discount to {d['customer']} cuts profit by {inr(d['cut'])}, from {inr(m['profit'])} "
                  f"to {inr(d['new_profit'])} (before fixed costs).",
                  f"{d['customer']} is your top customer this month, so even a small discount costs real money.",
                  "Offer the discount only if it brings repeat orders or faster payment.")
    if "afford" in t or "salar" in t:
        a = can_afford(m)
        verdict = "Yes" if a["margin"] >= 0 else "Not comfortably"
        return _r(f"{verdict}. You need about {inr(a['need'])} (fixed costs {inr(m['fixed'])}, supplier bills "
                  f"due in 30 days {inr(a['due_30'])}, GST estimate {inr(a['gst'])}) against cash of {inr(m['cash'])}; "
                  f"margin {inr(a['margin'])}.",
                  "This assumes no new sales are collected; the GST figure is an estimate only.",
                  "Collect overdue receivables first." if m["overdue_receivables"] > 0 else "Keep the margin as a buffer.")
    if "gst" in t or "tax" in t:
        return _r(f"GST estimate for {m['cur_period']} (latest month in the data): collected {inr(m['gst_collected'])} less input credit "
                  f"{inr(m['gst_input'])} = about {inr(m['gst_net'])} payable (estimate only).",
                  "Input credit rules, blocked credits and timing are not applied, and a full quarter needs all three months of data.",
                  "Ask your CA to confirm the figure before the due date.")
    if "weeks of cash" in t or "runway" in t or "how many weeks" in t or "cash" in t:
        rw = "more than a year" if m["runway"] > 52 else f"{m['runway']:.1f} weeks"
        return _r(f"You have {inr(m['cash'])} in cash, enough for about {rw} at your current spending of "
                  f"{inr(m['weekly_outflow'])} a week.",
                  "Spending is the average of paid bills, expenses and fixed costs in the months uploaded.",
                  "Collect overdue money to extend the runway." if m["overdue_receivables"] > 0 else "Keep watching the runway each month.")
    if "owe" in t or "overdue" in t or "receivable" in t:
        r = m["receivables"]
        if r.empty:
            return _r("Nobody owes you money right now.", "There are no unpaid sales in the data.", "Nothing to chase.")
        first = r.iloc[0]
        n = len(r)
        return _r(f"{n} customer bill(s) are unpaid, {inr(m['total_receivables'])} in total; "
                  f"{inr(m['overdue_receivables'])} is overdue. Oldest: {first['Party']}, "
                  f"{inr(first['Total'])}, {max(int(first['Days_Overdue']), 0)} days overdue.",
                  "Overdue money is cash you cannot use to pay your own bills.",
                  f"Send a polite reminder to {first['Party']} today.")
    if "expense" in t or "grew" in t or "cost" in t:
        g = m["cost_growth"]
        if g.empty or g.iloc[0] <= 0:
            return _r("No cost category grew compared with last month.", "All categories were flat or lower.",
                      "No action needed.")
        return _r(f"{g.index[0]} grew the most: up {inr(g.iloc[0])} compared with last month.",
                  "This is from Purchases and Expenses by category.", f"Review the {g.index[0]} bills with your CA.")
    if "target" in t or "track" in t:
        sp, pp = m["sales_pct"], m["profit_pct"]
        status = "on track" if (sp or 0) >= 100 and (pp or 0) >= 100 else "behind on at least one target"
        return _r(f"You are {status}: sales are {sp:.0f}% of target and profit after fixed costs is {pp:.0f}% of target.",
                  f"Sales {inr(m['sales'])}; profit after fixed costs {inr(m['profit_after_fixed'])}.",
                  "Check the Targets page for the details.")
    if "customer" in t and ("most" in t or "top" in t or "best" in t):
        if not m["top_customer"]:
            return None
        share = m["top_customer_sales"] / m["sales"] * 100 if m["sales"] else 0
        return _r(f"{m['top_customer']} gives you the most sales: {inr(m['top_customer_sales'])}, {share:.0f}% of this month.",
                  "Depending on one customer is a risk if they delay payment.", "Look for a second large customer.")
    if "pay" in t or "supplier" in t or "payable" in t:
        p = m["payables"]
        soon = p[p["Days_To_Due"] <= 15]
        if soon.empty:
            return _r("No supplier bills fall due in the next 15 days.", "All unpaid bills are due later.", "No urgent payments.")
        lst = "; ".join(f"{r.Party} {inr(r.Total)} in {max(int(r.Days_To_Due), 0)} days" for r in soon.itertuples())
        return _r(f"You need to pay {inr(soon['Total'].sum())} in the next 15 days: {lst}.",
                  "Late payment can cost interest or goodwill.", "Plan the cash for these dates.")
    if "profit" in t or "why" in t:
        chg = m["profit_chg"]
        direction = "up" if (chg or 0) >= 0 else "down"
        top = "; ".join(f"{n}: {'+' if v > 0 else '-'}{inr(abs(v))}" for n, v, _ in m["changes"][:3])
        pct = f"{abs(chg):.0f}%" if chg is not None else "n/a"
        return _r(f"Profit is {direction} {pct}: {inr(m['profit'])} this month against {inr(m['prev_profit'])} last month "
                  f"(before fixed costs).", f"Biggest movements: {top}.",
                  "Ask your CA whether the biggest cost jump is one-off.")
    return None


# ---------------------------------------------------------------- AI (optional)
def _summary_for_ai(m: dict, mp: dict) -> dict:
    return dict(
        month=m["cur_period"], sales=m["sales"], purchases=m["purchases"], expenses=m["expenses"],
        profit_before_fixed=m["profit"], fixed_costs=m["fixed"], profit_after_fixed=m["profit_after_fixed"],
        last_month_profit=m["prev_profit"], cash=m["cash"], runway_weeks=round(m["runway"], 1),
        weekly_spend=m["weekly_outflow"], gst_estimate_net=m["gst_net"], health=m["health"],
        receivables=[dict(who=mp.get(r.Party, r.Party), amount=r.Total, days_overdue=int(r.Days_Overdue))
                     for r in m["receivables"].itertuples()],
        payables=[dict(who=mp.get(r.Party, r.Party), amount=r.Total, days_to_due=int(r.Days_To_Due))
                  for r in m["payables"].itertuples()],
        biggest_changes=[dict(item=re.sub(r"Sales to (.+)", lambda x: "Sales to " + mp.get(x.group(1), x.group(1)), n),
                              change=v) for n, v, _ in m["changes"]],
    )


def ai_answer(q: str, m: dict, api_key: str):
    """Returns text or None. Names are masked before sending and restored afterwards."""
    mp = mask_map(m)
    prompt = ("You are Mini CFO, a plain-language finance assistant for an Indian small business owner. "
              "Answer ONLY from the JSON numbers below. Do not calculate new figures; if the answer is not in "
              "the data reply exactly: I don't have this information. Format: (1) direct answer with the number, "
              "(2) one line on why or what it means, (3) one suggested next step. Under 80 words. Reply in the "
              "language of the question (English or Hindi). Use the rupee symbol. Label GST as an estimate.\n\n"
              f"DATA: {json.dumps(_summary_for_ai(m, mp), default=float)}\n\nQUESTION: {q}")
    try:
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                          params={"key": api_key}, timeout=30,
                          json={"contents": [{"parts": [{"text": prompt}]}]})
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None
    for real, masked in mp.items():
        text = text.replace(masked, real)
    return text


# ---------------------------------------------------------------- note
def note_text(client: dict, m: dict) -> str:
    chg = "\n".join(f"- {n}: {'up' if v > 0 else 'down'} {inr(abs(v))}" for n, v, _ in m["changes"]) or "- No major changes"
    risks = []
    if m["overdue_receivables"] > 0:
        risks.append(f"{inr(m['overdue_receivables'])} of customer payments is overdue.")
    if m["runway"] < 8:
        risks.append(f"Cash covers only about {m['runway']:.1f} weeks of spending.")
    if m["profit_after_fixed"] < 0:
        risks.append("Profit after fixed costs is negative.")
    if not risks:
        risks.append("No major risks flagged this month.")
    actions = []
    r = m["receivables"]
    if not r.empty and r.iloc[0]["Days_Overdue"] > 0:
        actions.append(f"Collect {inr(r.iloc[0]['Total'])} from {r.iloc[0]['Party']} (overdue {int(r.iloc[0]['Days_Overdue'])} days).")
    if not m["payables"].empty:
        p = m["payables"].iloc[0]
        actions.append(f"Plan {inr(p['Total'])} for {p['Party']} due in {max(int(p['Days_To_Due']), 0)} days.")
    actions.append("Review the biggest cost increase with your CA." if m["changes"] else "Keep tracking costs monthly.")
    actions = actions[:3]
    return (f"# Monthly CFO note: {client['name']}, {m['cur_period']}\n\n"
            f"**Health: {m['health']}** ({'; '.join(m['health_reasons'])})\n\n"
            f"## Highlights\n"
            f"- Sales {inr(m['sales'])}; profit before fixed costs {inr(m['profit'])}; after fixed costs {inr(m['profit_after_fixed'])}.\n"
            f"- Cash {inr(m['cash'])}; runway about {m['runway']:.1f} weeks.\n"
            f"- Customers owe you {inr(m['total_receivables'])}; you owe suppliers {inr(m['total_payables'])}.\n"
            f"- GST estimate for the month: about {inr(m['gst_net'])} (estimate only).\n\n"
            f"## What changed since last month\n{chg}\n\n"
            f"## Risks\n" + "\n".join(f"- {x}" for x in risks) + "\n\n"
            f"## Three actions\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(actions, 1)) + "\n\n"
            f"_{DISCLAIMER}_\n")
