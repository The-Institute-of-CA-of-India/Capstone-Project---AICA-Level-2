/**
 * TDS Follow-up Inbox Sync – Google Apps Script (free alternative to n8n, Gmail only)
 * -------------------------------------------------------------------------------
 * Returns the sent follow-ups and deductor replies whose subject carries
 * [Ref TDS/<PAN>/<TAN>/<FY>], with PDF attachments, to the
 * TDS Credit Reconciliation Assistant. Nothing is stored anywhere.
 *
 * Setup (5 minutes):
 *  1. Go to https://script.google.com → New project → paste this file.
 *  2. Change ACCESS_KEY below to your own secret text.
 *  3. Deploy → New deployment → type "Web app"
 *       Execute as: Me    |    Who has access: Anyone
 *  4. Authorise Gmail access when asked, then copy the Web app URL (ends in /exec).
 *  5. In the tool: tab 4 → Inbox sync settings → paste the URL and the same ACCESS_KEY.
 */
const ACCESS_KEY = 'change-this-to-your-own-secret';
const MAX_PDF_BYTES = 3 * 1024 * 1024;

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.key !== ACCESS_KEY) return json_({ ok: false, error: 'Invalid key' });
  const pan = String(p.pan || '').toUpperCase();
  if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) return json_({ ok: false, error: 'Invalid PAN' });
  const days = Math.min(Math.max(parseInt(p.days, 10) || 90, 1), 730);
  const me = [Session.getActiveUser().getEmail()].concat(String(p.me || '').split(','))
    .map(function (s) { return s.trim().toLowerCase(); }).filter(String);

  const REF = /Ref TDS\/([A-Z]{5}[0-9]{4}[A-Z])\/([A-Z]{4}[0-9]{5}[A-Z])\/([0-9]{4}-[0-9]{2})/;
  const threads = GmailApp.search('subject:"Ref TDS/' + pan + '" newer_than:' + days + 'd', 0, 200);
  const messages = [];
  threads.forEach(function (th) {
    th.getMessages().forEach(function (m) {
      const subject = m.getSubject() || '';
      const r = subject.match(REF);
      if (!r || r[1] !== pan) return;
      const fromRaw = m.getFrom() || '';
      const from = (fromRaw.match(/<([^>]+)>/) || [null, fromRaw])[1].trim();
      const fromName = fromRaw.replace(/<[^>]+>/, '').replace(/"/g, '').trim();
      const attachments = [];
      m.getAttachments({ includeInlineImages: false }).forEach(function (a) {
        const name = a.getName() || 'attachment.pdf';
        if (!/pdf$/i.test(a.getContentType()) && !/\.pdf$/i.test(name)) return;
        if (attachments.length >= 5) return;
        const bytes = a.getBytes();
        if (bytes.length > MAX_PDF_BYTES) { attachments.push({ name: name, skipped: 'too large' }); return; }
        attachments.push({ name: name, base64: Utilities.base64Encode(bytes) });
      });
      messages.push({
        id: m.getId(), provider: 'gmail', threadId: th.getId(), subject: subject,
        refPan: r[1], refTan: r[2], refFy: r[3],
        direction: me.indexOf(from.toLowerCase()) >= 0 ? 'sent' : 'received',
        from: from, fromName: fromName, to: m.getTo(), date: m.getDate().toISOString(),
        body: stripQuoted_(m.getPlainBody()), attachments: attachments
      });
    });
  });
  messages.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
  return json_({ ok: true, pan: pan, syncedAt: new Date().toISOString(), count: messages.length, messages: messages });
}

function stripQuoted_(t) {
  const out = [];
  const lines = String(t || '').replace(/\r/g, '').split('\n');
  for (var i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/^On .+wrote:\s*$/.test(l) || /^-{2,}\s*Original Message/i.test(l) || /^From:\s/.test(l) || /^_{5,}/.test(l)) break;
    if (/^>/.test(l)) continue;
    out.push(l);
  }
  return out.join('\n').trim().slice(0, 4000);
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
