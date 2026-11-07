"""Draft Reply and Settings for the browser front end (same rules as the desktop dialogs)."""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

from ..core import ai, ai_client, client_facts, drafting, law_library, register, usage
from ..core.allowlist import Allowlist
from ..core.config import resolve_path, save_config
from ..core.detectors import load_client_master, save_client_master
from ..core.models import UserFacingError

TITLES = {"framing": "Issue framing", "reply": "Reply", "advisory": "Advisory", "law": "Law note"}


def _opts_key(o: dict[str, Any]) -> tuple:
    return (o["facts"], o["out"], o["in"], o["type"], bool(o["web"]), bool(o["lib"]))


class Draft:
    """One Draft Reply session for a verified redacted PDF. Only tokens leave this computer."""

    def __init__(self, job: drafting.DraftJob, cfg: dict[str, Any]) -> None:
        self.job = job
        self.cfg = cfg
        self.notice_text: str | None = None
        self.safe_facts = ""
        self.lib_block = ""
        self.previewed_key: tuple | None = None
        self.preview_text = ""
        self.notes: list[str] = []
        self.info = f"Verified file: {job.pdf_path.name}"
        self.output: drafting.DraftOutput | None = None
        self.output_mode = "reply"
        self.sections: dict[str, str] = {}
        self.placeholders: list[dict[str, str]] = []
        self.known = 0
        self.confirm: dict[str, Any] | None = None
        self.prompt_text = ""
        self.prompt_mode = ""  # sections the prompt asked for, used when the answer is pasted back
        self.ver = 0  # bumps whenever text the page shows is replaced by the engine
        self.facts_key, self.client_name, self.ay = "", "", ""
        self.facts: dict[str, Any] = {"name": "", "common": {}, "years": {}}
        try:
            self.ay = drafting.detect_ay(job)
            self.facts_key, self.client_name = client_facts.client_key(job.registry)
            self.facts = client_facts.load(self.facts_key)
        except UserFacingError:
            self.facts_key = ""

    # ------------------------------------------------------------------ what the page sees
    def public(self) -> dict[str, Any]:
        lib = law_library.file_count()
        return {
            "file": self.job.pdf_path.name, "ay": self.ay, "client": self.client_name, "hasFacts": bool(self.facts_key),
            "models": ai.choices(self.cfg), "model": ai.current(self.cfg), "noPdfWeb": ai.NO_PDF_WEB,
            "types": drafting.NOTICE_TYPES,
            "outputs": drafting.OUTPUTS, "sixBoxes": drafting.SIX_BOXES, "hows": drafting.HOW_MODES, "inModes": drafting.INPUT_MODES,
            "hasPrompt": bool(self.prompt_text),
            "libCount": lib, "libDefault": lib > 0 and bool(self.cfg.get("law_library", {}).get("enabled", True)),
            "preview": self.preview_text, "info": self.info, "ver": self.ver,
            "sections": [{"key": k, "title": TITLES[k], "text": v} for k, v in self.sections.items()],
            "placeholders": self.placeholders, "known": self.known, "hasOutput": self.output is not None,
        }

    # ------------------------------------------------------------------ preview
    def _user_text(self, o: dict[str, Any]) -> str:
        instructions = drafting.user_instructions(o["type"], o["out"], o["in"], self.safe_facts)
        if o["lib"] and self.lib_block:
            return self.lib_block + "\n\n" + instructions
        return instructions

    def prepare_task(self, o: dict[str, Any], allow: Allowlist, master: list, progress) -> dict[str, Any]:
        """Tokenise the facts, read the notice text and search the law library (runs in the background)."""
        safe_facts, notes = drafting.tokenise_facts(o["facts"], self.job, self.cfg, allow, master)
        need_text = (o["in"] in ("both", "text") or o["lib"]) and self.notice_text is None
        text = drafting.extract_text(self.job, copy.deepcopy(self.cfg), progress) if need_text else self.notice_text
        lib_block = ""
        if o["lib"] and text:
            progress(90, "Searching your law library")
            lib_cfg = self.cfg.get("law_library", {})
            excerpts = law_library.search(law_library.query_terms(text), int(lib_cfg.get("max_excerpts", 8)),
                                          int(lib_cfg.get("max_chars", 14000)))
            if excerpts:
                # Library files are the user's own, but tokenise them too in case old replies were saved there.
                lib_block, lib_notes = drafting.tokenise_facts(law_library.as_block(excerpts), self.job, self.cfg, allow, master)
                notes += [f"library: {n}" for n in lib_notes] + [f"{len(excerpts)} law library excerpt(s) included"]
            else:
                notes.append("no matching law library excerpts")
        return {"safe_facts": safe_facts, "notes": notes, "text": text, "lib_block": lib_block, "key": _opts_key(o)}

    def apply_prepared(self, prep: dict[str, Any], o: dict[str, Any]) -> None:
        self.safe_facts, self.notes, self.notice_text, self.lib_block = prep["safe_facts"], prep["notes"], prep["text"], prep["lib_block"]
        parts = []
        if o["in"] in ("both", "pdf"):
            parts.append(f"[Attached PDF: {self.job.pdf_path.name} - the verified redacted file]")
        if o["in"] in ("both", "text"):
            parts.append("=== Notice text ===\n" + (self.notice_text or ""))
        parts.append("=== Instructions, law library excerpts and your facts (tokenised) ===\n" + self._user_text(o))
        self.preview_text = "\n\n".join(parts)
        self.previewed_key = prep["key"]
        self.info = "Preview ready. Check that nothing personal is visible, then click Send."
        if self.notes:
            self.info += "  Facts: " + "; ".join(self.notes) + "."
        self.ver += 1

    # ------------------------------------------------------------------ send
    def _content(self, o: dict[str, Any]) -> list[dict[str, Any]]:
        pdf = self.job.pdf_bytes if o["in"] in ("both", "pdf") else None
        text = self.notice_text if o["in"] in ("both", "text") else None
        return ai_client.build_content(pdf, self.job.pdf_path.name, text, self._user_text(o))

    def _send_cfg(self, o: dict[str, Any]) -> dict[str, Any]:
        cfg = copy.deepcopy(self.cfg)
        if ai.valid_choice(cfg, str(o.get("model", ""))):
            cfg["ai"]["model"] = o["model"]
        return cfg

    def normalise(self, o: dict[str, Any]) -> dict[str, Any]:
        """Options as they will really be used: no PDF or web search for providers that cannot take them."""
        o = dict(o)
        if o.get("frame"):  # optional six-box add-on: an extra first section, and the boxes join the facts
            o["out"] = f"{drafting.FRAMING}+{o.get('out', '')}"
            o["facts"] = drafting.with_six_box(str(o.get("facts", "")), o.get("boxes") or {})
        o["out"] = "+".join(drafting.outputs_of(str(o.get("out", ""))))
        cfg = self._send_cfg(o)
        o["model"] = ai.current(cfg)
        pdf, web = ai.capabilities(cfg, o["model"])
        if o.get("how") == "prompt":  # a chat window takes text; it does its own searching, if any
            pdf, web = False, False
        if not pdf and o.get("in") in ("both", "pdf"):
            o["in"] = "text"
        if not web:
            o["web"] = False
        return o

    def estimate_task(self, o: dict[str, Any], allow: Allowlist, master: list, progress) -> dict[str, Any]:
        """Preview first if the options changed, then count the tokens for the cost question."""
        prep = None
        if self.previewed_key != _opts_key(o):
            prep = self.prepare_task(o, allow, master, progress)
        progress(95, "Estimating the cost")
        if prep is not None:
            saved = (self.safe_facts, self.notice_text, self.lib_block)
            self.safe_facts, self.notice_text, self.lib_block = prep["safe_facts"], prep["text"], prep["lib_block"]
            try:
                content = self._content(o)
            finally:
                self.safe_facts, self.notice_text, self.lib_block = saved
        else:
            content = self._content(o)
        tokens = ai.count_input_tokens(drafting.system_prompt(), content, self._send_cfg(o), bool(o["web"]))
        return {"prep": prep, "tokens": tokens}

    def apply_estimate(self, res: dict[str, Any], o: dict[str, Any]) -> dict[str, Any]:
        if res["prep"] is not None:
            self.apply_prepared(res["prep"], o)
        cfg = self._send_cfg(o)
        choice = ai.current(cfg)
        p_in, p_out, p_search = ai.prices(cfg, choice)
        web_max = int(cfg["ai"]["web_search_max_uses"]) if o["web"] else 0
        typical, worst = usage.estimate(p_in, p_out, res["tokens"], o["out"], web_max, p_search)
        spent = usage.month_spend()
        limit = float(cfg["ai"].get("monthly_limit_usd", 0) or 0)
        msg = (f"Send the content shown in 'What will be sent' to {ai.label(choice, cfg)}?\n\n"
               f"It contains tokens only. Real names and numbers stay on this computer.\n\n"
               f"Estimated cost: about ${typical:.2f} (at most ${worst:.2f}).\n"
               f"Spent this month: ${spent:.2f}" + (f" of your ${limit:.2f} limit." if limit else "."))
        over = bool(limit) and spent + typical > limit
        if over:
            msg += "\n\nWARNING: this draft would take you over your monthly limit."
        if choice.startswith(ai.PREFIX) and not (p_in or p_out):
            msg += "\n\nNote: no prices are set for this provider in Settings, so the estimate shows $0."
        self.confirm = {"key": _opts_key(o), "model": choice}
        return {"text": msg, "over": over}

    def send_task(self, o: dict[str, Any], progress) -> ai_client.DraftResult:
        if (not self.confirm or self.confirm["key"] != _opts_key(o) or self.confirm["model"] != o["model"]
                or self.previewed_key != _opts_key(o)):
            raise UserFacingError("The options changed after the cost estimate. Click Send again.")
        cfg = self._send_cfg(o)
        content = self._content(o)
        self.confirm = None
        return ai.draft_reply(drafting.system_prompt(), content, cfg, bool(o["web"]), progress)

    def apply_draft(self, result: ai_client.DraftResult, o: dict[str, Any]) -> None:
        usage.record(result.cost_usd)
        info = (f"Draft received from {result.model}. About ${result.cost_usd:.2f} "
                f"({result.input_tokens:,} in / {result.output_tokens:,} out tokens, {result.searches} web searches); "
                f"${usage.month_spend():.2f} spent this month. You can edit the text before saving.")
        if result.notes:
            info += " " + " ".join(result.notes)
        self._take_answer(result.text, o["out"], info)

    # ------------------------------------------------------------------ prompt for any AI chat
    def apply_prompt(self, prep: dict[str, Any], o: dict[str, Any]) -> None:
        """Show the self-contained prompt (tokens only) to copy into any AI chat."""
        self.apply_prepared(prep, o)
        notice = self.notice_text if o["in"] in ("both", "text") else None
        self.prompt_text = drafting.chat_prompt(drafting.system_prompt(), notice, self._user_text(o))
        self.preview_text = self.prompt_text
        self.prompt_mode = o["out"]
        self.info = ("Prompt ready. Copy it into any AI chat (it holds tokens only, no real names). Then paste the "
                     "AI's answer in the 'Paste AI answer' tab to restore real values.")
        if self.notes:
            self.info += "  Facts: " + "; ".join(self.notes) + "."

    def save_prompt(self) -> str:
        if not self.prompt_text:
            raise UserFacingError("Make the prompt first.")
        p = drafting.save_prompt(self.job, self.prompt_text)
        return f"Prompt saved in the output folder as {p.name}."

    def paste_answer(self, text: str, out: str) -> None:
        """Restore real values in an answer pasted back from an AI chat (nothing is sent anywhere)."""
        if not text.strip():
            raise UserFacingError("Paste the AI's answer first.")
        mode = self.prompt_mode or out
        info = "Answer pasted and real values restored on this computer. You can edit the text before saving."
        if not any(m in text for m in drafting.MARKERS.values()):
            info += (" The answer has no section markers, so all of it is in the first tab; move any advisory "
                     "part out by hand before saving.")
        self._take_answer(text, mode, info)

    def _take_answer(self, text: str, output_mode: str, info: str) -> None:
        self.output_mode = "+".join(drafting.outputs_of(output_mode))
        self.output = drafting.finalise(text, self.job, self.output_mode)
        self.sections = dict(self.output.restored)
        found = drafting.find_placeholders(self.output)
        known = client_facts.suggestions(found, self.facts, self.ay) if self.facts_key else {}
        self.placeholders = []
        for ph in found:
            # Enclosure lines read naturally as their own description, so pre-fill those.
            attach = re.match(r"\[\[\s*ATTACH\s*:\s*(.+?)\s*\]\]$", ph, re.IGNORECASE)
            value = known.get(ph) or (attach.group(1)[:1].upper() + attach.group(1)[1:] if attach else "")
            self.placeholders.append({"ph": ph, "value": value})
        self.known = len(known)
        if self.output.unrestored:
            info += " WARNING: these tokens could not be restored and are left as-is: " + ", ".join(self.output.unrestored)
        self.info = info
        self.ver += 1

    # ------------------------------------------------------------------ facts / save
    def facts_for(self, ay: str) -> list[dict[str, Any]]:
        return [{"key": k, "label": label, "perYear": per_year, "value": client_facts.get(self.facts, k, ay)}
                for k, label, per_year, _ in client_facts.FIELDS]

    def save_facts(self, ay: str, values: dict[str, str], years: dict[str, dict[str, str]]) -> None:
        """``values`` for the shown AY; ``years`` holds year-wise values typed for other AYs before switching."""
        if not self.facts_key:
            raise UserFacingError("No client could be identified in this notice, so there is no facts sheet.")
        for other_ay, vals in years.items():
            for k, v in vals.items():
                if k in client_facts.YEAR_FIELDS:
                    client_facts.put(self.facts, k, other_ay, str(v).strip())
        for k, v in values.items():
            client_facts.put(self.facts, k, ay, str(v).strip())
        self.ay = ay
        self.facts["name"] = self.client_name
        try:
            client_facts.save(self.facts_key, self.facts)
        except OSError as exc:
            raise UserFacingError("The facts sheet could not be saved.") from exc
        if self.output is not None:
            sugg = client_facts.suggestions([p["ph"] for p in self.placeholders], self.facts, self.ay)
            for p in self.placeholders:
                if not p["value"].strip() and sugg.get(p["ph"]):
                    p["value"] = sugg[p["ph"]]
            self.ver += 1

    def save(self, sections: dict[str, str], values: dict[str, str], remember: bool) -> dict[str, Any]:
        if self.output is None:
            raise UserFacingError("There is no draft to save yet.")
        edited = drafting.DraftOutput(self.output.tokens, {k: str(sections.get(k, v)) for k, v in self.sections.items()},
                                      self.output.unrestored)
        filled = drafting.fill_placeholders(edited, values)
        self.sections = dict(filled.restored)
        for p in self.placeholders:
            p["value"] = values.get(p["ph"], p["value"])
        paths = drafting.save_outputs(self.job, filled, self.output_mode, original=self.output)
        learned = 0
        if self.facts_key and remember:
            learned = client_facts.learn(self.facts, values, self.ay)
            if learned:
                self.facts["name"] = self.client_name
                client_facts.save(self.facts_key, self.facts)
        if self.job.vault_meta.get("original_sha256"):
            register.advance(self.job.vault_meta["original_sha256"], "Drafted")
        self.ver += 1
        msg = "Saved in the output folder:\n\n" + "\n".join(p.name for p in paths)
        if learned:
            msg += f"\n\n{learned} value(s) remembered in this client's facts sheet."
        return {"msg": msg}

    def open_folder(self) -> None:
        os.startfile(str(self.job.folder))  # noqa: S606 - opens Explorer locally


# ---------------------------------------------------------------------- settings
def settings_get(cfg: dict[str, Any]) -> dict[str, Any]:
    allow_path, master_path = resolve_path(cfg, "allowlist"), resolve_path(cfg, "client_master")
    rows = [[e.term, e.pii_type, e.role] for e in load_client_master(master_path)]
    return {
        "redactOfficer": bool(cfg["detection"]["redact_officer"]),
        "propagate": bool(cfg["detection"].get("propagate_values", True)),
        "acceptThreshold": float(cfg["detection"]["accept_threshold"]),
        "lowConf": float(cfg["ocr"]["low_confidence_threshold"]),
        "dpi": int(cfg["ocr"]["dpi"]),
        "outputRoot": cfg["paths"].get("output_root", "") or "",
        "allowlist": allow_path.read_text(encoding="utf-8") if allow_path.exists() else "",
        "master": rows,
        "hasKey": ai_client.has_api_key(),
        "claudeModels": [{"id": k, "label": f"{m.label}  (${m.price_in:g} / ${m.price_out:g} per M tokens)"}
                         for k, m in ai_client.MODELS.items()],
        "models": ai.choices(cfg), "model": ai.current(cfg), "effort": str(cfg["ai"]["effort"]),
        "providers": providers_get(cfg), "noPdfWeb": ai.NO_PDF_WEB,
        "efforts": ["low", "medium", "high", "xhigh", "max"],
        "webMax": int(cfg["ai"]["web_search_max_uses"]),
        "limit": float(cfg["ai"].get("monthly_limit_usd", 0) or 0),
        "spent": round(usage.month_spend(), 2),
    }


def _clamp(v: Any, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v or 0)))


def providers_get(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Other AI providers as Settings shows them (keys are never sent to the page, only whether one is saved)."""
    out = []
    for pid, p in ai.PROVIDERS.items():
        pc = ai.provider_cfg(cfg, pid)
        out.append({"id": pid, "label": p.label, "pdf": p.pdf, "web": p.web, "needsKey": p.needs_key,
                    "urlEditable": p.url_editable, "example": p.example_model, "baseUrl": pc.get("base_url", ""),
                    "model": pc.get("model", ""), "priceIn": float(pc.get("price_in") or 0),
                    "priceOut": float(pc.get("price_out") or 0), "priceSearch": float(pc.get("price_search") or 0),
                    "maxTokens": int(pc.get("max_tokens") or 0), "hasKey": ai.key_saved(pid)})
    return out


def providers_save(new: dict[str, Any], given: dict[str, Any]) -> list[tuple[str, str]]:
    """Copy provider settings into ``new``; returns (provider, key) pairs to store after the config is saved."""
    keys = []
    for pid, v in (given or {}).items():
        if pid not in ai.PROVIDERS or not isinstance(v, dict):
            continue
        p = ai.PROVIDERS[pid]
        pc = new.setdefault("providers", {}).setdefault(pid, {})
        if p.url_editable:
            url = str(v.get("baseUrl") or "").strip()
            pc["base_url"] = ai.check_url(url) if url else ""
        pc["model"] = ai.check_model(str(v.get("model") or ""))
        pc["price_in"] = round(_clamp(v.get("priceIn"), 0, 1000), 4)
        pc["price_out"] = round(_clamp(v.get("priceOut"), 0, 1000), 4)
        pc["price_search"] = round(_clamp(v.get("priceSearch"), 0, 10), 4)
        pc["max_tokens"] = int(_clamp(v.get("maxTokens"), 0, 1_000_000))
        if str(v.get("apiKey") or "").strip():
            keys.append((pid, str(v["apiKey"])))
    return keys


def settings_save(cfg: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Validate and write config.yaml, allowlist.yaml, client_master.csv and (optionally) the API key."""
    text = str(b["allowlist"])
    try:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise UserFacingError("The do-not-redact list must contain 'patterns', 'context_patterns' and 'words' sections.")
        Allowlist.from_dict(data)
    except yaml.YAMLError as exc:
        raise UserFacingError("The do-not-redact list is not valid YAML. Please check indentation and quotes.") from exc
    rows = [(str(r[0]), str(r[1]), str(r[2])) for r in b["master"] if str(r[0]).strip()]
    new = copy.deepcopy(cfg)
    new["detection"]["redact_officer"] = bool(b["redactOfficer"])
    new["detection"]["propagate_values"] = bool(b["propagate"])
    new["detection"]["accept_threshold"] = round(_clamp(b["acceptThreshold"], 0, 1), 2)
    new["ocr"]["low_confidence_threshold"] = round(_clamp(b["lowConf"], 0.3, 1), 2)
    new["ocr"]["dpi"] = int(_clamp(b["dpi"], 150, 600))
    new["paths"]["output_root"] = str(b["outputRoot"]).strip()
    if b["effort"] in ("low", "medium", "high", "xhigh", "max"):
        new["ai"]["effort"] = b["effort"]
    keys = providers_save(new, b.get("providers") or {})
    if ai.valid_choice(new, str(b["model"])):
        new["ai"]["model"] = b["model"]
    new["ai"]["monthly_limit_usd"] = round(_clamp(b["limit"], 0, 10000), 2)
    new["ai"]["web_search_max_uses"] = int(_clamp(b["webMax"], 0, 20))
    try:
        resolve_path(cfg, "allowlist").write_text(text, encoding="utf-8")
        save_client_master(resolve_path(cfg, "client_master"), rows)
        save_config(new)
        if str(b.get("apiKey") or "").strip():
            ai_client.set_api_key(str(b["apiKey"]))
        for pid, key in keys:
            ai.set_key(pid, key)
    except OSError as exc:
        raise UserFacingError("Settings could not be saved. Check that the Mukhota folder is not read-only.") from exc
    return new


def pick_folder(title: str = "Choose output folder") -> str:
    import tkinter as tk
    from tkinter import filedialog

    from .server import _dialog_lock

    with _dialog_lock:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(parent=root, title=title) or ""
        finally:
            root.destroy()


def open_draft(pdf: Path, cfg: dict[str, Any]) -> Draft:
    return Draft(drafting.prepare(pdf), copy.deepcopy(cfg))
