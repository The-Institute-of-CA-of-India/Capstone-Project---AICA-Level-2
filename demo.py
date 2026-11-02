"""Optional demonstration data, isolated from the user's live database."""
import accounting as a

def seed():
 with a.connection() as c:
  if c.execute('SELECT COUNT(*) FROM companies').fetchone()[0]: return
 cid=a.create_company(dict(name='DEMO · Gulf Trading LLC',country='United Arab Emirates',currency='AED',address='Dubai, UAE · Fictional training company',trn='',fy_start='2026-01-01'))['id']
 a.master(cid,'contacts',dict(name='DEMO · Oasis Retail',type='Customer',address='Dubai, UAE'))
 a.master(cid,'contacts',dict(name='DEMO · Meridian Supplies',type='Supplier',address='Abu Dhabi, UAE'))
 a.master(cid,'items',dict(name='Consulting services',sku='SRV-01',price='2500',tax='5',description='Professional consulting services'))
 s=a.state(cid);codes={x['code']:x['id'] for x in s['accounts']};customer,supplier=[x['id'] for x in s['contacts']]
 def post(d):
  v=a.save_draft(cid,d)['id'];a.post(cid,v);return v
 post(dict(kind='Opening balance',date='2026-01-01',flow='Financing',memo='Demonstration capital contribution',lines=[dict(account_id=codes['1010'],debit=150000,credit=0),dict(account_id=codes['3000'],debit=0,credit=150000)]))
 def doc(kind,dt,price,code,contact=None,**kw):
  return dict(kind=kind,date=dt,due_date=dt,contact_id=contact,currency='AED',rate=1,lines=[dict(account_id=codes[code],description='Demonstration '+kind.lower(),quantity=1,price=price,discount=0,tax=5)],**kw)
 sale=post(doc('Sales','2026-02-01',48000,'4000',customer))
 post(doc('Purchase','2026-02-02',18000,'5000',supplier))
 post(dict(kind='Receipt',date='2026-02-15',amount=30000,source_id=sale,currency='AED',rate=1))
 post(doc('Expense','2026-03-01',4200,'5100'))
 asset=post(doc('Asset purchase','2026-03-01',12000,'1500',flow='Investing'))
 a.add_asset(cid,dict(name='DEMO · Office equipment',acquired='2026-03-01',cost=12000,residual=0,months=36,purchase_id=asset))
 aid=a.state(cid)['assets'][0]['id'];a.depreciate(cid,aid,dict(date='2026-09-30'))
 a.save_draft(cid,doc('Sales','2026-10-01',7500,'4000',customer))
 a.create_company(dict(name='DEMO · Meridian UK Ltd',country='United Kingdom',currency='GBP',fy_start='2026-01-01'))
