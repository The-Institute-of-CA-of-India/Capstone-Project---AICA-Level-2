"""Settings: firm profile, reviewers, thresholds, engines, health check and rules versions
(SPEC §10.3 Settings, §12.1)."""

from __future__ import annotations

from html import escape

import streamlit as st
from pydantic import SecretStr, ValidationError

from appealiq import pipeline
from appealiq.config import (
    LOCAL_LLM_PRESETS,
    CloudSettings,
    FirmSettings,
    LMStudioSettings,
    Paths,
    RagSettings,
    Settings,
    save_settings,
)
from appealiq.fmt import inr
from appealiq.outputs.styles import PRIMARY_PRESETS
from appealiq.ui import state, theme

HEALTH_KEY = "health_items"
LOGO_TYPES = ["png", "jpg", "jpeg"]


def _rows(pairs: list[tuple[str, str]]) -> str:
    cells = "".join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in pairs)
    return f'<table class="aiq-kv">{cells}</table>'


def _save(settings: Settings, message: str) -> None:
    save_settings(settings, state.paths().settings_file)
    st.session_state["settings"] = settings
    st.session_state.pop("engine_checks", None)
    theme.render_callout(message, tone="green")


_PRESET_LABELS = {key: f"{name} ({url})" for key, (name, url) in LOCAL_LLM_PRESETS.items()}
_PRESET_LABELS["custom"] = "Custom URL (this computer only)"


def _firm(settings: Settings, paths: Paths) -> None:
    with st.form("firm"):
        st.markdown("**Firm profile** — printed on every report")
        name = st.text_input("Firm name", settings.firm.name, max_chars=120)
        address = st.text_input("Address line", settings.firm.address_line, max_chars=200)
        colours = list(PRIMARY_PRESETS)
        colour = st.selectbox("Report colour", colours,
                              index=colours.index(settings.firm.report_colour)
                              if settings.firm.report_colour in colours else 0)
        logo = st.file_uploader("Logo (PNG or JPG, shown in the report header)", type=LOGO_TYPES)
        remove = st.checkbox("Remove the current logo", disabled=not settings.firm.logo_path)
        if st.form_submit_button("Save firm profile", type="primary"):
            logo_path = None if remove else settings.firm.logo_path
            if logo is not None:
                ext = logo.name.rsplit(".", 1)[-1].lower()
                target = paths.config_dir / f"firm_logo.{ext}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(logo.getvalue())
                logo_path = str(target)
            firm = FirmSettings(name=name.strip() or "Your Firm Name",
                                address_line=address.strip(), logo_path=logo_path,
                                report_colour=colour)
            _save(settings.model_copy(update={"firm": firm}), "Firm profile saved.")
    if settings.firm.logo_path:
        st.caption(f"Logo: {settings.firm.logo_path}")


def _people_and_thresholds(settings: Settings) -> None:
    with st.form("thresholds"):
        st.markdown("**Reviewers, RAG thresholds and materiality**")
        reviewers = st.text_area("Reviewers (one per line)", "\n".join(settings.reviewers),
                                 height=100)
        c1, c2 = st.columns(2)
        red = c1.number_input("Red: due in this many days or less", 0, 60,
                              settings.rag.red_max_days)
        amber = c2.number_input("Amber: due in this many days or less", 1, 120,
                                settings.rag.amber_max_days)
        materiality = st.number_input("Materiality — tax effect at or above which a dismissed "
                                      "issue is recommended for appeal (₹)", 0, 10_00_00_000,
                                      settings.materiality, step=5_000)
        st.caption(f"Materiality: {inr(int(materiality))}")
        if st.form_submit_button("Save", type="primary"):
            try:
                rag = RagSettings(red_max_days=int(red), amber_max_days=int(amber))
            except ValidationError:
                theme.render_error("The amber threshold must be more than the red threshold.",
                                   "Raise the amber threshold or lower the red one, then save.")
                return
            names = [r.strip() for r in reviewers.splitlines() if r.strip()]
            _save(settings.model_copy(update={"reviewers": names, "rag": rag,
                                              "materiality": int(materiality)}),
                  "Reviewers and thresholds saved.")


def _local_llm_form(settings: Settings, paths: Paths) -> None:
    """Local LLM: LM Studio / Ollama preset or a custom localhost URL, model name, test."""
    current = settings.lmstudio
    with st.expander("Local AI (any OpenAI-compatible server on this computer)", expanded=True):
        keys = list(_PRESET_LABELS)
        preset = st.selectbox("Server", keys, index=keys.index(current.preset),
                              format_func=_PRESET_LABELS.__getitem__)
        if preset == "custom":
            url = st.text_input("Server URL", value=current.base_url,
                                help="Only localhost / 127.0.0.1 addresses are accepted.")
        else:
            url = LOCAL_LLM_PRESETS[preset][1]
            st.caption(f"URL: {url}")
        model = st.text_input("Model name", value=current.model,
                              help="Exactly as the server lists it, e.g. gemma-3-12b-it or "
                                   "gemma3:12b. Leave blank to use the first model listed.")
        c1, c2 = st.columns(2)
        timeout = c1.number_input("Timeout per call (s)", 5, 1800, current.timeout_s)
        max_tokens = c2.number_input("Max tokens", 256, 32768, current.max_tokens, step=256)
        extraction = st.checkbox(
            "Also re-read every issue with the AI during the analysis (slow)",
            value=current.ai_extraction,
            help="Off: the Standard engine extracts in seconds and AI notes are generated on "
                 "demand in the Review step.")
        fallback = st.checkbox(
            "When the Standard engine cannot read an order, ask local AI automatically",
            value=current.ai_fallback,
            help="Used only if the order type is unsure or no issue is found. The model points "
                 "at quotes with page and para; every quote is checked against the order, and "
                 "sections, amounts and dates are read by the program. Off: Review & Edit "
                 "offers 'Read with local AI' instead.")
        try:
            new = LMStudioSettings(preset=preset, base_url=url, model=model.strip(),
                                   timeout_s=int(timeout), max_tokens=int(max_tokens),
                                   ai_extraction=extraction, ai_fallback=fallback)
        except ValidationError:
            theme.render_error("The URL must point to this computer.",
                               "Use an address such as http://localhost:1234/v1.")
            return
        b1, b2 = st.columns(2)
        if b1.button("Test connection", use_container_width=True, key="llm_test"):
            with st.spinner("Contacting the local server…"):
                ok, message = pipeline.local_llm_status(new, paths)
            theme.render_callout(message, tone="green" if ok else "amber")
        if b2.button("Save", type="primary", use_container_width=True, key="llm_save"):
            _save(settings.model_copy(update={"lmstudio": new}), "Local AI settings saved.")


def _cloud_form(settings: Settings, paths: Paths) -> None:
    current = settings.cloud
    has_key = bool(current.api_key and current.api_key.get_secret_value())
    with st.expander("Cloud AI (optional — Anthropic API)"):
        st.caption("Used only for cases where you accept the confidentiality warning. The key "
                   "is stored in config/settings.yaml on this computer and is never logged. A "
                   "key in .env (ANTHROPIC_API_KEY) is used if this field is empty.")
        key = st.text_input("API key", type="password", value="",
                            placeholder="Set (hidden) — type a new key to replace it"
                            if has_key else "Not set")
        model = st.text_input("Model", value=current.model)
        b1, b2, b3 = st.columns(3)
        candidate = CloudSettings(model=model.strip() or current.model,
                                  api_key=SecretStr(key.strip()) if key.strip()
                                  else current.api_key)
        if b1.button("Test connection", use_container_width=True, key="cloud_test"):
            with st.spinner("Contacting the cloud service (no document text is sent)…"):
                ok, message = pipeline.cloud_status(
                    settings.model_copy(update={"cloud": candidate}), paths, live=True)
            theme.render_callout(message, tone="green" if ok else "amber")
        if b2.button("Save", type="primary", use_container_width=True, key="cloud_save"):
            _save(settings.model_copy(update={"cloud": candidate}), "Cloud settings saved.")
        if b3.button("Remove key", use_container_width=True, disabled=not has_key,
                     key="cloud_rm"):
            _save(settings.model_copy(update={"cloud": CloudSettings(model=current.model)}),
                  "Cloud API key removed.")


def _health(settings: Settings, paths: Paths) -> None:
    st.subheader("Health check")
    items = st.session_state.get(HEALTH_KEY)
    if items is None or st.button("Run the health check again"):
        with st.spinner("Checking components…"):
            items = pipeline.health_check(paths, settings)
        st.session_state[HEALTH_KEY] = items
    rows = []
    for i in items:
        if i.ok:
            badge = theme.badge_html("OK", "GREEN")
        elif i.optional:
            badge = theme.badge_html("Not available", "AMBER")
        else:
            badge = theme.badge_html("Problem", "RED")
        rows.append([i.name, badge, i.detail])
    theme.render_html(theme.table_html(["Component", "Status", "Detail"], rows, html_cols={1}))
    st.caption("Optional components (OCR, local AI, PDF conversion) degrade gracefully: the app "
               "keeps working without them and says so where it matters.")


def _rules(paths: Paths) -> None:
    st.subheader("Knowledge base (rules/)")
    health = pipeline.rules_health(paths)
    rows = [[f.file, f"v{f.version}" if f.version else "—",
             theme.badge_html("Valid", "GREEN") if f.ok else theme.badge_html("Invalid", "RED"),
             str(f.unverified) if f.ok else f.message] for f in health.files]
    theme.render_html(theme.table_html(["File", "Version", "Status", "Entries verified: false"],
                                       rows, html_cols={2}, numeric={3}))
    if not health.ok:
        theme.render_error("Some rules files could not be loaded: " + "; ".join(health.problems),
                           "Correct the YAML file; the affected steps fail with a notice until "
                           "then.")
    # Shown as text: this section sits inside the Advanced expander (no nested expanders)
    st.markdown(f"**{len(health.unverified)} legal values are marked verified: false** — the "
                "firm must verify them before production use.")
    st.markdown("\n".join(f"- {escape(u.label())}" for u in health.unverified) or "None.")


def render() -> None:
    """Render the Settings page."""
    st.title("Settings")
    settings, paths = state.settings(), state.paths()
    left, right = st.columns(2, gap="large")
    with left:
        _firm(settings, paths)
        _people_and_thresholds(settings)
    with right:
        st.markdown("**Engines**")
        _local_llm_form(settings, paths)
        _cloud_form(settings, paths)
        theme.render_card("Storage", _rows([("Settings file", str(paths.settings_file)),
                                             ("Data folder", str(paths.data_dir))]))
    st.divider()
    # CR-009 C: the knowledge base and the health check are for the administrator
    with st.expander("Advanced (administrator)", expanded=False, icon=":material/build:"):
        st.caption("Rules files, legal values awaiting verification and the component health "
                   "check. Change these only if you maintain AppealIQ for the firm.")
        _health(settings, paths)
        _rules(paths)
