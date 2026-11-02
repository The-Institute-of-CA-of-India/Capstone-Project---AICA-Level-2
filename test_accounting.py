import unittest,tempfile,sqlite3
from pathlib import Path
import accounting as a
class LedgerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=a.ROOT);self.old=a.DB;a.DB=Path(self.tmp.name)/'test.sqlite3';a.init()
  self.cid=a.create_company({'name':'Test UAE','currency':'AED','country':'UAE','fy_start':'2026-01-01'})['id']
  a.master(self.cid,'contacts',{'name':'Client','type':'Both'});s=a.state(self.cid);self.contact=s['contacts'][0]['id'];self.codes={x['code']:x['id'] for x in s['accounts']}
 def tearDown(self): a.DB=self.old;self.tmp.cleanup()
 def doc(self,kind='Sales',price='100',tax='5',dt='2026-01-10',**kw):
  code='4000' if kind in ('Sales','Credit note') else '1500' if kind=='Asset purchase' else '5000'
  return dict(kind=kind,date=dt,due_date=dt,currency='AED',rate='1',contact_id=self.contact,lines=[dict(account_id=self.codes[code],description='Test',quantity=1,price=price,tax=tax,discount=0)],**kw)
 def post(self,d):
  vid=a.save_draft(self.cid,d)['id'];a.post(self.cid,vid);return vid
 def report(self,end='2026-12-31'): return a.reports(self.cid,'2026-01-01',end)
 def test_draft_and_double_post(self):
  vid=a.save_draft(self.cid,self.doc())['id'];self.assertEqual(self.report()['summary']['income'],0);a.post(self.cid,vid)
  with self.assertRaises(ValueError): a.post(self.cid,vid)
  r=self.report();self.assertEqual(r['summary']['income'],10000);self.assertEqual(r['vat']['output'],500);self.assertEqual(r['summary']['trial_difference'],0);self.assertEqual(r['summary']['balance_difference'],0)
 def test_unbalanced_rejected(self):
  with self.assertRaises(ValueError): a.save_draft(self.cid,dict(kind='Journal',date='2026-01-01',lines=[{'account_id':self.codes['1010'],'debit':100,'credit':0},{'account_id':self.codes['3000'],'debit':0,'credit':90}]))
 def test_fx_and_partial_settlement(self):
  d=self.doc(price='100',tax='0');d.update(currency='USD',rate='3.67');vid=self.post(d)
  payment=dict(kind='Receipt',date='2026-02-01',currency='USD',rate='3.70',source_id=vid,amount='40',cash_account=self.codes['1010'])
  self.post(payment);r=self.report();self.assertEqual(r['aging'][0]['outstanding'],6000);self.assertEqual(r['aging'][0]['base'],22020)
  payment.update(date='2026-03-01',amount='60');self.post(payment);r=self.report();self.assertEqual(r['aging'],[]);self.assertEqual(r['summary']['cash'],37000);self.assertEqual(r['summary']['profit'],37000)
 def test_credit_and_purchase_debit_notes(self):
  for kind,note in [('Sales','Credit note'),('Purchase','Debit note')]:
   vid=self.post(self.doc(kind));self.post(self.doc(note,price='20',source_id=vid,dt='2026-01-15'))
  r=self.report();self.assertEqual([x['outstanding'] for x in r['aging']],[8400,8400]);self.assertEqual(r['summary']['trial_difference'],0)
 def test_reversal_and_historical_aging(self):
  vid=self.post(self.doc());pay=self.post(dict(kind='Receipt',date='2026-02-01',source_id=vid,amount=105))
  with self.assertRaises(ValueError): a.reverse(self.cid,vid,{'date':'2026-03-01','reason':'test'})
  a.reverse(self.cid,pay,{'date':'2026-03-01','reason':'test'});self.assertEqual(self.report('2026-02-28')['aging'],[]);self.assertEqual(self.report()['aging'][0]['outstanding'],10500)
  a.reverse(self.cid,vid,{'date':'2026-04-01','reason':'test'});r=self.report();self.assertEqual(r['aging'],[]);self.assertEqual(r['summary']['profit'],0);self.assertEqual(r['summary']['trial_difference'],0)
 def test_lock_and_company_isolation(self):
  other=a.create_company({'name':'Other','currency':'USD','country':'USA','fy_start':'2026-01-01'})['id'];d=self.doc()
  with self.assertRaises(ValueError): a.save_draft(other,d)
  a.lock(self.cid,{'date':'2026-01-31'})
  with self.assertRaises(ValueError): a.save_draft(self.cid,d)
  with self.assertRaises(ValueError): a.lock(self.cid,{'date':'2026-01-01'})
 def test_asset_depreciation_cap(self):
  vid=self.post(self.doc('Asset purchase',price='1200',tax='0',flow='Investing'))
  a.add_asset(self.cid,dict(name='Laptop',acquired='2026-01-10',cost=1200,residual=0,months=12,purchase_id=vid));aid=a.state(self.cid)['assets'][0]['id']
  a.depreciate(self.cid,aid,{'date':'2026-06-30'});a.depreciate(self.cid,aid,{'date':'2027-01-10'});self.assertEqual(a.state(self.cid)['assets'][0]['depreciated'],120000)
  with self.assertRaises(ValueError): a.depreciate(self.cid,aid,{'date':'2027-02-01'})
  with self.assertRaises(ValueError): a.add_asset(self.cid,dict(name='Duplicate',acquired='2026-01-10',cost=1,residual=0,months=12,purchase_id=vid))
 def test_bank_reconciliation(self):
  vid=self.post(dict(kind='Receipt',date='2026-01-10',amount=100,counter_account=self.codes['3000'],flow='Financing'));r=self.report();entry=next(x for x in r['ledger'] if x['cash']);d=dict(date='2026-01-31',account_id=self.codes['1010'],balance=100,entry_ids=[entry['id']]);a.reconcile(self.cid,d)
  with self.assertRaises(ValueError): a.reconcile(self.cid,d)
  self.assertEqual(self.report()['cashflow']['difference'],0)
 def test_overpayment_and_no_negative_values(self):
  vid=self.post(self.doc())
  with self.assertRaises(ValueError): self.post(dict(kind='Receipt',date='2026-01-20',amount=106,source_id=vid))
  for v in ('-10','NaN','Infinity'):
   with self.assertRaises(ValueError): a.save_draft(self.cid,self.doc(price=v))
 def test_group_aggregation(self):
  self.post(self.doc());r=a.group_report(dict(start='2026-01-01',end='2026-12-31',currency='USD',members=[{'id':self.cid,'rate':2}]))
  self.assertEqual(r['summary']['income'],20000)
 def test_rounding(self):
  d=self.doc(price='0.05');d['lines'][0]['quantity']=3;vid=self.post(d);v=next(v for v in a.state(self.cid)['vouchers'] if v['id']==vid);self.assertEqual(v['total'],16)
if __name__=='__main__': unittest.main(verbosity=2)

