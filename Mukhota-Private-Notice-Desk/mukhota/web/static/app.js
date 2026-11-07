/* Mukhota browser front end. Talks only to the local engine on 127.0.0.1. */
'use strict';

// One-time key from the address bar; kept for reloads, then removed from view.
const KEY = (() => {
  const k = new URLSearchParams(location.search).get('k');
  try { if (k) sessionStorage.setItem('mk', k); } catch (e) { /* storage blocked */ }
  let key = k;
  try { key = k || sessionStorage.getItem('mk'); } catch (e) { /* storage blocked */ }
  if (k) history.replaceState(null, '', '/');
  return key || '';
})();

const ICONS = {
  open: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  detect: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5',
  draw: 'M4 4h16v16H4zM8 8h8v8H8z',
  term: 'M4 7h16M4 12h10M4 17h7M17 15v6M14 18h6',
  apply: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  verify: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8 12l3 3 5-6',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 11v5M9.5 13.5h5',
  reply: 'M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5',
  register: 'M9 3h6v3H9zM7 4.5H5V21h14V4.5h-2M8 11h8M8 15h8M8 18.5h5',
  settings: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1',
  about: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5v.5',
};
const STEPS = ['Open', 'Detect & review', 'Redact', 'Verify', 'Draft reply'];

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') n.className = v;
    else if (k === 'style') n.setAttribute('style', v);
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) n.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid);
  return n;
};

let S = null;               // last state from the engine
let seq = 0;                // last event seen
let primed = false;         // first state fetched
let current = 0;            // page shown
let zoom = 0;               // 0 = fit width, otherwise pixels of paper width
let selected = '';          // selected candidate id
let drawMode = false;
let compare = false;
let offTypes = new Set();   // filter chips switched off
let polling = null;
let builtKey = '', builtSeq = 0;           // which document the stacked pages were built for

// ---------------------------------------------------------------- engine calls
async function api(path, body) {
  let res;
  try {
    res = await fetch('/api/' + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'X-Mukhota-Key': KEY, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    stopped();
    throw e;
  }
  if (res.status === 403) {
    await alertBox('Mukhota', 'This page has expired. Close it and start Mukhota again with run.bat.');
    throw new Error('forbidden');
  }
  const data = await res.json();
  if (data.error) {
    await alertBox('Mukhota', data.error);
    throw new Error(data.error);
  }
  return data;
}

async function refresh() {
  const st = await api('state?since=' + seq);
  S = st;
  render();
  if (!primed) {   // a reloaded page should not replay messages shown before the reload
    primed = true;
    seq = st.events.reduce((m, e) => Math.max(m, e.seq), seq);
  }
  for (const ev of st.events) {
    if (ev.seq <= seq) continue;   // another refresh already showed it
    seq = ev.seq;
    if (ev.kind === 'error' && S.draft) { draftFailed = ev.text; renderDraftStatus(S.draft); }
    if (ev.kind === 'error' || ev.kind === 'info') await alertBox(ev.title, ev.text);
    else if (ev.kind === 'draft-confirm') await confirmSend(ev.text, ev.over);
  }
  schedule();
}

function schedule() {
  clearTimeout(polling);
  // Fast while working; a slow heartbeat otherwise so the engine knows the page is open.
  polling = setTimeout(() => refresh().catch(() => {}), S && S.busy ? 400 : 30000);
}

function stopped() {
  clearTimeout(polling);
  document.body.replaceChildren(el('div', { class: 'empty', style: 'margin-top:20vh' },
    'Mukhota has stopped.', el('br'), el('span', {}, 'Start it again with run.bat.')));
}

async function act(path, body = {}) {
  try {
    const r = await api(path, body);
    await refresh();
    return r;
  } catch (e) {
    refresh().catch(() => {});
    return null;
  }
}

// ---------------------------------------------------------------- rendering
function render() {
  const st = S;
  // An engine older than this page does not send the flag at all; treat that as updated too.
  $('updatedBar').hidden = st.updated === false;
  const hasDoc = !!st.file;
  const busy = st.busy;
  $('filePill').textContent = hasDoc ? `${st.file.name}  ·  ${st.file.pages} page${st.file.pages !== 1 ? 's' : ''}` : 'No notice open';

  // Stepper
  const done = st.flow.done;
  $('steps').replaceChildren(...STEPS.flatMap((label, i) => {
    const state = i <= done ? 'done' : i === done + 1 ? 'current' : 'todo';
    const li = el('li', { class: state }, el('span', { class: 'dot' }, state === 'done' ? '✓' : String(i + 1)), label);
    return i < STEPS.length - 1 ? [li, el('li', { class: 'sep', 'aria-hidden': 'true' })] : [li];
  }));
  const prim = $('btnPrimary');
  prim.textContent = st.flow.label;
  prim.disabled = busy;

  // Toolbar
  for (const b of document.querySelectorAll('.tool')) {
    const a = b.dataset.act;
    if (['detect', 'draw', 'term', 'apply'].includes(a)) b.disabled = !hasDoc || busy;
    else if (a === 'folder') b.disabled = !st.hasOutput;
    else if (['open', 'verify', 'draft', 'settings'].includes(a)) b.disabled = busy;
  }
  $('btnOpenDraft').disabled = busy;
  if ((!hasDoc || busy) && drawMode) setDraw(false);

  // Nav
  current = Math.min(current, Math.max(0, st.pages.length - 1));
  for (const id of ['btnPrev', 'btnNext', 'pageSelect', 'chkReviewed', 'btnZoomIn', 'btnZoomOut', 'btnFit']) $(id).disabled = !hasDoc || !st.pages.length;
  $('btnCompare').disabled = !hasDoc || !st.hasAfter;
  if (!st.hasAfter && compare) setCompare(false);
  const sel = $('pageSelect');
  sel.replaceChildren(...st.pages.map((p) => {
    let label = `Page ${p.index + 1}  (${p.kind.toLowerCase()})`;
    if (p.needsReview && !p.reviewed) label += '  ⚠ Manual review required';
    else if (p.reviewed) label += '  ✔ reviewed';
    return el('option', { value: p.index, style: p.needsReview && !p.reviewed ? 'color:#C62828' : '' }, label);
  }));
  renderBanner();
  renderPage();
  renderList();

  // Draft tab
  $('draftLock').hidden = st.verified;
  renderDraft();

  // Status
  $('statusText').textContent = st.msg;
  $('bar').style.width = st.pct + '%';
  $('pct').textContent = st.pct + '%';
}

function pageUrl(i, which) {
  return `/api/page.png?n=${i}&which=${which}&k=${encodeURIComponent(KEY)}&v=${encodeURIComponent(builtKey)}`;
}

// All pages stacked in one scrolling column; images load as they come into view.
function buildPages(st) {
  const key = `${st.file.name}:${st.pages.length}:${compare ? st.afterVersion : ''}:${builtSeq}`;
  if (key === builtKey) return;
  builtKey = key;
  const make = (which) => st.pages.map((p) => el('div', {
    class: 'paper', 'data-page': p.index, style: `aspect-ratio:${p.w} / ${p.h}`,
  }, el('img', { alt: `Page ${p.index + 1}`, draggable: 'false', loading: 'lazy', src: pageUrl(p.index, which) }),
  which === 'orig' ? el('div', { class: 'overlays' }) : null,
  el('span', { class: 'page-tag' }, `${p.index + 1} / ${st.pages.length}`)));
  $('pagesOrig').replaceChildren(...make('orig'));
  $('pagesAfter').replaceChildren(...(compare ? make('after') : []));
}

function renderPage() {
  const st = S;
  const has = st.pages.length > 0;
  $('emptyNote').hidden = has;
  $('kindBadge').hidden = !has;
  if (!has) {
    builtKey = '';
    $('pagesOrig').replaceChildren();
    $('pagesAfter').replaceChildren();
    $('reviewBadge').hidden = true;
    return;
  }
  $('paneAfter').hidden = !compare;
  buildPages(st);
  applyZoom();
  updateNav();
  // Overlays in percent of each page, so they follow any zoom.
  const byPage = new Map();
  for (const c of st.candidates) {
    const page = st.pages[c.page];
    if (!page) continue;
    const tip = `${c.type}: ${c.value}  (${c.conf}%)`;
    const list = byPage.get(c.page) || [];
    for (const [x, y, w, h] of c.boxes) {
      list.push(el('div', {
        class: `box ${c.accepted ? 'on' : 'off'}${c.cid === selected ? ' sel' : ''}`, title: tip,
        style: `left:${x / page.w * 100}%;top:${y / page.h * 100}%;width:${w / page.w * 100}%;height:${h / page.h * 100}%;color:${c.colour}`,
        onclick: (e) => { if (!drawMode) { e.stopPropagation(); select(c.cid, false); } },
      }));
    }
    byPage.set(c.page, list);
  }
  for (const paper of $('pagesOrig').children) {
    paper.querySelector('.overlays').replaceChildren(...(byPage.get(Number(paper.dataset.page)) || []));
  }
}

// Page box, type badge and review tick follow the page in view.
function updateNav() {
  const page = S && S.pages[current];
  if (!page) return;
  $('pageSelect').value = String(current);
  $('kindBadge').textContent = page.kind === 'IMAGE' ? 'Scanned page (OCR)' : 'Text page';
  $('reviewBadge').hidden = !(page.needsReview && !page.reviewed);
  $('chkReviewed').checked = page.reviewed;
}

function pageInView() {
  const pane = $('paneOrig');
  const mark = pane.getBoundingClientRect().top + pane.clientHeight / 3;
  let idx = 0;
  for (const paper of $('pagesOrig').children) {
    if (paper.getBoundingClientRect().top <= mark) idx = Number(paper.dataset.page);
  }
  return idx;
}

function applyZoom() {
  for (const [pane, host] of [[$('paneOrig'), $('pagesOrig')], [$('paneAfter'), $('pagesAfter')]]) {
    const fit = Math.max(200, pane.clientWidth - 24);
    for (const paper of host.children) paper.style.width = (zoom || fit) + 'px';
  }
}

function renderList() {
  const cands = S.candidates;
  const total = cands.length;
  const acc = cands.filter((c) => c.accepted).length;
  $('summary').replaceChildren(...(total
    ? [el('span', { class: 'big' }, String(acc)), `of ${total} items will be redacted`]
    : [S.file ? 'Click ' : 'Open a PDF and click ', el('b', {}, 'Detect PII'), ' to scan this notice.']));
  $('rowBtns').hidden = !total;

  const types = [...new Set(cands.map((c) => c.type))].sort();
  const colour = Object.fromEntries(cands.map((c) => [c.type, c.colour]));
  $('chips').replaceChildren(...types.map((t) => el('button', {
    class: 'chip', style: `color:${colour[t]}`, 'aria-pressed': String(!offTypes.has(t)),
    onclick: () => { offTypes.has(t) ? offTypes.delete(t) : offTypes.add(t); renderList(); },
  }, el('span', {}, `${t} · ${cands.filter((c) => c.type === t).length}`))));

  const rows = visible().sort((a, b) => a.page - b.page || a.type.localeCompare(b.type));
  $('list').replaceChildren(...rows.map((c) => {
    const box = el('input', { type: 'checkbox', 'aria-label': 'Redact this item', onclick: (e) => e.stopPropagation(),
      onchange: (e) => setAccepted([c.cid], e.target.checked) });
    box.checked = c.accepted;
    return el('div', {
      class: `item${c.accepted ? '' : ' off'}${c.cid === selected ? ' sel' : ''}`, 'data-cid': c.cid,
      title: `Rule: ${c.rule}` + (c.role ? ` | Role: ${c.role}` : ''),
      onclick: () => select(c.cid, true),
    }, box, el('span', { class: 'dot', style: `color:${c.colour}` }),
    el('div', { class: 'txt' }, el('div', { class: 'typ', style: `color:${c.colour}` }, c.type), el('div', { class: 'val' }, c.value)),
    el('span', { class: 'pg' }, `p.${c.page + 1}`),
    el('span', { class: `conf${c.conf < 60 ? ' low' : ''}` }, `${c.conf}%`));
  }));
}

function visible() { return S.candidates.filter((c) => !offTypes.has(c.type)); }

function renderBanner() {
  const b = S.banner;
  const host = $('banner');
  if (!b) { host.hidden = true; host.dataset.v = ''; return; }
  const sig = JSON.stringify(b);
  if (host.dataset.v === sig) return;   // keep it closed if the user closed it
  host.dataset.v = sig;
  host.hidden = false;
  host.className = 'banner ' + (b.ok ? 'pass' : 'fail');
  $('bannerTitle').textContent = (b.ok ? '✔  ' : '✖  ') + b.title;
  $('bannerChips').replaceChildren(...b.chips.map((c) => el('span', { class: 'check ' + c.status }, `${c.status} · ${c.name}`)));
  const parts = [];
  if (b.details) parts.push(el('div', {}, b.details));
  for (const lk of b.leaks) {
    parts.push(el('div', {}, el('a', { href: '#', onclick: (e) => { e.preventDefault(); showPage(lk.page - 1); } }, `Page ${lk.page}`), ` – ${lk.text}`));
  }
  if (b.notes.length) parts.push(el('div', {}, el('b', {}, b.ok ? 'Notes: ' : ''), b.notes.join(' · ')));
  $('bannerDetails').replaceChildren(...parts);
}

// ---------------------------------------------------------------- interactions
function showPage(i) {
  if (!S || !S.pages.length) return;
  current = Math.max(0, Math.min(i, S.pages.length - 1));
  updateNav();
  const paper = $('pagesOrig').querySelector(`[data-page="${current}"]`);
  if (paper) $('paneOrig').scrollTop = paper.offsetTop - $('pagesOrig').offsetTop;
}

function select(cid, scrollPage) {
  selected = cid;
  const c = S.candidates.find((x) => x.cid === cid);
  if (!c) return;
  current = c.page;
  render();
  if (scrollPage) {
    const boxEl = $('pagesOrig').querySelector('.box.sel');
    if (boxEl) boxEl.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
  } else {
    const row = $('list').querySelector(`[data-cid="${cid}"]`);
    if (row) row.scrollIntoView({ block: 'nearest' });
  }
}

async function setAccepted(cids, on) {
  for (const c of S.candidates) if (cids.includes(c.cid)) c.accepted = on;
  render();
  await act('accept', { cids, on });
}

function setDraw(on, announce = false) {
  drawMode = on;
  document.querySelector('[data-act="draw"]').setAttribute('aria-pressed', String(on));
  $('well').classList.toggle('drawing', on);
  if (S && announce) {
    S.msg = on ? 'Draw Box: drag a rectangle on the page to redact it.' : 'Draw Box off.';
    $('statusText').textContent = S.msg;
  }
}

function setCompare(on) {
  compare = on;
  $('btnCompare').setAttribute('aria-pressed', String(on));
  if (S) {
    const keep = $('paneOrig').scrollTop;
    renderPage();
    $('paneOrig').scrollTop = keep;
    $('paneAfter').scrollTop = keep;
  }
}

async function doAction(a) {
  if (!S) return;
  if (a === 'open') {
    S.msg = 'Choose the notice PDF in the window that has opened (it may be behind the browser).';
    $('statusText').textContent = S.msg;
    const r = await act('open');
    if (r) { builtSeq++; current = 0; zoom = 0; selected = ''; offTypes = new Set(); setCompare(false); setDraw(false); $('paneOrig').scrollTop = 0; }
  } else if (a === 'detect') {
    await act('detect');
  } else if (a === 'draw') {
    setDraw(!drawMode, true);
  } else if (a === 'term') {
    const term = await promptBox('Add Term', 'Word or phrase to redact everywhere in this notice:');
    if (term && term.trim()) {
      const r = await act('term', { term });
      if (r && !r.found) await alertBox('Add Term', 'That term was not found in this notice.');
    }
  } else if (a === 'apply') {
    const s = await api('apply-summary', {}).catch(() => null);
    if (!s) return;
    let msg = `Redact ${s.accepted} ticked item(s) and create a new redacted PDF?\n\nThe original notice will not be changed.`;
    if (s.pending.length) msg += `\n\nPages flagged for manual review and not yet marked reviewed: ${s.pending.join(', ')}.`;
    if (s.replaces) msg += '\n\nAn earlier redacted copy in the output folder will be replaced.';
    if (await confirmBox('Apply Redaction', msg, 'Redact')) await act('apply');
  } else if (a === 'verify') {
    await act('verify');
  } else if (a === 'draft') {
    S.msg = 'Opening Draft Reply. If no verified notice is open, choose its redacted PDF in the window that opens.';
    $('statusText').textContent = S.msg;
    await act('draft/open');
  } else if (a === 'settings') {
    await openSettings();
  } else if (a === 'register') {
    await openRegister();
  } else if (a === 'folder') {
    await act('output-folder');
  } else if (a === 'about') {
    const info = await api('info').catch(() => null);
    if (info) await alertBox(`About ${info.app}`, `${info.title}\nVersion ${info.version}\n\n${info.tagline}\n\nRuns on this computer only. Redaction and verification never use the network.`);
  }
}

// Draw a box by dragging on the page.
(function drawing() {
  let start = null;   // [x, y, paper, rubber]
  const pos = (e, paper) => {
    const r = paper.getBoundingClientRect();
    return [Math.max(0, Math.min(e.clientX - r.left, r.width)), Math.max(0, Math.min(e.clientY - r.top, r.height)), r];
  };
  $('pagesOrig').addEventListener('mousedown', (e) => {
    const paper = e.target.closest('.paper');
    if (!drawMode || e.button !== 0 || !paper) return;
    e.preventDefault();
    const [x, y] = pos(e, paper);
    const rubber = el('div', { class: 'rubber' });
    paper.append(rubber);
    start = [x, y, paper, rubber];
    Object.assign(rubber.style, { left: x + 'px', top: y + 'px', width: '0px', height: '0px' });
  });
  window.addEventListener('mousemove', (e) => {
    if (!start) return;
    const [sx, sy, paper, rubber] = start;
    const [x, y] = pos(e, paper);
    Object.assign(rubber.style, {
      left: Math.min(x, sx) + 'px', top: Math.min(y, sy) + 'px',
      width: Math.abs(x - sx) + 'px', height: Math.abs(y - sy) + 'px',
    });
  });
  window.addEventListener('mouseup', async (e) => {
    if (!start) return;
    const [sx, sy, paper, rubber] = start;
    start = null;
    rubber.remove();
    const [x, y, r] = pos(e, paper);
    const index = Number(paper.dataset.page);
    const page = S.pages[index];
    const k = page.w / r.width;   // screen pixels -> page image pixels
    const box = { page: index, x: Math.min(x, sx) * k, y: Math.min(y, sy) * k, w: Math.abs(x - sx) * k, h: Math.abs(y - sy) * k };
    if (box.w > 4 && box.h > 4) await act('box', box);
  });
})();

// ---------------------------------------------------------------- dialogs
function modal(title, body, buttons) {
  return new Promise((resolve) => {
    $('modalTitle').textContent = title;
    $('modalBody').replaceChildren(...[body].flat());
    const close = (v) => { $('modalBack').hidden = true; document.removeEventListener('keydown', onKey); resolve(v); };
    const btns = buttons.map((b) => el('button', { class: b.main ? 'main' : '', onclick: () => close(b.value()) }, b.label));
    $('modalBtns').replaceChildren(...btns);
    const onKey = (e) => {
      if (e.key === 'Escape') close(buttons.find((b) => b.cancel)?.value() ?? null);
      if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') { e.preventDefault(); const m = buttons.find((b) => b.main); if (m) close(m.value()); }
    };
    document.addEventListener('keydown', onKey);
    $('modalBack').hidden = false;
    const focus = $('modalBody').querySelector('input') || btns.find((b) => b.className === 'main') || btns[0];
    if (focus) focus.focus();
  });
}
const alertBox = (title, text) => modal(title, text, [{ label: 'OK', main: true, cancel: true, value: () => true }]);
const confirmBox = (title, text, yes = 'Yes') => modal(title, text, [
  { label: 'Cancel', cancel: true, value: () => false }, { label: yes, main: true, value: () => true }]);
function promptBox(title, text) {
  const input = el('input', { type: 'text', autocomplete: 'off' });
  return modal(title, [el('div', {}, text), input], [
    { label: 'Cancel', cancel: true, value: () => null }, { label: 'Add', main: true, value: () => input.value }]);
}

// ---------------------------------------------------------------- Draft Reply
let draftFile = '';       // file the form was set up for
let draftVer = -1;        // engine text version shown in the tabs
let draftTab = 'sent';
let outSel = new Set(['reply', 'advisory']), howMode = 'send', inMode = 'both';
const OUT_ORDER = ['reply', 'advisory', 'law'];

function draftOpts() {
  return { model: $('dModel').value, type: $('dType').value, out: OUT_ORDER.filter((k) => outSel.has(k)).join('+'),
    how: howMode, in: inMode, web: $('dWeb').checked, lib: $('dLib').checked, facts: $('dFacts').value,
    frame: $('dFrame').checked,
    boxes: Object.fromEntries([...$('dBoxes').querySelectorAll('input')].map((i) => [i.dataset.box, i.value])) };
}

// Optional add-on: six-box issue framing before the reply.
function sixBoxes(d) {
  $('dBoxes').replaceChildren(...Object.entries(d.sixBoxes).map(([k, [label, hint]]) =>
    el('label', { class: 'field' }, label, el('input', { type: 'text', 'data-box': k, placeholder: hint }))));
  $('dFrame').checked = false;
  $('dSixBox').hidden = true;
}
$('dFrame').addEventListener('change', () => { $('dSixBox').hidden = !$('dFrame').checked; });

// Outputs: tick any (at least one stays ticked).
function outButtons(d) {
  $('dOut').replaceChildren(...Object.entries(d.outputs).map(([id, label]) => el('button', {
    type: 'button', 'aria-pressed': String(outSel.has(id)),
    onclick: () => {
      if (outSel.has(id) && outSel.size === 1) return;
      outSel.has(id) ? outSel.delete(id) : outSel.add(id);
      outButtons(d);
    },
  }, label)));
}

// Send to AI, or make a prompt for any AI chat (no API).
function applyHow(d) {
  const prompt = howMode === 'prompt';
  segButtons($('dHow'), d.hows, () => howMode, (v) => { howMode = v; applyHow(d); });
  $('dSendOnly').hidden = $('dSendBtns').hidden = prompt;
  $('dPromptNote').hidden = $('dPromptBtns').hidden = !prompt;
  renderTabButtons(d);
}

function segButtons(host, modes, getter, setter, disabled = []) {
  host.replaceChildren(...Object.entries(modes).map(([id, label]) => el('button', {
    type: 'button', 'aria-pressed': String(getter() === id), disabled: disabled.includes(id),
    onclick: () => { setter(id); segButtons(host, modes, getter, setter, disabled); },
  }, label)));
}

// PDF and web search only where the chosen model's provider can take them.
let webWanted = true;
function applyModelCaps() {
  const d = S.draft;
  const m = d && d.models.find((x) => x.id === $('dModel').value);
  if (!m) return;
  if (!m.pdf && inMode !== 'text') inMode = 'text';
  segButtons($('dIn'), d.inModes, () => inMode, (v) => { inMode = v; }, m.pdf ? [] : ['both', 'pdf']);
  $('dWeb').disabled = !m.web;
  $('dWeb').checked = m.web && webWanted;
  $('dCapsNote').hidden = m.pdf && m.web;
  $('dCapsNote').textContent = d.noPdfWeb;
}

function renderDraft() {
  const d = S.draft;
  $('draftSheet').hidden = !d;
  if (!d) { draftFile = ''; draftVer = -1; return; }
  if (draftFile !== d.file) {   // a new draft session: set the form up once
    draftFile = d.file;
    draftTab = 'sent';
    draftStarted = draftEnded = 0; draftFailed = '';
    outSel = new Set(['reply', 'advisory']); howMode = 'send'; inMode = 'both';
    pastePanel.querySelector('textarea').value = '';
    $('draftFile').textContent = d.file + (d.client ? `  ·  ${d.client}` : '') + (d.ay ? `  ·  AY ${d.ay}` : '');
    $('dModel').replaceChildren(...d.models.map((m) => el('option', { value: m.id }, m.label + (m.ready ? '' : '  (no key saved)'))));
    $('dModel').value = d.model;
    webWanted = true;
    $('dType').replaceChildren(...d.types.map((t) => el('option', { value: t }, t)));
    outButtons(d);
    segButtons($('dIn'), d.inModes, () => inMode, (v) => { inMode = v; });
    $('dLibLabel').textContent = `Use my law library (${d.libCount} file${d.libCount !== 1 ? 's' : ''} in law_library\\)`;
    $('dLib').checked = d.libDefault;
    $('dLib').disabled = d.libCount === 0;
    $('dWeb').checked = true;
    $('dFacts').value = '';
    sixBoxes(d);
    $('btnFacts').disabled = !d.hasFacts;
    $('dRemember').checked = d.hasFacts;
    $('dRemember').disabled = !d.hasFacts;
    $('rememberLabel').textContent = "Remember the values I type here in this client's facts sheet" + (d.ay ? ` (AY ${d.ay})` : '');
    applyModelCaps();
    applyHow(d);
  }
  if (draftVer !== d.ver) {     // the engine replaced the text: rebuild the tabs
    draftVer = d.ver;
    buildDraftTabs(d);
  }
  const busy = S.busy;
  for (const id of ['btnPreview', 'btnSend', 'btnDraftClose', 'btnMakePrompt']) $(id).disabled = busy;
  pastePanel.querySelector('button').disabled = busy;
  $('btnCopyPrompt').disabled = $('btnSavePrompt').disabled = busy || !d.hasPrompt;
  $('btnSave').disabled = busy || !d.hasOutput;
  renderDraftStatus(d);
}

// Draft status bar: READY / WORKING / DONE / FAILED, with the time taken.
let draftStarted = 0, draftEnded = 0, draftFailed = '', draftWasBusy = false;

function renderDraftStatus(d) {
  const busy = S.busy;
  if (busy && !draftWasBusy) { draftStarted = Date.now(); draftEnded = 0; draftFailed = ''; }
  if (!busy && draftWasBusy) draftEnded = Date.now();
  draftWasBusy = busy;
  const state = busy ? 'busy' : draftFailed ? 'error' : draftStarted && S.pct >= 100 ? 'done' : 'idle';
  $('dStatus').dataset.state = state;
  $('dState').textContent = { idle: 'READY', busy: 'WORKING', done: 'DONE', error: 'FAILED' }[state];
  $('draftInfo').textContent = busy ? S.msg : draftFailed ? 'Stopped: ' + draftFailed.split('\n')[0] : d.info;
  const pct = state === 'error' ? 0 : S.pct;
  $('dBar').style.width = pct + '%';
  $('dPct').textContent = pct + '%';
  showDraftTime();
}

function showDraftTime() {
  if (!draftStarted) { $('dTime').textContent = ''; return; }
  const s = Math.floor(((draftEnded || Date.now()) - draftStarted) / 1000);
  $('dTime').textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
setInterval(() => { if (S && S.draft && S.busy) showDraftTime(); }, 1000);

function draftTabList(d) {
  const tabs = [{ key: 'sent', title: howMode === 'prompt' ? 'Prompt to copy' : 'What will be sent' }];
  if (howMode === 'prompt') tabs.push({ key: 'paste', title: 'Paste AI answer' });
  tabs.push(...d.sections.map((s) => ({ key: s.key, title: s.title + ' (editable)' })));
  if (d.hasOutput) tabs.push({ key: 'ph', title: `Fill placeholders (${d.placeholders.length})` });
  return tabs;
}

function renderTabButtons(d) {
  const tabs = draftTabList(d);
  if (!tabs.some((t) => t.key === draftTab)) draftTab = 'sent';
  $('dTabs').replaceChildren(...tabs.map((t) => el('button', {
    role: 'tab', class: 'tab', 'data-tab': t.key, 'aria-selected': String(t.key === draftTab),
    onclick: () => { draftTab = t.key; showDraftTab(); },
  }, t.title)));
  showDraftTab();
}

// The paste box keeps its text when the tabs are rebuilt.
const pastePanel = el('div', { class: 'paste-wrap', 'data-key': 'paste' },
  el('div', { class: 'muted' }, "Paste the AI chat's whole answer here. Mukhota puts the real names back on this computer; nothing is sent anywhere."),
  el('textarea', { class: 'mono', placeholder: '<<<REPLY>>> ...' }),
  el('div', { class: 'btn-row' }, el('button', { class: 'primary', onclick: () => usePaste() }, 'Use this answer')));

async function usePaste() {
  draftTab = 'sent';
  const r = await act('draft/paste', { opts: draftOpts(), text: pastePanel.querySelector('textarea').value });
  if (!r) draftTab = 'paste';
  renderTabButtons(S.draft);
}

function buildDraftTabs(d) {
  if (d.hasOutput && ['sent', 'paste'].includes(draftTab) && d.sections.length) draftTab = d.sections[0].key;
  const panels = [];
  const sent = el('textarea', { readonly: true, class: 'mono', 'data-key': 'sent', placeholder: howMode === 'prompt' ? 'Click "Make prompt" to build the prompt to copy.' : 'Click "Preview what will be sent" to see exactly what the model will receive.' });
  sent.value = d.preview;
  panels.push(sent);
  for (const s of d.sections) {
    const ta = el('textarea', { 'data-key': s.key, 'data-section': s.key, placeholder: '(The model did not return this section.)' });
    ta.value = s.text;
    panels.push(ta);
  }
  if (d.hasOutput) {
    const rows = d.placeholders.map((p) => {
      const input = el('input', { type: 'text', 'data-ph': p.ph });
      input.value = p.value;
      return el('tr', {}, el('td', {}, p.ph), el('td', {}, input));
    });
    panels.push(el('div', { class: 'ph-wrap', 'data-key': 'ph' },
      el('div', { class: 'muted' }, 'Fill in the facts the model did not have. These values are used only on this computer, when saving the Word files; they are never sent to any AI provider. Blank rows stay as [[...]] in the files.',
        d.known ? el('div', {}, el('b', {}, `${d.known} value(s) pre-filled from this client's facts sheet.`)) : null),
      rows.length ? el('table', { class: 'ph-table' }, el('tr', {}, el('th', {}, 'Placeholder in the draft'), el('th', {}, 'Your value (leave blank to keep it)')), ...rows)
        : el('div', { class: 'muted' }, 'No placeholders in this draft.')));
  }
  panels.push(pastePanel);
  $('dPanels').replaceChildren(...panels);
  $('rememberRow').hidden = !d.hasOutput;
  renderTabButtons(d);
}

async function copyPrompt() {
  const text = S.draft && S.draft.preview;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {  // clipboard API unavailable: select the text and copy the old way
    const ta = $('dPanels').querySelector('textarea[data-key="sent"]');
    ta.hidden = false; ta.select(); document.execCommand('copy'); showDraftTab();
  }
  $('draftInfo').textContent = 'Prompt copied. Paste it into your AI chat, then paste its answer in the "Paste AI answer" tab.';
}

function showDraftTab() {
  for (const b of $('dTabs').children) b.setAttribute('aria-selected', String(b.dataset.tab === draftTab));
  for (const p of $('dPanels').children) p.hidden = p.dataset.key !== draftTab;
}

async function confirmSend(text, over) {
  const ok = await modal('Send for drafting', text, over
    ? [{ label: 'Send anyway', value: () => true }, { label: "Don't send", main: true, cancel: true, value: () => false }]
    : [{ label: 'No', cancel: true, value: () => false }, { label: 'Yes, send', main: true, value: () => true }]);
  if (ok) await act('draft/send', { opts: draftOpts() });
  else { S.msg = 'Not sent.'; $('draftInfo').textContent = S.msg; }
}

async function saveDraft() {
  const sections = {};
  for (const ta of $('dPanels').querySelectorAll('textarea[data-section]')) sections[ta.dataset.section] = ta.value;
  const values = {};
  for (const inp of $('dPanels').querySelectorAll('input[data-ph]')) values[inp.dataset.ph] = inp.value;
  const r = await act('draft/save', { sections, values, remember: $('dRemember').checked });
  if (r && r.msg) await alertBox('Saved', r.msg);
}

async function factsDialog() {
  let info = await api('draft/facts', {}).catch(() => null);
  if (!info) return;
  const years = {};          // year-wise values typed for other AYs before switching
  let ay = info.ay;
  const ayInput = el('input', { type: 'text', placeholder: 'e.g. 2024-25' });
  ayInput.value = ay;
  const inputs = {};
  const form = el('div', { class: 'facts-form' });
  const fill = (fields) => {
    form.replaceChildren(el('label', {}, 'Assessment year (for year-wise facts)'), ayInput);
    for (const f of fields) {
      const inp = inputs[f.key] && !f.perYear ? inputs[f.key] : el('input', { type: 'text' });
      if (!(inputs[f.key] && !f.perYear)) inp.value = (years[ay] && years[ay][f.key] !== undefined) ? years[ay][f.key] : f.value;
      inp.dataset.perYear = f.perYear ? '1' : '';
      inputs[f.key] = inp;
      form.append(el('label', {}, f.label + (f.perYear ? '  (this AY)' : '')), inp);
    }
  };
  fill(info.fields);
  ayInput.addEventListener('change', async () => {
    const next = ayInput.value.trim();
    if (next === ay) return;
    years[ay] = Object.fromEntries(Object.entries(inputs).filter(([, i]) => i.dataset.perYear).map(([k, i]) => [k, i.value]));
    ay = next;
    const r = await api('draft/facts', { ay }).catch(() => null);
    if (r) fill(r.fields);
  });
  const ok = await modal(`Client facts — ${info.client}`, [form,
    el('p', { class: 'muted' }, 'Used only to fill [[TO CONFIRM]] placeholders on this computer. Never sent to any AI provider.')],
  [{ label: 'Cancel', cancel: true, value: () => false }, { label: 'Save', main: true, value: () => true }]);
  if (!ok) return;
  const finalAy = ayInput.value.trim();
  if (finalAy !== ay) {   // typed a new AY and pressed Save straight away
    years[ay] = Object.fromEntries(Object.entries(inputs).filter(([, i]) => i.dataset.perYear).map(([k, i]) => [k, i.value]));
  }
  delete years[finalAy];
  const values = Object.fromEntries(Object.entries(inputs).map(([k, i]) => [k, i.value]));
  await act('draft/facts-save', { ay: finalAy, values, years });
}

// ---------------------------------------------------------------- Settings
function masterRow(r) {
  const cells = r.map((v) => { const i = el('input', { type: 'text' }); i.value = v; return i; });
  const tr = el('tr', {}, ...cells.map((c) => el('td', {}, c)),
    el('td', {}, el('button', { class: 'del', title: 'Remove row', 'aria-label': 'Remove row', onclick: () => tr.remove() }, '✕')));
  return tr;
}

async function openSettings() {
  const s = await api('settings', {}).catch(() => null);
  if (!s) return;
  $('sOfficer').checked = s.redactOfficer;
  $('sPropagate').checked = s.propagate;
  $('sAccept').value = s.acceptThreshold;
  $('sLowConf').value = s.lowConf;
  $('sDpi').value = s.dpi;
  $('sOut').value = s.outputRoot;
  $('sAllowText').value = s.allowlist;
  $('sMasterRows').replaceChildren(...s.master.map(masterRow));
  $('sKeyState').textContent = s.hasKey ? 'A key is saved' : 'No key saved';
  $('sKey').value = '';
  claudeModels = s.claudeModels;
  noPdfWebText = s.noPdfWeb;
  provEdit = Object.fromEntries(s.providers.map((p) => [p.id, { ...p, apiKey: '' }]));
  $('pSelect').replaceChildren(...s.providers.map((p) => el('option', { value: p.id }, p.label)));
  pShown = '';
  showProvider(s.providers[0].id);
  defaultModels(s.model);
  $('sEffort').replaceChildren(...s.efforts.map((e) => el('option', { value: e }, e)));
  $('sEffort').value = s.effort;
  $('sWeb').value = s.webMax;
  $('sLimit').value = s.limit;
  $('sSpent').textContent = `Spent this month: $${s.spent.toFixed(2)}`;
  settingsTab('sGeneral');
  $('settingsSheet').hidden = false;
}

function settingsTab(id) {
  for (const b of $('sTabs').children) b.setAttribute('aria-selected', String(b.dataset.tab === id));
  for (const p of document.querySelectorAll('.s-panel')) p.hidden = p.id !== id;
}

// Other providers: edited one at a time, kept here until Save.
let provEdit = {}, pShown = '', claudeModels = [], noPdfWebText = '';
const P_FIELDS = { pUrl: 'baseUrl', pModel: 'model', pKey: 'apiKey', pIn: 'priceIn', pOut: 'priceOut', pSearch: 'priceSearch', pMax: 'maxTokens' };

function storeProvider() {
  const p = provEdit[pShown];
  if (!p) return;
  for (const [id, key] of Object.entries(P_FIELDS)) p[key] = $(id).type === 'number' ? Number($(id).value || 0) : $(id).value;
}

function showProvider(pid) {
  storeProvider();
  pShown = pid;
  const p = provEdit[pid];
  $('pSelect').value = pid;
  for (const [id, key] of Object.entries(P_FIELDS)) $(id).value = p[key] ?? '';
  $('pUrl').readOnly = !p.urlEditable;
  $('pUrl').placeholder = p.urlEditable ? 'https://... (http:// only for this computer)' : '';
  $('pModel').placeholder = p.example ? `e.g. ${p.example}` : 'Model name';
  $('pKeyState').textContent = !p.needsKey ? 'No key needed' : p.hasKey ? 'A key is saved' : 'No key saved';
  $('pKeyRow').hidden = $('pKeyBtns').hidden = !p.needsKey && !p.hasKey;
  $('pSearchRow').hidden = !p.web;
  $('pCaps').textContent = p.pdf && p.web ? 'Reads the redacted PDF and can search the web, like Claude.' : noPdfWebText || 'Text only.';
}

function defaultModels(selected) {
  storeProvider();
  const keep = selected ?? $('sModel').value;
  const opts = [...claudeModels.map((m) => ({ id: m.id, label: m.label })),
    ...Object.values(provEdit).filter((p) => String(p.model).trim() && String(p.baseUrl).trim())
      .map((p) => ({ id: 'p:' + p.id, label: `${p.label} - ${p.model}` }))];
  $('sModel').replaceChildren(...opts.map((m) => el('option', { value: m.id }, m.label)));
  $('sModel').value = opts.some((m) => m.id === keep) ? keep : opts[0].id;
}

async function saveSettings() {
  storeProvider();
  const body = {
    redactOfficer: $('sOfficer').checked, propagate: $('sPropagate').checked,
    acceptThreshold: Number($('sAccept').value), lowConf: Number($('sLowConf').value), dpi: Number($('sDpi').value),
    outputRoot: $('sOut').value, allowlist: $('sAllowText').value,
    master: [...$('sMasterRows').children].map((tr) => [...tr.querySelectorAll('input')].map((i) => i.value)),
    apiKey: $('sKey').value, model: $('sModel').value, effort: $('sEffort').value,
    webMax: Number($('sWeb').value), limit: Number($('sLimit').value),
    providers: Object.fromEntries(Object.values(provEdit).map((p) => [p.id, {
      baseUrl: p.baseUrl, model: p.model, apiKey: p.apiKey, priceIn: p.priceIn, priceOut: p.priceOut,
      priceSearch: p.priceSearch, maxTokens: p.maxTokens }])),
  };
  const r = await act('settings/save', body);
  $('sKey').value = '';
  $('pKey').value = '';
  for (const p of Object.values(provEdit)) p.apiKey = '';
  if (r) $('settingsSheet').hidden = true;
}

// ---------------------------------------------------------------- Case Register
const CASE_COLS = [['client', 'Client'], ['file', 'Notice'], ['section', 'Section'], ['ay', 'AY'],
  ['noticeDate', 'Notice date'], ['dueIso', 'Due date'], ['due', 'Due'], ['status', 'Status']];
let reg = null;            // last register listing
let selCase = null;
let caseSort = null;       // [key, direction] or null for soonest-due order

async function openRegister() {
  const r = await api('register', {}).catch(() => null);
  if (!r) return;
  showRegister(r);
  $('registerSheet').hidden = false;
}

function showRegister(r) {
  reg = r;
  if (!r.cases.some((c) => c.id === selCase)) selCase = null;
  $('registerSummary').textContent = `${r.cases.length} notice(s). ${r.soon} not filed and due within 7 days or overdue.`;
  $('registerHead').replaceChildren(...CASE_COLS.map(([k, label]) => el('th', {
    class: 'sortable', title: 'Sort', onclick: () => {
      caseSort = caseSort && caseSort[0] === k ? (caseSort[1] > 0 ? [k, -1] : null) : [k, 1];
      showRegister(reg);
    },
  }, label + (caseSort && caseSort[0] === k ? (caseSort[1] > 0 ? ' ▲' : ' ▼') : ''))));
  let rows = [...r.cases];
  if (caseSort) {
    const [k, dir] = caseSort;
    rows.sort((a, b) => dir * String(a[k] ?? '').localeCompare(String(b[k] ?? ''), undefined, { numeric: true }));
  }
  $('registerRows').replaceChildren(...(rows.length ? rows.map((c) => el('tr', {
    class: c.id === selCase ? 'sel' : '',
    onclick: () => { selCase = c.id; showRegister(reg); },
    ondblclick: () => { selCase = c.id; editCase(); },
  }, el('td', {}, c.client || '(not yet known)'), el('td', {}, c.file), el('td', {}, c.section), el('td', {}, c.ay),
  el('td', {}, c.noticeDate), el('td', { class: c.urgency }, c.dueDate), el('td', { class: c.urgency }, c.due),
  el('td', {}, el('span', { class: 'status-pill ' + c.status }, c.status))))
    : [el('tr', {}, el('td', { colspan: '8', class: 'muted' }, 'No notices yet. Every notice you open is added here.'))]));
  for (const id of ['btnCaseEdit', 'btnCaseFiled', 'btnCaseRemove']) $(id).disabled = selCase === null;
  const sel = r.cases.find((c) => c.id === selCase);
  $('btnCaseFolder').disabled = !sel || !sel.hasFolder;
}

async function caseCall(path, body) {
  const r = await api(path, body).catch(() => null);
  if (r && r.cases) showRegister(r);
}

async function editCase() {
  const c = reg && reg.cases.find((x) => x.id === selCase);
  if (!c) return;
  const client = el('input', { type: 'text' });
  client.value = c.client;
  const due = el('input', { type: 'date' });
  due.value = c.dueIso;
  const status = el('select', {}, ...reg.statuses.map((s) => el('option', { value: s }, s)));
  status.value = c.status;
  const form = el('div', { class: 'facts-form' },
    el('label', {}, 'Notice'), el('div', {}, c.file),
    el('label', {}, 'Client'), client, el('label', {}, 'Reply due date'), due, el('label', {}, 'Status'), status);
  const ok = await modal('Edit case', form, [{ label: 'Cancel', cancel: true, value: () => false }, { label: 'Save', main: true, value: () => true }]);
  if (ok) await caseCall('register/update', { id: c.id, client: client.value, due: due.value, status: status.value });
}

async function showReminder() {
  const r = await api('reminder', {}).catch(() => null);
  const rem = r && r.reminder;
  if (!rem) return;
  $('reminderTitle').textContent = `${rem.count} repl${rem.count === 1 ? 'y' : 'ies'} due within 7 days` + (rem.overdue ? ` (${rem.overdue} overdue)` : '') + ':';
  $('reminderLines').textContent = rem.lines.join('  ·  ') + (rem.count > rem.lines.length ? '  ·  …' : '');
  $('reminder').hidden = false;
}

// ---------------------------------------------------------------- wiring
for (const b of document.querySelectorAll('.tool')) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', ICONS[b.dataset.icon]);
  svg.append(p);
  b.prepend(svg);
  b.addEventListener('click', () => doAction(b.dataset.act));
}
$('btnPrimary').addEventListener('click', () => doAction(S.flow.action));
$('btnPrev').addEventListener('click', () => showPage(current - 1));
$('btnNext').addEventListener('click', () => showPage(current + 1));
$('pageSelect').addEventListener('change', (e) => showPage(Number(e.target.value)));
$('chkReviewed').addEventListener('change', (e) => act('reviewed', { page: current, on: e.target.checked }));
$('btnCompare').addEventListener('click', () => setCompare(!compare));
const paperWidth = () => ($('pagesOrig').firstElementChild || {}).clientWidth || 800;
$('btnZoomIn').addEventListener('click', () => { zoom = Math.round(paperWidth() * 1.25); applyZoom(); });
$('btnZoomOut').addEventListener('click', () => { zoom = Math.max(200, Math.round(paperWidth() * 0.8)); applyZoom(); });
$('btnFit').addEventListener('click', () => { zoom = 0; applyZoom(); });
$('bannerClose').addEventListener('click', () => { $('banner').hidden = true; });
$('btnAll').addEventListener('click', () => setAccepted(visible().map((c) => c.cid), true));
$('btnNone').addEventListener('click', () => setAccepted(visible().map((c) => c.cid), false));
for (const [tab, panel, other, otherPanel] of [['tabItems', 'panelItems', 'tabDraft', 'panelDraft'], ['tabDraft', 'panelDraft', 'tabItems', 'panelItems']]) {
  $(tab).addEventListener('click', () => {
    $(tab).setAttribute('aria-selected', 'true'); $(other).setAttribute('aria-selected', 'false');
    $(panel).hidden = false; $(otherPanel).hidden = true;
  });
}
$('btnOpenDraft').addEventListener('click', () => doAction('draft'));
$('btnAbout').addEventListener('click', () => doAction('about'));
$('btnPreview').addEventListener('click', () => act('draft/preview', { opts: draftOpts() }));
$('btnSend').addEventListener('click', () => act('draft/estimate', { opts: draftOpts() }));
$('btnSave').addEventListener('click', saveDraft);
$('btnMakePrompt').addEventListener('click', () => { draftTab = 'sent'; act('draft/prompt', { opts: draftOpts() }); });
$('btnCopyPrompt').addEventListener('click', copyPrompt);
$('btnSavePrompt').addEventListener('click', async () => {
  const r = await act('draft/prompt-save', {});
  if (r && r.msg) await alertBox('Prompt saved', r.msg);
});
$('btnFacts').addEventListener('click', factsDialog);
$('btnDraftFolder').addEventListener('click', () => act('draft/folder'));
$('btnDraftClose').addEventListener('click', async () => {
  if (S.draft && S.draft.hasOutput && !(await confirmBox('Close Draft Reply', 'Close Draft Reply? Anything not saved as Word will be lost.', 'Close'))) return;
  await act('draft/close');
});
for (const b of $('sTabs').children) b.addEventListener('click', () => settingsTab(b.dataset.tab));
$('btnSettingsCancel').addEventListener('click', () => {
  $('sKey').value = ''; $('pKey').value = ''; provEdit = {}; pShown = ''; $('settingsSheet').hidden = true;
});
$('btnSettingsSave').addEventListener('click', saveSettings);
$('btnAddRow').addEventListener('click', () => { const tr = masterRow(['', 'NAME', '']); $('sMasterRows').append(tr); tr.querySelector('input').focus(); });
$('btnRemoveKey').addEventListener('click', async () => {
  if (!(await confirmBox('Remove saved key', 'Remove the saved Claude API key from Windows Credential Manager?', 'Remove'))) return;
  if (await act('settings/remove-key', { provider: 'claude' })) $('sKeyState').textContent = 'No key saved';
});
$('pSelect').addEventListener('change', (e) => showProvider(e.target.value));
for (const id of ['pModel', 'pUrl']) $(id).addEventListener('change', () => defaultModels());
$('btnRemovePKey').addEventListener('click', async () => {
  const p = provEdit[pShown];
  if (!p || !(await confirmBox('Remove saved key', `Remove the saved ${p.label} API key from Windows Credential Manager?`, 'Remove'))) return;
  if (await act('settings/remove-key', { provider: p.id })) { p.hasKey = false; showProvider(p.id); }
});
$('dModel').addEventListener('change', applyModelCaps);
$('dWeb').addEventListener('change', (e) => { if (!e.target.disabled) webWanted = e.target.checked; });
$('btnBrowse').addEventListener('click', async () => {
  const r = await api('settings/browse', {}).catch(() => null);
  if (r && r.folder) $('sOut').value = r.folder;
});
$('btnRegisterClose').addEventListener('click', () => { $('registerSheet').hidden = true; });
$('btnCaseEdit').addEventListener('click', editCase);
$('btnCaseFiled').addEventListener('click', () => caseCall('register/update', (() => {
  const c = reg.cases.find((x) => x.id === selCase);
  return { id: c.id, client: c.client, due: c.dueIso, status: 'Filed' };
})()));
$('btnCaseFolder').addEventListener('click', () => caseCall('register/folder', { id: selCase }));
$('btnCaseRemove').addEventListener('click', async () => {
  if (await confirmBox('Remove', 'Remove this notice from the register? Files are not deleted.', 'Remove')) {
    await caseCall('register/delete', { id: selCase });
  }
});
$('btnReminderOpen').addEventListener('click', () => { $('reminder').hidden = true; openRegister(); });
$('btnReminderClose').addEventListener('click', () => { $('reminder').hidden = true; });
$('btnQuit').addEventListener('click', async () => {
  if (S && S.busy && !(await confirmBox('Quit', 'Work is still running. Quit anyway?', 'Quit'))) return;
  try { await api('quit', {}); } catch (e) { /* already stopping */ }
  stopped();
});
// Side by side: keep both panes scrolled to the same place.
$('paneOrig').addEventListener('scroll', () => {
  if (!S || !S.pages.length) return;
  const i = pageInView();
  if (i !== current) { current = i; updateNav(); }
});
let syncing = false;
for (const [a, b] of [['paneOrig', 'paneAfter'], ['paneAfter', 'paneOrig']]) {
  $(a).addEventListener('scroll', () => {
    if (syncing || !compare) return;
    syncing = true;
    $(b).scrollTop = $(a).scrollTop;
    $(b).scrollLeft = $(a).scrollLeft;
    requestAnimationFrame(() => { syncing = false; });
  });
}
window.addEventListener('resize', () => { if (!zoom) applyZoom(); });
document.addEventListener('keydown', (e) => {
  if (!$('modalBack').hidden || !$('draftSheet').hidden || !$('settingsSheet').hidden
      || !$('registerSheet').hidden
      || ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  if (e.key === 'PageDown') { e.preventDefault(); showPage(current + 1); }
  if (e.key === 'PageUp') { e.preventDefault(); showPage(current - 1); }
});

refresh().then(showReminder).catch(() => {});
