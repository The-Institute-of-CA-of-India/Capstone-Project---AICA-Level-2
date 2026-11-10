// Arithmetic copied verbatim from the original Apps Script (calcVisit_), with the Google-only helpers stubbed.
// It contains no clinic data. It exists only so tests can prove the new engine gives identical totals.
var PAY_METHODS = ['Cash','M-Pesa','Bank Transfer'];
var Utilities = { getUuid: function(){ return 'abcdef12-0000'; } };
function today_(){ return '2026-01-01'; }
function round2_(n){ return Math.round((Number(n) || 0) * 100 + 1e-9) / 100; }
function calcVisit_(v){
  var lines = (v.lines || []).map(function(l){
    var qty = Number(l.qty) || 0, rate = Number(l.rate) || 0;
    return { name: String(l.name || '').slice(0, 160), category: String(l.category || ''),
             qty: qty, rate: rate, amount: round2_(qty * rate) };
  }).filter(function(l){ return l.name; });
  var subtotal = round2_(lines.reduce(function(a, l){ return a + l.amount; }, 0));
  var discount = Math.min(Math.max(round2_(v.discount), 0), subtotal);
  var net = round2_(subtotal - discount);
  var vatOn = !!v.vatOn, rate = Number(v.vatRate) || 0, inclusive = !!v.vatInclusive;
  var vat = 0, total = net, taxable = net;
  if(vatOn && rate > 0){
    if(inclusive){ vat = round2_(net * rate / (100 + rate)); taxable = round2_(net - vat); total = net; }
    else { vat = round2_(net * rate / 100); taxable = net; total = round2_(net + vat); }
  }
  var payments = (v.payments || []).map(function(p){
    var m = PAY_METHODS.indexOf(p.method) >= 0 ? p.method : 'Cash';
    return { id: String(p.id || Utilities.getUuid().slice(0, 8)), date: String(p.date || v.date || today_()).slice(0, 10),
             method: m, amount: round2_(p.amount), ref: String(p.ref || '').slice(0, 60) };
  }).filter(function(p){ return p.amount > 0; });
  var paid = round2_(payments.reduce(function(a, p){ return a + p.amount; }, 0));
  var balance = round2_(total - paid);
  var status = v.void ? 'Void' : (total <= 0 ? 'No charge' : (balance <= 0.005 ? 'Paid' : (paid > 0 ? 'Part-paid' : 'Unpaid')));
  v.lines = lines; v.subtotal = subtotal; v.discount = discount; v.vatOn = vatOn; v.vatRate = rate;
  v.vatInclusive = inclusive; v.vat = vat; v.taxable = taxable; v.total = total;
  v.payments = payments; v.paid = paid; v.balance = balance; v.status = status;
  return v;
}
export { calcVisit_ };
