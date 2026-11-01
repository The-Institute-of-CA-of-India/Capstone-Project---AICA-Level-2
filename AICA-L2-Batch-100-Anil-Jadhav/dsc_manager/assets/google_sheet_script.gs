/**
 * DSC Management Tool - Google Sheet for the partners.
 *
 * The custodian's PC sends the reports here; this script writes one tab per
 * report (with filters) and the Dashboard. Do not edit the tabs by hand:
 * every update replaces them.
 *
 * Setup (once): Extensions > Apps Script, replace everything with this script,
 * Save, then Deploy > New deployment > Web app, Execute as: Me,
 * Who has access: Anyone > Deploy > Authorise. Copy the "Web app" URL into
 * DSC Manager > Settings > Google Sheet.
 */
var KEY = 'PUT-KEY-HERE';  // written in by DSC Manager - keep it secret
var NAVY = '#1b2a41';
var ACCENT = '#2b5797';
var MUTED = '#64748b';
var RED = '#b42318';
var TILE = '#eef2f7';
var FORMATS = {text: '@', num: '0', date: 'dd-mm-yyyy', datetime: 'dd-mm-yyyy h:mm AM/PM'};

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var data = JSON.parse(e.postData.contents);
    if (data.key !== KEY) {
      return reply({ok: false, error: 'This sheet has a different key. In DSC Manager open Settings > Google Sheet, ' +
                                      'click Copy Script, paste it here again and deploy a new version.'});
    }
    if (data.ping) {
      return reply({ok: true, ping: true, sheet: SpreadsheetApp.getActiveSpreadsheet().getName()});
    }
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    writeDashboard(ss, data);
    for (var i = 0; i < data.tabs.length; i++) {
      writeTab(ss, data, data.tabs[i], i + 1);
    }
    removeBlankDefault(ss, data);
    SpreadsheetApp.flush();
    return reply({ok: true, tabs: data.tabs.length + 1, updated: data.updated});
  } catch (err) {
    return reply({ok: false, error: 'Sheet script error: ' + err});
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return ContentService.createTextOutput('The DSC Manager sheet script is running. Paste this link into ' +
                                         'DSC Manager > Settings > Google Sheet.');
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** The tab with this name at this position (0 = first), emptied. */
function freshTab(ss, name, position) {
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  ss.setActiveSheet(sh);
  ss.moveActiveSheet(position + 1);
  var filter = sh.getFilter();
  if (filter) filter.remove();
  sh.getCharts().forEach(function (c) { sh.removeChart(c); });
  sh.clear();
  sh.setFrozenRows(0);
  if (sh.getProtections(SpreadsheetApp.ProtectionType.SHEET).length === 0) {
    sh.protect().setDescription('Filled in by DSC Manager').setWarningOnly(true);
  }
  return sh;
}

/** Firm name, address, report title and update time; returns the next free row. */
function header(sh, data, title) {
  sh.getRange(1, 1).setValue(data.firm || 'DSC Management Tool').setFontSize(14).setFontWeight('bold')
    .setFontColor(NAVY);
  sh.getRange(2, 1).setValue((data.address || []).join(', ')).setFontColor(MUTED);
  sh.getRange(3, 1).setValue(title).setFontSize(12).setFontWeight('bold').setFontColor(ACCENT);
  sh.getRange(4, 1).setValue('Updated on ' + data.updated + ' from the custodian\'s PC. Do not edit - every ' +
                             'update replaces this tab.').setFontStyle('italic').setFontColor(MUTED);
  return 6;
}

/** A table (headings + rows) at row; returns the row after it. */
function writeTable(sh, row, t) {
  var ncol = t.headings.length;
  sh.getRange(row, 1, 1, ncol).setValues([t.headings]).setFontWeight('bold').setFontColor('#ffffff')
    .setBackground(NAVY).setWrap(true).setVerticalAlignment('middle');
  if (!t.rows.length) {
    sh.getRange(row + 1, 1).setValue('Nothing to show.').setFontColor(MUTED).setFontStyle('italic');
    return row + 2;
  }
  var range = sh.getRange(row + 1, 1, t.rows.length, ncol);
  var formats = t.rows.map(function (r) {
    return t.kinds.map(function (kind, c) {
      // A date-time with no time recorded shows the date only.
      if (kind === 'datetime' && String(r[c]).length <= 10) return FORMATS.date;
      return FORMATS[kind] || '@';
    });
  });
  range.setNumberFormats(formats);  // before the values, so text stays text
  range.setValues(t.rows);
  range.setBackgrounds(t.rows.map(function (r, i) {
    var color = t.colors[i] || '#ffffff';
    return t.kinds.map(function () { return color; });
  }));
  return row + 1 + t.rows.length;
}

function writeTab(ss, data, t, position) {
  var sh = freshTab(ss, t.name, position);
  var head = header(sh, data, t.title);
  var end = writeTable(sh, head, t);
  sh.setFrozenRows(head);
  sh.getRange(head, 1, Math.max(end - head, 2), t.headings.length).createFilter();
  sh.autoResizeColumns(1, t.headings.length);
  for (var c = 1; c <= t.headings.length; c++) {
    var w = sh.getColumnWidth(c);
    sh.setColumnWidth(c, Math.min(Math.max(w + 16, 80), 320));
  }
}

function writeDashboard(ss, data) {
  var d = data.dashboard;
  var sh = freshTab(ss, 'Dashboard', 0);
  var row = header(sh, data, 'Dashboard');
  // Tiles: four in a row, each a number, its name and a note.
  for (var i = 0; i < d.cards.length; i++) {
    var card = d.cards[i];
    var r = row + Math.floor(i / 4) * 4;
    var c = 1 + (i % 4);
    var tile = sh.getRange(r, c, 3, 1).setBackground(TILE).setHorizontalAlignment('center');
    tile.setBorder(true, true, true, true, false, false, '#cbd5e1', SpreadsheetApp.BorderStyle.SOLID);
    sh.getRange(r, c).setValue(card[1]).setNumberFormat('0').setFontSize(22).setFontWeight('bold')
      .setFontColor(card[3] ? RED : NAVY);
    sh.getRange(r + 1, c).setValue(card[0]).setFontWeight('bold');
    sh.getRange(r + 2, c).setValue(card[2]).setFontColor(card[3] ? RED : MUTED).setFontSize(9);
  }
  for (var col = 1; col <= 4; col++) sh.setColumnWidth(col, 190);
  sh.setColumnWidth(5, 24);

  // Who holds the tokens: a small table and a chart beside the tiles.
  sh.getRange(row, 6, 1, 2).setValues([['Who holds the tokens', 'Tokens']]).setFontWeight('bold')
    .setFontColor('#ffffff').setBackground(NAVY);
  sh.getRange(row + 1, 6, d.holders.length, 2).setValues(d.holders);
  sh.getRange(row + 1, 7, d.holders.length, 1).setNumberFormat('0');
  sh.setColumnWidth(6, 170);
  sh.setColumnWidth(7, 80);
  var chart = sh.newChart().setChartType(Charts.ChartType.PIE)
    .addRange(sh.getRange(row, 6, d.holders.length + 1, 2))
    .setPosition(row + d.holders.length + 2, 6, 0, 0)
    .setOption('title', 'Who holds the tokens').setOption('pieHole', 0.45)
    .setOption('colors', [NAVY, ACCENT, '#0f766e']).setOption('width', 340).setOption('height', 210)
    .build();
  sh.insertChart(chart);

  row += Math.ceil(d.cards.length / 4) * 4 + 1;
  row = Math.max(row, 6 + d.holders.length + 13);  // below the chart
  [d.out_now, d.expiring].forEach(function (t) {
    sh.getRange(row, 1).setValue(t.title).setFontSize(12).setFontWeight('bold').setFontColor(ACCENT);
    row = writeTable(sh, row + 1, t) + 1;
  });
}

/** The empty "Sheet1" a new spreadsheet starts with. */
function removeBlankDefault(ss, data) {
  var ours = {Dashboard: true};
  data.tabs.forEach(function (t) { ours[t.name] = true; });
  ss.getSheets().forEach(function (sh) {
    if (!ours[sh.getName()] && sh.getLastRow() === 0 && sh.getLastColumn() === 0) ss.deleteSheet(sh);
  });
  ss.setActiveSheet(ss.getSheetByName('Dashboard'));
}
