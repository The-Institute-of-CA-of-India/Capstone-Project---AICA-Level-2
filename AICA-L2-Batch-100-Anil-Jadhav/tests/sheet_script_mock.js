// Runs google_sheet_script.gs against a mock of Google's spreadsheet objects with a real payload.
const fs = require('fs');
const dir = process.argv[2];
const src = fs.readFileSync(process.argv[3], 'utf8').replace('PUT-KEY-HERE', 'secret');
function chain() {  // any method returns the same object
  const p = new Proxy(function () {}, { get: () => () => p });
  return p;
}
function makeRange(sh, r, c, nr, nc) {
  const check = (arr, what) => {
    if (!Array.isArray(arr) || arr.length !== nr || arr.some(x => x.length !== nc))
      throw new Error(`${sh.name} ${what} size mismatch at R${r}C${c}: want ${nr}x${nc}`);
  };
  const rg = {
    setValues(v) { check(v, 'setValues'); for (let i = 0; i < nr; i++) for (let j = 0; j < nc; j++) sh.cells[(r + i) + ',' + (c + j)] = v[i][j]; return rg; },
    setNumberFormats(v) { check(v, 'setNumberFormats'); for (let i = 0; i < nr; i++) for (let j = 0; j < nc; j++) sh.fmts[(r + i) + ',' + (c + j)] = v[i][j]; return rg; },
    setBackgrounds(v) { check(v, 'setBackgrounds'); return rg; },
    setValue(v) { if (nr * nc !== 1) throw new Error('setValue on a block'); sh.cells[r + ',' + c] = v; return rg; },
    createFilter() { if (sh.filter) throw new Error('filter exists'); sh.filter = { remove() { sh.filter = null; } }; return rg; },
  };
  for (const m of ['setFontWeight', 'setFontColor', 'setBackground', 'setWrap', 'setVerticalAlignment',
    'setHorizontalAlignment', 'setBorder', 'setFontSize', 'setFontStyle', 'setNumberFormat']) rg[m] = () => rg;
  return rg;
}
function makeSheet(name) {
  const sh = { name, cells: {}, fmts: {}, filter: null, charts: [], prot: [] };
  Object.assign(sh, {
    getName: () => name,
    getRange: (r, c, nr = 1, nc = 1) => {
      if (r < 1 || c < 1 || nr < 1 || nc < 1) throw new Error(`bad range ${r},${c},${nr},${nc}`);
      return makeRange(sh, r, c, nr, nc);
    },
    getFilter: () => sh.filter,
    getCharts: () => sh.charts.slice(), removeChart: (c) => { sh.charts = sh.charts.filter(x => x !== c); },
    clear: () => { sh.cells = {}; sh.fmts = {}; return sh; }, setFrozenRows: () => sh,
    getProtections: () => sh.prot, protect: () => { const p = chain(); sh.prot.push(p); return p; },
    autoResizeColumns: () => sh, getColumnWidth: () => 100, setColumnWidth: () => sh,
    newChart: () => chain(), insertChart: (c) => sh.charts.push(c),
    getLastRow: () => (Object.keys(sh.cells).length ? 1 : 0), getLastColumn: () => (Object.keys(sh.cells).length ? 1 : 0),
  });
  return sh;
}
let sheets = [makeSheet('Sheet1')];
let active = null;
const ss = {
  getName: () => 'Test', getSheets: () => sheets.slice(),
  getSheetByName: (n) => sheets.find(s => s.name === n) || null,
  insertSheet: (n) => { const s = makeSheet(n); sheets.push(s); return s; },
  setActiveSheet: (s) => { active = s; return s; },
  moveActiveSheet: (pos) => { sheets = sheets.filter(s => s !== active); sheets.splice(pos - 1, 0, active); },
  deleteSheet: (s) => { sheets = sheets.filter(x => x !== s); },
};
global.SpreadsheetApp = { getActiveSpreadsheet: () => ss, flush() {}, BorderStyle: { SOLID: 1 }, ProtectionType: { SHEET: 1 } };
global.Charts = { ChartType: { PIE: 'pie' } };
global.LockService = { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) };
global.ContentService = { MimeType: { JSON: 'json' }, createTextOutput: (t) => ({ text: t, setMimeType() { return this; } }) };
eval(src + '\nglobal.doPost = doPost;');

const body = fs.readFileSync(dir + '/payload.json', 'utf8');
for (let run = 1; run <= 2; run++) console.log('run', run, doPost({ postData: { contents: body } }).text);
const empty = JSON.parse(body);
empty.tabs.forEach(t => { t.rows = []; t.colors = []; });
empty.dashboard.out_now.rows = []; empty.dashboard.expiring.rows = [];
console.log('empty data:', doPost({ postData: { contents: JSON.stringify(empty) } }).text);
doPost({ postData: { contents: body } });
console.log('wrong key:', doPost({ postData: { contents: JSON.stringify({ key: 'x' }) } }).text.slice(0, 70));
console.log('ping:', doPost({ postData: { contents: JSON.stringify({ key: 'secret', ping: true }) } }).text);
console.log('tabs:', sheets.map(s => `${s.name}(${s.charts.length}c ${s.prot.length}p ${s.filter ? 'F' : '-'})`).join(' '));
const d = sheets[0].cells;
console.log('dashboard:', d['1,1'], '|', d['3,1'], '|', d['4,1']);
console.log('tiles:', d['6,1'], d['7,1'], '/', d['6,3'], d['7,3'], d['8,3'], '/', d['14,1'], d['15,1']);
console.log('lists:', Object.keys(d).filter(k => /^2[2-9],1$/.test(k)).map(k => k + '=' + d[k]).slice(0, 4).join(' ; '));
const c = sheets[1];
console.log('custody headings:', [1, 2, 3, 4, 5, 6, 7].map(i => c.cells['6,' + i]).join(' | '));
console.log('custody row:', [1, 2, 3, 4, 5, 6, 7].map(i => c.cells['7,' + i] + ' [' + c.fmts['7,' + i] + ']').join(' | '));
