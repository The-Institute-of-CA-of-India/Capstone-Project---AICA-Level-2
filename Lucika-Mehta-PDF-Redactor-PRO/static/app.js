/* PDF Redactor PRO - workstation front end (no external libraries) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") {
      for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith("--")) el.style.setProperty(sk, sv); else el.style[sk] = sv; }
    }
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
};
const fill = (el, ...kids) => { el.replaceChildren(...kids.flat(Infinity).filter(k => k !== null && k !== undefined && k !== false)); return el; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;

const GROUP_COLOURS = { tax: "var(--g-tax)", bank: "var(--g-bank)", names: "var(--g-names)", contact: "var(--g-contact)", visual: "var(--g-visual)", custom: "var(--g-custom)" };
const GROUP_NAMES = { custom: "Added words" };
const SETTINGS_KEY = "redactor.settings.v2";
const UI_KEY = "redactor.ui.v1";
const UI_DEFAULTS = { theme: "light", fs: 1, view: "redacted", outlines: false };
const UI = (() => { try { return { ...UI_DEFAULTS, ...JSON.parse(localStorage.getItem(UI_KEY) || "{}") }; } catch (_) { return { ...UI_DEFAULTS }; } })();
const darkQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
function applyUI() {
  const dark = UI.theme === "dark" || (UI.theme === "system" && darkQuery && darkQuery.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.style.setProperty("--fs", String(UI.fs));
}
function saveUI() { try { localStorage.setItem(UI_KEY, JSON.stringify(UI)); } catch (_) { /* storage blocked */ } applyUI(); }
applyUI();
if (darkQuery && darkQuery.addEventListener) darkQuery.addEventListener("change", () => { if (UI.theme === "system") applyUI(); });

const S = {
  meta: null, settings: null,
  client: { pans: "", dates: "", names: "", mobiles: "", ids: "", passwords: "", words: "", keep: "" },
  picked: [], folder: "", subfolders: true,
  batch: null, current: -1, detail: null,
  view: UI.view, tool: "select", zoom: 1, showMarks: UI.outlines,
  pending: null, baseline: "", selBox: null, revealed: new Set(),
  fileFilter: "all", fileSearch: "", itemSearch: "", tab: "items", addScope: "file",
};

/* ------------------------------------------------------------------ api */
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch (_) { /* not json */ }
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res;
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function toast(msg, err = false) {
  const t = h("div", { class: "toast" + (err ? " err" : "") }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), err ? 7000 : 3200);
}
function status(msg) { $("#status-msg").textContent = msg || ""; }

function modal(title, text, buttons) {
  return new Promise(resolve => {
    const scrim = h("div", { style: { position: "fixed", inset: 0, background: "rgba(15,20,28,.45)", zIndex: 95, display: "flex", alignItems: "center", justifyContent: "center" } });
    const card = h("div", { class: "prog-card", role: "dialog", "aria-modal": "true" },
      h("h3", {}, title), h("p", { style: { color: "var(--text-2)", margin: "6px 0 16px" } }, text),
      h("div", { style: { display: "flex", gap: "8px", justifyContent: "flex-end" } },
        buttons.map(b => h("button", { class: "btn " + (b.cls || ""), onclick: () => { scrim.remove(); resolve(b.value); } }, b.label))));
    scrim.append(card); document.body.append(scrim);
    $("button.primary", card)?.focus();
  });
}

/* ------------------------------------------------------------- settings */
function defaultSettings(meta) {
  return {
    rules: meta.rules.filter(r => r.default).map(r => r.key),
    profile: "auto", style: "label", ocr_mode: meta.ocr ? "auto" : "off", ocr_dpi: 300, ocr_langs: ["eng"],
    verify_scans: true, add_text_layer: true, propagate: true, protect_itba_din: true,
    anonymise_names: false, scrub_metadata: true, workers: meta.default_workers,
  };
}
function loadSettings() {
  const d = defaultSettings(S.meta);
  try { Object.assign(d, JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}")); } catch (_) { /* storage blocked */ }
  d.ocr_langs = (d.ocr_langs || ["eng"]).filter(l => S.meta.langs.includes(l));
  if (!d.ocr_langs.length) d.ocr_langs = ["eng"];
  if (!S.meta.ocr) d.ocr_mode = "off";
  S.settings = d;
}
function saveSettings() {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(S.settings)); } catch (_) { /* storage blocked */ }
  renderComposerSummary();
}
const lines = t => (t || "").split(/\r?\n/).map(x => x.trim()).filter(Boolean);
const many = t => (t || "").split(/[\r\n,;]+/).map(x => x.trim()).filter(Boolean);
function runOptions() {
  const c = S.client;
  return {
    ...S.settings,
    custom_terms: lines(c.words), keep_terms: lines(c.keep), passwords: many(c.passwords),
    password_hints: { pans: many(c.pans), dates: many(c.dates), names: many(c.names), mobiles: many(c.mobiles), ids: many(c.ids) },
  };
}

const PROFILE_OPTS = [["auto", "Detect per file"], ["bank", "Bank statements"], ["notice", "IT notices and orders"], ["kyc", "KYC documents"], ["asis", "Use my selection exactly"]];

function renderDrawer() {
  const st = S.settings, m = S.meta;
  const tog = (label, key, hint) => h("label", { class: "tog" },
    h("input", { type: "checkbox", checked: st[key], onchange: e => { st[key] = e.target.checked; saveSettings(); } }),
    h("span", {}, label, hint ? h("div", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))" } }, hint) : null));
  const groups = m.groups.map(g => {
    const rules = m.rules.filter(r => r.group === g.key);
    const on = rules.filter(r => st.rules.includes(r.key)).length;
    return h("details", { class: "sect", open: g.key === "names" ? true : null },
      h("summary", {}, h("span", {}, g.label, h("span", { class: "muted", style: { fontFamily: "var(--body)", fontSize: "calc(12px * var(--fs, 1))", marginLeft: "6px" } }, `${on} of ${rules.length}`))),
      h("div", {}, rules.map(r => h("label", { class: "tog", style: { "--gc": GROUP_COLOURS[g.key] } },
        h("input", { type: "checkbox", checked: st.rules.includes(r.key), onchange: e => {
          st.rules = e.target.checked ? [...new Set([...st.rules, r.key])] : st.rules.filter(k => k !== r.key);
          saveSettings(); renderDrawer();
        } }),
        h("span", { class: "sw" }), h("span", {}, r.label)))));
  });
  const d = $("#drawer");
  fill(d, 
    h("div", { class: "drawer-h" }, "Settings", h("button", { class: "btn small", onclick: closeDrawer }, "Done")),
    h("div", { class: "drawer-b" },
      appearanceSection(),
      h("div", { class: "sect-h" }, "Redaction"),
      h("div", { class: "pad", style: { paddingTop: "4px" } },
        h("div", { class: "field" }, h("label", {}, "Document type"),
          h("select", { class: "inp", onchange: e => { st.profile = e.target.value; saveSettings(); } },
            PROFILE_OPTS.map(([v, l]) => h("option", { value: v, selected: st.profile === v }, l))),
          h("span", { class: "hint" }, "Detection adjusts each file: notices keep reference numbers visible; KYC copies also get photos and signatures blacked out.")),
        h("div", { class: "field" }, h("label", {}, "How redacted items appear"),
          h("div", { class: "seg" },
            h("button", { class: st.style === "label" ? "on" : "", onclick: () => { st.style = "label"; saveSettings(); renderDrawer(); } }, "Labelled boxes [ACCT-1]"),
            h("button", { class: st.style === "black" ? "on" : "", onclick: () => { st.style = "black"; saveSettings(); renderDrawer(); } }, "Plain black boxes")),
          h("span", { class: "hint" }, "Labels stay the same for the same value across every file, so the AI can follow an account or party without seeing it."))),
      h("div", { class: "sect-h" }, "What to redact"),
      groups,
      h("details", { class: "sect", open: true }, h("summary", {}, "Scanned pages"),
        h("div", {},
          h("div", { style: { marginBottom: "8px" } }, ocrCard(true)),
          h("div", { class: "grid2" },
            h("div", { class: "field" }, h("label", {}, "Read scans with OCR"),
              h("select", { class: "inp", disabled: !m.ocr, onchange: e => { st.ocr_mode = e.target.value; saveSettings(); } },
                [["auto", "Scanned pages only"], ["all", "Every page with an image"], ["off", "Off"]].map(([v, l]) => h("option", { value: v, selected: st.ocr_mode === v }, l)))),
            h("div", { class: "field" }, h("label", {}, "OCR quality"),
              h("select", { class: "inp", disabled: !m.ocr, onchange: e => { st.ocr_dpi = +e.target.value; saveSettings(); } },
                [200, 300, 400].map(v => h("option", { value: v, selected: st.ocr_dpi === v }, `${v} dpi`))))),
          h("div", { class: "field" }, h("label", {}, "Languages"),
            h("div", { style: { display: "flex", gap: "14px" } }, ["eng", "hin", "mar"].map(l => {
              const has = m.langs.includes(l);
              return h("label", { class: "tog", title: has ? "" : "Install this language pack with Tesseract" },
                h("input", { type: "checkbox", disabled: !has, checked: st.ocr_langs.includes(l), onchange: e => {
                  st.ocr_langs = e.target.checked ? [...new Set([...st.ocr_langs, l])] : st.ocr_langs.filter(x => x !== l);
                  if (!st.ocr_langs.length) st.ocr_langs = ["eng"]; saveSettings();
                } }), { eng: "English", hin: "Hindi", mar: "Marathi" }[l] + (has ? "" : " (not installed)"));
            }))),
          tog("Re-check scanned pages after redaction", "verify_scans"),
          tog("Add searchable text to scanned pages", "add_text_layer", "The AI reads redacted scans as text, which is more accurate."))),
      h("details", { class: "sect", open: true }, h("summary", {}, "Batch"),
        h("div", {},
          tog("Redact a value found in one file in every file", "propagate"),
          tog("Keep income-tax notice DIN visible", "protect_itba_din"),
          tog("Rename outputs Document_01, 02 …", "anonymise_names", "Use when file names carry client names."),
          tog("Remove metadata, attachments, links and form data", "scrub_metadata"),
          h("div", { class: "field", style: { marginTop: "6px" } }, h("label", {}, `Processor cores to use (of ${m.cpus})`),
            h("input", { class: "inp", type: "number", min: 1, max: m.cpus, value: st.workers, style: { width: "90px" },
              onchange: e => { st.workers = Math.max(1, Math.min(m.cpus, +e.target.value || 1)); saveSettings(); } }))))),
    S.meta.mode === "browser" && S.meta.frozen ? h("div", { class: "pad" }, h("button", { class: "btn block", onclick: async () => {
      await post("/api/quit", {}).catch(() => {}); document.body.innerHTML = "<p style='padding:40px;font:16px sans-serif'>PDF Redactor PRO has closed. You can close this tab.</p>";
    } }, "Quit PDF Redactor PRO")) : null,
    h("div", { class: "drawer-f" }, "Appearance applies at once. Redaction settings apply to the next batch. Both are remembered on this computer; passwords and client details are never saved."));
}
function appearanceSection() {
  const seg = (key, opts, after) => h("div", { class: "seg" }, opts.map(([v, l]) =>
    h("button", { class: UI[key] === v ? "on" : "", onclick: () => { UI[key] = v; saveUI(); if (after) after(); renderDrawer(); } }, l)));
  const fsSet = v => { UI.fs = Math.round(Math.max(0.85, Math.min(1.3, v)) * 100) / 100; saveUI(); renderDrawer(); if (S.detail) renderViewer(); };
  return h("div", {},
    h("div", { class: "sect-h" }, "Appearance"),
    h("div", { class: "pad", style: { paddingTop: "4px" } },
      h("div", { class: "field" }, h("label", {}, "Theme"), seg("theme", [["light", "Light"], ["dark", "Dark"], ["system", "Match Windows"]])),
      h("div", { class: "field" }, h("label", {}, "Text size"),
        h("div", { class: "fs-ctl" },
          h("button", { title: "Smaller text", "aria-label": "Smaller text", onclick: () => fsSet(UI.fs - 0.05) }, "A−"),
          h("span", { class: "v" }, `${Math.round(UI.fs * 100)}%`),
          h("button", { title: "Larger text", "aria-label": "Larger text", onclick: () => fsSet(UI.fs + 0.05) }, "A+"),
          h("button", { title: "Reset", style: { width: "auto", padding: "0 8px", fontWeight: 500 }, onclick: () => fsSet(1) }, "Reset"))),
      h("div", { class: "field" }, h("label", {}, "Open files in"),
        seg("view", [["redacted", "Redacted"], ["original", "Original"], ["split", "Side by side"]], () => { if (S.detail) setView(UI.view); })),
      h("label", { class: "tog" }, h("input", { type: "checkbox", checked: UI.outlines, onchange: e => {
        UI.outlines = e.target.checked; saveUI(); S.showMarks = UI.outlines; if (S.detail) renderViewer(); } }), "Show redaction outlines by default"),
      h("button", { class: "btn small", style: { marginTop: "6px" }, onclick: () => {
        Object.assign(UI, UI_DEFAULTS); saveUI();
        S.settings = defaultSettings(S.meta); saveSettings(); renderDrawer(); if (S.detail) renderViewer();
        toast("Settings restored to defaults");
      } }, "Restore all defaults")));
}
function openDrawer() { renderDrawer(); $("#drawer").classList.remove("closed"); $("#scrim").classList.remove("hidden"); }
function closeDrawer() { $("#drawer").classList.add("closed"); $("#scrim").classList.add("hidden"); }

/* ------------------------------------------------------------------ OCR */
const LANG_NAMES = { eng: "English", hin: "Hindi", mar: "Marathi" };
async function checkOcr(folder) {
  try {
    const r = await post("/api/ocr/check", folder ? { folder } : {});
    Object.assign(S.meta, { ocr: r.ocr, langs: r.langs, tessdata: r.tessdata });
    if (r.ocr) {
      if (S.settings.ocr_mode === "off") S.settings.ocr_mode = "auto";
      saveSettings();
      toast("OCR is ready: " + r.langs.map(l => LANG_NAMES[l] || l).join(", "));
    } else toast("Tesseract OCR was still not found. Check the installation folder.", true);
  } catch (e) { toast(e.message, true); }
  if (!S.batch) renderComposer();
  renderDrawer();
}
function ocrCard(compact = false) {
  const m = S.meta;
  if (m.ocr) {
    const missing = ["hin", "mar"].filter(l => !m.langs.includes(l));
    return h("div", { class: "ocr-card ok" }, h("span", { class: "ico" }, "✓"),
      h("div", {}, h("strong", {}, "OCR is ready"), h("span", { class: "muted" }, " for scanned pages in " + m.langs.map(l => LANG_NAMES[l] || l).join(", ")),
        missing.length ? h("div", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))" } }, `To add ${missing.map(l => LANG_NAMES[l]).join(" and ")}, run the Tesseract installer again and tick them under Additional language data, then press Check again.`) : null,
        !compact ? h("div", { style: { marginTop: "4px" } }, h("button", { class: "btn small", onclick: () => checkOcr() }, "Check again")) : null));
  }
  const win = m.platform === "nt";
  const folder = h("input", { class: "inp", placeholder: win ? "C:\\Program Files\\Tesseract-OCR" : "/opt/homebrew/share/tessdata", style: { flex: 1 } });
  return h("div", { class: "ocr-card alert warn", style: { display: "flex" } }, h("span", { class: "ico" }, "!"),
    h("div", { style: { flex: 1 } },
      h("strong", {}, "Scanned pages can't be read yet"),
      h("div", {}, "OCR needs Tesseract, a free program installed once:"),
      win ? h("ol", {},
        h("li", {}, "Download the Windows installer from ", h("a", { href: "https://github.com/UB-Mannheim/tesseract/wiki", target: "_blank", rel: "noopener" }, "the UB Mannheim Tesseract page"), "."),
        h("li", {}, "Install it in the default folder. On Choose Components, open Additional language data and tick Hindi and Marathi."),
        h("li", {}, "Press Check again. There is no need to restart."))
        : h("ol", {}, h("li", {}, "In Terminal run: brew install tesseract tesseract-lang"), h("li", {}, "Press Check again.")),
      h("div", { style: { display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" } },
        h("button", { class: "btn small primary", onclick: () => checkOcr() }, "Check again")),
      h("details", { style: { marginTop: "6px" } }, h("summary", { style: { cursor: "pointer", fontSize: "calc(12px * var(--fs, 1))" } }, "Installed in a different folder?"),
        h("div", { style: { display: "flex", gap: "6px", marginTop: "6px" } }, folder,
          h("button", { class: "btn small", onclick: () => checkOcr(folder.value) }, "Use this folder")))));
}

/* ------------------------------------------------------------- composer */
function renderComposer() {
  const c = S.client;
  const one = (label, key, ph) => h("div", { class: "field" }, h("label", { for: "c-" + key }, label),
    h("input", { class: "inp", id: "c-" + key, placeholder: ph, value: c[key], oninput: e => { c[key] = e.target.value; } }));
  const ta = (label, key, ph, rows = 2, hint) => h("div", { class: "field" }, h("label", { for: "c-" + key }, label),
    h("textarea", { class: "inp", id: "c-" + key, rows, placeholder: ph, oninput: e => { c[key] = e.target.value; } }, c[key]),
    hint ? h("span", { class: "hint" }, hint) : null);
  const warn = [];
  if (!S.meta.self_test) warn.push(h("div", { class: "alert err" }, "The installed PDF library moves neighbouring text when redacting. Run the launcher again so that the supported version is installed."));

  fill($("#composer"), h("div", { class: "compose-wrap" },
    h("h1", {}, "Prepare documents for AI review"),
    h("p", { class: "lede" }, "Add bank statements, notices, KYC copies and working files. Identifiers are removed on this computer before anything leaves it."),
    warn.length ? h("div", { style: { gridColumn: "1 / -1" } }, warn) : null,
    h("section", { class: "panel" },
      h("div", { class: "panel-h" }, "Documents", h("span", { class: "muted", style: { fontFamily: "var(--body)", fontSize: "calc(12px * var(--fs, 1))" } }, "PDF, scans, Excel, CSV, Word")),
      h("div", { class: "panel-b" },
        h("div", { id: "drop" },
          h("div", { class: "drop-bars", "aria-hidden": "true" }, h("i"), h("i"), h("i"), h("i")),
          h("strong", {}, "Drop files here"),
          h("span", { class: "muted" }, "or"),
          h("button", { class: "btn", onclick: () => $("#file-input").click() }, "Choose files")),
        h("div", { id: "picked" }),
        h("div", { class: "or" }, "or a whole folder"),
        h("div", { class: "field" }, h("label", { for: "folder-in" }, "Folder path"),
          h("input", { class: "inp", id: "folder-in", placeholder: "D:\\Clients\\Sample Traders\\AY 2024-25", value: S.folder,
            oninput: e => { S.folder = e.target.value; renderStart(); } })),
        h("label", { class: "tog" }, h("input", { type: "checkbox", checked: S.subfolders, onchange: e => { S.subfolders = e.target.checked; } }),
          "Include sub-folders; redacted copies are saved next to the folder with the same structure"),
        h("div", { style: { marginTop: "12px" } }, ocrCard()))),
    h("section", { class: "panel" },
      h("div", { class: "panel-h" }, "Client details", h("span", { class: "muted", style: { fontFamily: "var(--body)", fontSize: "calc(12px * var(--fs, 1))" } }, "Used for this batch only")),
      h("div", { class: "panel-b", style: { paddingBottom: "4px" } },
        h("div", { class: "muted", style: { fontSize: "calc(12px * var(--fs, 1))", marginBottom: "8px" } }, "Locked statements, 26AS, AIS and ITR-V files are opened with common password formats built from these details."),
        h("div", { class: "grid2" }, one("PAN", "pans", "AAKCS1234F"), one("Date of birth or incorporation", "dates", "15/04/1980")),
        h("div", { class: "grid3" }, one("Name", "names", "Sample Traders"), one("Mobile", "mobiles", ""), one("Customer ID", "ids", "")),
        one("Passwords", "passwords", "Exact passwords, if you know them"),
        h("div", { class: "hint", style: { marginTop: "-4px", marginBottom: "8px" } }, "Separate several values with commas.")),
      h("details", { class: "sect", open: true }, h("summary", {}, "Words"),
        h("div", {},
          ta("Also redact", "words", "Client names, addresses, counterparties: one per line", 2),
          ta("Never redact", "keep", "Exact values to leave visible: one per line", 1)))),
    h("div", { class: "start-row" },
      h("div", { class: "summary-line", id: "set-summary" }),
      h("button", { class: "btn small", onclick: openDrawer }, "Change"),
      h("div", { class: "grow" }),
      h("button", { class: "btn accent big", id: "btn-start", onclick: startRun }, "Redact")),
    h("div", { class: "contact-strip" }, h("img", { src: "/static/brand/logo.svg", alt: "" }),
      h("span", { class: "grow" }, `${S.meta.app} is designed and maintained by ${S.meta.author}. For help, feedback or feature requests, get in touch.`),
      h("button", { class: "btn small", id: "btn-contact-strip", onclick: e => { e.stopPropagation(); contactPop(e.currentTarget); } }, "Contact us"))));
  wireDrop(); renderPicked(); renderComposerSummary(); renderStart();
}
function renderComposerSummary() {
  const el = $("#set-summary"); if (!el || !S.settings) return;
  const st = S.settings;
  fill(el, 
    h("span", { class: "s" }, PROFILE_OPTS.find(p => p[0] === st.profile)?.[1] || st.profile),
    h("span", { class: "s" }, st.style === "label" ? "Labelled boxes" : "Black boxes"),
    h("span", { class: "s" }, plural(st.rules.length, "item type")),
    h("span", { class: "s" }, st.ocr_mode === "off" ? "No OCR" : "OCR " + st.ocr_langs.join("+")),
    st.propagate ? h("span", { class: "s" }, "Batch-wide values") : null);
}
function renderPicked() {
  const el = $("#picked"); if (!el) return;
  fill(el, ...S.picked.map((f, i) => h("span", { class: "pchip", title: f.name }, h("span", {}, f.name),
    h("button", { "aria-label": "Remove " + f.name, onclick: () => { S.picked.splice(i, 1); renderPicked(); renderStart(); } }, "×"))));
}
function renderStart() {
  const b = $("#btn-start"); if (!b) return;
  if (S.picked.length) { b.textContent = `Redact ${plural(S.picked.length, "file")}`; b.disabled = false; }
  else if (S.folder.trim()) { b.textContent = "Redact the folder"; b.disabled = false; }
  else { b.textContent = "Redact"; b.disabled = true; }
}
function addFiles(list) {
  const ok = S.meta.extensions;
  let skipped = 0;
  for (const f of list) {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ok.includes(ext)) { skipped++; continue; }
    if (!S.picked.some(p => p.name === f.name && p.size === f.size)) S.picked.push(f);
  }
  if (skipped) toast(`${plural(skipped, "file")} skipped: unsupported type`);
  renderPicked(); renderStart();
}
function wireDrop() {
  const d = $("#drop");
  ["dragenter", "dragover"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => d.addEventListener(ev, e => { e.preventDefault(); d.classList.remove("over"); }));
  d.addEventListener("drop", e => addFiles(e.dataTransfer.files));
}

/* ----------------------------------------------------------- running */
async function startRun() {
  const opts = runOptions();
  if (!opts.rules.length && !opts.custom_terms.length) { toast("Choose at least one item type in Settings.", true); return; }
  try {
    if (S.picked.length) {
      const fd = new FormData();
      S.picked.forEach(f => fd.append("files", f, f.name));
      fd.append("options", JSON.stringify(opts));
      await api("/api/run", { method: "POST", body: fd });
    } else {
      await post("/api/run-folder", { folder: S.folder, subfolders: S.subfolders, options: opts });
    }
  } catch (e) { toast(e.message, true); return; }
  await watchJob("Reading files");
  S.current = -1; S.picked = [];
  await loadBatch(0);
}
function watchJob(title) {
  $("#progress").classList.remove("hidden");
  $("#prog-stage").textContent = title; $("#prog-file").textContent = ""; $("#prog-bar").style.width = "0%"; $("#prog-count").textContent = "";
  return new Promise(resolve => {
    const tick = async () => {
      let j;
      try { j = await api("/api/progress"); } catch (_) { setTimeout(tick, 600); return; }
      if (j.total) {
        const share = j.stage === "Reading" ? 0 : (j.stage === "Redacting" ? 0.5 : 0);
        const span = j.stage === "Re-applying" ? 1 : 0.5;
        $("#prog-bar").style.width = `${Math.round((share + span * j.done / j.total) * 100)}%`;
        $("#prog-stage").textContent = { Reading: "Reading files", Redacting: "Redacting", "Re-applying": "Re-applying to every file" }[j.stage] || j.stage;
        $("#prog-file").textContent = j.name || "";
        $("#prog-count").textContent = `${j.done} of ${j.total}`;
      }
      if (j.running) { setTimeout(tick, 350); return; }
      $("#progress").classList.add("hidden");
      if (j.error) toast(j.error, true);
      resolve(j);
    };
    setTimeout(tick, 250);
  });
}

/* ------------------------------------------------------------- batch */
async function loadBatch(select) {
  try { S.batch = await api("/api/batch"); } catch (_) { S.batch = null; }
  const has = !!S.batch;
  $("#app").classList.toggle("no-batch", !has);
  $("#composer").classList.toggle("hidden", has);
  $("#workspace").classList.toggle("hidden", !has);
  ["#btn-new", "#btn-records", "#btn-download"].forEach(s => $(s).classList.toggle("hidden", !has));
  renderTopStats();
  if (!has) { renderComposer(); return; }
  renderFiles();
  const target = select ?? (S.current >= 0 ? S.current : 0);
  await selectFile(Math.min(target, S.batch.files.length - 1), true);
}
function renderTopStats() {
  const el = $("#top-stats"); const t = S.batch?.totals;
  if (!t) { fill(el, ); return; }
  fill(el, 
    h("span", { class: "chip" }, h("b", {}, t.redacted), `of ${t.files} files redacted`),
    h("span", { class: "chip" }, h("b", {}, t.items), "items"),
    h("span", { class: "chip" + (t.attention ? " warn" : "") }, h("b", {}, t.attention), "need a look"));
}
const typeTag = f => ({ pdf: "PDF", xlsx: "XLS", xls: "XLS", csv: "CSV", docx: "DOC" }[f.kind] || "FILE");
function needsLook(f) { return f.status !== "ok" || f.recheck.state === "warn"; }
function renderFiles() {
  const q = S.fileSearch.toLowerCase();
  const files = S.batch.files.filter(f =>
    (!q || f.name.toLowerCase().includes(q)) &&
    (S.fileFilter === "all" || (S.fileFilter === "attention" && needsLook(f)) || (S.fileFilter === "edited" && f.edited)));
  $("#file-count").textContent = S.batch.files.length;
  fill($("#file-list"), ...files.map(f => {
    const dot = f.status === "locked" || f.status === "error" ? "err" : (f.recheck.state === "warn" || f.status === "no_findings" ? "warn" : (f.recheck.state === "ok" ? "ok" : "none"));
    const meta = [f.profile_label, f.kind === "pdf" ? plural(f.pages, "page") : null, f.ocr_pages ? `${f.ocr_pages} OCR` : null].filter(Boolean);
    return h("div", { class: "frow" + (f.index === S.current ? " on" : ""), role: "option", "aria-selected": f.index === S.current,
      title: `${f.name}\n${f.status_text}${f.message ? "\n" + f.message : ""}`, onclick: () => selectFile(f.index) },
      h("span", { class: "ftype", "data-t": typeTag(f) }),
      h("span", { class: "fname" }, f.name),
      h("span", { class: "fstat" }, h("span", { class: "badge" }, f.items), h("span", {}, f.edited ? h("span", { class: "edited" }, "edited ") : null, h("span", { class: "dot " + dot }))),
      h("span", { class: "fmeta" }, meta.map((m, i) => h("span", {}, m))));
  }));
  if (!files.length) $("#file-list").append(h("div", { class: "empty-note" }, "No files match."));
}

/* -------------------------------------------------------- file + pending */
function pendingFromDetail(d) {
  return {
    keep: new Set(d.findings.filter(f => f.state === "kept-file").map(f => f.value)),
    terms: [...d.terms],
    boxes: d.manual.map(m => ({ page: m.page, box: m.box, saved: true })),
  };
}
const sig = p => JSON.stringify([[...p.keep].sort(), p.terms, p.boxes.map(b => [b.page, b.box.map(v => +v.toFixed(4))])]);
const dirty = () => S.pending && sig(S.pending) !== S.baseline;

async function confirmLeave() {
  if (!dirty()) return true;
  const v = await modal("Apply your changes?", `You have changes on ${S.detail.name} that are not applied yet.`,
    [{ label: "Stay", value: "stay" }, { label: "Discard", value: "discard" }, { label: "Apply", value: "apply", cls: "primary" }]);
  if (v === "stay") return false;
  if (v === "apply") await applyPending();
  return true;
}
async function selectFile(i, force = false) {
  if (!force && i === S.current) return;
  if (!force && !(await confirmLeave())) return;
  S.current = i; S.selBox = null;
  try { S.detail = await api(`/api/file/${i}`); } catch (e) { toast(e.message, true); return; }
  S.pending = pendingFromDetail(S.detail); S.baseline = sig(S.pending);
  $$(".frow").forEach(r => r.classList.remove("on"));
  renderFiles(); renderWorkspace();
}
function renderWorkspace() {
  const d = S.detail;
  const isPdf = d.kind === "pdf" && d.pages > 0;
  $$("#toolbar [data-view], #toolbar [data-tool], #btn-marks, #pg-prev, #pg-next, #z-in, #z-out, #z-fit").forEach(b => b.disabled = !isPdf);
  $("#pg-in").disabled = !isPdf;
  $("#pg-total").textContent = isPdf ? `of ${d.pages}` : "";
  renderViewer(); renderItems(); renderAdd(); renderDetails(); renderPending();
}
function renderPending() {
  const on = dirty();
  $("#pending").classList.toggle("hidden", !on);
  if (!on) return;
  const base = pendingFromDetail(S.detail);
  const unred = [...S.pending.keep].filter(v => !base.keep.has(v)).length;
  const rered = [...base.keep].filter(v => !S.pending.keep.has(v)).length;
  const nb = S.pending.boxes.filter(b => !b.saved).length;
  const rb = base.boxes.length - S.pending.boxes.filter(b => b.saved).length;
  const nt = S.pending.terms.filter(t => !base.terms.includes(t)).length;
  const rt = base.terms.filter(t => !S.pending.terms.includes(t)).length;
  const parts = [];
  if (nb) parts.push(`${plural(nb, "new box", "new boxes")}`);
  if (rb) parts.push(`${plural(rb, "box", "boxes")} removed`);
  if (unred) parts.push(`${plural(unred, "item")} left visible`);
  if (rered) parts.push(`${plural(rered, "item")} redacted again`);
  if (nt) parts.push(`${plural(nt, "word")} added`);
  if (rt) parts.push(`${plural(rt, "word")} removed`);
  $("#pending-text").textContent = "Not applied yet: " + parts.join(", ");
}
async function applyPending() {
  const p = S.pending;
  try {
    status("Applying…");
    S.detail = await post(`/api/file/${S.current}/apply`, {
      keep_values: [...p.keep], terms: p.terms, boxes: p.boxes.map(b => ({ page: b.page, box: b.box })),
    });
  } catch (e) { toast(e.message, true); status(""); return; }
  S.pending = pendingFromDetail(S.detail); S.baseline = sig(S.pending); S.selBox = null;
  imgBust++;
  status(""); toast(`Applied to ${S.detail.name}`);
  const keepScroll = $("#viewer").scrollTop;
  try { S.batch = await api("/api/batch"); renderTopStats(); renderFiles(); } catch (_) { /* keep going */ }
  renderWorkspace(); $("#viewer").scrollTop = keepScroll;
}
function discardPending() { S.pending = pendingFromDetail(S.detail); S.selBox = null; refreshMarks(); renderItems(); renderAdd(); renderPending(); }
function changed() { refreshMarks(); renderItems(); renderAdd(); renderPending(); }

/* --------------------------------------------------------------- viewer */
let imgBust = 0, observer = null;
function pageScale(pw) {
  const v = $("#viewer");
  const avail = v.clientWidth - 56 - (S.view === "split" ? 18 : 0);
  const per = S.view === "split" ? avail / 2 : avail;
  const maxW = Math.min(per, S.view === "split" ? 1100 : 1500);
  return (maxW / pw) * S.zoom;
}
function markState(f) {
  const k = S.pending.keep.has(f.value);
  if (f.state === "redacted") return k ? "pending-keep" : "redacted";
  if (f.state === "kept-file") return k ? "kept" : "pending-redact";
  return "kept";       // kept-batch: changed from the Items menu
}
function renderViewer() {
  const v = $("#viewer"), d = S.detail;
  v.classList.toggle("draw", S.tool === "draw");
  v.classList.toggle("show-marks", S.showMarks);
  $$("#toolbar [data-view]").forEach(b => b.classList.toggle("on", b.dataset.view === S.view));
  $$("#toolbar [data-tool]").forEach(b => b.classList.toggle("on", b.dataset.tool === S.tool));
  $("#btn-marks").classList.toggle("on", S.showMarks);
  if (observer) observer.disconnect();
  if (d.kind !== "pdf" || !d.pages) {
    if (d.status === "locked" || d.status === "error") {
      fill(v, h("div", { class: "sheet", style: { minHeight: "auto" } }, h("h3", { style: { fontFamily: "var(--head)", fontWeight: 500, marginTop: 0 } }, d.status_text), d.message,
        d.status === "locked" ? h("p", {}, "Start a new batch with the client's PAN and date of birth, or the password, to open it.") : null));
    } else {
      const html = esc(d.text || "(no text)").replace(/(\[[A-Z]+-\d+\]|\[[A-Z]+\]|█+)/g, '<span class="rd">$1</span>');
      fill(v, h("div", { class: "sheet", html }));
    }
    $("#z-val").textContent = "—"; $("#pg-in").value = "";
    return;
  }
  const pages = h("div", { class: "pages" });
  observer = new IntersectionObserver(ents => ents.forEach(e => { if (e.isIntersecting) loadImg(e.target); }), { root: v, rootMargin: "600px" });
  d.page_sizes.forEach(([pw, ph], idx) => {
    const p = idx + 1, sc = pageScale(pw);
    const W = Math.round(pw * sc), H = Math.round(ph * sc);
    const mk = which => {
      const pg = h("div", { class: `pg view-${which}`, "data-page": p, "data-which": which, style: { width: W + "px", height: H + "px" } },
        h("span", { class: "pg-num" }, `Page ${p}`),
        S.view === "split" ? h("span", { class: "pg-cap" }, which === "original" ? "Original" : "Redacted") : null,
        h("img", { alt: `Page ${p} ${which}`, "data-w": W }),
        h("div", { class: "pg-overlay", "data-page": p }));
      observer.observe(pg);
      return pg;
    };
    if (S.view === "split") pages.append(h("div", { class: "prow" }, mk("original"), mk("redacted")));
    else pages.append(mk(S.view));
  });
  fill(v, pages);
  $("#z-val").textContent = `${Math.round(S.zoom * 100)}%`;
  refreshMarks(); updatePageNo();
}
function loadImg(pg) {
  const img = $("img", pg);
  const dpr = window.devicePixelRatio || 1;
  const pw = S.detail.page_sizes[+pg.dataset.page - 1][0];
  const dpi = Math.max(60, Math.min(240, Math.round((+img.dataset.w / pw) * 72 * dpr / 20) * 20));
  const src = `/api/file/${S.current}/page/${pg.dataset.page}?which=${pg.dataset.which}&dpi=${dpi}&v=${imgBust}`;
  if (img.getAttribute("src") !== src) img.src = src;
}
function refreshMarks() {
  if (!S.detail || S.detail.kind !== "pdf") return;
  const q = S.itemSearch.toLowerCase();
  $$(".pg-overlay").forEach(ov => {
    const p = +ov.dataset.page;
    fill(ov, );
    S.detail.findings.forEach(f => f.boxes.forEach(b => {
      if (b.page !== p) return;
      const [x0, y0, x1, y1] = b.box, st = markState(f);
      const m = h("div", { class: `mark ${st}`, "data-fid": f.id,
        title: `${f.type}${f.label ? " [" + f.label + "]" : ""}\n${st === "redacted" || st === "pending-redact" ? "Click to leave visible" : "Click to redact"}`,
        style: { left: x0 * 100 + "%", top: y0 * 100 + "%", width: (x1 - x0) * 100 + "%", height: (y1 - y0) * 100 + "%", "--gc": GROUP_COLOURS[f.group] || GROUP_COLOURS.custom } },
        h("span", { class: "tag" }, f.label || f.type));
      m.style.setProperty("--gc", GROUP_COLOURS[f.group] || GROUP_COLOURS.custom);
      m.addEventListener("click", e => { if (S.tool !== "select") return; e.stopPropagation(); toggleKeep(f.value); });
      m.addEventListener("mouseenter", () => hiRow(f.id, true));
      m.addEventListener("mouseleave", () => hiRow(f.id, false));
      if (q && !(f.value + f.type + f.label).toLowerCase().includes(q)) m.style.opacity = .25;
      ov.append(m);
    }));
    S.pending.boxes.forEach((b, j) => {
      if (b.page !== p) return;
      const [x0, y0, x1, y1] = b.box;
      const el = h("div", { class: "mbox" + (b.saved ? " saved" : "") + (S.selBox === j ? " sel" : ""), title: b.saved ? "Your box (applied). Click to select, Delete to remove." : "New box (not applied yet)",
        style: { left: x0 * 100 + "%", top: y0 * 100 + "%", width: (x1 - x0) * 100 + "%", height: (y1 - y0) * 100 + "%" } },
        h("button", { class: "x", title: "Remove box", onclick: e => { e.stopPropagation(); removeBox(j); } }, "×"));
      el.addEventListener("mousedown", e => { if (S.tool === "select") { e.stopPropagation(); S.selBox = j; refreshMarks(); } });
      ov.append(el);
    });
  });
}
function toggleKeep(value) {
  if (S.pending.keep.has(value)) S.pending.keep.delete(value); else S.pending.keep.add(value);
  changed();
}
function removeBox(j) { S.pending.boxes.splice(j, 1); S.selBox = null; changed(); }
function hiRow(fid, on) { const r = $(`.irow[data-fid="${fid}"]`); if (r) r.style.background = on ? "var(--manila-soft)" : ""; }
function flashFinding(f) {
  const first = f.boxes[0];
  if (!first) return;
  const pg = $(`.pg[data-page="${first.page}"]`);
  const v = $("#viewer");
  if (pg) {
    const top = pg.offsetTop + first.box[1] * pg.offsetHeight - v.clientHeight / 3;
    v.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }
  setTimeout(() => {
    $$(`.mark[data-fid="${f.id}"]`).forEach(m => { m.classList.add("flash"); setTimeout(() => m.classList.remove("flash"), 1400); });
  }, 250);
}

/* drawing */
let drawState = null;
function overlayFromEvent(e) { return e.target.closest(".pg-overlay"); }
function startDraw(e) {
  if (S.tool !== "draw" || e.button !== 0) return;
  const ov = overlayFromEvent(e); if (!ov) return;
  e.preventDefault();
  const r = ov.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
  const box = h("div", { class: "drawing" });
  ov.append(box);
  drawState = { ov, r, x0: x, y0: y, x1: x, y1: y, el: box };
  place();
  function place() {
    const s = drawState, l = Math.min(s.x0, s.x1), t = Math.min(s.y0, s.y1);
    Object.assign(s.el.style, { left: l * 100 + "%", top: t * 100 + "%", width: Math.abs(s.x1 - s.x0) * 100 + "%", height: Math.abs(s.y1 - s.y0) * 100 + "%" });
  }
  const move = ev => {
    drawState.x1 = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
    drawState.y1 = Math.min(1, Math.max(0, (ev.clientY - r.top) / r.height));
    place();
  };
  const up = () => {
    window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
    const s = drawState; drawState = null; s.el.remove();
    const bw = Math.abs(s.x1 - s.x0) * s.r.width, bh = Math.abs(s.y1 - s.y0) * s.r.height;
    if (bw < 4 || bh < 4) return;
    const nb = { page: +s.ov.dataset.page, box: [Math.min(s.x0, s.x1), Math.min(s.y0, s.y1), Math.max(s.x0, s.x1), Math.max(s.y0, s.y1)], saved: false };
    S.pending.boxes.push(nb);
    S.selBox = S.pending.boxes.length - 1;
    changed();
    offerText(nb);
  };
  window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
}

/* after drawing over text: offer to redact the same text everywhere */
async function offerText(nb) {
  let text = "";
  try { text = (await post(`/api/file/${S.current}/text-in-box`, { page: nb.page, box: nb.box })).text; } catch (_) { return; }
  if (!text || text.length < 3) return;
  const el = $(".mbox.sel"); if (!el) return;
  closeMenus();
  const r = el.getBoundingClientRect();
  const short = text.length > 42 ? text.slice(0, 40) + "…" : text;
  const box = S.pending.boxes.indexOf(nb);
  const pop = h("div", { class: "pop textpop", style: { left: Math.min(r.left, window.innerWidth - 410) + "px", top: (r.bottom + 8) + "px", minWidth: "0", width: "390px" } },
    h("div", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))", marginBottom: "4px" } }, "Text under the box"),
    h("div", { style: { fontFamily: "var(--head)", fontSize: "calc(13.5px * var(--fs, 1))", marginBottom: "10px", wordBreak: "break-word" } }, short),
    h("div", { style: { display: "flex", gap: "6px", flexWrap: "wrap" } },
      h("button", { class: "btn small", onclick: () => closeMenus() }, "Just this box"),
      h("button", { class: "btn small primary", onclick: () => {
        closeMenus();
        if (box >= 0) S.pending.boxes.splice(box, 1);
        if (!S.pending.terms.includes(text)) S.pending.terms.push(text);
        applyPending();
      } }, "Every match in this file"),
      h("button", { class: "btn small", onclick: () => {
        closeMenus();
        if (box >= 0) S.pending.boxes.splice(box, 1);
        S.pending.boxes = S.pending.boxes;  // keep other unsaved boxes
        batchUpdate({ add_terms: [text] }, "Redacting in all files", "Redacted in all files");
      } }, "In all files")));
  pop.addEventListener("click", e => e.stopPropagation());
  pop.addEventListener("mousedown", e => e.stopPropagation());
  document.body.append(pop);
}

/* paging + zoom */
function visiblePage() {
  const v = $("#viewer"); const pgs = $$(".pg", v);
  const mid = v.scrollTop + v.clientHeight * 0.3;
  let cur = 1;
  for (const pg of pgs) { if (pg.offsetTop <= mid) cur = +pg.dataset.page; }
  return cur;
}
function updatePageNo() { if (S.detail?.kind === "pdf") $("#pg-in").value = visiblePage(); }
function goPage(p) {
  const d = S.detail; if (!d || d.kind !== "pdf") return;
  p = Math.max(1, Math.min(d.pages, p));
  const pg = $(`.pg[data-page="${p}"]`);
  if (pg) $("#viewer").scrollTo({ top: pg.offsetTop - 20 });
  $("#pg-in").value = p;
}
function setZoom(z) {
  const v = $("#viewer"); const rel = v.scrollTop / Math.max(1, v.scrollHeight);
  S.zoom = Math.max(0.4, Math.min(3, z));
  renderViewer();
  v.scrollTop = rel * v.scrollHeight;
}

/* ---------------------------------------------------------- items panel */
function renderItems() {
  const d = S.detail, q = S.itemSearch.toLowerCase();
  const el = $("#tab-items");
  const findings = d.findings.filter(f => !q || (f.value + " " + f.type + " " + f.label).toLowerCase().includes(q));
  $("#items-count").textContent = d.findings.length ? ` ${d.findings.length}` : "";
  const order = [...S.meta.groups.map(g => g.key), "custom"];
  const groups = order.map(g => [g, findings.filter(f => (f.group || "custom") === g)]).filter(([, l]) => l.length);
  const head = h("div", { class: "items-head" },
    h("input", { class: "search", placeholder: "Filter items", value: S.itemSearch, "aria-label": "Filter items",
      oninput: e => { S.itemSearch = e.target.value; renderItemsList(); refreshMarks(); } }));
  fill(el, head, h("div", { id: "items-list" }));
  renderItemsList(groups);
  function renderItemsList(gs) {
    const qq = S.itemSearch.toLowerCase();
    const fs = d.findings.filter(f => !qq || (f.value + " " + f.type + " " + f.label).toLowerCase().includes(qq));
    gs = gs && qq === q ? gs : order.map(g => [g, fs.filter(f => (f.group || "custom") === g)]).filter(([, l]) => l.length);
    const list = $("#items-list");
    if (!d.findings.length) {
      fill(list, h("div", { class: "empty-note" }, d.status === "locked" ? "This file is locked." : "Nothing was detected in this file. Check the pages, and draw a box over anything that should go."));
      return;
    }
    fill(list, ...gs.map(([g, items]) => {
      const gname = GROUP_NAMES[g] || S.meta.groups.find(x => x.key === g)?.label || g;
      const allOn = items.every(f => !S.pending.keep.has(f.value) && f.state !== "kept-batch");
      return h("div", { class: "grp", style: { "--gc": GROUP_COLOURS[g] } },
        h("div", { class: "grp-h" }, h("span", { class: "sw" }), h("span", { class: "gname" }, gname), h("span", { class: "gcount" }, items.length),
          h("button", { class: "gall", onclick: () => {
            items.forEach(f => { if (f.state === "kept-batch") return; if (allOn) S.pending.keep.add(f.value); else S.pending.keep.delete(f.value); });
            changed();
          } }, allOn ? "Leave all visible" : "Redact all")),
        items.map(f => itemRow(f)));
    }));
  }
}
function itemRow(f) {
  const st = markState(f), on = st === "redacted" || st === "pending-redact";
  const shown = S.revealed.has(f.id) ? f.value : f.masked;
  const pages = f.pages.length ? "p. " + f.pages.join(", ") : (f.where?.length ? f.where.join(", ") : "");
  const row = h("div", { class: "irow" + (on ? "" : " off"), "data-fid": f.id, style: { "--gc": GROUP_COLOURS[f.group] || GROUP_COLOURS.custom },
    onclick: e => { if (e.target.closest("input,button")) return; flashFinding(f); },
    onmouseenter: () => $$(`.mark[data-fid="${f.id}"]`).forEach(m => m.classList.add("flash")),
    onmouseleave: () => $$(`.mark[data-fid="${f.id}"]`).forEach(m => m.classList.remove("flash")) },
    h("input", { type: "checkbox", checked: on, disabled: f.state === "kept-batch", title: f.state === "kept-batch" ? "Left visible in all files (use the menu to change)" : (on ? "Untick to leave visible" : "Tick to redact"),
      onchange: () => toggleKeep(f.value) }),
    h("span", { class: "ival" + (S.revealed.has(f.id) ? " reveal" : ""), title: "Double-click to show or hide the full value",
      ondblclick: () => { S.revealed.has(f.id) ? S.revealed.delete(f.id) : S.revealed.add(f.id); renderItems(); } }, shown),
    h("span", { class: "iright" },
      f.state === "kept-batch" ? h("span", { class: "kept-tag" }, "visible everywhere") : (!on ? h("span", { class: "kept-tag" }, "visible") : null),
      h("button", { class: "imenu", title: "More", "aria-label": "More actions", onclick: e => { e.stopPropagation(); itemMenu(e.currentTarget, f); } }, "⋯")),
    h("span", { class: "imeta" }, f.label ? h("span", { class: "ilabel" }, f.label) : null, h("span", {}, f.short || f.type), pages ? h("span", {}, pages) : null));
  return row;
}
function itemMenu(anchor, f) {
  closeMenus();
  const r = anchor.getBoundingClientRect();
  const items = [];
  if (f.boxes.length) items.push(["Show on the page", () => flashFinding(f)]);
  if (f.state === "kept-batch") items.push(["Redact again in all files", () => batchUpdate({ remove_keep: [f.value] }, "Redacting again in all files", "Redacted again in all files")]);
  else items.push(["Leave visible in all files", () => batchUpdate({ add_keep: [f.value] }, "Leaving visible in all files", "Left visible in all files")]);
  if (f.state !== "kept-batch") items.push(["Redact this text in all files", () => batchUpdate({ add_terms: [f.value] }, "Redacting in all files", "Redacted in all files")]);
  items.push([S.revealed.has(f.id) ? "Hide full value" : "Show full value", () => { S.revealed.has(f.id) ? S.revealed.delete(f.id) : S.revealed.add(f.id); renderItems(); }]);
  const m = h("div", { class: "menu", style: { left: Math.min(r.left - 180, window.innerWidth - 230) + "px", top: r.bottom + 4 + "px" } },
    items.map(([l, fn]) => h("button", { onclick: () => { closeMenus(); fn(); } }, l)));
  document.body.append(m);
}
function closeMenus() { $$(".menu, .pop").forEach(m => m.remove()); }

async function batchUpdate(payload, title, done) {
  if (dirty()) { const ok = await confirmLeave(); if (!ok) return; }
  try { await post("/api/batch/update", payload); } catch (e) { toast(e.message, true); return; }
  await watchJob(title);
  imgBust++;
  await loadBatch(S.current);
  toast(done || "Updated all files");
}

/* ------------------------------------------------------------ add panel */
function renderAdd() {
  const d = S.detail, el = $("#tab-add");
  const ta = h("textarea", { class: "inp", rows: 3, placeholder: "Text to black out, one per line\n(names, addresses, reference numbers)" });
  const terms = S.pending.terms, bterms = S.batch.batch_terms, bkeep = S.batch.batch_keep;
  fill(el, 
    h("div", { class: "pad" },
      h("div", { class: "field" }, h("label", {}, "Redact text"), ta),
      h("div", { style: { display: "flex", gap: "8px", alignItems: "center" } },
        h("div", { class: "seg" },
          h("button", { class: S.addScope === "file" ? "on" : "", onclick: () => { S.addScope = "file"; renderAdd(); } }, "This file"),
          h("button", { class: S.addScope === "all" ? "on" : "", onclick: () => { S.addScope = "all"; renderAdd(); } }, "All files")),
        h("div", { style: { flex: 1 } }),
        h("button", { class: "btn primary small", onclick: () => {
          const add = lines(ta.value); if (!add.length) return;
          if (S.addScope === "file") { add.forEach(t => { if (!S.pending.terms.includes(t)) S.pending.terms.push(t); }); applyPending(); }
          else batchUpdate({ add_terms: add }, "Redacting in all files", "Redacted in all files");
        } }, "Redact")),
      d.kind === "pdf" ? h("p", { class: "muted", style: { fontSize: "calc(12px * var(--fs, 1))", margin: "12px 0 0" } }, "To black out an area, choose Draw box (D) and drag over the page.") : null),
    section("Boxes you drew", S.pending.boxes.map((b, j) => h("div", { class: "lrow" },
      h("span", {}, h("a", { onclick: () => { S.selBox = j; goPage(b.page); refreshMarks(); } }, `Page ${b.page}`), b.saved ? "" : "  (not applied)"),
      h("button", { title: "Remove", onclick: () => removeBox(j) }, "Remove"))), "None yet"),
    section("Words for this file", terms.map(t => h("div", { class: "lrow" }, h("span", {}, t),
      h("button", { title: "Remove", onclick: () => { S.pending.terms = S.pending.terms.filter(x => x !== t); applyPending(); } }, "Remove"))), "None"),
    section("Words for all files", bterms.map(t => h("div", { class: "lrow" }, h("span", {}, t),
      h("button", { onclick: () => batchUpdate({ remove_terms: [t] }, "Updating all files") }, "Remove"))), "None"),
    section("Left visible in all files", bkeep.map(t => h("div", { class: "lrow" }, h("span", {}, t),
      h("button", { onclick: () => batchUpdate({ remove_keep: [t] }, "Updating all files") }, "Redact again"))), "None"));
}
function section(title, rows, empty) {
  return h("div", {}, h("div", { class: "sect-h" }, title), h("div", { class: "list-sm" }, rows.length ? rows : h("span", { class: "muted", style: { fontSize: "calc(12px * var(--fs, 1))" } }, empty)));
}

/* -------------------------------------------------------- details panel */
function renderDetails() {
  const d = S.detail, el = $("#tab-details");
  const rc = d.recheck;
  fill(el, 
    h("dl", { class: "kv" },
      h("dt", {}, "File"), h("dd", {}, d.name),
      h("dt", {}, "Output"), h("dd", {}, d.output || "—"),
      h("dt", {}, "Type"), h("dd", {}, d.profile_label),
      h("dt", {}, "Status"), h("dd", {}, d.status_text),
      h("dt", {}, "Re-check"), h("dd", {}, h("span", { class: "dot " + rc.state }), " ", rc.text),
      d.kind === "pdf" ? [h("dt", {}, "Pages"), h("dd", {}, `${d.pages}${d.ocr_pages ? `, ${d.ocr_pages} read with OCR` : ""}`)] : null,
      d.message ? [h("dt", {}, "Notes"), h("dd", {}, d.message)] : null),
    d.residual.length ? section("Still detected after redaction", d.residual.map(r => h("div", { class: "lrow" },
      h("span", {}, r.page ? h("a", { onclick: () => goPage(r.page) }, `Page ${r.page}`) : "", ` ${r.type} ${r.masked}`))), "") : null,
    d.layout_pages.length ? h("div", { class: "pad" }, h("div", { class: "alert warn" }, `Text moved on page ${d.layout_pages.join(", ")} during redaction. Compare the pages before sharing.`)) : null,
    h("div", { class: "pad" },
      d.output ? h("a", { class: "btn block", href: `/api/file/${d.index}/download` }, "Download this file") : null),
    h("dl", { class: "kv", style: { paddingTop: 0 } },
      h("dt", {}, "Original SHA-256"), h("dd", { class: "muted", style: { fontSize: "calc(11px * var(--fs, 1))" } }, d.sha_in || "—"),
      h("dt", {}, "Redacted SHA-256"), h("dd", { class: "muted", style: { fontSize: "calc(11px * var(--fs, 1))" } }, d.sha_out || "—")));
}

/* ------------------------------------------------------- top bar menus */
function popAt(btn, content) {
  closeMenus();
  const r = btn.getBoundingClientRect();
  const p = h("div", { class: "pop", style: { top: r.bottom + 6 + "px", right: Math.max(8, window.innerWidth - r.right) + "px" } }, content);
  document.body.append(p);
  const ph = p.offsetHeight;
  if (r.bottom + 6 + ph > window.innerHeight - 8) p.style.top = Math.max(8, r.top - ph - 6) + "px";
  return p;
}
function downloadPop() {
  const done = S.batch.files.filter(f => f.output);
  const single = done.length === 1;
  const opt = { text: true, tables: true, combined: false };
  const chk = (k, l, hint) => h("label", { class: "tog" }, h("input", { type: "checkbox", checked: opt[k], onchange: e => { opt[k] = e.target.checked; } }), h("span", {}, l, hint ? h("div", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))" } }, hint) : null));
  const q = () => `text=${+opt.text}&tables=${+opt.tables}&combined=${+opt.combined}`;
  const go = async () => {
    let plan;
    try { plan = await api(`/api/download/plan?${q()}`); } catch (e) { toast(e.message, true); return; }
    closeMenus();
    plan.items.forEach((it, n) => setTimeout(() => {
      const a = h("a", { href: it.url, download: it.name, style: { display: "none" } });
      document.body.append(a); a.click(); a.remove();
    }, n * 600));
    const notes = (plan.notes || []).join(" ");
    if (plan.items.length > 1) toast(`Downloading ${plan.items.map(i => i.name).join(" and ")}. ${notes}`.trim());
    else if (notes) toast(notes);
  };
  const p = popAt($("#btn-download"), [
    h("h4", {}, "Download"),
    h("p", {}, single
      ? `${done[0].output} is downloaded as it is. Ticked extras come as separate files.`
      : `${done.length} redacted files are downloaded together as one ZIP.`),
    chk("text", "Text version (.txt)", "Easier for the AI to read accurately"),
    chk("tables", "Bank transactions as a table (.csv)", "Date, narration, debit, credit and balance, with each balance verified"),
    single ? null : chk("combined", "One combined PDF with bookmarks"),
    h("button", { class: "btn primary block", style: { marginTop: "10px" }, onclick: go }, single ? "Download" : `Download ZIP (${done.length} files)`),
    S.batch.folder ? [h("div", { class: "sep" }), h("button", { class: "btn block", onclick: async () => {
      try { const r = await post("/api/folder/save", opt); toast(`Saved to ${r.out}`); } catch (e) { toast(e.message, true); }
      closeMenus();
    } }, "Save next to the source folder")] : null]);
  p.addEventListener("click", e => e.stopPropagation());
}

function recordsPop() {
  const client = h("input", { class: "inp", id: "rec-client", placeholder: "Leave blank to fill by hand" });
  const tool = h("input", { class: "inp", id: "rec-tool", placeholder: "e.g. Claude, ChatGPT; or leave blank" });
  const q = () => `client=${encodeURIComponent(client.value)}&ai_tool=${encodeURIComponent(tool.value)}`;
  const p = popAt($("#btn-records"), [
    h("h4", {}, "Records for your file"),
    h("p", {}, "An A4 Certificate of Redaction with statutory references, the log" + (S.batch.style === "label" ? " and the label key with the original values" : "") + ". Keep these on this computer; never upload them."),
    h("div", { class: "field" }, h("label", { for: "rec-client" }, "Client / engagement reference"), client),
    h("div", { class: "field" }, h("label", { for: "rec-tool" }, "AI tool to be used"), tool),
    h("p", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))", marginTop: "-2px" } }, "Firm, signatory, membership number, UDIN, place and date print as blank lines for signing."),
    h("div", { style: { display: "flex", gap: "8px" } },
      h("button", { class: "btn", style: { flex: 1 }, onclick: () => { window.location = `/api/download/certificate?${q()}`; closeMenus(); } }, "Certificate only"),
      h("button", { class: "btn primary", style: { flex: 1 }, onclick: () => { window.location = `/api/download/records?${q()}`; closeMenus(); } }, "All records (ZIP)"))]);
  p.addEventListener("click", e => e.stopPropagation());
}

/* -------------------------------------------------------------- contact */
function contactPop(anchor) {
  const m = S.meta, tel = m.contact.phone.replace(/[^+\d]/g, "");
  const copy = (text, what) => h("button", { class: "copy", onclick: async () => {
    try { await navigator.clipboard.writeText(text); toast(`${what} copied`); } catch (_) { toast(text); }
  } }, "Copy");
  const ic = d => h("span", { html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>` });
  const subject = encodeURIComponent(`${m.app} v${m.version}: feedback`);
  const p = popAt(anchor || $("#btn-contact"), h("div", { class: "contact-card" },
    h("div", { class: "contact-head" }, h("img", { src: "/static/brand/logo.svg", alt: "" }),
      h("div", {}, h("div", { class: "t1" }, m.app), h("div", { class: "t2" }, `Designed and developed by ${m.author}`))),
    h("div", { class: "crow" }, ic('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>'),
      h("div", {}, h("div", { class: "k" }, "Phone"), h("a", { href: `tel:${tel}` }, m.contact.phone)), copy(m.contact.phone, "Phone number")),
    h("div", { class: "crow" }, ic('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
      h("div", {}, h("div", { class: "k" }, "E-mail"), h("a", { href: `mailto:${m.contact.email}?subject=${subject}` }, m.contact.email)), copy(m.contact.email, "E-mail address")),
    h("div", { class: "crow" }, ic('<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/>'),
      h("div", {}, h("div", { class: "k" }, "Version"), h("span", {}, `${m.app} v${m.version}`)), h("span")),
    h("p", { class: "muted", style: { fontSize: "calc(11.5px * var(--fs, 1))", margin: "8px 0 0" } }, "For help, feedback or feature requests, call or write any time. Please do not send client documents by e-mail.")));
  p.addEventListener("click", e => e.stopPropagation());
}

/* ------------------------------------------------------------- keyboard */
function onKey(e) {
  const tag = (e.target.tagName || "").toLowerCase();
  const typing = tag === "input" || tag === "textarea" || tag === "select";
  if (e.key === "Escape") { closeMenus(); if (!$("#drawer").classList.contains("closed")) closeDrawer(); else if (S.selBox !== null) { S.selBox = null; refreshMarks(); } return; }
  if (!S.batch || !S.detail || typing) return;
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); if (dirty()) applyPending(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key;
  if (k === "d" || k === "D") setTool("draw");
  else if (k === "v" || k === "V") setTool("select");
  else if (k === "r" || k === "R") setView("redacted");
  else if (k === "o" || k === "O") setView("original");
  else if (k === "s" || k === "S") setView("split");
  else if (k === "m" || k === "M") { S.showMarks = !S.showMarks; renderViewer(); }
  else if (k === "ArrowRight" || k === "PageDown") { e.preventDefault(); goPage(visiblePage() + 1); }
  else if (k === "ArrowLeft" || k === "PageUp") { e.preventDefault(); goPage(visiblePage() - 1); }
  else if (k === "+" || k === "=") setZoom(S.zoom * 1.15);
  else if (k === "-" || k === "_") setZoom(S.zoom / 1.15);
  else if (k === "0") setZoom(1);
  else if ((k === "Delete" || k === "Backspace") && S.selBox !== null) { e.preventDefault(); removeBox(S.selBox); }
  else if (k === "j" || k === "J") { const n = nextFile(1); if (n !== null) selectFile(n); }
  else if (k === "k" || k === "K") { const n = nextFile(-1); if (n !== null) selectFile(n); }
}
function nextFile(dir) {
  const ids = $$(".frow").map(r => S.batch.files.find(f => f.name === $(".fname", r).textContent)?.index).filter(x => x !== undefined);
  const pos = ids.indexOf(S.current);
  const n = ids[pos + dir];
  return n === undefined ? null : n;
}
function setTool(t) { S.tool = t; $("#viewer").classList.toggle("draw", t === "draw"); $$("#toolbar [data-tool]").forEach(b => b.classList.toggle("on", b.dataset.tool === t)); status(t === "draw" ? "Drag over the page to add a redaction box" : ""); }
function setView(v) { if (S.view === v) return; S.view = v; renderViewer(); }

/* ----------------------------------------------------------------- init */
async function init() {
  S.meta = await api("/api/meta");
  $("#ver").textContent = `${S.meta.app} v${S.meta.version}`;
  document.title = S.meta.app;
  $("#btn-contact").addEventListener("click", e => { e.stopPropagation(); contactPop(); });
  loadSettings();
  $("#file-input").setAttribute("accept", S.meta.extensions.join(","));
  $("#file-input").addEventListener("change", e => { addFiles(e.target.files); e.target.value = ""; });
  $("#btn-settings").addEventListener("click", openDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  $("#btn-new").addEventListener("click", async () => {
    if (!(await confirmLeave())) return;
    const v = await modal("Start a new batch?", "The current results stay available only until you start the new batch. Download what you need first.",
      [{ label: "Cancel", value: false }, { label: "Start new batch", value: true, cls: "primary" }]);
    if (!v) return;
    await post("/api/reset", {}); S.batch = null; S.detail = null; S.current = -1; await loadBatch();
  });
  $("#btn-download").addEventListener("click", e => { e.stopPropagation(); downloadPop(); });
  $("#btn-records").addEventListener("click", e => { e.stopPropagation(); recordsPop(); });
  document.addEventListener("click", e => { if (!e.target.closest(".menu,.pop")) closeMenus(); });
  $("#file-search").addEventListener("input", e => { S.fileSearch = e.target.value; renderFiles(); });
  $$("#file-filters button").forEach(b => b.addEventListener("click", () => { S.fileFilter = b.dataset.f; $$("#file-filters button").forEach(x => x.classList.toggle("on", x === b)); renderFiles(); }));
  $$("#toolbar [data-view]").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
  $$("#toolbar [data-tool]").forEach(b => b.addEventListener("click", () => setTool(b.dataset.tool)));
  $("#btn-marks").addEventListener("click", () => { S.showMarks = !S.showMarks; renderViewer(); });
  $("#pg-prev").addEventListener("click", () => goPage(visiblePage() - 1));
  $("#pg-next").addEventListener("click", () => goPage(visiblePage() + 1));
  $("#pg-in").addEventListener("change", e => goPage(+e.target.value || 1));
  $("#z-in").addEventListener("click", () => setZoom(S.zoom * 1.15));
  $("#z-out").addEventListener("click", () => setZoom(S.zoom / 1.15));
  $("#z-fit").addEventListener("click", () => setZoom(1));
  $("#btn-apply").addEventListener("click", applyPending);
  $("#btn-discard").addEventListener("click", discardPending);
  $$(".tabs button").forEach(b => b.addEventListener("click", () => {
    S.tab = b.dataset.tab; $$(".tabs button").forEach(x => x.classList.toggle("on", x === b));
    ["items", "add", "details"].forEach(t => $("#tab-" + t).classList.toggle("hidden", t !== S.tab));
  }));
  const v = $("#viewer");
  v.addEventListener("mousedown", startDraw);
  v.addEventListener("mousedown", e => { if (S.tool === "select" && !e.target.closest(".mbox") && S.selBox !== null) { S.selBox = null; refreshMarks(); } });
  v.addEventListener("scroll", () => { clearTimeout(v._t); v._t = setTimeout(updatePageNo, 60); });
  v.addEventListener("wheel", e => { if (e.ctrlKey) { e.preventDefault(); setZoom(S.zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)); } }, { passive: false });
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (S.detail) renderViewer(); }, 150); });
  window.addEventListener("beforeunload", e => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });
  document.addEventListener("keydown", onKey);
  renderDrawer();
  if (S.meta.has_batch) await loadBatch(); else { fill($("#top-stats")); renderComposer(); }
}
init().catch(e => toast("Could not start: " + e.message, true));

// Tell the program this window is still open (it stops by itself once every window is closed)
function ping() { fetch("/api/ping", { method: "POST", keepalive: true }).catch(() => {}); }
ping();
setInterval(ping, 5000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) ping(); });
