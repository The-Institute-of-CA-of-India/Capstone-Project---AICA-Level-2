"""Builds Phase4_Review_SAMPLE.xlsx: scenario summary, weekly forecast per scenario (with live check formulas),
all forecast flows, Gemini commentary with the amount check, assistant question-bank results, known-flow accuracy."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .phase1_workbook import NOTE_FONT, NUM, _sheet
from .phase2_workbook import BAD_FILL, OK_FILL


def build(results: dict, out_file: Path) -> Path:
    fc, comm, qa, acc = results["forecast"], results["commentary"], results["assistant"], results["accuracy"]
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    lines = [("CashSense - Phase 4 review workbook (SAMPLE DATA)", Font(bold=True, size=14)),
             (f"As at {results['as_of']}; 13 weeks to {next(iter(fc.values()))['end']}", None), ("", None),
             ("Method", Font(bold=True)),
             ("Known flows: uncleared cheques (BRS), open receivables (overdue spread over weeks 1-4), open payables "
              "(overdue MSME paid at once - sec 43B(h)), commitments register.", None),
             ("Run-rate: new sales and purchases from the same month last year per party, on credit terms.", None),
             ("Funding: cash above Rs 15 lakh swept to CC; shortfall drawn from CC; CC interest 10.5% at month end.", None),
             ("Alert: CC utilisation above 85% of the Rs 2 crore limit.", None), ("", None),
             ("Results", Font(bold=True)),
             (f"Known flows vs independent answer key: {acc['known_flow_weeks_matching']} of {acc['known_flow_weeks']} "
              f"scenario-weeks identical", None),
             (f"Assistant question bank: {qa.get('passed', 0)}/{qa.get('asked', 0)} passed"
              + (f" ({qa['note']})" if qa.get("note") else ""), None),
             (f"Gemini commentary: {'used, ' + comm.get('model', '') if comm.get('ai_used') else 'not available'}; "
              f"unverified amounts: {comm.get('unverified_amounts', [])}", None),
             ("", None), ("Forecasts are estimates based on stated assumptions.", NOTE_FONT)]
    for text, font in lines:
        ws.append([text])
        if font:
            ws.cell(ws.max_row, 1).font = font
    ws.column_dimensions["A"].width = 130

    _sheet(wb, "Scenarios", ["Scenario", "Label", "Peak week", "Peak CC drawn", "Peak utilisation", "Min headroom",
                             "First 85% alert week", "Alert weeks", "Total inflow", "Total outflow"],
           [[s, r["label"], r["summary"]["peak_week"], r["summary"]["peak_cc_drawn_paise"] / 100,
             r["summary"]["peak_utilisation"], r["summary"]["min_headroom_paise"] / 100,
             r["summary"]["first_alert_week"] or "none", ", ".join(map(str, r["summary"]["alert_weeks"])) or "none",
             r["summary"]["total_inflow_paise"] / 100, -r["summary"]["total_outflow_paise"] / 100]
            for s, r in fc.items()], num_cols=(4, 6, 9, 10), widths={2: 46})
    for s, r in fc.items():
        sh = _sheet(wb, f"Weekly {s}"[:31], ["Week", "Start", "End", "Inflow", "Outflow", "Net flow", "Net position",
                                             "CC drawn", "Headroom", "Utilisation", "Alert", "Check: position roll"],
                    [[w["week"], w["start"], w["end"], w["inflow_paise"] / 100, w["outflow_paise"] / 100,
                      w["net_flow_paise"] / 100, w["net_position_paise"] / 100, w["cc_drawn_paise"] / 100,
                      w["cc_headroom_paise"] / 100, w["cc_utilisation"], w["alert"]] for w in r["weeks"]],
                    num_cols=(4, 5, 6, 7, 8, 9))
        opening = r["opening"]["net_position_paise"] / 100
        for i in range(2, sh.max_row + 1):
            prev = f"G{i - 1}" if i > 2 else str(opening)
            sh[f"L{i}"] = f'=IF(ROUND({prev}+F{i}-G{i},2)=0,"OK","CHECK")'
            sh[f"J{i}"].number_format = "0%"
    base = fc["base"]
    _sheet(wb, "Flows (base)", ["Date", "Category", "Label", "Party", "Basis", "Amount"],
           [[f["when"], f["category"], f["label"], f["party_id"], f["basis"], f["amount_paise"] / 100]
            for f in sorted(base["flows"], key=lambda x: x["when"])], num_cols=(6,), widths={3: 60})
    cm = [["Headline", comm.get("headline", "")]] + [[f"Scenario: {k}", v] for k, v in comm.get("scenarios", {}).items()] \
        + [[f"Action {i + 1}", a] for i, a in enumerate(comm.get("actions", []))] \
        + [["Unverified amounts", ", ".join(map(str, comm.get("unverified_amounts", []))) or "none"],
           ["Model", comm.get("model", comm.get("error", ""))]]
    _sheet(wb, "Commentary", ["Part", "Text (Gemini)"], cm, widths={1: 24, 2: 120})
    qs = _sheet(wb, "Assistant Q&A", ["Question", "Answer (Gemini + tools)", "Tools used", "Expected", "Pass"],
                [[q["q"], q.get("answer", ""), ", ".join(q.get("tools_used", [])), q.get("expected", ""),
                  "yes" if q.get("pass") else "NO"] for q in qa.get("results", [])], widths={1: 50, 2: 90, 4: 30})
    for i in range(2, qs.max_row + 1):
        qs[f"E{i}"].fill = OK_FILL if qs[f"E{i}"].value == "yes" else BAD_FILL
    _sheet(wb, "Power BI export", ["Table", "Rows"], [[k, v] for k, v in results["powerbi"].items()], widths={1: 30})
    out_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_file)
    _ = NUM
    return out_file
