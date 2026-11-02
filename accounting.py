"""LedgerDesk double-entry accounting engine; monetary storage uses integer cents."""
import sqlite3, json, calendar, sys
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parent
DATA_ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else ROOT
DB=DATA_ROOT/'data'/'ledgerdesk.sqlite3'
KINDS=['Sales','Purchase','Expense','Income','Asset purchase','Receipt','Payment','Credit note','Debit note','Journal','Opening balance']
TYPES=['Asset','Liability','Equity','Income','Expense']
COA=[('1000','Cash','Asset',1),('1010','Bank','Asset',1),('1100','Trade receivables','Asset',0),('1200','Inventory','Asset',0),('1300','Recoverable input VAT','Asset',0),('1400','Prepayments','Asset',0),('1500','Property, plant and equipment','Asset',0),('1590','Accumulated depreciation','Asset',0),('2000','Trade payables','Liability',0),('2100','Output VAT payable','Liability',0),('2200','Accruals','Liability',0),('2300','Borrowings','Liability',0),('3000','Share capital','Equity',0),('3100','Retained earnings','Equity',0),('4000','Sales revenue','Income',0),('4100','Other income','Income',0),('4200','Realised FX gain','Income',0),('5000','Cost of sales / purchases','Expense',0),('5100','General expenses','Expense',0),('5200','Employee costs','Expense',0),('5300','Depreciation','Expense',0),('5400','Realised FX loss','Expense',0),('5500','Tax expense','Expense',0)]
def dec(x):
    try:
        v=Decimal(str(x))
        if not v.is_finite() or abs(v)>Decimal('100000000000'): raise ValueError('Number outside permitted range.')
        return v
    except (InvalidOperation,TypeError): raise ValueError('Enter a valid number.')
def money(x): return int((dec(x)*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def convert(cents,rate): return int((Decimal(cents)*dec(rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def day(x): return date.fromisoformat(str(x)).isoformat()
def required(x,label):
    s=str(x or '').strip()
    if not s or len(s)>500: raise ValueError(label+' is required (maximum 500 characters).')
    return s
def currency(x):
    s=str(x).upper().strip()
    if len(s)!=3 or not s.isascii() or not s.isalpha(): raise ValueError('Use a three-letter currency code.')
    if s in ('BHD','KWD','OMR','JOD','TND','LYD','IQD','JPY','KRW','CLP','VND'): raise ValueError('This release supports two-decimal currencies only.')
    return s
@contextmanager
def connection(write=False):
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    try:
        if write: c.execute('BEGIN IMMEDIATE')
        yield c
        c.commit()
    except Exception:
        c.rollback();raise
    finally: c.close()
def init():
    with connection() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY,name TEXT NOT NULL,currency TEXT NOT NULL,country TEXT NOT NULL,trn TEXT,address TEXT,fy_start TEXT NOT NULL,locked_until TEXT DEFAULT '',created TEXT);
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,company_id INTEGER REFERENCES companies(id),code TEXT NOT NULL,name TEXT NOT NULL,type TEXT NOT NULL,cash INTEGER DEFAULT 0,UNIQUE(company_id,code));
        CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY,company_id INTEGER REFERENCES companies(id),name TEXT NOT NULL,type TEXT NOT NULL,email TEXT,trn TEXT,address TEXT);
        CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,company_id INTEGER REFERENCES companies(id),name TEXT NOT NULL,sku TEXT,price TEXT,tax TEXT,description TEXT);
        CREATE TABLE IF NOT EXISTS vouchers(id INTEGER PRIMARY KEY,company_id INTEGER REFERENCES companies(id),number TEXT NOT NULL,kind TEXT NOT NULL,date TEXT NOT NULL,due_date TEXT,status TEXT NOT NULL,contact_id INTEGER REFERENCES contacts(id),currency TEXT NOT NULL,rate TEXT NOT NULL,total INTEGER DEFAULT 0,base_total INTEGER DEFAULT 0,reference TEXT,memo TEXT,data TEXT NOT NULL,source_id INTEGER REFERENCES vouchers(id),reversed_by INTEGER REFERENCES vouchers(id),created TEXT,UNIQUE(company_id,number));
        CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,voucher_id INTEGER REFERENCES vouchers(id),account_id INTEGER REFERENCES accounts(id),debit INTEGER NOT NULL CHECK(debit>=0),credit INTEGER NOT NULL CHECK(credit>=0),flow TEXT NOT NULL,reconciled TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS allocations(id INTEGER PRIMARY KEY,source_id INTEGER REFERENCES vouchers(id),voucher_id INTEGER REFERENCES vouchers(id),amount INTEGER NOT NULL,base_amount INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY,company_id INTEGER REFERENCES companies(id),name TEXT NOT NULL,acquired TEXT NOT NULL,cost INTEGER NOT NULL,residual INTEGER NOT NULL,months INTEGER NOT NULL,last_date TEXT NOT NULL,depreciated INTEGER DEFAULT 0,purchase_id INTEGER REFERENCES vouchers(id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,company_id INTEGER,timestamp TEXT,action TEXT,detail TEXT);
        CREATE INDEX IF NOT EXISTS voucher_dates ON vouchers(company_id,date,status);
        CREATE INDEX IF NOT EXISTS ledger_accounts ON entries(account_id,voucher_id);
        ''')
def audit(c,cid,action,detail): c.execute('INSERT INTO audit(company_id,timestamp,action,detail) VALUES(?,?,?,?)',(cid,datetime.now().isoformat(timespec='seconds'),action,str(detail)))
def company(c,cid):
    r=c.execute('SELECT * FROM companies WHERE id=?',(cid,)).fetchone()
    if not r: raise ValueError('Company not found.')
    return dict(r)
def create_company(d):
    with connection(True) as c:
        cid=c.execute('INSERT INTO companies(name,currency,country,trn,address,fy_start,created) VALUES(?,?,?,?,?,?,?)',(required(d.get('name'),'Company name'),currency(d.get('currency','AED')),required(d.get('country','UAE'),'Country'),d.get('trn',''),d.get('address',''),day(d['fy_start']),datetime.now().isoformat())).lastrowid
        c.executemany('INSERT INTO accounts(company_id,code,name,type,cash) VALUES(?,?,?,?,?)',[(cid,*a) for a in COA]);audit(c,cid,'Company created',d['name']);return {'id':cid}
def master(cid,kind,d):
    with connection(True) as c:
        company(c,cid);name=required(d.get('name'),'Name')
        if kind=='accounts':
            if d.get('type') not in TYPES: raise ValueError('Invalid account type.')
            cash=int(bool(d.get('cash')))
            if cash and d['type']!='Asset': raise ValueError('Cash/bank must be an asset.')
            c.execute('INSERT INTO accounts(company_id,code,name,type,cash) VALUES(?,?,?,?,?)',(cid,required(d.get('code'),'Code'),name,d['type'],cash))
        elif kind=='contacts':
            if d.get('type') not in ('Customer','Supplier','Both'): raise ValueError('Invalid contact type.')
            c.execute('INSERT INTO contacts(company_id,name,type,email,trn,address) VALUES(?,?,?,?,?,?)',(cid,name,d['type'],d.get('email',''),d.get('trn',''),d.get('address','')))
        elif kind=='items':
            if dec(d.get('price',0))<0 or not 0<=dec(d.get('tax',0))<=100: raise ValueError('Invalid price or tax rate.')
            c.execute('INSERT INTO items(company_id,name,sku,price,tax,description) VALUES(?,?,?,?,?,?)',(cid,name,d.get('sku',''),str(d.get('price',0)),str(d.get('tax',0)),d.get('description','')))
        else: raise ValueError('Unknown master.')
        audit(c,cid,'Master added',kind+': '+name);return {'ok':True}
def check_date(co,dt):
    day(dt)
    if dt<co['fy_start']: raise ValueError('Date precedes the company books start date.')
    if co['locked_until'] and dt<=co['locked_until']: raise ValueError('This accounting period is locked.')
def outstanding(c,vid):
    v=c.execute('SELECT * FROM vouchers WHERE id=?',(vid,)).fetchone()
    if not v: raise ValueError('Source document not found.')
    a=c.execute("SELECT COALESCE(SUM(a.amount),0),COALESCE(SUM(a.base_amount),0) FROM allocations a JOIN vouchers v ON v.id=a.voucher_id WHERE a.source_id=? AND v.status='Posted'",(vid,)).fetchone()
    return v['total']-a[0],v['base_total']-a[1]
def build(c,cid,d):
    co=company(c,cid);kind=d.get('kind')
    if kind not in KINDS: raise ValueError('Invalid voucher type.')
    dt=day(d['date']);check_date(co,dt);due=day(d.get('due_date') or dt)
    if due<dt: raise ValueError('Due date cannot precede document date.')
    cur=currency(d.get('currency',co['currency']));rate=dec(d.get('rate','1'))
    if rate<=0 or rate>1000000 or (cur==co['currency'] and rate!=1): raise ValueError('Enter a positive exchange rate; base-currency rate must be 1.')
    accounts={r['id']:dict(r) for r in c.execute('SELECT * FROM accounts WHERE company_id=?',(cid,))};codes={r['code']:r['id'] for r in accounts.values()}
    contact=int(d['contact_id']) if d.get('contact_id') else None
    if contact:
        p=c.execute('SELECT * FROM contacts WHERE id=? AND company_id=?',(contact,cid)).fetchone()
        if not p: raise ValueError('Invalid company contact.')
    if kind in ('Sales','Purchase','Credit note','Debit note') and not contact: raise ValueError('Select a customer or supplier.')
    flow=d.get('flow','Operating')
    if flow not in ('Operating','Investing','Financing'): raise ValueError('Select a cash-flow category.')
    entries=[]
    def add(a,amount):
        a=int(a)
        if a not in accounts: raise ValueError('Invalid company account.')
        if amount: entries.append((a,max(amount,0),max(-amount,0),flow))
    source=None;allocation=None;total=0;base=0;calculated=[];net_total=0;vat_total=0
    if kind in ('Journal','Opening balance'):
        if cur!=co['currency']: raise ValueError('Journals must use base currency.')
        for line in d.get('lines',[]):
            dr,cr=money(line.get('debit',0)),money(line.get('credit',0))
            if dr<0 or cr<0 or (dr and cr): raise ValueError('Each journal line needs one debit or credit.')
            add(line['account_id'],dr-cr)
        total=base=sum(e[1] for e in entries)
    elif kind in ('Receipt','Payment'):
        total=money(d.get('amount',0));base=convert(total,rate)
        if total<=0 or base<=0: raise ValueError('Amount must be positive.')
        cash=int(d.get('cash_account') or codes['1010'])
        if cash not in accounts or not accounts[cash]['cash']: raise ValueError('Select a cash/bank account.')
        source=int(d['source_id']) if d.get('source_id') else None;sign=1 if kind=='Receipt' else -1;add(cash,sign*base);carrying=base
        if source:
            s=c.execute('SELECT * FROM vouchers WHERE id=? AND company_id=?',(source,cid)).fetchone();expected='Sales' if kind=='Receipt' else 'Purchase'
            if not s or s['kind']!=expected or s['status']!='Posted' or s['currency']!=cur or dt<s['date']: raise ValueError('Select an earlier posted '+expected+' in the same currency.')
            if contact and contact!=s['contact_id']: raise ValueError('Contact does not match the invoice.')
            contact=s['contact_id'];remaining,remain_base=outstanding(c,source)
            if total>remaining: raise ValueError('Settlement exceeds outstanding amount.')
            carrying=remain_base if total==remaining else convert(total,s['rate']);allocation=(source,total,carrying)
            add(codes['1100' if kind=='Receipt' else '2000'],-sign*carrying);diff=sign*(carrying-base);add(codes['5400' if diff>0 else '4200'],diff)
        else:
            counter=int(d.get('counter_account') or codes['4100' if kind=='Receipt' else '5100'])
            if counter in (codes['1100'],codes['2000']): raise ValueError('Select a source invoice to settle receivables/payables.')
            add(counter,-sign*base)
    else:
        sales=kind in ('Sales','Income','Credit note');credit=kind in ('Credit note','Debit note')
        if credit:
            source=int(d.get('source_id') or 0);s=c.execute('SELECT * FROM vouchers WHERE id=? AND company_id=?',(source,cid)).fetchone()
            if not s or s['kind']!=('Sales' if sales else 'Purchase') or s['status']!='Posted' or s['currency']!=cur or s['contact_id']!=contact or dt<s['date']: raise ValueError('Credit/debit notes require a matching earlier posted invoice/bill.')
            if rate!=dec(s['rate']): raise ValueError('Use the source document exchange rate for this note.')
        sign=(-1 if sales else 1)*(-1 if credit else 1);tax_total=0
        for line in d.get('lines',[]):
            required(line.get('description'),'Line description');qty=dec(line.get('quantity',1));price=dec(line.get('price',0));discount=dec(line.get('discount',0));tax=dec(line.get('tax',0))
            if qty<=0 or price<0 or not 0<=discount<=100 or not 0<=tax<=100: raise ValueError('Check quantity, price, discount and tax rate.')
            net=money(qty*price*(1-discount/100));vat=convert(net,tax/100);account=int(line['account_id'])
            if account not in accounts or accounts[account]['cash'] or account in (codes['1100'],codes['2000'],codes['1300'],codes['2100']): raise ValueError('Select a revenue, expense or non-control asset account.')
            if sales and accounts[account]['type']!='Income': raise ValueError('Sales/income lines require income accounts.')
            if not sales and accounts[account]['type'] not in ('Asset','Expense'): raise ValueError('Purchase lines require expense or asset accounts.')
            if kind=='Asset purchase' and account!=codes['1500']: raise ValueError('Asset purchases use account 1500.')
            bnet=convert(net,rate);bvat=convert(vat,rate);add(account,sign*bnet);tax_total+=bvat;total+=net+vat;base+=bnet+bvat
            net_total+=net;vat_total+=vat;calculated.append(dict(description=line['description'],quantity=str(qty),price=str(price),discount=str(discount),tax=str(tax),net=net,vat=vat,total=net+vat))
        if total<=0 or base<=0: raise ValueError('Add at least one positive item.')
        add(codes['2100' if sales else '1300'],sign*tax_total)
        if kind in ('Sales','Credit note'): control=codes['1100']
        elif kind in ('Purchase','Debit note'): control=codes['2000']
        else:
            control=int(d.get('cash_account') or codes['1010'])
            if control not in accounts or not accounts[control]['cash']: raise ValueError('Select cash/bank. Use Purchase for credit purchases.')
        add(control,-sign*base)
        if credit:
            remaining,remaining_base=outstanding(c,source)
            if total>remaining or base>remaining_base: raise ValueError('Note exceeds remaining invoice/bill balance.')
            allocation=(source,total,base)
    if len(entries)<2 or sum(e[1]-e[2] for e in entries)!=0: raise ValueError('Voucher must balance: total debits must equal total credits.')
    if any(max(e[1],e[2])>10**15 for e in entries): raise ValueError('Voucher exceeds maximum posting size.')
    return dict(kind=kind,date=dt,due_date=due,contact_id=contact,currency=cur,rate=str(rate),total=total,base_total=base,source_id=source,entries=entries,allocation=allocation,calculated=calculated,net_total=net_total,vat_total=vat_total)
def save_draft(cid,d):
    with connection(True) as c:
        b=build(c,cid,d);d=dict(d);d['calculation']={k:b[k] for k in ('calculated','net_total','vat_total')};vid=d.get('id');values=(b['kind'],b['date'],b['due_date'],b['contact_id'],b['currency'],b['rate'],b['total'],b['base_total'],str(d.get('reference',''))[:500],str(d.get('memo',''))[:2000],json.dumps(d),b['source_id'])
        if vid:
            old=c.execute('SELECT * FROM vouchers WHERE id=? AND company_id=?',(vid,cid)).fetchone()
            if not old or old['status']!='Draft': raise ValueError('Only drafts can be edited.')
            c.execute('UPDATE vouchers SET kind=?,date=?,due_date=?,contact_id=?,currency=?,rate=?,total=?,base_total=?,reference=?,memo=?,data=?,source_id=? WHERE id=?',(*values,vid))
        else:
            seq=c.execute('SELECT COALESCE(MAX(id),0)+1 FROM vouchers').fetchone()[0]
            vid=c.execute('INSERT INTO vouchers(kind,date,due_date,contact_id,currency,rate,total,base_total,reference,memo,data,source_id,company_id,number,status,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*values,cid,f'V-{seq:06d}','Draft',datetime.now().isoformat())).lastrowid
        audit(c,cid,'Draft saved',vid);return {'id':vid,'preview':b}
def post(cid,vid):
    with connection(True) as c:
        v=c.execute('SELECT * FROM vouchers WHERE id=? AND company_id=?',(vid,cid)).fetchone()
        if not v or v['status']!='Draft': raise ValueError('Only a draft can be posted; it may already be posted.')
        b=build(c,cid,json.loads(v['data']))
        c.executemany('INSERT INTO entries(voucher_id,account_id,debit,credit,flow) VALUES(?,?,?,?,?)',[(vid,*e) for e in b['entries']])
        if b['allocation']:
            source,amount,base=b['allocation'];c.execute('INSERT INTO allocations(source_id,voucher_id,amount,base_amount) VALUES(?,?,?,?)',(source,vid,amount,base))
        c.execute("UPDATE vouchers SET status='Posted' WHERE id=?",(vid,));audit(c,cid,'Voucher posted',v['number']);return {'ok':True}
def reverse(cid,vid,d):
    with connection(True) as c:
        co=company(c,cid);dt=day(d['date']);check_date(co,dt);v=c.execute('SELECT * FROM vouchers WHERE id=? AND company_id=?',(vid,cid)).fetchone()
        if not v or v['status']!='Posted' or v['kind']=='Reversal' or dt<v['date']: raise ValueError('Select a posted original voucher and a reversal date on/after its date.')
        if c.execute("SELECT 1 FROM allocations a JOIN vouchers v ON v.id=a.voucher_id WHERE a.source_id=? AND v.status='Posted'",(vid,)).fetchone(): raise ValueError('Reverse linked settlements/notes first.')
        if c.execute('SELECT 1 FROM assets WHERE purchase_id=?',(vid,)).fetchone() or json.loads(v['data']).get('asset_depreciation'): raise ValueError('Asset-linked vouchers require an accountant-approved adjustment journal.')
        reason=required(d.get('reason'),'Reversal reason');seq=c.execute('SELECT COALESCE(MAX(id),0)+1 FROM vouchers').fetchone()[0]
        rid=c.execute("INSERT INTO vouchers(company_id,number,kind,date,due_date,status,contact_id,currency,rate,total,base_total,memo,data,source_id,created) VALUES(?,?,'Reversal',?,?,'Posted',?,?,?,?,?,?,?,?,?)",(cid,f'V-{seq:06d}',dt,dt,v['contact_id'],v['currency'],v['rate'],v['total'],v['base_total'],reason,'{}',vid,datetime.now().isoformat())).lastrowid
        c.execute('INSERT INTO entries(voucher_id,account_id,debit,credit,flow) SELECT ?,account_id,credit,debit,flow FROM entries WHERE voucher_id=?',(rid,vid));c.execute("UPDATE vouchers SET status='Reversed',reversed_by=? WHERE id=?",(rid,vid));audit(c,cid,'Voucher reversed',v['number']+': '+reason);return {'id':rid}
def state(cid):
    with connection() as c:
        out={'company':company(c,cid)}
        for table in ('accounts','contacts','items','assets'): out[table]=[dict(r) for r in c.execute(f'SELECT * FROM {table} WHERE company_id=? ORDER BY id',(cid,))]
        out['vouchers']=[dict(r) for r in c.execute('SELECT v.*,p.name contact_name FROM vouchers v LEFT JOIN contacts p ON p.id=v.contact_id WHERE v.company_id=? ORDER BY v.date DESC,v.id DESC',(cid,))]
        for v in out['vouchers']:
            v['data']=json.loads(v['data']);v['outstanding'],v['outstanding_base']=outstanding(c,v['id'])
        out['audit']=[dict(r) for r in c.execute('SELECT * FROM audit WHERE company_id=? ORDER BY id DESC LIMIT 500',(cid,))];return out
def reports(cid,start,end):
    start=day(start);end=day(end)
    if start>end: raise ValueError('Report start date must precede end date.')
    with connection() as c:
        co=company(c,cid);acc=[dict(r) for r in c.execute('SELECT * FROM accounts WHERE company_id=? ORDER BY code',(cid,))]
        rows=[dict(r) for r in c.execute('SELECT e.*,v.date,v.number,v.kind,v.memo,v.contact_id,v.id document_id,a.code,a.name,a.type,a.cash,p.name contact_name FROM entries e JOIN vouchers v ON v.id=e.voucher_id JOIN accounts a ON a.id=e.account_id LEFT JOIN contacts p ON p.id=v.contact_id WHERE v.company_id=? AND v.date<=? ORDER BY v.date,v.id,e.id',(cid,end))];trial=[]
        for a in acc:
            ar=[r for r in rows if r['account_id']==a['id']];opening=sum(r['debit']-r['credit'] for r in ar if r['date']<start);debit=sum(r['debit'] for r in ar if r['date']>=start);credit=sum(r['credit'] for r in ar if r['date']>=start);trial.append(dict(**a,opening=opening,debit=debit,credit=credit,balance=opening+debit-credit))
        income=sum(a['credit']-a['debit'] for a in trial if a['type']=='Income');expense=sum(a['debit']-a['credit'] for a in trial if a['type']=='Expense');cumulative=sum(-a['balance'] for a in trial if a['type'] in ('Income','Expense'));assets=sum(a['balance'] for a in trial if a['type']=='Asset');liabilities=sum(-a['balance'] for a in trial if a['type']=='Liability');equity=sum(-a['balance'] for a in trial if a['type']=='Equity')+cumulative
        flows={x:0 for x in ('Operating','Investing','Financing')}
        for r in rows:
            if r['cash'] and r['date']>=start: flows[r['flow']]+=r['debit']-r['credit']
        cash_open=sum(a['opening'] for a in trial if a['cash']);cash_close=sum(a['balance'] for a in trial if a['cash']);aging=[]
        for v in c.execute("SELECT v.*,p.name contact_name FROM vouchers v LEFT JOIN contacts p ON p.id=v.contact_id WHERE v.company_id=? AND v.kind IN ('Sales','Purchase') AND v.status IN ('Posted','Reversed') AND v.date<=?",(cid,end)):
            if v['reversed_by'] and c.execute('SELECT date FROM vouchers WHERE id=?',(v['reversed_by'],)).fetchone()[0]<=end: continue
            alloc=c.execute('SELECT COALESCE(SUM(a.amount),0),COALESCE(SUM(a.base_amount),0) FROM allocations a JOIN vouchers w ON w.id=a.voucher_id LEFT JOIN vouchers rv ON rv.id=w.reversed_by WHERE a.source_id=? AND w.date<=? AND (rv.date IS NULL OR rv.date>?)',(v['id'],end,end)).fetchone();rem=v['total']-alloc[0];rb=v['base_total']-alloc[1]
            if rem:
                days=(date.fromisoformat(end)-date.fromisoformat(v['due_date'])).days;aging.append(dict(number=v['number'],kind=v['kind'],contact=v['contact_name'],due_date=v['due_date'],currency=v['currency'],outstanding=rem,base=rb,days=max(days,0),bucket='Current' if days<=0 else '1-30' if days<=30 else '31-60' if days<=60 else '61-90' if days<=90 else '90+'))
        vat={'input':sum(a['debit']-a['credit'] for a in trial if a['code']=='1300'),'output':sum(a['credit']-a['debit'] for a in trial if a['code']=='2100')}
        return dict(company=co,start=start,end=end,trial=trial,ledger=[r for r in rows if r['date']>=start],aging=aging,vat=vat,summary=dict(income=income,expense=expense,profit=income-expense,assets=assets,liabilities=liabilities,equity=equity,cumulative_profit=cumulative,cash=cash_close,trial_difference=sum(a['balance'] for a in trial),balance_difference=assets-liabilities-equity),cashflow=dict(**flows,opening=cash_open,closing=cash_close,change=cash_close-cash_open,difference=cash_close-cash_open-sum(flows.values())))
def add_asset(cid,d):
    with connection(True) as c:
        co=company(c,cid);acquired=day(d['acquired']);check_date(co,acquired);cost=money(d['cost']);residual=money(d.get('residual',0));months=int(d['months'])
        if cost<=0 or not 0<=residual<cost or not 1<=months<=1200: raise ValueError('Check cost, residual value and useful life.')
        pid=int(d['purchase_id']);v=c.execute("SELECT * FROM vouchers WHERE id=? AND company_id=? AND status='Posted' AND kind IN ('Asset purchase','Purchase','Opening balance','Journal')",(pid,cid)).fetchone()
        if not v or acquired<v['date']: raise ValueError('Link a posted acquisition dated on/before available-for-use date.')
        cap=c.execute("SELECT COALESCE(SUM(e.debit-e.credit),0) FROM entries e JOIN accounts a ON a.id=e.account_id WHERE e.voucher_id=? AND a.code='1500'",(pid,)).fetchone()[0];used=c.execute('SELECT COALESCE(SUM(cost),0) FROM assets WHERE purchase_id=?',(pid,)).fetchone()[0]
        if cost+used>cap: raise ValueError('Registered costs exceed acquisition voucher debit to account 1500.')
        c.execute('INSERT INTO assets(company_id,name,acquired,cost,residual,months,last_date,purchase_id) VALUES(?,?,?,?,?,?,?,?)',(cid,required(d['name'],'Asset name'),acquired,cost,residual,months,acquired,pid));audit(c,cid,'Asset registered',d['name']);return {'ok':True}
def depreciate(cid,aid,d):
    with connection(True) as c:
        co=company(c,cid);dt=day(d['date']);check_date(co,dt);a=c.execute('SELECT * FROM assets WHERE id=? AND company_id=?',(aid,cid)).fetchone()
        if not a or dt<=a['last_date']: raise ValueError('Choose a date after the last depreciation date.')
        start=date.fromisoformat(a['acquired']);end=date.fromisoformat(dt);y=start.year+(start.month-1+a['months'])//12;m=(start.month-1+a['months'])%12+1;finish=date(y,m,min(start.day,calendar.monthrange(y,m)[1]));days=min((end-start).days+1,(finish-start).days);target=convert(a['cost']-a['residual'],Decimal(days)/Decimal((finish-start).days));amount=target-a['depreciated']
        if amount<=0: raise ValueError('No further depreciation is due.')
        codes={r['code']:r['id'] for r in c.execute('SELECT * FROM accounts WHERE company_id=?',(cid,))};seq=c.execute('SELECT COALESCE(MAX(id),0)+1 FROM vouchers').fetchone()[0]
        vid=c.execute("INSERT INTO vouchers(company_id,number,kind,date,due_date,status,currency,rate,total,base_total,memo,data,created) VALUES(?,?,'Journal',?,?,'Posted',?,'1',?,?,?,?,?)",(cid,f'V-{seq:06d}',dt,dt,co['currency'],amount,amount,'Depreciation: '+a['name'],json.dumps({'asset_depreciation':aid}),datetime.now().isoformat())).lastrowid
        c.executemany('INSERT INTO entries(voucher_id,account_id,debit,credit,flow) VALUES(?,?,?,?,?)',[(vid,codes['5300'],amount,0,'Operating'),(vid,codes['1590'],0,amount,'Operating')]);c.execute('UPDATE assets SET last_date=?,depreciated=? WHERE id=?',(dt,target,aid));audit(c,cid,'Depreciation posted',str(aid)+' through '+dt);return {'id':vid,'amount':amount}
def lock(cid,d):
    with connection(True) as c:
        co=company(c,cid);dt=day(d['date'])
        if dt<co['fy_start'] or (co['locked_until'] and dt<co['locked_until']): raise ValueError('Period lock can only move forward within the books period.')
        c.execute('UPDATE companies SET locked_until=? WHERE id=?',(dt,cid));audit(c,cid,'Period locked',dt);return {'ok':True}
def reconcile(cid,d):
    with connection(True) as c:
        dt=day(d['date']);acc=int(d['account_id']);a=c.execute('SELECT * FROM accounts WHERE id=? AND company_id=? AND cash=1',(acc,cid)).fetchone()
        if not a: raise ValueError('Choose a bank/cash account.')
        ids=[int(x) for x in d.get('entry_ids',[])];rows=c.execute('SELECT e.*,v.date FROM entries e JOIN vouchers v ON v.id=e.voucher_id WHERE e.account_id=? AND v.date<=?',(acc,dt)).fetchall();eligible={r['id']:r for r in rows if not r['reconciled']}
        if not ids or len(ids)!=len(set(ids)) or any(i not in eligible for i in ids): raise ValueError('Select unreconciled entries through the statement date.')
        cleared=sum(r['debit']-r['credit'] for r in rows if r['reconciled'])+sum(eligible[i]['debit']-eligible[i]['credit'] for i in ids)
        if cleared!=money(d['balance']): raise ValueError(f'Selected cleared balance {cleared/100:,.2f} does not match statement closing balance.')
        for i in ids: c.execute('UPDATE entries SET reconciled=? WHERE id=?',(dt,i))
        audit(c,cid,'Bank reconciled',f'{a["name"]} through {dt}; balance {cleared/100:.2f}');return {'ok':True}
def group_report(d):
    results=[];combined={};totals={k:0 for k in ('income','expense','profit','assets','liabilities','equity','cash')}
    for member in d.get('members',[]):
        rate=dec(member['rate'])
        if rate<=0: raise ValueError('Translation rates must be positive.')
        r=reports(int(member['id']),d['start'],d['end']);results.append({'company':r['company']['name'],'currency':r['company']['currency'],'rate':str(rate),'profit':convert(r['summary']['profit'],rate),'assets':convert(r['summary']['assets'],rate)})
        for k in totals: totals[k]+=convert(r['summary'][k],rate)
        for a in r['trial']:
            key=(a['code'],a['type'])
            if key not in combined: combined[key]={'code':a['code'],'name':a['name'],'type':a['type'],'balance':0}
            combined[key]['balance']+=convert(a['balance'],rate)
    if not results or len({int(m['id']) for m in d['members']})!=len(results): raise ValueError('Select distinct group companies.')
    return {'members':results,'summary':totals,'trial':list(combined.values()),'currency':currency(d['currency']),'notice':'Management aggregation only: one user-entered rate per entity; no IAS 21 translation, eliminations, ownership/NCI or statutory consolidation.'}
