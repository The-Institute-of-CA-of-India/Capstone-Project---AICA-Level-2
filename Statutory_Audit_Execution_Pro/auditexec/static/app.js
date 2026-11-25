/* Statutory Audit Execution Pro v4 - front end */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const S = { user: null, meta: null, people: [], engs: [], mywork: [], eid: null, eng: null, prog: null, adverse: [], code: null, area: null, tab: 'steps', filter: 'all', dirty: {}, q: '', collapsed: {} };
const isP = () => S.user.role === 'Partner', isPS = () => S.user.role !== 'Junior';
const roleName = r => S.meta.role_label[r] || r;

async function api(url, opt = {}) {
  const o = { method: opt.method || 'GET', headers: {} };
  if (opt.json !== undefined) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(opt.json); }
  if (opt.form) o.body = opt.form;
  let r; try { r = await fetch(url, o); } catch (e) { throw new Error('Cannot reach the server. Check your network connection.'); }
  let d = {}; try { d = await r.json(); } catch (e) {}
  if (r.status === 401 && url !== '/api/login') { S.user = null; render(); throw new Error('Your session has ended. Please sign in again.'); }
  if (!r.ok) throw new Error(d.error || 'Something went wrong.');
  return d;
}
function toast(msg, bad) { const t = document.createElement('div'); t.className = 'toast' + (bad ? ' bad' : ''); t.textContent = msg; $('#toast').append(t); setTimeout(() => t.remove(), bad ? 7000 : 3200); }
const today = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
const MON = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
function isoFrom(txt) { const m = /^(\d{1,2})-(\w{3})-(\d{4})/.exec(txt || ''); if (!m) return ''; const i = MON.indexOf(m[2].toLowerCase()); return i < 0 ? '' : `${m[3]}-${String(i + 1).padStart(2, '0')}-${m[1].padStart(2, '0')}`; }

/* ----- unsaved-work tracking: keys step<n> | concl | evna | q<id> ----- */
const nDirty = () => Object.keys(S.dirty).length;
function markDirty(key, val) { S.dirty[key] = val; updateSaveBar(); }
function updateSaveBar() {
  const b = $('#savebar'); if (!b) return; const n = nDirty();
  b.classList.toggle('dirty', n > 0); $('#sv_msg').textContent = n ? `${n} unsaved change${n > 1 ? 's' : ''}` : 'All work saved'; $('#sv_btn').disabled = !n;
}
async function saveAll() {
  let n = 0;
  for (const k of Object.keys(S.dirty)) {
    const d = S.dirty[k];
    try {
      if (k.startsWith('step')) await api(`/api/engagements/${S.eid}/areas/${S.code}/step/${k.slice(4)}`, { method: 'PUT', json: d });
      else if (k === 'concl' || k === 'evna') await saveWp(d);
      else if (k.startsWith('q')) await api('/api/queries/' + k.slice(1), { method: 'PUT', json: { management_response: d.text, close: false } });
    } catch (e) { throw new Error((k.startsWith('step') ? 'Step ' + k.slice(4) + ': ' : '') + e.message); }
    delete S.dirty[k]; n++;
  }
  return n;
}
const doSave = () => run(async () => {
  if (!nDirty()) return toast('Nothing to save – all work is already saved');
  let n = 0; try { n = await saveAll(); } finally { await reloadArea(); } toast(`Work saved (${n} item${n > 1 ? 's' : ''})`);
});
/* Ask before leaving the current module / company when something is unsaved */
function leave(next, label) {
  const n = nDirty(); if (!n) return next();
  const A = S.area, t = A ? `WP ${A.topic.no} · ${esc(A.topic.title)}` : 'this module';
  modal(`<h2>Save your work?</h2><div style="width:460px"><p style="margin:0 0 4px">You have <b>${n} unsaved change${n > 1 ? 's' : ''}</b> in <b>${t}</b>.</p><p class="muted" style="margin:0">Saved work is stored on the server and stays available to the whole team.</p>
  <div class="inline mt"><button class="btn gold" id="lv_s">Save and ${label || 'continue'}</button><button class="btn ghost" id="lv_d">Don’t save</button><button class="btn ghost right" id="lv_c">Stay here</button></div></div>`, true);
  $('#lv_c').onclick = closeModal;
  $('#lv_d').onclick = () => { S.dirty = {}; closeModal(); next(); };
  $('#lv_s').onclick = () => run(async () => { await saveAll(); closeModal(); toast('Work saved'); next(); });
}
const navTo = code => { if (code === S.code) return; leave(() => run(() => goArea(code))); };
function exitCompany() {
  const go = async () => { S.eid = null; S.code = null; S.area = null; S.dirty = {}; S.q = ''; await boot(); render(); };
  const name = esc(S.eng ? S.eng.client_name : 'this company');
  if (nDirty()) return leave(() => run(go), 'exit');
  modal(`<h2>Exit ${name}?</h2><div style="width:420px"><p style="margin:0">All your work in this company is saved. You will return to the list of engagements.</p><div class="inline mt"><button class="btn gold" id="ex_y">Exit company</button><button class="btn ghost right" id="ex_n">Stay here</button></div></div>`, true);
  $('#ex_n').onclick = closeModal; $('#ex_y').onclick = () => run(async () => { closeModal(); await go(); });
}
const signOut = () => leave(async () => { await api('/api/logout', { method: 'POST' }); S.user = null; S.eid = null; S.dirty = {}; render(); }, 'sign out');
window.addEventListener('beforeunload', e => { if (nDirty()) { e.preventDefault(); e.returnValue = ''; } });
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && S.user && S.code && S.area && !S.area.locked && S.area.wp.applicability === 'Applicable') { e.preventDefault(); doSave(); } });

const run = async fn => { try { await fn(); } catch (e) { toast(e.message, true); } };

const ADV = /(qualif\w*|disclaim\w*|adverse\w*|unable to|not able to|could not|cannot be|not provided|not received|not confirmed|not furnished|not available|not produced|not submitted|not obtained|non[- ]?compliance|not complied|not in compliance|violat\w*|breach\w*|misstate\w*|discrepanc\w*|shortfall|short provision|under[- ]?provi\w*|scope (limitation|restriction)|limitation of scope|fraud\w*|irregular\w*|overdue|not reconciled|unreconciled|material (weakness|uncertainty|misstatement)|deficien\w*|doubt\w*|emphasis of matter|subject to|disagree\w*|not satisfactory|unsatisfactory|exception\w*|not recorded|not accounted|not disclosed|non[- ]?disclosure|penalt\w*|default\w*|lapse\w*|delay\w*)/gi;
const NEG = /\b(no|nil|without|zero|not any|none)\s+(\w+\s+)?$/i;
function hl(text) {
  text = String(text ?? ''); let out = '', pos = 0, m; ADV.lastIndex = 0;
  while ((m = ADV.exec(text))) { if (NEG.test(text.slice(Math.max(0, m.index - 18), m.index))) continue; out += esc(text.slice(pos, m.index)) + '<mark>' + esc(m[0]) + '</mark>'; pos = m.index + m[0].length; }
  return (out + esc(text.slice(pos))).replace(/\n/g, '<br>');
}
const hasAdv = t => hl(t).includes('<mark>');
function wfBadge(a) {
  if (a.na) return '<span class="badge b-mute">Not applicable</span>';
  if (a.undecided) return '<span class="badge b-gold">Decide applicability</span>';
  return { Reviewed: '<span class="badge b-ok">✓ Reviewed</span>', Compiled: '<span class="badge b-blue">Awaiting review</span>', Returned: '<span class="badge b-bad">Returned</span>' }[a.workflow]
    || (a.state === 'Complete' ? '<span class="badge b-warn">Ready to compile</span>' : a.state === 'In progress' ? '<span class="badge b-warn">In progress</span>' : '<span class="badge b-mute">Not started</span>');
}
const dotClass = (a, adv) => adv ? 'adv' : a.na ? 'na' : a.undecided ? 'undec' : a.workflow === 'Reviewed' ? 'complete' : a.workflow === 'Compiled' ? 'blue' : a.state === 'Complete' ? 'complete' : a.state === 'In progress' ? 'partial' : 'empty';

/* ================= shell / routing ================= */
function render() { S.user ? (S.eid ? shell() : home()) : login(); }
function modal(html, locked) { $('#modal').innerHTML = `<div class="mbox">${html}</div>`; $('#modal').classList.remove('hidden'); $('#modal').onclick = e => { if (!locked && e.target.id === 'modal') closeModal(); }; }
function closeModal() { $('#modal').classList.add('hidden'); $('#modal').innerHTML = ''; }
window.closeModal = closeModal;

function login() {
  $('#app').innerHTML = `<div class="login">
  <div class="login-art"><div><div class="firm">KHARE DESHMUKH & CO. · CHARTERED ACCOUNTANTS</div><h1>Statutory Audit<br>Execution Pro</h1>
  <p>One workspace for statutory audit programmes, evidence, queries and conclusions — compiled by the team, reviewed by the Partner.</p></div>
  <ul><li>Live completion status for every audit module</li><li>Compiled-by and reviewed-by recorded on each working paper</li><li>Complete working-paper file with adverse remarks highlighted</li></ul></div>
  <div class="login-form"><form class="login-box" id="lf" autocomplete="on"><h2>Welcome back</h2><div class="sub">Sign in to your audit workspace</div>
  <label for="u">Username</label><input id="u" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" autofocus>
  <label for="p">Password</label><div class="pw"><input id="p" name="password" type="password" autocomplete="current-password"><button type="button" id="eye" tabindex="-1">Show</button></div>
  <div class="err" id="err"></div><button class="btn block gold" type="submit">Sign in</button>
  <div class="demo">Logins are issued by the Partner. If you have forgotten your password, ask the Partner to reset it.</div></form></div></div>`;
  $('#eye').onclick = () => { const p = $('#p'), h = p.type === 'password'; p.type = h ? 'text' : 'password'; $('#eye').textContent = h ? 'Hide' : 'Show'; p.focus(); };
  $('#lf').onsubmit = async ev => { ev.preventDefault(); $('#err').textContent = '';
    try { S.user = await api('/api/login', { method: 'POST', json: { username: $('#u').value, password: $('#p').value } }); await boot(); render(); if (S.user.must_change) changePw(true); }
    catch (e) { $('#err').textContent = e.message; } };
}
async function boot() { [S.engs, S.mywork, S.people] = await Promise.all([api('/api/engagements'), api('/api/my-work'), api('/api/people')]); }

function accountMenu() {
  return `<div class="menu" id="acct"><button class="btn ghost" id="acb">${esc(S.user.name)} · ${roleName(S.user.role)} ▾</button><div class="dd">
  ${isP() ? '<a id="m_users">👥 Manage users & roles</a><a id="m_bak">💾 Backup & restore</a><hr>' : ''}<a id="m_pw">🔑 Change my password</a><a id="m_out">Sign out</a></div></div>`;
}
function bindAccount() {
  const m = $('#acct'); $('#acb').onclick = e => { e.stopPropagation(); m.classList.toggle('open'); }; document.onclick = () => m.classList.remove('open');
  $('#m_pw').onclick = () => changePw(false); $('#m_out').onclick = signOut;
  if ($('#m_users')) $('#m_users').onclick = manageUsers; if ($('#m_bak')) $('#m_bak').onclick = backups;
}

function home() {
  $('#app').innerHTML = `<div style="max-width:1120px;margin:0 auto;padding:36px 30px 60px"><div class="top"><div><div style="letter-spacing:.2em;font-size:11px;font-weight:700;color:var(--gold)">STATUTORY AUDIT EXECUTION PRO</div><h1>Audit engagements</h1>
  <div class="crumb">Welcome, ${esc(S.user.name)}</div></div><div class="inline">${isPS() ? '<button class="btn gold" id="ne">+ New engagement</button>' : ''}${accountMenu()}</div></div>
  ${S.mywork.length ? `<div class="sec" style="margin-top:0"><h2>My assigned modules</h2></div><div class="mywork">${S.mywork.map(w => `<div class="mw" data-e="${w.eid}" data-c="${w.topic_code}"><b>${esc(w.client_name)}</b><span class="muted">FY ${esc(w.financial_year)}</span><span>${esc(w.title)}</span><span class="right muted">${w.due_date ? 'Due ' + esc(w.due_date) : ''}</span><span class="badge b-warn">${esc(w.workflow)}</span></div>`).join('')}</div>` : ''}
  <div class="sec"><h2>All engagements</h2></div><div class="grid g2" id="el"></div></div>`;
  bindAccount(); if ($('#ne')) $('#ne').onclick = newEng;
  $('#el').innerHTML = S.engs.length ? S.engs.map(e => `<div class="card eng-card" data-id="${e.id}"><div class="inline"><h2>${esc(e.client_name)}</h2><span class="badge b-blue right">FY ${esc(e.financial_year)}</span></div>
    <div class="muted" style="margin:4px 0 14px">${esc(e.entity_type)} · ${esc(e.framework || '')}</div><div class="inline"><b>${e.pct}%</b><span class="muted">complete · ${e.compiled + e.reviewed}/${e.live_areas} compiled · ${e.reviewed} reviewed by Partner · ${e.open_queries} open queries</span></div>
    <div class="bar mt"><i style="width:${e.pct}%"></i></div></div>`).join('') : '<div class="card"><h2>No engagements yet</h2><p class="muted">A Partner or Sr Staff member can create one using “New engagement”.</p></div>';
  document.querySelectorAll('.eng-card').forEach(c => c.onclick = () => openEng(+c.dataset.id));
  document.querySelectorAll('.mw').forEach(c => c.onclick = () => run(async () => { S.eid = +c.dataset.e; S.dirty = {}; await refresh(); S.code = c.dataset.c; S.tab = 'steps'; S.area = await api(`/api/engagements/${S.eid}/areas/${S.code}`); shell(); }));
}
function newEng() {
  modal(`<h2>Create audit engagement</h2><div style="width:520px"><label>Client / entity name</label><input id="n_c">
  <div class="two"><div><label>Financial year</label><input id="n_f" value="2025-26"></div><div><label>Target completion</label><input id="n_d" type="date"></div></div>
  <div class="two"><div><label>Type of entity</label><select id="n_t">${S.meta.entity_types.map(x => `<option>${x}</option>`).join('')}</select></div>
  <div><label>Accounting framework</label><select id="n_w"><option>Accounting Standards (AS)</option><option>Indian Accounting Standards (Ind AS)</option><option>Other / Not applicable</option></select></div></div>
  <label>Overall materiality (₹) — enter 0 if not yet decided</label><input id="n_m" value="0">
  <div class="note info">Audit modules that apply only to companies (CARO, secretarial, ESOP) are shown automatically for companies.</div>
  <div class="inline mt"><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn gold right" id="n_s">Create engagement</button></div></div>`);
  $('#n_s').onclick = () => run(async () => { const r = await api('/api/engagements', { method: 'POST', json: { client_name: $('#n_c').value, financial_year: $('#n_f').value, deadline: $('#n_d').value, entity_type: $('#n_t').value, framework: $('#n_w').value, materiality: $('#n_m').value } }); closeModal(); await boot(); openEng(r.id); });
}
async function openEng(id) { S.eid = id; S.code = null; S.dirty = {}; S.filter = 'all'; await refresh(); render(); }
async function refresh() {
  const d = await api('/api/engagements/' + S.eid); S.eng = d.engagement; S.prog = d.progress; S.adverse = d.adverse;
  if (S.code) S.area = await api(`/api/engagements/${S.eid}/areas/${S.code}`);
}
async function goArea(code, tab) { if (code !== S.code) S.dirty = {}; S.code = code; S.tab = tab || 'steps'; S.area = await api(`/api/engagements/${S.eid}/areas/${code}`); shell(); }

function applyNavFilter() {
  const q = (S.q || '').trim().toLowerCase();
  document.querySelectorAll('.ng').forEach(g => { let any = false;
    g.querySelectorAll('a').forEach(a => { const m = !q || a.dataset.s.includes(q); a.classList.toggle('hid', !m); if (m) any = true; });
    g.classList.toggle('hid', !any); g.classList.toggle('searching', !!q); });
  const e = $('#nempty'); if (e) e.classList.toggle('hid', !q || !!document.querySelector('.ng:not(.hid)'));
}
function shell() {
  const navTop = $('.nav') ? $('.nav').scrollTop : 0, mainTop = $('#main') ? $('#main').scrollTop : 0, same = S._lc === S.code && S._lt === S.tab;
  const hi = new Set(S.adverse.filter(a => a.severity === 'High').map(a => a.code));
  const groups = S.meta.groups.map(g => { const as = S.prog.areas.filter(a => a.group === g); if (!as.length) return '';
    const done = as.filter(a => a.na || a.state === 'Complete').length;
    return `<div class="ng ${S.collapsed[g] ? 'shut' : ''}" data-g="${esc(g)}"><h4 class="gh"><span class="car">▾</span><span class="gt">${esc(g)}</span><span class="gc">${done}/${as.length}</span></h4><div class="gi">${as.map(a => `<a data-c="${a.code}" data-s="${esc((a.no + ' wp' + a.no + ' ' + a.title).toLowerCase())}" class="${S.code === a.code ? 'on' : ''}"><span class="wn">${a.no}</span><span class="dot ${dotClass(a, hi.has(a.code))}"></span><span class="t">${esc(a.title)}</span><span class="p">${a.na ? 'N/A' : a.undecided ? '?' : a.workflow === 'Reviewed' ? '✓' : a.pct + '%'}</span></a>`).join('')}</div></div>`; }).join('');
  $('#app').innerHTML = `<div class="shell"><aside class="side"><div class="brand"><div class="k">KHARE DESHMUKH & CO.</div><div class="n">Statutory Audit Execution Pro</div></div>
  <div class="eng" id="back" title="Exit this company"><b>${esc(S.eng.client_name)}</b><span>FY ${esc(S.eng.financial_year)} · ${S.prog.overall_pct}% complete</span></div>
  <button class="exitco" id="exitco">⏏ Exit company</button>
  <div class="navsearch"><input id="nq" placeholder="Find a module – number or name" autocomplete="off"></div>
  <div class="nav"><a id="dash" class="${!S.code ? 'on' : ''}"><span class="dot complete"></span><span class="t"><b>Dashboard & reports</b></span></a>${groups}<div class="nempty hid" id="nempty">No module matches your search.</div></div>
  <div class="foot"><span>${esc(S.user.name)} · ${roleName(S.user.role)}</span><a id="pwl" style="cursor:pointer;color:var(--gold2)">Sign out</a></div></aside><main class="main" id="main"></main></div>`;
  $('#pwl').onclick = signOut; $('#back').onclick = exitCompany; $('#exitco').onclick = exitCompany;
  $('#dash').onclick = () => leave(() => { S.dirty = {}; S.code = null; shell(); });
  document.querySelectorAll('.nav a[data-c]').forEach(a => a.onclick = () => navTo(a.dataset.c));
  document.querySelectorAll('.gh').forEach(h => h.onclick = () => { const g = h.parentElement; g.classList.toggle('shut'); S.collapsed[g.dataset.g] = g.classList.contains('shut'); });
  $('#nq').value = S.q; $('#nq').oninput = e => { S.q = e.target.value; applyNavFilter(); }; applyNavFilter();
  const nav = $('.nav'); nav.scrollTop = navTop; const on = $('.nav a.on');
  if (on) { const r = on.getBoundingClientRect(), nr = nav.getBoundingClientRect(); if (r.top < nr.top || r.bottom > nr.bottom) on.scrollIntoView({ block: 'center' }); }
  S.code ? areaView() : dashboard();
  if (same) $('#main').scrollTop = mainTop; S._lc = S.code; S._lt = S.tab;
}

/* ================= dashboard ================= */
function dashboard() {
  const P = S.prog, e = S.eng, high = S.adverse.filter(a => a.severity === 'High').length, live = P.areas.filter(a => !a.na);
  const queue = live.filter(a => a.workflow === 'Compiled'), pend = P.areas.filter(a => a.pending.length);
  const mine = P.areas.filter(a => a.assigned_to === S.user.id && a.workflow !== 'Reviewed' && !a.na);
  const F = { all: a => true, pending: a => !a.na && a.workflow !== 'Reviewed' && a.workflow !== 'Compiled', review: a => a.workflow === 'Compiled', done: a => a.workflow === 'Reviewed', adverse: a => S.adverse.some(x => x.code === a.code), mine: a => a.assigned_to === S.user.id };
  const shown = P.areas.filter(F[S.filter]);
  const readyPct = live.length ? Math.round(P.reviewed / live.length * 100) : 0;
  $('#main').innerHTML = `<div class="top"><div><h1>${esc(e.client_name)}</h1><div class="crumb">FY ${esc(e.financial_year)} · ${esc(e.entity_type)} · ${esc(e.framework)} · Materiality ₹${(+e.materiality || 0).toLocaleString('en-IN')} ${isPS() ? '<a href="#" id="mat" style="color:var(--blue)">edit</a>' : ''}</div></div>
  <div class="inline"><div class="menu" id="rep"><button class="btn gold" id="repb">Reports & tools ▾</button><div class="dd">
  <a href="/api/engagements/${S.eid}/export/working-paper">⬇ Complete working papers (Word)</a><a href="/report/${S.eid}" target="_blank">🖨 Complete working papers (print / PDF)</a><a href="/report/${S.eid}?part=summary" target="_blank">🖨 Partner summary – 1 view (print / PDF)</a>
  <a href="/api/engagements/${S.eid}/export/observations">⬇ Audit observations list (Word)</a><a href="/api/engagements/${S.eid}/export/queries">⬇ Query tracker (Excel)</a><hr><a id="t_bulk">📎 Bulk evidence upload</a><a id="t_log">🕘 Activity log</a>${isP() ? '<a id="t_roll">⏭ Roll over to next year</a>' : ''}</div></div>${accountMenu()}</div></div>
  <div class="hero"><div class="ring" style="--p:${P.overall_pct}"><div><b>${P.overall_pct}%</b><small>COMPLETE</small></div></div>
  <div><h2>${P.reviewed} of ${live.length} modules reviewed by Partner</h2><p>${P.compiled} compiled and awaiting Partner review · ${P.returned} returned to staff · ${P.pending_total} items pending across ${pend.length} modules.</p>
  <div class="bar" style="background:rgba(255,255,255,.18);max-width:520px"><i style="width:${readyPct}%;background:var(--gold2)"></i></div>
  <div class="hchips" style="margin-top:14px"><span class="hchip">Steps ${P.steps_done}/${P.steps_total}</span><span class="hchip">${P.files} evidence files</span><span class="hchip">${P.open_queries} open queries</span><span class="hchip">${P.open_notes} open review notes</span><span class="hchip">${S.adverse.length} adverse remarks</span>${P.undecided ? `<span class="hchip">${P.undecided} modules to decide</span>` : ''}</div></div></div>
  <div class="grid g5 mt"><div class="kpi ok"><div class="v">${P.complete}</div><div class="l">Content complete</div></div><div class="kpi warn"><div class="v">${P.compiled}</div><div class="l">Awaiting Partner review</div></div>
  <div class="kpi ok"><div class="v">${P.reviewed}</div><div class="l">Reviewed by Partner</div></div><div class="kpi warn"><div class="v">${P.open_queries}</div><div class="l">Open queries</div></div><div class="kpi bad"><div class="v">${high}</div><div class="l">High-priority adverse</div></div></div>
  ${isP() && queue.length ? `<div class="sec"><h2>Review queue – compiled modules awaiting you</h2></div><div class="card">${queue.map(a => `<div class="pendrow" data-c="${a.code}"><span class="muted">WP ${a.no}</span><div><div class="nm">${esc(a.title)}</div><small>Compiled by ${esc(a.compiled_by)} · ${esc(a.compiled_at)}${a.exceptions ? ' · ⚠ ' + a.exceptions + ' exception(s)' : ''}</small></div><button class="btn sm">Review →</button></div>`).join('')}</div>` : ''}
  ${!isP() && mine.length ? `<div class="sec"><h2>Assigned to me</h2></div><div class="card">${mine.map(a => `<div class="pendrow" data-c="${a.code}"><span class="muted">WP ${a.no}</span><div><div class="nm">${esc(a.title)}</div><small>${a.due_date ? 'Due ' + esc(a.due_date) + ' · ' : ''}${a.pending.map(esc).join(' · ') || 'Ready to compile'}</small></div>${wfBadge(a)}</div>`).join('')}</div>` : ''}
  <div class="sec"><h2>Audit modules</h2><div class="filters">${[['all', 'All'], ['pending', 'In progress'], ['review', 'Awaiting review'], ['done', 'Reviewed'], ['adverse', 'Adverse'], ['mine', 'Mine']].map(([k, l]) => `<button data-f="${k}" class="${S.filter === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
  <div class="areas">${shown.map(a => `<div class="area" data-c="${a.code}"><div class="h"><div><div class="code">WP ${a.no} · ${esc(a.group)}</div><div class="ti">${esc(a.title)}</div></div>${wfBadge(a)}</div>
  <div class="bar ${a.workflow === 'Reviewed' ? 'ok' : ''}"><i style="width:${a.pct}%"></i></div>
  ${a.na ? `<div class="muted" style="margin-top:8px;font-size:12px">${esc(a.na_reason)}</div>` : a.undecided ? '<div class="muted" style="margin-top:10px;font-size:12px">Applicability not yet decided – open the module and choose Applicable or Not applicable.</div>' : `<div class="tabs-mini"><span class="tm ${a.tabs.steps}">Steps ${a.steps_done}/${a.steps_total}</span><span class="tm ${a.tabs.evidence}">Evidence ${a.files}</span><span class="tm ${a.tabs.queries}">Queries</span><span class="tm ${a.tabs.conclusion}">Conclusion</span></div>
  <div class="muted" style="font-size:11.5px;margin-top:9px">${a.compiled_by ? 'Compiled by <b>' + esc(a.compiled_by) + '</b>' : a.assigned_name ? 'Assigned to <b>' + esc(a.assigned_name) + '</b>' : 'Not assigned'}${a.reviewed_by ? ' · Reviewed by <b>' + esc(a.reviewed_by) + '</b>' : ''}</div>`}</div>`).join('') || '<div class="muted">Nothing to show.</div>'}</div>
  <div class="sec"><h2>What is pending</h2></div><div class="card">${pend.length ? pend.map(a => `<div class="pendrow" data-c="${a.code}"><span class="muted">WP ${a.no}</span><div><div class="nm">${esc(a.title)}</div><small>${a.pending.map(esc).join(' · ')}</small></div>${wfBadge(a)}</div>`).join('') : '<div class="note ok">Nothing pending.</div>'}</div>
  <div class="sec"><h2>Adverse / negative / disclaimer remarks</h2></div>${adverseTable()}
  <div class="sec"><h2>Overall audit conclusion</h2></div>${overallForm()}`;
  const mm = $('#rep'); $('#repb').onclick = ev => { ev.stopPropagation(); mm.classList.toggle('open'); }; bindAccountOnly(mm);
  document.querySelectorAll('.filters button').forEach(b => b.onclick = () => { S.filter = b.dataset.f; dashboard(); });
  document.querySelectorAll('.area,.pendrow').forEach(el => el.onclick = () => run(() => goArea(el.dataset.c)));
  document.querySelectorAll('.goto').forEach(el => el.onclick = () => run(() => goArea(el.dataset.c)));
  $('#t_bulk').onclick = bulkUpload; $('#t_log').onclick = activityLog; if ($('#t_roll')) $('#t_roll').onclick = rollover;
  if ($('#mat')) $('#mat').onclick = ev => { ev.preventDefault(); const v = prompt('Overall materiality (₹):', e.materiality); if (v !== null) run(async () => { await api(`/api/engagements/${S.eid}/materiality`, { method: 'PUT', json: { materiality: v } }); await refresh(); shell(); }); };
  const sv = $('#oc_save'); if (sv) { sv.onclick = () => run(async () => { await api(`/api/engagements/${S.eid}/conclusion`, { method: 'PUT', json: { overall_type: $('#oc_t').value, overall_conclusion: $('#oc_c').value, basis_of_conclusion: $('#oc_b').value } }); toast('Overall conclusion saved'); await refresh(); shell(); });
    $('#oc_draft').onclick = () => run(async () => { const d = await api(`/api/engagements/${S.eid}/draft-paragraphs`); modal(`<h2>Draft reporting paragraphs</h2><div style="width:760px"><div class="note info">Generated from the adverse register. A starting point only – edit before use. Professional judgement rests with the Partner.</div><textarea class="mono" id="dr">${esc(d.text)}</textarea><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Close</button><button class="btn ghost" id="dr_c">Copy</button><button class="btn gold right" id="dr_u">Put into “Basis for the conclusion”</button></div></div>`);
      $('#dr_c').onclick = () => { navigator.clipboard.writeText($('#dr').value); toast('Copied'); }; $('#dr_u').onclick = () => { $('#oc_b').value = $('#dr').value; closeModal(); toast('Added – remember to save'); }; }); }
}
function bindAccountOnly(rep) { const m = $('#acct'); $('#acb').onclick = e => { e.stopPropagation(); m.classList.toggle('open'); rep.classList.remove('open'); }; document.onclick = () => { m.classList.remove('open'); rep.classList.remove('open'); };
  $('#m_pw').onclick = () => changePw(false); $('#m_out').onclick = signOut; if ($('#m_users')) $('#m_users').onclick = manageUsers; if ($('#m_bak')) $('#m_bak').onclick = backups; }
function adverseTable() {
  if (!S.adverse.length) return '<div class="note ok">No exceptions, qualifications, disclaimers or open queries recorded.</div>';
  return `<div class="card" style="padding:0;overflow:hidden"><table class="reg"><tr><th>Ref</th><th>Audit area</th><th>Where written</th><th>Remark</th><th>Priority</th></tr>${S.adverse.map(a => `<tr class="${a.severity}"><td>${esc(a.ref)}</td><td><a class="goto" data-c="${a.code}" style="cursor:pointer;text-decoration:underline">${esc(a.area)}</a></td><td>${esc(a.where)}</td><td>${hl(a.text) || '<i>(no text)</i>'}</td><td><b>${a.severity}</b><br><small>${esc(a.reason)}</small></td></tr>`).join('')}</table></div>`;
}
function overallForm() {
  const e = S.eng, ro = !isPS(), allRev = S.prog.reviewed === S.prog.live_areas;
  return `<div class="card">${ro ? '<div class="note info">Only the Partner or Sr Staff can record the overall conclusion.</div>' : (!allRev ? `<div class="note warn">${S.prog.live_areas - S.prog.reviewed} module(s) are not yet reviewed by the Partner. Finalise the conclusion only after the review is complete.</div>` : '')}
  <label>Proposed basis of conclusion</label><select id="oc_t" ${ro ? 'disabled' : ''}><option value="">— select —</option>${Object.entries(S.meta.overall_types).map(([k, v]) => `<option value="${k}" ${e.overall_type === k ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>
  <label>Overall conclusion</label><textarea id="oc_c" ${ro ? 'disabled' : ''}>${esc(e.overall_conclusion)}</textarea>
  <label>Basis for the conclusion (key matters, qualifications, limitations)</label><textarea id="oc_b" style="min-height:120px" ${ro ? 'disabled' : ''}>${esc(e.basis_of_conclusion)}</textarea>
  ${ro ? '' : '<div class="inline mt"><button class="btn" id="oc_save">Save overall conclusion</button><button class="btn ghost" id="oc_draft">✎ Draft paragraphs from adverse remarks</button></div>'}</div>`;
}

/* ================= area ================= */
function wfBar(A) {
  const w = A.wp.workflow || 'Not Started', st = w === 'Reviewed' ? 3 : w === 'Compiled' ? 2 : A.progress.state === 'Complete' ? 1 : 0;
  const steps = [['Work in progress', w === 'Returned' ? 'Returned by Partner' : A.wp.assigned_name ? 'Assigned: ' + A.wp.assigned_name : 'Staff completing tabs'], ['Compiled', A.wp.prepared_by ? 'by ' + A.wp.prepared_by : 'by staff'], ['Partner review', w === 'Compiled' ? 'Awaiting Partner' : 'Partner examines'], ['Reviewed', A.wp.reviewed_by ? 'by ' + A.wp.reviewed_by : 'Review Complete']];
  const pos = w === 'Reviewed' ? 4 : w === 'Compiled' ? 2 : 0;
  return `<div class="wfbar">${steps.map((s, i) => `${i ? `<div class="wfline ${i <= pos ? 'done' : ''}"></div>` : ''}<div class="wfstep ${i < pos ? 'done' : i === pos ? 'now' : ''}"><div class="c">${i < pos ? '✓' : i + 1}</div><div><b>${s[0]}</b><small>${esc(s[1])}</small></div></div>`).join('')}</div>`;
}
function pnView() {
  const arr = S.prog.areas, i = arr.findIndex(a => a.code === S.code), pv = arr[i - 1], nx = arr[i + 1];
  $('#pn').innerHTML = `${pv ? `<button class="btn ghost" id="pv">← WP ${pv.no} · ${esc(pv.title)}</button>` : '<span></span>'}${nx ? `<button class="btn ghost" id="nx">WP ${nx.no} · ${esc(nx.title)} →</button>` : ''}`;
  if (pv) $('#pv').onclick = () => navTo(pv.code); if (nx) $('#nx').onclick = () => navTo(nx.code);
}
const setAppl = (value, reason) => run(async () => {
  if (nDirty()) await saveAll();
  await api(`/api/engagements/${S.eid}/areas/${S.code}/applicability`, { method: 'PUT', json: { value, reason } });
  closeModal(); toast(value === 'NA' ? 'Marked not applicable – module treated as completed' : 'Marked applicable – you can now enter the work'); S.tab = 'steps'; await reloadArea();
});
function askNA() {
  modal(`<h2>Mark this module as not applicable?</h2><div style="width:480px"><p class="muted" style="margin:0 0 6px">The module will be treated as completed. Any work already entered is kept, and comes back if you change your choice later.</p><label>Why is it not applicable to ${esc(S.eng.client_name)}?</label><textarea id="na_r" placeholder="e.g. The entity has no leased assets, so no right-of-use assets or lease liabilities."></textarea>
  <div class="inline mt"><button class="btn gold" id="na_y">Mark not applicable</button><button class="btn ghost right" onclick="closeModal()">Cancel</button></div></div>`);
  $('#na_y').onclick = () => setAppl('NA', $('#na_r').value);
}
function gateView() {
  const A = S.area, w = A.wp, c = esc(S.eng.client_name);
  if (w.applicability === 'NA') {
    $('#gate').innerHTML = `<div class="gate na"><span class="gtag">Not applicable · counted as completed</span><h2>This module does not apply to ${c}</h2><p class="why"><b>Reason recorded:</b> ${esc(w.na_reason)}</p>
    <p class="muted">Confirmed by ${esc(w.applicability_by)} on ${esc(w.applicability_at)}. It shows as “Not applicable” in the dashboard and reports. You can reverse this at any time – the module then opens for work.</p><button class="btn gold" id="g_a">Change to Applicable and start work</button></div>`;
    $('#g_a').onclick = () => setAppl('Applicable');
  } else {
    $('#gate').innerHTML = `<div class="gate"><h2>Is this module applicable to ${c}?</h2><p class="muted" style="max-width:640px">${esc(w.objective || A.topic.objective)}</p>
    <div class="gbtns"><button class="gbtn yes" id="g_y"><b>Applicable</b><span>Open the audit steps, evidence and conclusion for data entry</span></button><button class="gbtn no" id="g_n"><b>Not applicable</b><span>Record the reason – the module is marked as completed</span></button></div>
    <div class="gna hid" id="g_nb"><label>Why is this module not applicable to ${c}?</label><textarea id="g_r" placeholder="Give the reason – this is shown in the working papers"></textarea><div class="inline mt"><button class="btn gold" id="g_c">Confirm not applicable</button><button class="btn ghost" id="g_x">Cancel</button></div></div>
    <p class="muted" style="margin-top:16px;font-size:12.5px">You can change this choice at any time.</p></div>`;
    $('#g_y').onclick = () => setAppl('Applicable'); $('#g_n').onclick = () => { $('#g_nb').classList.remove('hid'); $('#g_r').focus(); };
    $('#g_x').onclick = () => $('#g_nb').classList.add('hid'); $('#g_c').onclick = () => setAppl('NA', $('#g_r').value);
  }
}
function areaView() {
  const A = S.area, p = A.progress, T = p.tabs, lock = A.locked, openNotes = p.open_notes, ap = A.wp.applicability || '', on = ap === 'Applicable';
  const tabs = [['steps', 'Audit steps', `${p.steps_done}/${p.steps_total}`, T.steps], ['evidence', 'Evidence', p.files, T.evidence], ['queries', 'Queries', A.queries.length, T.queries], ['notes', 'Review notes', A.notes.length ? `${openNotes} open` : '', openNotes ? 'partial' : 'complete'], ['conclusion', 'Conclusion & sign-off', '', T.conclusion]];
  $('#main').innerHTML = `${on && !lock ? '<div class="savebar" id="savebar"><span class="sd"></span><span id="sv_msg"></span><button class="btn sm gold" id="sv_btn">Save work</button></div>' : ''}
  <div class="top"><div><div class="crumb">WP ${A.topic.no} · ${esc(A.topic.group)} · ${esc(S.eng.client_name)}</div><h1>${esc(A.topic.title)}</h1><div class="crumb">${esc(A.wp.objective || A.topic.objective)}</div>
  ${on ? `<div class="who-line"><span>Compiled by: <b>${esc(A.wp.prepared_by || '— pending —')}</b>${A.wp.prepared_at ? ' · ' + esc(A.wp.prepared_at) : ''}</span><span>Reviewed by Partner: <b>${esc(A.wp.reviewed_by || '— pending —')}</b>${A.wp.reviewed_at ? ' · ' + esc(A.wp.reviewed_at) : ''}</span></div>` : ''}</div>
  <div style="text-align:right;min-width:230px">${wfBadge({ ...p, workflow: A.wp.workflow })} <b style="margin-left:6px">${p.pct}%</b><div class="bar mt"><i style="width:${p.pct}%"></i></div>
  ${isPS() ? `<div class="inline mt" style="justify-content:flex-end"><select id="as_u" style="width:150px;padding:6px"><option value="0">Unassigned</option>${S.people.map(x => `<option value="${x.id}" ${A.wp.assigned_to === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select><input id="as_d" type="date" value="${esc(A.wp.due_date || '')}" style="width:140px;padding:6px"></div>` : (A.wp.assigned_name ? `<div class="muted" style="font-size:12px;margin-top:6px">Assigned to ${esc(A.wp.assigned_name)}${A.wp.due_date ? ' · due ' + esc(A.wp.due_date) : ''}</div>` : '')}</div></div>
  ${on ? wfBar(A) : ''}
  ${on && !lock ? `<div class="applbar"><span>✓ Applicable to this entity${A.wp.applicability_by ? ' · confirmed by ' + esc(A.wp.applicability_by) + ', ' + esc(A.wp.applicability_at) : ''}</span><a id="ap_na">Not applicable? Change</a></div>` : ''}
  ${on && p.pending.length && !lock ? `<div class="note warn"><b>Still pending:</b> ${p.pending.map(esc).join(' · ')}</div>` : ''}
  ${A.wp.workflow === 'Compiled' ? '<div class="note info"><b>Compiled – awaiting Partner review.</b> This module is locked for staff until the Partner completes the review or sends it back.</div>' : ''}
  ${A.wp.workflow === 'Reviewed' ? '<div class="note ok"><b>Reviewed and locked.</b> The Partner can send it back if changes are required.</div>' : ''}
  ${on ? `<div class="tabs">${tabs.map(([k, l, c, d]) => `<button class="tab ${S.tab === k ? 'on' : ''}" data-t="${k}"><span class="dot ${d}"></span>${l}${c !== '' ? `<span class="cnt">${c}</span>` : ''}</button>`).join('')}</div><div id="tabbody"></div>` : '<div id="gate"></div>'}
  <div class="pn" id="pn"></div>`;
  if ($('#as_u')) { const sv = () => run(async () => { await api(`/api/engagements/${S.eid}/areas/${S.code}/assign`, { method: 'PUT', json: { user_id: +$('#as_u').value, due_date: $('#as_d').value } }); toast('Assignment saved'); await refresh(); });
    $('#as_u').onchange = sv; $('#as_d').onchange = sv; }
  if ($('#savebar')) { $('#sv_btn').onclick = doSave; updateSaveBar(); }
  if ($('#ap_na')) $('#ap_na').onclick = askNA;
  document.querySelectorAll('.tab').forEach(b => b.onclick = () => { S.tab = b.dataset.t; areaView(); });
  if (on) ({ steps: stepsTab, evidence: evidenceTab, queries: queriesTab, notes: notesTab, conclusion: conclusionTab })[S.tab](); else gateView();
  pnView();
}
async function reloadArea() { await refresh(); shell(); updateSaveBar(); }

function noteHtml(n, lock) {
  const open = n.status === 'Open';
  return `<div class="rnote ${open ? '' : 'cleared'}"><b>${open ? '● Review note' : '✓ Cleared'}</b> — ${hl(n.note)}<div class="who">Raised by ${esc(n.raised_by_name)} · ${esc(n.raised_at)}${n.response ? `<br>Response: ${esc(n.response)} (${esc(n.cleared_by_name)}, ${esc(n.cleared_at)})` : ''}</div>
  ${open ? `<textarea placeholder="How have you addressed this note?" data-nr="${n.id}"></textarea><div class="inline" style="margin-top:6px"><button class="btn sm" data-nc="${n.id}">Mark as addressed</button>${isP() ? `<button class="btn sm ghost" data-nd="${n.id}">Delete note</button>` : ''}</div>` : (isPS() ? `<div class="inline" style="margin-top:6px"><button class="btn sm ghost" data-no="${n.id}">Reopen</button></div>` : '')}</div>`;
}
function bindNotes(root) {
  root.querySelectorAll('[data-nc]').forEach(b => b.onclick = () => run(async () => { await api('/api/notes/' + b.dataset.nc, { method: 'PUT', json: { action: 'clear', response: $(`[data-nr="${b.dataset.nc}"]`, root).value } }); toast('Note addressed'); await reloadArea(); }));
  root.querySelectorAll('[data-no]').forEach(b => b.onclick = () => run(async () => { await api('/api/notes/' + b.dataset.no, { method: 'PUT', json: { action: 'reopen' } }); await reloadArea(); }));
  root.querySelectorAll('[data-nd]').forEach(b => b.onclick = () => confirm('Delete this review note?') && run(async () => { await api('/api/notes/' + b.dataset.nd, { method: 'PUT', json: { action: 'delete' } }); await reloadArea(); }));
}
function addNote(step) {
  modal(`<h2>Add review note${step ? ' – step ' + step : ''}</h2><div style="width:480px"><textarea id="rn" placeholder="What needs to be corrected, explained or supported?"></textarea><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn gold right" id="rn_s">Add note</button></div></div>`);
  $('#rn_s').onclick = () => run(async () => { await api(`/api/engagements/${S.eid}/areas/${S.code}/notes`, { method: 'POST', json: { step_no: step || 0, note: $('#rn').value } }); closeModal(); await reloadArea(); });
}

function stepsTab() {
  const A = S.area, lock = A.locked, T0 = today();
  $('#tabbody').innerHTML = A.steps.map(s0 => { const d = S.dirty['step' + s0.no], s = d ? { ...s0, ...d } : s0, wd = s.work_date || isoFrom(s0.checked_at) || T0;
  return `<div class="step ${s.status} ${d ? 'unsaved' : ''}" data-n="${s.no}"><div class="row"><div class="no">${s.no}</div><div style="flex:1">
  <div class="pr">${esc(s.procedure)}</div><div class="chips">${s.assertions.map(a => `<span class="chip">${esc(a)}</span>`).join('')}</div>
  <div class="seg" data-v="${s.status}">${[['Completed', 'c', '✓ Done – no issue'], ['Exception', 'e', '⚠ Exception'], ['NA', 'n', 'Not applicable'], ['', 'p', 'Pending']].map(([v, c, l]) => `<button data-s="${v}" class="${s.status === v ? 'on ' + c : ''}" ${lock ? 'disabled' : ''}>${l}</button>`).join('')}</div>
  <textarea placeholder="What evidence did you examine and what was the result? (mandatory for exceptions and not-applicable)" ${lock ? 'disabled' : ''}>${esc(s.remarks)}</textarea>
  <div class="inline" style="margin-top:8px">${lock ? '' : '<button class="btn sm save">Save step</button>'}${isPS() ? `<button class="btn sm ghost addn" data-st="${s.no}">+ Review note</button>` : ''}<label class="wdl">Work carried out on <input type="date" class="wd" value="${esc(wd)}" ${lock ? 'disabled' : ''}></label><span class="meta">${s0.checked_at ? `Updated by ${esc(s0.checked_by)} · ${esc(s0.checked_at)}` : ''}</span><span class="unsavedtag">Unsaved</span>${hasAdv(s.remarks) ? '<span class="badge b-warn right">Adverse wording – highlighted in file</span>' : ''}</div>
  <div class="snote">${s.notes.map(n => noteHtml(n, lock)).join('')}</div></div></div></div>`; }).join('');
  document.querySelectorAll('.step').forEach(el => {
    const no = +el.dataset.n, seg = $('.seg', el); let val = seg.dataset.v;
    const cur = () => ({ status: val, remarks: $('textarea', el).value, work_date: $('.wd', el).value || T0 });
    const touch = () => { el.classList.add('unsaved'); markDirty('step' + no, cur()); };
    seg.querySelectorAll('button').forEach(b => b.onclick = () => { if (lock) return; val = b.dataset.s; seg.querySelectorAll('button').forEach(x => x.className = ''); b.className = 'on ' + ({ Completed: 'c', Exception: 'e', NA: 'n', '': 'p' })[val]; touch(); });
    if (!lock) { $('textarea', el).oninput = touch; $('.wd', el).onchange = touch; }
    if ($('.save', el)) $('.save', el).onclick = () => run(async () => { await api(`/api/engagements/${S.eid}/areas/${S.code}/step/${no}`, { method: 'PUT', json: cur() }); delete S.dirty['step' + no]; toast('Step saved'); await reloadArea(); });
    bindNotes(el);
  });
  document.querySelectorAll('.addn').forEach(b => b.onclick = () => addNote(+b.dataset.st));
}

const ICON = { PDF: 'PDF', Excel: 'XLS', CSV: 'CSV', Word: 'DOC', Image: 'IMG', Text: 'TXT', PowerPoint: 'PPT', Email: 'MAIL', Archive: 'ZIP', File: 'FILE' };
const sz = b => b > 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
function evidenceTab() {
  const A = S.area, lock = A.locked, w = { ...A.wp, ...(S.dirty.evna || {}) };
  $('#tabbody').innerHTML = `${lock ? '' : `<div class="drop" id="drop"><div class="ic">📎</div><b>Drag and drop evidence here, or choose files</b><p>Excel, CSV, Word, PDF, JPG / PNG, email, PowerPoint, ZIP — multiple files allowed</p>
  <div style="max-width:700px;margin:12px auto;text-align:left"><label>Relates to audit step(s)</label><div class="sel-steps" id="ev_steps">${A.steps.map(s => `<label><input type="checkbox" value="${s.no}"> Step ${s.no}</label>`).join('')}<span class="muted" style="font-size:12px">(leave blank for the whole module)</span></div>
  <label>What does this evidence show?</label><input id="ev_desc" placeholder="e.g. Bank confirmation as on 31-Mar-26"></div><input type="file" id="ev_file" multiple hidden><button class="btn" id="ev_btn">Choose files</button></div>`}
  <div class="files">${A.evidence.length ? A.evidence.map(f => `<div class="file"><div class="fi ${f.kind}">${ICON[f.kind] || 'FILE'}</div><div><div class="n">${esc(f.source_name)}</div>
  <div class="d">${f.steps.length ? 'Step ' + f.steps.join(', ') + ' · ' : ''}${esc(f.description || 'No description')} · ${sz(f.size_bytes)} · ${esc(f.uploaded_by_name)}, ${esc(f.uploaded_at)}${f.stale ? ' · <span class="stale">⚠ file dated before the audit year</span>' : ''}</div></div>
  <div class="inline"><button class="btn ghost sm" data-v="${f.id}" data-k="${f.kind}" data-n="${esc(f.source_name)}">View</button><button class="btn ghost sm" onclick="location.href='/api/evidence/${f.id}/file?download=1'">⬇</button>${lock ? '' : `<button class="btn ghost sm" data-e="${f.id}">Edit</button><button class="btn ghost sm" data-d="${f.id}">✕</button>`}</div></div>`).join('') : '<div class="note warn">No evidence uploaded yet for this module.</div>'}</div>
  ${A.evidence.length || lock ? '' : `<div class="card mt"><b>No evidence needed for this module?</b><div class="muted" style="margin:4px 0 8px">Tick only if no document is relevant, and give the reason.</div>
  <label style="display:flex;gap:8px;align-items:center;text-transform:none;font-size:13px"><input type="checkbox" id="ev_na" style="width:auto" ${w.evidence_na ? 'checked' : ''}> Evidence not required</label>
  <input id="ev_nar" placeholder="Reason" value="${esc(w.evidence_na_reason)}" style="margin-top:8px"><div class="mt"><button class="btn sm" id="ev_nas">Save</button></div></div>`}`;
  const up = files => run(async () => {
    const fd = new FormData(); [...files].forEach(f => fd.append('files', f)); fd.append('modified', JSON.stringify([...files].map(f => f.lastModified)));
    fd.append('steps', [...document.querySelectorAll('#ev_steps input:checked')].map(x => x.value).join(',')); fd.append('description', $('#ev_desc').value);
    const r = await api(`/api/engagements/${S.eid}/areas/${S.code}/evidence`, { method: 'POST', form: fd });
    toast(`${r.saved.length} file(s) uploaded` + (r.rejected.length ? `; not allowed: ${r.rejected.join(', ')}` : ''), !!r.rejected.length); await reloadArea(); });
  if ($('#drop')) { const d = $('#drop'); $('#ev_btn').onclick = () => $('#ev_file').click(); $('#ev_file').onchange = e => e.target.files.length && up(e.target.files);
    ['dragover', 'dragenter'].forEach(t => d.addEventListener(t, e => { e.preventDefault(); d.classList.add('over'); })); ['dragleave', 'drop'].forEach(t => d.addEventListener(t, e => { e.preventDefault(); d.classList.remove('over'); }));
    d.addEventListener('drop', e => e.dataTransfer.files.length && up(e.dataTransfer.files)); }
  document.querySelectorAll('[data-d]').forEach(b => b.onclick = () => confirm('Remove this evidence file?') && run(async () => { await api('/api/evidence/' + b.dataset.d, { method: 'DELETE' }); await reloadArea(); }));
  document.querySelectorAll('[data-v]').forEach(b => b.onclick = () => viewFile(+b.dataset.v, b.dataset.k, b.dataset.n));
  document.querySelectorAll('[data-e]').forEach(b => b.onclick = () => { const f = A.evidence.find(x => x.id == b.dataset.e);
    modal(`<h2>Edit evidence details</h2><div style="width:520px"><label>Description</label><input id="ee_d" value="${esc(f.description)}"><label>Relates to step(s)</label><div class="sel-steps" id="ee_s">${A.steps.map(s => `<label><input type="checkbox" value="${s.no}" ${f.steps.includes(s.no) ? 'checked' : ''}> Step ${s.no}</label>`).join('')}</div>
    <div class="inline mt"><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn gold right" id="ee_s2">Save</button></div></div>`);
    $('#ee_s2').onclick = () => run(async () => { await api('/api/evidence/' + f.id, { method: 'PUT', json: { description: $('#ee_d').value, steps: [...document.querySelectorAll('#ee_s input:checked')].map(x => +x.value) } }); closeModal(); await reloadArea(); }); });
  if ($('#ev_nas')) { const t = () => markDirty('evna', { evidence_na: $('#ev_na').checked, evidence_na_reason: $('#ev_nar').value }); $('#ev_na').onchange = t; $('#ev_nar').oninput = t;
    $('#ev_nas').onclick = () => run(async () => { await saveWp({ evidence_na: $('#ev_na').checked, evidence_na_reason: $('#ev_nar').value }); delete S.dirty.evna; toast('Saved'); await reloadArea(); }); }
}
async function viewFile(id, kind, name) {
  const u = `/api/evidence/${id}/file`;
  if (kind === 'Image') return modal(`<h2>${esc(name)}</h2><img src="${u}">`);
  if (name.toLowerCase().endsWith('.pdf')) return modal(`<h2>${esc(name)}</h2><iframe src="${u}"></iframe>`);
  if (kind === 'Excel' || kind === 'CSV') return run(async () => {
    const t = await api(`/api/evidence/${id}/table`);
    modal(`<h2>${esc(name)}</h2><p class="muted">${t.rows.toLocaleString()} rows · showing first ${t.data.length}</p><div style="max-height:60vh;overflow:auto"><table><tr>${t.cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>${t.data.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table></div>
    <div class="inline mt"><button class="btn sm" id="chk">Run data checks</button><button class="btn ghost sm" onclick="location.href='${u}?download=1'">⬇ Download original</button></div><div id="chkout"></div>`);
    $('#chk').onclick = () => run(async () => { const c = await api(`/api/evidence/${id}/table?checks=1`); $('#chkout').innerHTML = c.checks.length ? `<div class="note warn mt">${c.checks.length} item(s) flagged for evaluation – prompts, not conclusions.</div><div style="max-height:30vh;overflow:auto"><table><tr><th>Severity</th><th>Check</th><th>Item</th><th>Detail</th></tr>${c.checks.map(x => `<tr><td>${esc(x.severity)}</td><td>${esc(x.rule)}</td><td>${esc(x.item)}</td><td>${esc(x.description)}</td></tr>`).join('')}</table></div>` : '<div class="note ok mt">No items flagged.</div>'; });
  });
  modal(`<h2>${esc(name)}</h2><p class="muted">This file type cannot be previewed here.</p><button class="btn" onclick="location.href='${u}?download=1'">⬇ Download to open</button>`);
}

function queriesTab() {
  const A = S.area;
  $('#tabbody').innerHTML = `<div class="inline" style="margin-bottom:14px"><button class="btn" id="aq">+ Raise audit query</button><span class="muted">Open queries keep this module from showing 100%.</span></div>
  ${A.queries.length ? A.queries.map(q => `<div class="q"><div class="inline"><h3>#${q.id} ${esc(q.title)}</h3><span class="badge ${q.status === 'Closed' ? 'b-ok' : q.status === 'Responded' ? 'b-blue' : 'b-warn'} right">${q.status}</span></div>
  <p>${hl(q.description)}</p><label>Management response</label><textarea data-q="${q.id}" ${q.status === 'Closed' ? 'disabled' : ''}>${esc(S.dirty['q' + q.id] ? S.dirty['q' + q.id].text : q.management_response)}</textarea>
  ${q.status === 'Closed' ? '' : `<div class="inline mt"><button class="btn sm ghost" data-r="${q.id}">Save response</button>${isPS() ? `<button class="btn sm" data-x="${q.id}">Save & close query</button>` : ''}</div>`}</div>`).join('') : '<div class="note info">No audit queries raised for this module.</div>'}`;
  $('#aq').onclick = () => { modal(`<h2>Raise audit query</h2><div style="width:480px"><label>Short title</label><input id="q_t"><label>Details – what is needed from management</label><textarea id="q_d"></textarea><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn gold right" id="q_s">Raise query</button></div></div>`);
    $('#q_s').onclick = () => run(async () => { await api(`/api/engagements/${S.eid}/areas/${S.code}/queries`, { method: 'POST', json: { title: $('#q_t').value, description: $('#q_d').value } }); closeModal(); await reloadArea(); }); };
  document.querySelectorAll('textarea[data-q]').forEach(t => { if (!t.disabled) t.oninput = () => markDirty('q' + t.dataset.q, { text: t.value }); });
  const upd = (id, close) => run(async () => { await api('/api/queries/' + id, { method: 'PUT', json: { management_response: $(`textarea[data-q="${id}"]`).value, close } }); delete S.dirty['q' + id]; toast(close ? 'Query closed' : 'Response saved'); await reloadArea(); });
  document.querySelectorAll('[data-r]').forEach(b => b.onclick = () => upd(b.dataset.r, false)); document.querySelectorAll('[data-x]').forEach(b => b.onclick = () => upd(b.dataset.x, true));
}

function notesTab() {
  const A = S.area, gen = A.notes.filter(n => n.step_no === 0), stp = A.notes.filter(n => n.step_no > 0);
  $('#tabbody').innerHTML = `<div class="inline" style="margin-bottom:14px">${isPS() ? '<button class="btn" id="gn">+ Add review note</button>' : ''}<span class="muted">The Partner and Sr Staff raise notes here or against a step. Staff address each note; all must be cleared before the module can be compiled or review completed.</span></div>
  ${A.notes.length ? `<div class="card">${[...gen, ...stp].map(n => `<div>${n.step_no ? `<span class="badge b-mute">Step ${n.step_no}</span>` : '<span class="badge b-blue">General</span>'}${noteHtml(n, A.locked)}</div><div style="height:8px"></div>`).join('')}</div>` : '<div class="note ok">No review notes for this module.</div>'}`;
  if ($('#gn')) $('#gn').onclick = () => addNote(0); bindNotes($('#tabbody'));
}

async function saveWp(over = {}) {
  const w = S.area.wp, body = { rev: w.rev, objective: w.objective, conclusion: w.conclusion, conclusion_type: w.conclusion_type, evidence_na: w.evidence_na, evidence_na_reason: w.evidence_na_reason, ...over };
  const r = await api(`/api/engagements/${S.eid}/areas/${S.code}/workpaper`, { method: 'PUT', json: body }); Object.assign(S.area.wp, body, { rev: r.rev }); return r;
}
function conclusionTab() {
  const A = S.area, w = A.wp, lock = A.locked, p = A.progress, st = w.workflow || 'Not Started', dc = S.dirty.concl;
  let curT = dc ? dc.conclusion_type : w.conclusion_type; const curC = dc ? dc.conclusion : w.conclusion;
  const desc = { Satisfactory: 'Objective achieved, no issues', Observations: 'Achieved, but observations need to be reported', Qualified: 'Material issue noted – qualification / adverse', Disclaimer: 'Could not obtain sufficient evidence' };
  const canCompile = st === 'Not Started' || st === 'Returned';
  $('#tabbody').innerHTML = `${w.py_conclusion || w.py_type ? `<div class="pyb"><b>Prior-year conclusion</b> ${w.py_type ? '· ' + esc(S.meta.conclusion_types[w.py_type] || w.py_type) : ''}<div style="margin-top:4px">${hl(w.py_conclusion)}</div></div>` : ''}
  <div class="card"><label style="margin-top:0">Conclusion type</label><div class="opts">${Object.entries(S.meta.conclusion_types).map(([k, v]) => `<div class="opt ${k} ${curT === k ? 'on' : ''}" data-k="${k}"><b>${esc(v.split(' – ')[0])}</b><span>${desc[k]}</span></div>`).join('')}</div>
  <label>Conclusion</label><textarea id="cc" style="min-height:150px" ${lock ? 'disabled' : ''} placeholder="State what was done, what was found, and the conclusion reached. Mention any limitation or non-compliance clearly.">${esc(curC)}</textarea><div id="cc_warn"></div>
  ${lock ? '' : '<div class="inline mt"><button class="btn" id="cc_save">Save conclusion</button></div>'}</div>
  ${st === 'Compiled' && isP() ? `<div class="reviewbox" style="margin:0 0 18px"><h3>Partner review</h3><p>Compiled by ${esc(w.prepared_by)} on ${esc(w.prepared_at)}. Go through the audit steps, evidence, queries and conclusion. When satisfied, complete the review — it will be recorded under your name.</p>
  <div class="inline"><label class="wdl" style="margin:0">Review date <input type="date" id="wf_rd" value="${today()}"></label><button class="btn ok" id="wf_r">✓ Review Complete</button><button class="btn back" id="wf_b">↩ Send back to staff</button></div></div>` : ''}
  <div class="card"><h3>Compile & review</h3><div class="grid g2 mt"><div><div class="muted">Compiled by</div><b>${esc(w.prepared_by || '— pending —')}</b><div class="muted" style="font-size:12px">${esc(w.prepared_at || '')}</div></div>
  <div><div class="muted">Reviewed by (Partner)</div><b>${esc(w.reviewed_by || '— pending —')}</b><div class="muted" style="font-size:12px">${esc(w.reviewed_at || '')}</div></div></div>
  ${canCompile ? `<div class="inline mt"><label class="wdl" style="margin:0">Compilation date <input type="date" id="wf_cd" value="${today()}"></label><button class="btn gold" id="wf_c">Mark module as Compiled</button><span class="muted">Saves all your entries, then records you as the compiler. Available when every tab is complete.</span></div>` : ''}</div>
  ${st === 'Compiled' && !isP() ? '<div class="stamp wait mt">Awaiting Partner review</div>' : ''}
  ${st === 'Reviewed' ? `<div class="stamp mt">✓ Reviewed by ${esc(w.reviewed_by)} · ${esc(w.reviewed_at)}</div>${isP() ? '<div class="mt"><button class="btn ghost" id="wf_b">↩ Reopen / send back to staff</button></div>' : ''}` : ''}`;
  const warn = () => { const t = $('#cc').value; $('#cc_warn').innerHTML = hasAdv(t) ? `<div class="note warn"><b>Adverse wording detected</b> — it will be highlighted in the final file:<br>${hl(t)}</div>` : ''; }; warn();
  const touch = () => markDirty('concl', { conclusion: $('#cc').value, conclusion_type: curT });
  $('#cc').oninput = () => { warn(); if (!lock) touch(); };
  document.querySelectorAll('.opt').forEach(o => o.onclick = () => { if (lock) return; curT = o.dataset.k; document.querySelectorAll('.opt').forEach(x => x.classList.remove('on')); o.classList.add('on'); touch(); });
  if ($('#cc_save')) $('#cc_save').onclick = () => run(async () => { await saveWp({ conclusion: $('#cc').value, conclusion_type: curT }); delete S.dirty.concl; toast('Conclusion saved'); await reloadArea(); });
  const wf = (action, extra) => api(`/api/engagements/${S.eid}/areas/${S.code}/workflow`, { method: 'POST', json: { action, ...extra } });
  if ($('#wf_c')) $('#wf_c').onclick = () => run(async () => { await saveAll(); await saveWp({ conclusion: $('#cc').value, conclusion_type: curT }); delete S.dirty.concl; await wf('compile', { date: $('#wf_cd').value }); toast('Module compiled – now awaiting Partner review'); await reloadArea(); });
  if ($('#wf_r')) $('#wf_r').onclick = () => run(async () => { await wf('review', { date: $('#wf_rd').value }); toast('Review complete – recorded under your name'); await reloadArea(); });
  if ($('#wf_b')) $('#wf_b').onclick = () => { const r = prompt('What needs to be corrected? (staff will see this as a review note)'); if (r) run(async () => { await wf('return', { reason: r }); toast('Sent back to staff'); await reloadArea(); }); };
}

/* ================= tools & admin ================= */
function changePw(force) {
  modal(`<h2>${force ? 'Set your own password' : 'Change my password'}</h2><div style="width:400px">${force ? '<div class="note warn">You are using a password issued by the Partner. Please choose your own password before continuing.</div>' : ''}<label>Current password</label><input id="c_o" type="password"><label>New password (min 6 characters)</label><input id="c_n" type="password">
  <div class="inline mt">${force ? '' : '<button class="btn ghost" onclick="closeModal()">Cancel</button>'}<button class="btn gold right" id="c_s">Change password</button></div></div>`, force);
  $('#c_s').onclick = () => run(async () => { await api('/api/me/password', { method: 'POST', json: { old: $('#c_o').value, new: $('#c_n').value } }); S.user.must_change = false; closeModal(); toast('Password changed'); });
}
async function manageUsers() {
  const us = await api('/api/users');
  modal(`<h2>Manage users & roles</h2><div style="width:800px"><div class="note info">Only the Partner can create, change or reset logins. New and reset passwords must be changed by the user at first sign-in.</div>
  <div class="user-row" style="font-weight:700;color:var(--mute);font-size:12px"><span>NAME</span><span>USERNAME</span><span>ROLE</span><span>STATUS</span><span></span></div>
  ${us.map(u => `<div class="user-row"><span><b>${esc(u.name)}</b> <a data-nm="${u.id}" data-v="${esc(u.name)}" style="cursor:pointer;color:var(--blue);font-size:12px">rename</a></span><span>${esc(u.username)}</span>
  <select data-ro="${u.id}">${['Partner', 'Senior', 'Junior'].map(r => `<option value="${r}" ${u.role === r ? 'selected' : ''}>${roleName(r)}</option>`).join('')}</select>
  <span>${u.active ? '<span class="badge b-ok">Active</span>' : '<span class="badge b-bad">Disabled</span>'}</span><span class="inline"><button class="btn ghost sm" data-rp="${u.id}">Reset password</button><button class="btn ghost sm" data-tg="${u.id}" data-a="${u.active}">${u.active ? 'Disable' : 'Enable'}</button></span></div>`).join('')}
  <h3 style="margin-top:22px">Create new login</h3><div class="two"><div><label>Full name (shown as “compiled by” / “reviewed by”)</label><input id="u_n"></div><div><label>Username</label><input id="u_u"></div>
  <div><label>Role</label><select id="u_r"><option value="Junior">Jr Staff</option><option value="Senior">Sr Staff</option><option value="Partner">Partner</option></select></div><div><label>Initial password (min 6)</label><input id="u_p"></div></div>
  <div class="inline mt"><button class="btn ghost" onclick="closeModal()">Close</button><button class="btn gold right" id="u_s">Create login</button></div></div>`);
  const put = (id, j, msg) => run(async () => { await api('/api/users/' + id, { method: 'PUT', json: j }); if (msg) toast(msg); manageUsers(); });
  document.querySelectorAll('[data-rp]').forEach(b => b.onclick = () => { const v = prompt('New password for this user (min 6 characters):'); if (v) put(b.dataset.rp, { password: v }, 'Password reset – user must change it at next sign-in'); });
  document.querySelectorAll('[data-tg]').forEach(b => b.onclick = () => put(b.dataset.tg, { active: b.dataset.a !== '1' }));
  document.querySelectorAll('[data-ro]').forEach(s => s.onchange = () => put(s.dataset.ro, { role: s.value }, 'Role updated'));
  document.querySelectorAll('[data-nm]').forEach(a => a.onclick = () => { const v = prompt('Full name:', a.dataset.v); if (v) put(a.dataset.nm, { name: v }, 'Name updated'); });
  $('#u_s').onclick = () => run(async () => { await api('/api/users', { method: 'POST', json: { name: $('#u_n').value, username: $('#u_u').value, role: $('#u_r').value, password: $('#u_p').value } }); toast('Login created'); S.people = await api('/api/people'); manageUsers(); });
}
async function backups() {
  const bs = await api('/api/backups');
  modal(`<h2>Backup & restore</h2><div style="width:620px"><div class="note info">A backup is taken automatically every day (last 14 kept). It contains all engagements, working papers and evidence. Store copies on a different drive or cloud storage.</div>
  <div class="inline"><button class="btn gold" id="bk_n">Create backup now</button></div>
  <div style="margin:14px 0;max-height:200px;overflow:auto">${bs.map(b => `<div class="logrow" style="grid-template-columns:1fr 80px 90px"><span>${esc(b.name)}</span><span>${b.mb} MB</span><a href="/api/backups/${encodeURIComponent(b.name)}">⬇ Download</a></div>`).join('') || '<div class="muted">No backups yet.</div>'}</div>
  <h3>Restore from a backup file</h3><div class="note warn">Restoring replaces all current data with the backup. A safety backup of the current data is taken first. Everyone will be signed out.</div>
  <input type="file" id="rs_f" accept=".zip"><label>Type RESTORE to confirm</label><input id="rs_c"><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Close</button><button class="btn red right" id="rs_s">Restore</button></div></div>`);
  $('#bk_n').onclick = () => run(async () => { await api('/api/backups', { method: 'POST' }); toast('Backup created'); backups(); });
  $('#rs_s').onclick = () => run(async () => { const f = $('#rs_f').files[0]; if (!f) throw new Error('Choose a backup file.'); const fd = new FormData(); fd.append('file', f); fd.append('confirm', $('#rs_c').value); await api('/api/restore', { method: 'POST', form: fd }); closeModal(); alert('Restore complete. Please sign in again.'); S.user = null; S.eid = null; render(); });
}
async function activityLog() {
  const rows = await api(`/api/engagements/${S.eid}/log`);
  modal(`<h2>Activity log – ${esc(S.eng.client_name)}</h2><div style="width:820px;max-height:62vh;overflow:auto">${rows.map(r => `<div class="logrow"><span class="muted">${esc(r.when)}</span><b>${esc(r.who)}</b><span>${esc(r.action)}${r.area ? ' · ' + esc(r.area) : ''}${r.detail ? ' – ' + esc(r.detail) : ''}</span></div>`).join('') || '<div class="muted">No activity yet.</div>'}</div><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Close</button></div>`);
}
function bulkUpload() {
  modal(`<h2>Bulk evidence upload</h2><div style="width:620px"><div class="note info">Select many files, or a whole client folder. Files are placed by name: start the file name with the working-paper number shown in the left menu (e.g. <b>8 Bank statement.pdf</b> or <b>WP8 Bank statement.pdf</b>) or include the module name (e.g. “Trade Receivables ageing.xlsx”). Anything not recognised is listed so you can upload it manually. Modules locked for review are skipped.</div>
  <div class="inline"><button class="btn" id="bu_f">Choose files</button><button class="btn ghost" id="bu_d">Choose a folder</button></div><input type="file" id="bu_i" multiple hidden><input type="file" id="bu_j" webkitdirectory hidden><div id="bu_o" class="mt"></div></div>`);
  const go = files => run(async () => { if (!files.length) return; const fd = new FormData(); [...files].forEach(f => { fd.append('files', f); }); fd.append('modified', JSON.stringify([...files].map(f => f.lastModified)));
    const r = await api(`/api/engagements/${S.eid}/bulk-evidence`, { method: 'POST', form: fd }); const placed = Object.entries(r.placed);
    $('#bu_o').innerHTML = `${placed.length ? `<div class="note ok"><b>Placed:</b><br>${placed.map(([c, f]) => `WP ${(S.prog.areas.find(x => x.code === c) || {}).no || c}: ${f.map(esc).join(', ')}`).join('<br>')}</div>` : ''}${r.unmatched.length ? `<div class="note warn"><b>Could not match (upload manually):</b><br>${r.unmatched.map(esc).join('<br>')}</div>` : ''}${(r.not_applicable || []).length ? `<div class="note warn"><b>Skipped – module not marked applicable yet:</b><br>${r.not_applicable.map(esc).join('<br>')}</div>` : ''}${r.locked.length ? `<div class="note bad"><b>Skipped – module locked:</b><br>${r.locked.map(esc).join('<br>')}</div>` : ''}${r.rejected.length ? `<div class="note bad"><b>File type not allowed:</b><br>${r.rejected.map(esc).join('<br>')}</div>` : ''}`; await refresh(); });
  $('#bu_f').onclick = () => $('#bu_i').click(); $('#bu_d').onclick = () => $('#bu_j').click(); $('#bu_i').onchange = e => go(e.target.files); $('#bu_j').onchange = e => go(e.target.files);
}
function rollover() {
  modal(`<h2>Roll over to next year</h2><div style="width:480px"><div class="note info">Creates a new engagement for the same client with the same modules, materiality and applicability. Last year's conclusions are shown for reference and unresolved queries are carried forward. Evidence and step results start fresh.</div><label>New financial year</label><input id="ro_f" placeholder="e.g. 2026-27"><div class="inline mt"><button class="btn ghost" onclick="closeModal()">Cancel</button><button class="btn gold right" id="ro_s">Create next-year engagement</button></div></div>`);
  $('#ro_s').onclick = () => run(async () => { const r = await api(`/api/engagements/${S.eid}/rollover`, { method: 'POST', json: { financial_year: $('#ro_f').value } }); closeModal(); toast(`Created. ${r.carried_queries} open queries carried forward.`); await boot(); await openEng(r.id); });
}

(async function init() { const d = await api('/api/me'); S.meta = d.meta; S.user = d.user; if (S.user) await boot(); render(); if (S.user && S.user.must_change) changePw(true); })();
