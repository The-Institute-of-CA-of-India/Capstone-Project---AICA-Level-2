/**
 * CashSense - daily treasury briefing and schedulers (Google Apps Script). SAMPLE data only.
 *
 * CashSense (on the laptop) POSTs the daily briefing to this web app with a shared secret.
 * This script then:
 *   - logs it to the Google Sheet "CashSense Briefings" (created by setup),
 *   - emails the briefing to the Google account that runs the script,
 *   - runs time-driven schedulers (installed by setup):
 *       eveningReminder  daily 18:00  - reminder if approvals or high risks are waiting
 *       staleCheck       daily 10:00  - alert if no briefing has arrived for 26 hours (CashSense not running?)
 *       weeklyDigest     Monday 09:00 - week's trend of CC utilisation and risks from the sheet
 *
 * Set up once:
 *   1. Project Settings > Script properties > add CASHSENSE_SECRET = (APPS_SCRIPT_SECRET from CashSense's .env)
 *   2. Run setup() once and allow the permissions it asks for.
 *   3. Deploy > New deployment > Web app: Execute as "Me", Who has access "Anyone". Copy the /exec URL into
 *      CashSense's .env as APPS_SCRIPT_URL.
 */

const SHEET_NAME = 'CashSense Briefings';
const HEADERS = ['Received (IST)', 'As at', 'Cash (CA+CL)', 'CC drawn', 'CC use today', 'Worst scenario',
  'Worst peak use', 'First 85% alert week', 'Open/escalated risks', 'High risks', 'Approvals waiting',
  'All BRS agreed', 'Headline'];

function setup() {
  const props = PropertiesService.getScriptProperties();
  let id = props.getProperty('SHEET_ID');
  if (!id) {
    const ss = SpreadsheetApp.create(SHEET_NAME + ' (SAMPLE)');
    ss.getSheets()[0].setName('Briefings').appendRow(HEADERS);
    ss.getSheets()[0].setFrozenRows(1);
    id = ss.getId();
    props.setProperty('SHEET_ID', id);
  }
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));   // no duplicates on re-run
  ScriptApp.newTrigger('eveningReminder').timeBased().everyDays(1).atHour(18).inTimezone('Asia/Kolkata').create();
  ScriptApp.newTrigger('staleCheck').timeBased().everyDays(1).atHour(10).inTimezone('Asia/Kolkata').create();
  ScriptApp.newTrigger('weeklyDigest').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(9)
    .inTimezone('Asia/Kolkata').create();
  if (!props.getProperty('CASHSENSE_SECRET')) {
    throw new Error('Add the script property CASHSENSE_SECRET (APPS_SCRIPT_SECRET from CashSense .env) and run setup again.');
  }
  Logger.log('Sheet: https://docs.google.com/spreadsheets/d/' + id + '  - 3 triggers installed.');
}

function doPost(e) {
  const props = PropertiesService.getScriptProperties();
  let body;
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad json' }); }
  const secret = props.getProperty('CASHSENSE_SECRET');
  if (!secret || body.secret !== secret) return json_({ ok: false, error: 'unauthorised' });
  const b = body.briefing || {};
  if (body.ping) return json_({ ok: true, pong: true });
  logToSheet_(b);
  props.setProperty('LAST_BRIEFING', JSON.stringify(compact_(b)));
  props.setProperty('LAST_BRIEFING_AT', String(Date.now()));
  if (body.send_email !== false) sendBriefing_(b);
  return json_({ ok: true, received: b.as_of || '' });
}

function doGet() {
  return json_({ ok: true, service: 'CashSense briefing receiver (SAMPLE)' });
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function me_() { return Session.getEffectiveUser().getEmail(); }

function esc_(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

function compact_(b) {
  return { as_of: b.as_of, cc_use: b.cc_use_today, pending: b.pending_approvals, high: b.high_risks,
           risks: b.open_risks, worst: b.worst_scenario, worst_peak: b.worst_peak_use, headline: b.headline };
}

function logToSheet_(b) {
  const id = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (!id) return;
  const sh = SpreadsheetApp.openById(id).getSheetByName('Briefings');
  sh.appendRow([Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd HH:mm'), b.as_of, b.cash, b.cc_drawn,
    b.cc_use_today, b.worst_scenario, b.worst_peak_use, b.first_alert_week || 'none', b.open_risks, b.high_risks,
    b.pending_approvals, b.all_brs_agreed ? 'yes' : 'NO', b.headline || '']);
}

function sendBriefing_(b) {
  const rows = (b.reconciliations || []).map(r =>
    '<tr><td>' + esc_(r.account_id) + '</td><td>' + esc_(r.bank) + '</td><td>' + esc_(r.status) + '</td></tr>').join('');
  const scen = (b.scenarios || []).map(s =>
    '<tr><td>' + esc_(s.label) + '</td><td>' + esc_(s.peak_use) + ' (week ' + esc_(s.peak_week) + ')</td><td>' +
    esc_(s.first_alert_week || 'none') + '</td></tr>').join('');
  const risks = (b.risks || []).map(r => '<li><b>' + esc_(r.severity) + '</b> ' + esc_(r.text) + '</li>').join('');
  const actions = (b.actions || []).map(a => '<li>' + esc_(a) + '</li>').join('');
  const html =
    '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px">' +
    '<div style="background:#c62828;color:#fff;padding:4px 8px;font-size:12px">SAMPLE DATA - fictitious company</div>' +
    '<h2 style="color:#0f3d5e">CashSense briefing - as at ' + esc_(b.as_of) + '</h2>' +
    '<p><b>' + esc_(b.headline || '') + '</b></p>' +
    '<p>Cash in current + collections: <b>' + esc_(b.cash) + '</b><br>CC drawn: <b>' + esc_(b.cc_drawn) +
    '</b> (' + esc_(b.cc_use_today) + ' of limit)<br>Approvals waiting in Telegram: <b>' + esc_(b.pending_approvals) +
    '</b><br>Risks open or escalated: <b>' + esc_(b.open_risks) + '</b> (' + esc_(b.high_risks) + ' high)</p>' +
    '<h3>Bank reconciliation</h3><table border="1" cellpadding="4" style="border-collapse:collapse">' +
    '<tr><th>Account</th><th>Bank balance</th><th>BRS</th></tr>' + rows + '</table>' +
    '<h3>13-week forecast</h3><table border="1" cellpadding="4" style="border-collapse:collapse">' +
    '<tr><th>Scenario</th><th>Peak CC use</th><th>First 85% alert week</th></tr>' + scen + '</table>' +
    (risks ? '<h3>Risks</h3><ul>' + risks + '</ul>' : '') +
    (actions ? '<h3>Suggested actions (Gemini)</h3><ul>' + actions + '</ul>' : '') +
    '<p style="color:#777;font-size:12px">Sent by Google Apps Script from the CashSense daily run. ' +
    'Forecasts are estimates based on stated assumptions.</p></div>';
  MailApp.sendEmail({ to: me_(), subject: 'CashSense briefing ' + b.as_of + ' - CC ' + b.cc_use_today +
    (b.high_risks ? ' - ' + b.high_risks + ' HIGH risk(s)' : ''), htmlBody: html });
}

function eveningReminder() {
  const last = JSON.parse(PropertiesService.getScriptProperties().getProperty('LAST_BRIEFING') || '{}');
  if (!last.as_of || (!last.pending && !last.high)) return;
  MailApp.sendEmail({ to: me_(), subject: 'CashSense reminder: ' + (last.pending || 0) + ' approval(s), ' +
    (last.high || 0) + ' high risk(s) waiting',
    htmlBody: '<p>As at ' + esc_(last.as_of) + ': <b>' + esc_(last.pending) + '</b> approval(s) are waiting in Telegram ' +
      '(send /pending to the bot) and <b>' + esc_(last.high) + '</b> high-risk flag(s) are open.</p>' +
      '<p>' + esc_(last.headline || '') + '</p><p style="color:#777;font-size:12px">SAMPLE data.</p>' });
}

function staleCheck() {
  const at = Number(PropertiesService.getScriptProperties().getProperty('LAST_BRIEFING_AT') || 0);
  if (at && Date.now() - at < 26 * 3600 * 1000) return;
  MailApp.sendEmail({ to: me_(), subject: 'CashSense: no briefing received in the last 26 hours',
    htmlBody: '<p>The daily CashSense run has not sent a briefing. Check that the laptop, the CashSense API ' +
      'and n8n are running (scripts/start_cashsense.ps1, scripts/start_n8n.ps1).</p>' });
}

function weeklyDigest() {
  const id = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (!id) return;
  const values = SpreadsheetApp.openById(id).getSheetByName('Briefings').getDataRange().getValues();
  const last = values.slice(1).slice(-7);
  if (!last.length) return;
  const rows = last.map(r => '<tr><td>' + esc_(r[0]) + '</td><td>' + esc_(r[4]) + '</td><td>' + esc_(r[6]) +
    '</td><td>' + esc_(r[9]) + '</td><td>' + esc_(r[10]) + '</td></tr>').join('');
  MailApp.sendEmail({ to: me_(), subject: 'CashSense weekly digest',
    htmlBody: '<h3>Last ' + last.length + ' briefings</h3><table border="1" cellpadding="4" style="border-collapse:collapse">' +
      '<tr><th>Received</th><th>CC use</th><th>Worst peak</th><th>High risks</th><th>Approvals</th></tr>' + rows +
      '</table><p style="color:#777;font-size:12px">SAMPLE data.</p>' });
}

/** Run from the editor to test the email without CashSense. */
function testBriefing() {
  sendBriefing_({ as_of: 'TEST', headline: 'Test briefing from the Apps Script editor', cash: 'Rs 0.00',
    cc_drawn: 'Rs 0.00', cc_use_today: '0%', pending_approvals: 0, open_risks: 0, high_risks: 0 });
}
