/** CSV export with protection against spreadsheet formula injection (=, +, -, @ at the start of a cell). */
export function toCsv(rows: (string | number | boolean | undefined | null)[][]): string {
  return rows.map((r) => r.map((c) => {
    let s = c == null ? '' : String(c);
    if (/^[=+\-@\t\r]/.test(s) && !/^-?\d+(\.\d+)?$/.test(s)) s = "'" + s;
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }).join(',')).join('\r\n');
}
export function downloadText(filename: string, text: string, mime = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob(['\uFEFF' + text], { type: mime }));
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
