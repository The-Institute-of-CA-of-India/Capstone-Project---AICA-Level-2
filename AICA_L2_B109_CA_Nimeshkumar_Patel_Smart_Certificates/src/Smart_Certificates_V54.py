"""Smart Certifictes — CA Document Automation Manager. Python 3.10+; pip install PyQt6 pymupdf python-docx openpyxl"""
import sys, re, json, sqlite3, traceback, shutil, os, subprocess
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
# Install missing dependencies only when running as a Python script.
if not getattr(sys, 'frozen', False):
    import importlib.util
    dependencies = [('PyQt6','PyQt6'),('fitz','PyMuPDF'),('docx','python-docx'),('openpyxl','openpyxl'),('PIL','Pillow'),('pytesseract','pytesseract')]
    missing=[package for module,package in dependencies if importlib.util.find_spec(module) is None]
    if missing:
        print('Installing required packages:', ', '.join(missing))
        subprocess.check_call([sys.executable,'-m','pip','install',*missing])

from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QLineEdit,QTextEdit,QPushButton,QLabel,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QSpinBox,QDoubleSpinBox,QGroupBox,QSplitter,QScrollArea,QInputDialog,QDialog,QDialogButtonBox)
from PyQt6.QtCore import Qt
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_BREAK
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
import fitz

ROOT=Path.home()/"Documents"/"CA_Document_Manager"
ROOT.mkdir(parents=True,exist_ok=True)
DB=ROOT/'clients.sqlite3'
CON=sqlite3.connect(DB)
CON.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, pan TEXT, gstin TEXT, address TEXT, firm TEXT, updated TEXT)')
CON.execute('CREATE TABLE IF NOT EXISTS itr (id INTEGER PRIMARY KEY, client_id INTEGER, ay TEXT, form TEXT, income TEXT, ack TEXT, filing TEXT, source TEXT, UNIQUE(client_id,ay,ack))')
CON.execute('CREATE TABLE IF NOT EXISTS itr_financials (client_id INTEGER, ay TEXT, ack TEXT, turnover TEXT, turnover_basis TEXT, networth TEXT, networth_basis TEXT, source TEXT, PRIMARY KEY(client_id,ay,ack))')
CON.execute('CREATE TABLE IF NOT EXISTS ca_signers (id INTEGER PRIMARY KEY, firm TEXT NOT NULL, signer TEXT NOT NULL, designation TEXT, mrn TEXT, frn TEXT, address TEXT, phone TEXT, email TEXT, place TEXT, is_default INTEGER DEFAULT 0)')
CON.execute("CREATE TABLE IF NOT EXISTS client_extra (client_id INTEGER PRIMARY KEY, entity_type TEXT, mrl_signer TEXT, mrl_position TEXT)")
CON.execute('CREATE TABLE IF NOT EXISTS itr_status (client_id INTEGER NOT NULL, ay TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT, reviewed INTEGER DEFAULT 0, PRIMARY KEY(client_id,ay))')
CON.execute('CREATE TABLE IF NOT EXISTS client_name_parts (client_id INTEGER PRIMARY KEY, first_name TEXT, middle_name TEXT, surname TEXT)')
CON.execute('CREATE TABLE IF NOT EXISTS itr_accounting_method (client_id INTEGER, ay TEXT, ack TEXT, method TEXT, PRIMARY KEY(client_id,ay,ack))')
CON.commit()

LETTERHEAD_CONFIG=ROOT/'letterhead_v22.json'

def load_letterhead_config():
    try:return json.loads(LETTERHEAD_CONFIG.read_text(encoding='utf-8'))
    except Exception:return {}


def split_person_name(full):
    parts=safe(full).split()
    if len(parts)<=1:return (parts[0] if parts else '', '', '')
    if len(parts)==2:return (parts[0], '', parts[1])
    return (parts[0], ' '.join(parts[1:-1]), parts[-1])

def pdf_identity(pages):
    """Read only labelled fields from the correct ITR sections; never use generic PAN/name labels as values."""
    first=pages[0] if pages else ''
    def next_values(label, count):
        lines=[x.strip() for x in first.splitlines() if x.strip()]
        for i,line in enumerate(lines[:-1]):
            if label in line:
                values=re.split(r"\s{2,}",lines[i+1].strip())
                if len(values)>=count:return values
        return []
    names=next_values('(A1) First Name',4)
    if len(names)<4 or not re.fullmatch(r'[A-Z]{5}\d{4}[A-Z]',names[3]):
        names=['','','','']
    location=next_values('(A5) Status',3)
    street=next_values('(A8) Road/',3)
    region=next_values('(A11) State',3)
    address=''
    if len(location)>=3 and len(street)>=3 and len(region)>=3:
        parts=[location[1],location[2],street[0],street[1],street[2],re.sub(r'^\d+-','',region[0]),region[2]]
        clean=[]
        for part in parts:
            if part and (not clean or clean[-1].casefold()!=part.casefold()):clean.append(part)
        address=', '.join(clean)
    gst=''
    for pg in pages:
        m=re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b',pg)
        if m:gst=m.group(0);break
    firm=''
    # ITR-3: presumptive business name is on the table preceding item 61i.
    for pg in pages:
        if 'Gross Turnover or Gross Receipts' in pg and 'Name Of Business' in pg:
            head=pg.split('Gross Turnover or Gross Receipts',1)[0]
            for line in head.splitlines():
                m=re.match(r'^\s*\d+\s{2,}(.+?)\s{2,}(?:Retail|Wholesale|Manufactur|Services|Other|Trading|Professional)',line,re.I)
                if m:firm=m.group(1).strip();break
            if firm:break
    if not firm:
        # For regular books, inspect the nature-of-business table; blank is valid.
        for pg in pages[:8]:
            if 'Trade name of the proprietorship' not in pg:continue
            for line in pg.splitlines():
                m=re.match(r'^\s*\d+\s{2,}\d{4,6}\s{2,}(.+?)\s{2,}\S+',line)
                if m:firm=m.group(1).strip();break
            if firm:break
    return {'name_parts':tuple(names[:3]),'pan':names[3], 'gstin':gst,'address':address,'firm':firm,
            'entity_type':'Individual' if location and location[0].lower()=='individual' else ''}

def normalize_ay(s):
    m=re.search(r'(20\d{2})\s*[-–/]\s*(\d{2,4})',s)
    return m.group(1)+'-'+m.group(2)[-2:] if m else ''

def detect_statuses(text):
    """Extract latest processing state from each AY block of the portal's Filed Returns screen.
    Do not confuse historic workflow events with the latest status or refund payment.
    """
    text=re.sub(r'[ \t]+',' ',text)
    pat=r'(?im)^\s*(?:A\.?Y\.?|Assessment\s+Year)\s*[:\-]?\s*(20\d{2}\s*[-–/]\s*\d{2,4})\b'
    anchors=list(re.finditer(pat,text)); out={}
    for i,m in enumerate(anchors):
        block=text[m.end():anchors[i+1].start() if i+1<len(anchors) else len(text)]
        # Ignore any trailing page navigation; the first actual processing event
        # is the latest event on the income-tax portal's descending timeline.
        choices=[(r'Processed\s+with\s+no\s+demand\s*/\s*refund','Processed with no demand/refund'),
                 (r'Processed\s+with\s+refund\s+due','Processed with refund due'),
                 (r'Processed\s+with\s+demand\s+due','Processed with demand due'),
                 (r'Successfully\s+e[- ]?verified','Successfully e-verified'),
                 (r'Under\s+Processing','Under processing'),
                 (r'Pending\s+for\s+e[- ]?verification','Pending for e-verification')]
        hits=[]
        for pattern,label in choices:
            for match in re.finditer(pattern,block,re.I):hits.append((match.start(),label))
        if hits:out[normalize_ay(m.group(1))]=min(hits)[1]
    return out

def money(v):
    try:return f'{Decimal(str(v).replace(",", "")):,.2f}'
    except:return '0.00'
def dec(v):
    try:return Decimal(str(v).replace(',','').replace('₹','').strip() or '0')
    except:return Decimal(0)
def safe(v):return str(v or '').strip()
def classify_accounting_method(pages, itr_form=''):
    """Classification is provisional; the user confirms it before saving."""
    content='\n'.join(pages)
    form=(itr_form or '').upper().replace(' ','').replace('-','')
    if form=='ITR4':return 'Presumptive (ITR-4)'
    if re.search(r'\b61i\s+[1-9][\d,]*(?:\.\d+)?\s*$',content,re.M|re.I) or re.search(r'\b62i\s+[1-9][\d,]*(?:\.\d+)?\s*$',content,re.M|re.I):
        return 'Presumptive (ITR-3)'
    if re.search(r'PART A\s*[-–]\s*TRADING ACCOUNT',content,re.I) or re.search(r'PART A-BS',content,re.I):
        return 'Regular books (ITR-3)'
    return 'Review manually'

def extract_regular_sales_from_pdf(path):
    """Read sale rows using PDF coordinates, not just text-line order.
    Return (goods, services) only if both amounts are unambiguous.
    """
    amount_re=re.compile(r'^-?\d[\d,]*(?:\.\d+)?$')
    def amount_token(w):
        t=w[4].strip().replace('₹','').replace(' ','')
        return t if amount_re.fullmatch(t) else None
    try:
        with fitz.open(path) as pdf:
            for page in pdf:
                words=page.get_text('words',sort=True)
                if not words:continue
                full=page.get_text(sort=True)
                if not re.search(r'Sale of goods',full,re.I) or not re.search(r'Sale of services',full,re.I):continue
                if not re.search(r'Revenue from operations|Sales/Gross receipts of business',full,re.I):continue
                labels={}
                for kind,phrase in [('goods',['Sale','of','goods']),('services',['Sale','of','services'])]:
                    for i in range(len(words)-2):
                        if [words[i+j][4].lower().strip(':') for j in range(3)]==[x.lower() for x in phrase]:
                            labels[kind]=(words[i][0],min(words[i+j][1] for j in range(3)),max(words[i+j][3] for j in range(3)))
                            break
                if len(labels)!=2:continue
                results={}
                for kind,(x,y0,y1) in labels.items():
                    # Amount should be to the right of the description and close to its row.
                    # PDF extraction may place numeric value on the next text line.
                    candidates=[]
                    for w in words:
                        val=amount_token(w)
                        if val is None or w[0] <= x+160:continue
                        dy=abs((w[1]+w[3])/2-(y0+y1)/2)
                        if dy>24:continue
                        candidates.append((dy,-w[0],val))
                    if candidates:
                        candidates.sort()
                        # Do not choose a nearby number if it could belong to the other sale row.
                        nearest=candidates[0]
                        if len(candidates)==1 or candidates[1][0]-nearest[0]>3:
                            results[kind]=nearest[2].replace(',','')
                if len(results)==2:return results['goods'],results['services']
    except Exception:
        return None,None
    return None,None

def extract_business_financials(pages, method='Auto detect'):
    """Conservative FY 2025-26 / AY 2026-27 ITR PDF extraction.
    Missing/ambiguous values remain blank. Capital is business capital, not personal NW.
    """
    num = r'-?\d[\d,]*(?:\.\d+)?'
    def clean(v):
        return str(Decimal(v.replace(',', '')))
    def line_amount(lines, label, codes=()):
        """Accept only a labelled row, never a nearby unrelated total."""
        for i, line in enumerate(lines):
            if not re.search(label, line, re.I):
                continue
            tail = re.split(label, line, maxsplit=1, flags=re.I)[-1].strip()
            # Code markers like 'i', 'ii', 'a' may precede amount.
            tail = re.sub(r'^(?:\(?[a-z]{1,3}\)?|[A-Za-z]\d{0,2})\s+', '', tail)
            m = re.search(r'(?:^|\s)(' + num + r')\s*$', tail)
            if m:
                return clean(m.group(1))
            # Some PDFs wrap the value onto its own following line.
            if i + 1 < len(lines):
                nxt = lines[i+1].strip()
                if re.fullmatch(num, nxt):
                    return clean(nxt)
                if re.fullmatch(r'(?:[a-z]{1,3}\s+)?'+num, nxt, re.I):
                    return clean(re.search(num+r'$',nxt).group())
        return None
    turnover = basis = capital = capital_basis = ''
    presumptive = method.startswith('Presumptive')
    regular = method.startswith('Regular books')
    if not presumptive:
        for pg in pages:
            if not re.search(r'Revenue\s+from\s+operations',pg,re.I):
                continue
            if not re.search(r'Sales\s*/\s*Gross\s+receipts\s+of\s+business',pg,re.I):
                continue
            block = re.split(r'Sales\s*/\s*Gross\s+receipts\s+of\s+business',pg,flags=re.I,maxsplit=1)[1]
            block = re.split(r'\n\s*(?:B\s+Gross receipts from Profession|Other operating revenues|Total Revenue from operations)',block,flags=re.I,maxsplit=1)[0]
            lines=block.splitlines()
            goods=line_amount(lines,r'\bSale\s+of\s+goods\b')
            services=line_amount(lines,r'\bSale\s+of\s+services\b')
            if goods is not None and services is not None:
                turnover=str(Decimal(goods)+Decimal(services))
                basis='ITR-3 Part A-Trading: sale of goods + sale of services; confirm with source PDF'
                break
    if presumptive or (not regular and not turnover):
        found=[]
        for pg in pages:
            for line in pg.splitlines():
                for code,desc in [('61i','ITR-3 44AD 61i'),('62i','ITR-3 44ADA 62i')]:
                    m=re.search(r'\b'+code+r'\s+('+num+r')\s*$',line,re.I)
                    if m and Decimal(m.group(1).replace(',',''))!=0:
                        found.append((clean(m.group(1)),desc))
            if method=='Presumptive (ITR-4)':
                lines=pg.splitlines()
                for label,desc in [(r'Gross\s+turnover\s+or\s+gross\s+receipts','ITR-4 gross turnover/receipts'),(r'Gross\s+receipts\s+from\s+profession','ITR-4 professional receipts')]:
                    val=line_amount(lines,label)
                    if val is not None and Decimal(val)!=0:found.append((val,desc))
        unique={(v,d) for v,d in found}
        if len(unique)==1:turnover,basis=next(iter(unique))
        # Multiple possible schedules: do not guess which applies.
    if not presumptive:
        for pg in pages:
            if not re.search(r'PART\s*A\s*[-–]?\s*BS|Sources\s+of\s+funds|Proprietor.s\s+fund',pg,re.I):
                continue
            lines=pg.splitlines()
            for label,desc in [(r"(?:Proprietor['’]?s?\s+capital|Proprietor['’]?s?\s+fund|Capital\s+of\s+proprietor)",'Proprietor capital'),(r"(?:Partner(?:s)?['’]?\s*/\s*Member(?:s)?['’]?\s+capital|Partner(?:s)?['’]?\s+capital|Member(?:s)?['’]?\s+capital)",'Partners/members capital')]:
                val=line_amount(lines,label)
                if val is not None:
                    capital=val;capital_basis='Part A-BS '+desc+' (business capital only; NOT personal net worth)'
                    break
            if capital:break
    # ITR-4: Schedule BP E1/E3 and Financial Particulars E11 are distinct
    # from income E2/E8 and GST outward supplies E10.
    if method == 'Presumptive (ITR-4)':
        for pg in pages:
            lines=pg.splitlines()
            if re.search(r'COMPUTATION OF PRESUMPTIVE BUSINESS INCOME|SCHEDULE BP',pg,re.I):
                e1=line_amount(lines,r'Gross\s+Turnover\s+or\s+Gross\s+Receipts')
                e3=line_amount(lines,r'^\s*Gross\s+Receipts\s*\(E3\s+limited')
                if e1 and Decimal(e1)>0:
                    turnover=e1;basis='ITR-4 Schedule BP E1: Gross turnover/receipts (44AD)'
                elif e3 and Decimal(e3)>0:
                    turnover=e3;basis='ITR-4 Schedule BP E3: Gross receipts (44ADA)'
            if re.search(r'FINANCIAL PARTICULARS OF THE BUSINESS',pg,re.I):
                v=line_amount(lines,r'Partners\s*/\s*Members\s+own\s+capital')
                if v is not None:
                    capital=v;capital_basis='ITR-4 Schedule BP E11: Partners/Members own capital (business capital only, not personal net worth)'
    return turnover,basis,capital,capital_basis

def extract_itr(path):
    with fitz.open(path) as pdf:
        pages=[p.get_text(sort=True) for p in pdf]
    text=pages[0] if pages else ''
    def pick(pattern,source=text):
        m=re.search(pattern,source,re.I|re.M)
        return safe(m.group(1)) if m else ''
    pan=pick(r'\bPAN\s*[:\-]?\s*([A-Z]{5}\d{4}[A-Z])') or pick(r'\b([A-Z]{5}\d{4}[A-Z])\b')
    ay=normalize_ay(pick(r'Assessment\s*Year\s*[:\-]?\s*(20\d{2}\s*[-–/]\s*20\d{2}|20\d{2}\s*[-–/]\s*\d{2})') or pick(r'\b(20\d{2}\s*[-–/]\s*(?:20\d{2}|\d{2}))\b'))
    ack=pick(r'Acknowledg(?:e)?ment\s*(?:Number|No\.)\s*[:\-]?\s*(\d{12,20})')
    filing=pick(r'Date of [Ff]iling\s*[:\-]?\s*(\d{1,2}[-/]\w+[-/]20\d{2})')
    form=pick(r'\bForm Number\s*(ITR[- ]?[1-7])') or pick(r'\bFORM\s*(ITR[- ]?[1-7])')
    name=pick(r'\bName\s+([A-Z][A-Z .]{4,65})(?=\n|\s+Address)')
    if not name:
        names=[pick(r'\(A'+str(i)+r'\)\s*'+label+r'.*?\n\s*([A-Z]+)') for i,label in [(1,'First Name'),(2,'Middle Name'),(3,'Last Name')]]
        name=' '.join(x for x in names if x)
    income=pick(r'\bTotal Income\s+(?:1A?|2)\s+([\d,]+)(?:\s|$)') or pick(r'\bTotal Income\s+([\d,]+)(?:\s|$)')
    accounting_method=classify_accounting_method(pages,form)
    turnover,turnover_basis,networth,networth_basis=extract_business_financials(pages,accounting_method)
    if not turnover and form.upper().replace(' ','') in ('ITR-3','ITR3'):
        # ITR-3 may contain 44AD/44ADA gross turnover even when trading account is zero.
        # Locate code 61i / 62i beside gross receipts, never presumptive profit 61ii.
        presumptive_found=[]
        for pg in pages:
            for line in pg.splitlines():
                m=re.search(r'\b(61i|62i)\s+([\d,]+(?:\.\d+)?)\s*$',line,re.I)
                if m and Decimal(m.group(2).replace(',',''))>0:
                    presumptive_found.append((m.group(1).lower(),m.group(2).replace(',','')))
        distinct={k:v for k,v in presumptive_found}
        if distinct:
            turnover=str(sum(Decimal(v) for v in distinct.values()))
            turnover_basis='ITR-3 presumptive gross turnover/receipts (PDF schedule codes '+', '.join(sorted(distinct))+'); verify with original return'
    if accounting_method.startswith('Regular books') and not turnover:
        goods,services=extract_regular_sales_from_pdf(path)
        if goods is not None and services is not None:
            turnover=str(Decimal(goods)+Decimal(services))
            turnover_basis='ITR-3 regular books: sale of goods + sale of services (PDF table-position extraction; review required)'
    identity=pdf_identity(pages)
    gst,address,firm=identity['gstin'],identity['address'],identity['firm']
    if any(identity['name_parts']):name=' '.join(x for x in identity['name_parts'] if x)
    if identity['pan']:pan=identity['pan']
    # Do not infer personal net worth from a business capital account or a zero-filled BS.
    return dict(accounting_method=accounting_method,name=name,name_parts=identity['name_parts'],entity_type=identity['entity_type'],pan=pan,gstin=gst,address=address,firm=firm,ay=ay,form=form,income=income.replace(',',''),ack=ack,filing=filing,source=str(path),turnover=turnover,turnover_basis=turnover_basis,networth=networth,networth_basis=networth_basis)

def extract_itr_json(path):
    """Read common portal/utility JSON layouts; never guess financial figures."""
    raw=Path(path).read_text(encoding='utf-8-sig')
    obj=json.loads(raw)
    if isinstance(obj,str):
        try:obj=json.loads(obj)
        except (ValueError,TypeError):pass
    entries=[]
    def walk(node,path=()):
        if isinstance(node,dict):
            for k,v in node.items():walk(v,path+(str(k),))
        elif isinstance(node,list):
            for i,v in enumerate(node):walk(v,path+(str(i),))
        elif node is not None and not isinstance(node,bool):entries.append((path,str(node).strip()))
    walk(obj)
    def keynorm(k):return re.sub(r'[^a-z0-9]','',str(k).lower())
    def values(*names):
        wanted={keynorm(n) for n in names}
        return [(p,v) for p,v in entries if p and keynorm(p[-1]) in wanted and v]
    def unique(*names):
        vs={v for _,v in values(*names)}
        return next(iter(vs)) if len(vs)==1 else ''
    def numeric(v):
        if not re.fullmatch(r'-?\d[\d,]*(?:\.\d+)?',v or ''):return ''
        return str(Decimal(v.replace(',','')))
    form=''
    for path_,_ in entries:
        for x in path_:
            m=re.fullmatch(r'ITR[-_ ]?([1-7])',x,re.I)
            if m:form='ITR-'+m.group(1)
    form=unique('FormName','FormNumber','ITRForm') or form
    ay=normalize_ay(unique('AssessmentYear','AsstYear','AY','assessment_year','AssmntYear'))
    if not ay:
        candidates={normalize_ay(v) for p,v in entries if p and re.search(r'assessment|asstyear|assmntyear',p[-1],re.I) and normalize_ay(v)}
        if len(candidates)==1:ay=candidates.pop()
    # Some JSON exports encode assessment year as YYYY (e.g. 2026 means AY 2026-27).
    if not ay:
        vals={v for _,v in values('AssessmentYear','AsstYear','AssmntYear') if re.fullmatch(r'20\d{2}',v)}
        if len(vals)==1:
            yr=int(vals.pop());ay=f'{yr}-{(yr+1)%100:02d}'
    pan=unique('PAN','Pan')
    first=unique('FirstName','First_Name');middle=unique('MiddleName','Middle_Name');last=unique('SurName','LastName','Last_Name')
    # Identity is intentionally never applied to the saved client master.
    ack=unique('AckNo','AcknowledgementNo','AcknowledgmentNo','AcknowledgmentNumber','AcknowledgementNumber','AckNumber','AckNum','ReceiptNo','ReceiptNumber')
    if not ack:
        ack_candidates={v for p,v in entries if p and re.search(r'ack|acknowledg|receipt',p[-1],re.I) and re.fullmatch(r'\d{12,20}',v)}
        if len(ack_candidates)==1:ack=ack_candidates.pop()
    if not ack:
        m=re.fullmatch(r'(\d{12,20})',Path(path).stem)
        if m:ack=m.group(1) # source filename; verify against source document
    income=numeric(unique('TotalIncome','TotIncome','TotalIncomeAsPerReturn'))
    filing=unique('FilingDate','DateOfFiling','DateOfFilingReturn','ReturnFilingDate')
    method='Presumptive (ITR-4)' if form=='ITR-4' else 'Regular books (ITR-3)' if form=='ITR-3' else 'Review manually'
    def amounts(keys):
        found={numeric(v) for _,v in values(*keys) if numeric(v)}
        return list(found)
    turnover=basis=capital=capital_basis=''
    goods=amounts(['SaleOfGoods','SalesOfGoods']);services=amounts(['SaleOfServices','SalesOfServices'])
    if len(goods)==1 and len(services)==1:
        turnover=str(Decimal(goods[0])+Decimal(services[0]));basis='JSON: SaleOfGoods + SaleOfServices; verify Part A Trading Account'
    else:
        totals=amounts(['GrossTurnover','GrossTurnoverOrGrossReceipts','GrossReceipts','TotGrossTurnover','GrossTurnoverGrsRcpt'])
        if len(totals)==1:turnover=totals[0];basis='JSON: labelled turnover/receipts; verify source schedule'
    # Prefer exact schema paths: ITR-3 regular books and ITR-4 presumptive particulars.
    # A generic recursive match can accidentally read unrelated partner-firm capital.
    itr_root=obj.get('ITR',obj) if isinstance(obj,dict) else {}
    form_root=itr_root.get('ITR3',itr_root.get('ITR4',{})) if isinstance(itr_root,dict) else {}
    def at(root,*keys):
        for key in keys:
            if not isinstance(root,dict):return None
            root=root.get(key)
        return root
    if form=='ITR-3':
        bs=at(form_root,'PARTA_BS')
        cap=at(bs,'FundSrc','PropFund','PropCap')
        reserves=at(bs,'FundSrc','PropFund','ResrNSurp','TotResrNSurp')
        proprietor_fund=at(bs,'FundSrc','PropFund','TotPropFund')
        if cap is not None and numeric(str(cap)):
            capital=numeric(str(cap))
            capital_basis='ITR-3 PARTA_BS.FundSrc.PropFund.PropCap (business capital only; not personal net worth)'
        elif proprietor_fund is not None and numeric(str(proprietor_fund)):
            capital=numeric(str(proprietor_fund))
            capital_basis='ITR-3 PARTA_BS.FundSrc.PropFund.TotPropFund (proprietor fund; review reserves)'
        if reserves is not None and numeric(str(reserves)):
            capital_basis+='; reserves='+numeric(str(reserves))
        trading=at(form_root,'TradingAccount')
        total=at(trading,'SalesGrossReceiptsTotal')
        if total is not None and numeric(str(total)):
            turnover=numeric(str(total));basis='ITR-3 TradingAccount.SalesGrossReceiptsTotal'
    elif form=='ITR-4':
        # E11 is the capital/own funds disclosure in ITR-4 Financial Particulars.
        e11=values('E11','OwnCapital','PartnersMembersOwnCapital')
        valid={numeric(v) for _,v in e11 if numeric(v)}
        if len(valid)==1:
            capital=valid.pop();capital_basis='ITR-4 Financial Particulars E11 (business capital only)'
    if not capital:
        capitals=amounts(['ProprietorsCapital','ProprietorCapital','PropCap','PropCapital','PartnersCapital','PartnerCapital','MembersCapital','OwnCapital'])
        if len(capitals)==1:
            capital=capitals[0];capital_basis='JSON: business capital only; not personal net worth'
    return dict(accounting_method=method,name='',name_parts=('','',''),entity_type='',pan=pan,gstin=unique('GSTIN'),address='',firm='',ay=ay,form=form,income=income,ack=ack,filing=filing,source=str(path),turnover=turnover,turnover_basis=basis,networth=capital,networth_basis=capital_basis)

def styled_doc(title,firm,body,table_headers=None,rows=None,closing=True):
    d=Document();sec=d.sections[0];sec.top_margin=Inches(.75);sec.bottom_margin=Inches(.7)
    normal=d.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10)
    p=d.add_paragraph();r=p.add_run(firm or 'CHARTERED ACCOUNTANTS');r.bold=True;r.font.size=Pt(15);r.font.color.rgb=RGBColor(20,56,100)
    d.add_paragraph('Chartered Accountants')
    d.add_paragraph('Date: '+date.today().strftime('%d %B %Y'))
    p=d.add_paragraph();p.alignment=1;r=p.add_run(title.upper());r.bold=True;r.font.size=Pt(13)
    for para in body.split('\n'):
        if para.strip():d.add_paragraph(para)
    if table_headers:
        t=d.add_table(rows=1, cols=len(table_headers));t.style='Table Grid'
        for i,x in enumerate(table_headers):t.rows[0].cells[i].text=str(x)
        for vals in rows or []:
            cells=t.add_row().cells
            for i,x in enumerate(vals):cells[i].text=str(x)
    if closing:
        d.add_paragraph('\nIssued at the request of the applicant for the stated purpose, subject to verification of the underlying records.')
        d.add_paragraph('\nFor, '+(firm or '________________________'))
        d.add_paragraph('Chartered Accountants\n\nAuthorised Signatory: __________________\nMembership No.: ______________\nFRN: ______________\nUDIN (if applicable): ______________')
    return d

def offer_open(parent,path):
    answer=QMessageBox.question(parent,'Export completed',f'Saved to:\n{path}\n\nOpen the exported file now?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
    if answer==QMessageBox.StandardButton.Yes:
        try:
            if sys.platform=='win32':os.startfile(str(path))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as e:QMessageBox.warning(parent,'Cannot open',str(e))

def polish_doc(d):
    sec=d.sections[0];sec.top_margin=Inches(.7);sec.bottom_margin=Inches(.65);sec.left_margin=Inches(.78);sec.right_margin=Inches(.78)
    normal=d.styles['Normal'];normal.font.name='Aptos';normal.font.size=Pt(9.5);normal.paragraph_format.space_after=Pt(7)
    for p in d.paragraphs:
        if p.alignment==WD_ALIGN_PARAGRAPH.CENTER:
            for r in p.runs:r.font.color.rgb=RGBColor(19,62,106)
    for t in d.tables:
        t.alignment=WD_TABLE_ALIGNMENT.CENTER
        for i,row in enumerate(t.rows):
            for c in row.cells:
                c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for p in c.paragraphs:
                    for r in p.runs:r.font.size=Pt(8.5)
                if i==0:
                    from docx.oxml import OxmlElement
                    from docx.oxml.ns import qn
                    tcPr=c._tc.get_or_add_tcPr();shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'173F68');tcPr.append(shd)
                    for p in c.paragraphs:
                        for r in p.runs:r.bold=True;r.font.color.rgb=RGBColor(255,255,255)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;footer.add_run('Issued solely for the specified recipient and purpose | Verify particulars before signature').font.size=Pt(8)

def save_doc(doc,parent,name):
    path,_=QFileDialog.getSaveFileName(parent,'Save Word document',str(ROOT/(Path(name).stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.docx')),'Word (*.docx)')
    if path:
        if not path.lower().endswith('.docx'):path+='.docx'
        try:
            doc.save(path);offer_open(parent,path)
        except PermissionError:
            QMessageBox.warning(parent,'File is locked','Close the document in Microsoft Word or select another filename, then retry.')

def field(label,value=''):
    w=QLineEdit();w.setText(str(value));w.setPlaceholderText(label);return w

def table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
    t.setAlternatingRowColors(True)
    return t

def addrow(t,values):
    row=t.rowCount();t.insertRow(row)
    for j,val in enumerate(values):t.setItem(row,j,QTableWidgetItem(str(val)))
def cell(t,i,j):
    widget=t.cellWidget(i,j)
    if isinstance(widget,QComboBox):return widget.currentText().strip()
    return t.item(i,j).text().strip() if t.item(i,j) else ''

def add_itr_verification_row(t,values):
    row=t.rowCount();t.insertRow(row)
    for j in (0,1):t.setItem(row,j,QTableWidgetItem(str(values[j] if values[j] else (date.today().strftime('%d-%m-%Y') if j==1 else ''))))
    if t.columnCount()>4:t.setItem(row,4,QTableWidgetItem(str(values[4]) if len(values)>4 else ""))
    for j in (2,3):
        combo=QComboBox();combo.addItems(['YES','NO'])
        combo.setCurrentText(str(values[j]).upper() if str(values[j]).upper() in ('YES','NO') else 'YES')
        t.setCellWidget(row,j,combo)


def configure_document(d,preset,font,size):
    sec=d.sections[0];sec.top_margin=Inches(.7);sec.bottom_margin=Inches(.65);sec.left_margin=Inches(.75);sec.right_margin=Inches(.75)
    normal=d.styles['Normal'];normal.font.name=('Georgia' if preset==3 and font=='Aptos' else font);normal.font.size=Pt(size)
    normal.paragraph_format.space_after=Pt(7 if preset!=4 else 4)
    normal.paragraph_format.line_spacing=1.13 if preset!=4 else 1.05
    normal.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY

def financial_table_v6(d,headers,rows,style):
    t=d.add_table(rows=1,cols=len(headers));t.style='Table Grid' if style!=2 else 'Light Shading Accent 1'
    for j,x in enumerate(headers):t.rows[0].cells[j].text=str(x)
    for row in rows:
        c=t.add_row().cells
        for j,x in enumerate(row):c[j].text=str(x)
    for j,cell_ in enumerate(t.rows[0].cells):
        for p in cell_.paragraphs:
            for r in p.runs:r.bold=True
        if style==0:
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'173F68');cell_._tc.get_or_add_tcPr().append(sh)
            for p in cell_.paragraphs:
                for r in p.runs:r.font.color.rgb=RGBColor(255,255,255)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:p.alignment=WD_ALIGN_PARAGRAPH.LEFT

def finish_document_v6(d,preset):
    palette=[RGBColor(28,51,75),RGBColor(18,62,106),RGBColor(25,25,25),RGBColor(78,48,48),RGBColor(37,53,68)]
    for p in d.paragraphs:
        p.paragraph_format.widow_control=True
        if not p.text.strip():
            p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0)
            for r in p.runs:r.font.size=Pt(1)
        elif p.alignment==WD_ALIGN_PARAGRAPH.JUSTIFY and len(p.text.strip())<65:
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT
        if p.alignment==WD_ALIGN_PARAGRAPH.CENTER:
            for r in p.runs:r.font.color.rgb=palette[preset]
    footer=d.sections[0].footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run('Prepared for the specified addressee and purpose only').font.size=Pt(8)

class Main(QMainWindow):
 def __init__(self):
    super().__init__();self.setWindowTitle('Smart Certifictes V31 — Certificate Workspace');self.resize(1180,800)
    self.client_id=None;self.tabs=QTabWidget();self.tabs.tabBar().setUsesScrollButtons(True);self.tabs.setDocumentMode(True);self.setCentralWidget(self.tabs)
    self.make_itr();self.make_clients();self.make_gst_tab("GSTR-1");self.make_gst_tab("GSTR-3B");self.make_certificate();self.make_itr_verification_inputs();self.make_representation();self.make_networth();self.make_settings();self.make_signers();self.load_signers()
    self.statusBar().showMessage('Offline • Data stored at '+str(ROOT))
    self.setStyleSheet('QMainWindow{background:#f4f7fb}QTabWidget::pane{border:1px solid #dce5f0;background:white}QPushButton{background:#175c9e;color:white;border:0;border-radius:5px;padding:9px 13px;font-weight:600}QPushButton:hover{background:#0b447b}QLineEdit,QTextEdit,QTableWidget,QComboBox{border:1px solid #cad5e1;border-radius:4px;padding:5px;background:white}QLabel{color:#263849}QTabBar::tab{padding:11px 16px;background:#e7edf5}QTabBar::tab:selected{background:#175c9e;color:white}')
 def tab(self,title):
    # Each tab has its own vertical scrollbar. Content is never compressed to fit
    # a short display, and the scrollbar remains accessible when maximized.
    page=QWidget()
    outer=QVBoxLayout(page);outer.setContentsMargins(0,0,0,0)
    scroll=QScrollArea(page)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    content=QWidget()
    content.setMinimumWidth(780)
    v=QVBoxLayout(content);v.setContentsMargins(18,16,18,20);v.setSpacing(10)
    scroll.setWidget(content);outer.addWidget(scroll)
    self.tabs.addTab(page,title)
    return v
 def btn(self,layout,label,fn):
    b=QPushButton(label);b.clicked.connect(fn);layout.addWidget(b);return b
 def error(self,e):QMessageBox.critical(self,'Error',str(e));self.statusBar().showMessage(traceback.format_exc().splitlines()[-1])
 def make_clients(self):
    v=self.tab('Clients');v.addWidget(QLabel('CLIENT MASTER • Select a saved client or create a new one'))
    self.client_select=QComboBox();self.client_select.currentIndexChanged.connect(self.load_client);v.addWidget(self.client_select)
    self.cf={k:field(k) for k in ['Name','PAN','GSTIN','Address','Business / Trade Name']}
    self.name_parts={k:field(k) for k in ['First Name','Middle Name','Surname']}
    for w in self.name_parts.values():w.editingFinished.connect(self.sync_full_name)
    f=QFormLayout()
    for k,w in self.name_parts.items():f.addRow(k,w)
    for k,w in self.cf.items():f.addRow(k,w)
    self.entity_type=QComboBox();self.entity_type.addItems(['Individual','Proprietorship Firm','Partnership Firm','LLP','Private Limited Company','Public Limited Company','HUF','Trust','Society','AOP / BOI','Other'])
    f.addRow('Type of assessee / entity',self.entity_type)
    self.client_mrl_signer=field('Name of person signing the management representation');f.addRow('MRL signatory name',self.client_mrl_signer)
    self.client_mrl_position=QComboBox();self.client_mrl_position.setEditable(True);self.client_mrl_position.addItems(['Proprietor','Partner','Designated Partner','Director','Managing Director','Karta','Trustee','Authorised Signatory','Individual / Self','Other'])
    f.addRow('MRL signatory position',self.client_mrl_position)
    v.addLayout(f);r=QHBoxLayout();self.btn(r,'New client',self.new_client);self.btn(r,'Save client',self.save_client);self.btn(r,'Delete selected client',self.delete_client);v.addLayout(r)
    v.addWidget(QLabel('Client master details are reused in certificates and management representation letters.'))
    self.refresh_clients()
 def sync_full_name(self):
    full=' '.join(w.text().strip() for w in self.name_parts.values() if w.text().strip())
    if full:self.cf['Name'].setText(full)
 def refresh_clients(self,selected=None):
    self.client_select.blockSignals(True);self.client_select.clear();self.client_select.addItem('— New client —',None)
    for cid,name,pan in CON.execute('SELECT id,name,pan FROM clients ORDER BY name'):
        self.client_select.addItem(f'{name}  |  {pan or "No PAN"}',cid)
        if cid==selected:self.client_select.setCurrentIndex(self.client_select.count()-1)
    self.client_select.blockSignals(False)
    if selected:self.load_client()
 def new_client(self):
    self.client_select.setCurrentIndex(0);self.client_id=None
    for w in self.cf.values():w.clear()
    for w in self.name_parts.values():w.clear()
    self.entity_type.setCurrentIndex(0);self.client_mrl_signer.clear();self.client_mrl_position.setCurrentText('Proprietor')
 def load_client(self):
    cid=self.client_select.currentData();self.client_id=cid
    if cid:
        r=CON.execute('SELECT name,pan,gstin,address,firm FROM clients WHERE id=?',(cid,)).fetchone()
        if r:
            for w,val in zip(self.cf.values(),r):w.setText(val or '')
            parts=CON.execute('SELECT first_name,middle_name,surname FROM client_name_parts WHERE client_id=?',(cid,)).fetchone() or split_person_name(r[0])
            for w,val in zip(self.name_parts.values(),parts):w.setText(val or '')
        extra=CON.execute('SELECT entity_type,mrl_signer,mrl_position FROM client_extra WHERE client_id=?',(cid,)).fetchone()
        if extra:
            self.entity_type.setCurrentText(extra[0] or 'Individual');self.client_mrl_signer.setText(extra[1] or '');self.client_mrl_position.setCurrentText(extra[2] or 'Proprietor')
        else:self.entity_type.setCurrentText('Individual');self.client_mrl_signer.clear();self.client_mrl_position.setCurrentText('Proprietor')
    else:
        for w in self.cf.values():w.clear()
        for w in self.name_parts.values():w.clear()
        self.entity_type.setCurrentText('Individual');self.client_mrl_signer.clear();self.client_mrl_position.setCurrentText('Proprietor')
    if hasattr(self,'itr_table'):self.load_itr()
    if hasattr(self,'itr_engager'):self.autofill_itr_parties()
 def save_client(self):
    self.sync_full_name()
    vals=[w.text().strip() for w in self.cf.values()]
    if not vals[0]:return QMessageBox.warning(self,'Missing name','Enter client name.')
    if vals[1] and not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]',vals[1].upper()):return QMessageBox.warning(self,'Invalid PAN','PAN should have 10 characters in the prescribed pattern.')
    vals[1]=vals[1].upper();vals[2]=vals[2].upper()
    if self.client_id:
        CON.execute('UPDATE clients SET name=?,pan=?,gstin=?,address=?,firm=?,updated=? WHERE id=?',(*vals,str(date.today()),self.client_id))
    else:
        c=CON.execute('INSERT INTO clients(name,pan,gstin,address,firm,updated) VALUES(?,?,?,?,?,?)',(*vals,str(date.today())))
        self.client_id=c.lastrowid
    CON.execute('INSERT OR REPLACE INTO client_extra(client_id,entity_type,mrl_signer,mrl_position) VALUES (?,?,?,?)',(self.client_id,self.entity_type.currentText(),self.client_mrl_signer.text().strip(),self.client_mrl_position.currentText().strip()))
    CON.execute('INSERT OR REPLACE INTO client_name_parts(client_id,first_name,middle_name,surname) VALUES(?,?,?,?)',(self.client_id,*[w.text().strip() for w in self.name_parts.values()]))
    CON.commit();self.refresh_clients(self.client_id);self.statusBar().showMessage('Client saved')
 def delete_client(self):
    if not self.client_id:return
    if QMessageBox.question(self,'Confirm deletion','Delete client and all saved ITR records?')!=QMessageBox.StandardButton.Yes:return
    CON.execute('DELETE FROM client_name_parts WHERE client_id=?',(self.client_id,));CON.execute('DELETE FROM client_extra WHERE client_id=?',(self.client_id,));CON.execute('DELETE FROM itr WHERE client_id=?',(self.client_id,));CON.execute('DELETE FROM clients WHERE id=?',(self.client_id,));CON.commit();self.refresh_clients();self.new_client();self.load_itr()
 def make_itr(self):
    v=self.tab('Step 1 • Import ITR PDF');v.addWidget(QLabel('START HERE: Create/select a client once in Clients tab, then import any number of ITR PDFs / JSONs. Client names are never extracted or overwritten.'))
    r=QHBoxLayout();self.btn(r,'Import PDF / JSON',self.import_pdfs);self.btn(r,'Save edited rows',self.save_itr);self.btn(r,'Remove selected row',self.remove_itr);self.btn(r,'Export ITR Excel',self.export_itr);v.addLayout(r)
    self.itr_table=table(['AY','ITR Form','Total Income (₹)','Acknowledgement No.','Filing Date','PDF Source']);self.itr_table.setMinimumHeight(230);v.addWidget(self.itr_table)
    v.addWidget(QLabel('PDF / JSON: check all extracted amounts against the filed ITR. Blank means not reliably identified.'))
 def load_itr(self):
    self.itr_table.setRowCount(0)
    if self.client_id:
        for r in CON.execute('SELECT ay,form,income,ack,filing,source FROM itr WHERE client_id=? ORDER BY ay',(self.client_id,)):addrow(self.itr_table,r)
 def import_pdfs(self):
     paths,_=QFileDialog.getOpenFileNames(self,'Import ITR PDF or JSON','','ITR files (*.pdf *.json)')
     if not paths:return
     imported=0;skipped=[];last_cid=None;last_imported_ay=None
     for path in paths:
        try:
             d=extract_itr_json(path) if path.lower().endswith('.json') else extract_itr(path)
             source_pan=(d.get('pan') or '').strip().upper()
             # PAN is the only automatic identity key. Extracted names are never used.
             selected=CON.execute('SELECT id,name,pan FROM clients WHERE id=?',(self.client_id,)).fetchone() if self.client_id else None
             matching=CON.execute('SELECT id,name,pan FROM clients WHERE UPPER(pan)=? ORDER BY id LIMIT 1',(source_pan,)).fetchone() if source_pan else None
             if selected and source_pan and selected[2] and selected[2].strip().upper()!=source_pan:
                 skipped.append(f'{Path(path).name}: PAN differs from selected client; no import.')
                 continue
             if selected and matching and selected[0]!=matching[0]:
                 skipped.append(f'{Path(path).name}: PAN belongs to a different saved client; no import.')
                 continue
             target=matching or selected
             if not target:
                 skipped.append(f'{Path(path).name}: Create/select client manually in Clients tab before importing.')
                 continue
             cid=target[0]
             # A missing identifier is not a reason to discard an otherwise readable JSON.
             # Ask for missing values only, never ask for client identity again.
             if not d.get('ay'):
                 ay,ok=QInputDialog.getText(self,'Missing assessment year',f'{Path(path).name}\nEnter assessment year (e.g. 2026-27):')
                 if not ok or not normalize_ay(ay):
                     skipped.append(f'{Path(path).name}: Assessment year not confirmed.');continue
                 d['ay']=normalize_ay(ay)
             if not d.get('ack'):
                 ack,ok=QInputDialog.getText(self,'Missing acknowledgement number',f'{Path(path).name}\nEnter ITR acknowledgement number (digits only):')
                 if not ok or not re.fullmatch(r'\d{12,20}',ack.strip()):
                     skipped.append(f'{Path(path).name}: Acknowledgement number not confirmed.');continue
                 d['ack']=ack.strip()
             method=d.get('accounting_method') or 'Review manually'
             CON.execute('INSERT OR REPLACE INTO itr_accounting_method(client_id,ay,ack,method) VALUES(?,?,?,?)',(cid,d['ay'],d['ack'],method))
             CON.execute('INSERT INTO itr(client_id,ay,form,income,ack,filing,source) VALUES(?,?,?,?,?,?,?) ON CONFLICT(client_id,ay,ack) DO UPDATE SET form=excluded.form,income=excluded.income,filing=excluded.filing,source=excluded.source',(cid,d['ay'],d.get('form',''),d.get('income',''),d['ack'],d.get('filing',''),path))
             CON.execute("INSERT INTO itr_financials(client_id,ay,ack,turnover,turnover_basis,networth,networth_basis,source) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(client_id,ay,ack) DO UPDATE SET turnover=excluded.turnover,turnover_basis=excluded.turnover_basis,networth=excluded.networth,networth_basis=excluded.networth_basis,source=excluded.source",(cid,d['ay'],d['ack'],d.get('turnover',''),d.get('turnover_basis',''),d.get('networth',''),d.get('networth_basis',''),path))
             CON.commit();imported+=1;last_cid=cid;last_imported_ay=d['ay']
        except Exception as e:
             skipped.append(f'{Path(path).name}: {e}')
     if last_cid is not None:self.refresh_clients(last_cid)
     self.load_itr()
     if last_imported_ay and hasattr(self,'nw_ay'):
         self._v54_select_networth_ay(last_imported_ay)
     message=f'{imported} ITR file(s) imported. Existing client names and details were not changed.'
     if skipped:message+='\n\nNot imported:\n'+'\n'.join(skipped[:15])
     QMessageBox.information(self,'ITR import completed',message)
 def import_status_evidence(self):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Select a client first.')
    paths,_=QFileDialog.getOpenFileNames(self,'Import income tax portal filed return status PDF / screenshot','','PDF and images (*.pdf *.png *.jpg *.jpeg *.tif *.tiff)')
    if not paths:return
    matches={};unread=[]
    for path in paths:
        try:
            content=''
            if path.lower().endswith('.pdf'):
                with fitz.open(path) as pdf:
                    content='\n'.join(page.get_text(sort=True) for page in pdf)
                    # Scanned PDFs may have no searchable text; OCR is fallback only.
                    if not detect_statuses(content):
                        try:
                            import pytesseract,io
                            from PIL import Image
                            content+='\n'+'\n'.join(pytesseract.image_to_string(Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2,2)).tobytes('png')))) for page in pdf)
                        except Exception as e:
                            unread.append(Path(path).name+': OCR unavailable ('+str(e)[:100]+')')
            else:
                import pytesseract
                from PIL import Image
                content=pytesseract.image_to_string(Image.open(path))
            statuses=detect_statuses(content)
            if not statuses:
                unread.append(Path(path).name+': no AY/status pairs detected')
                continue
            for ay,status in statuses.items():matches[ay]=(status,path)
        except Exception as e:unread.append(f'{Path(path).name}: {e}')
    saved=[]
    for ay,(status,path) in sorted(matches.items()):
        if not CON.execute('SELECT 1 FROM itr WHERE client_id=? AND ay=?',(self.client_id,ay)).fetchone():
            unread.append(f'{ay}: no matching saved ITR for this client');continue
        ok=QMessageBox.question(self,'Verify imported ITR status',f'Assessment year: {ay}\nDetected latest processing status: {status}\nEvidence: {Path(path).name}\n\nThis is an extraction from the supplied PDF, not live portal verification.\nHave you compared it with the portal screenshot?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if ok!=QMessageBox.StandardButton.Yes:continue
        CON.execute('INSERT INTO itr_status(client_id,ay,status,evidence,reviewed) VALUES(?,?,?,?,1) ON CONFLICT(client_id,ay) DO UPDATE SET status=excluded.status,evidence=excluded.evidence,reviewed=1',(self.client_id,ay,status,path));saved.append(ay)
    CON.commit()
    if saved:
        self.refresh_clients(self.client_id)
        if hasattr(self,'fin_table') and self.fin_table.rowCount():
            for i in range(self.fin_table.rowCount()):
                ay=cell(self.fin_table,i,0)
                if ay in saved:self.fin_table.setItem(i,5,QTableWidgetItem(matches[ay][0]))
    QMessageBox.information(self,'Status import',f'Confirmed statuses saved: {", ".join(saved) or "None"}'+('\nUnmatched / unreadable: '+', '.join(unread) if unread else '')+'\n\nStatus is based on the uploaded evidence, not a live government portal check.')
 def edit_itr_status(self):
    if not self.client_id:return QMessageBox.warning(self,'Client','Select client first.')
    ay,ok=QInputDialog.getItem(self,'Select assessment year','AY',[r[0] for r in CON.execute('SELECT DISTINCT ay FROM itr WHERE client_id=? ORDER BY ay',(self.client_id,))],0,False)
    if not ok or not ay:return
    options=['Processed with refund due','Processed with no demand/refund','Processed with demand due','Successfully e-verified','Under processing','Pending for e-verification']
    status,ok=QInputDialog.getItem(self,'Verified status','Choose status from the portal evidence:',options,0,True)
    if not ok or not status.strip():return
    evidence,ok=QInputDialog.getText(self,'Evidence reference','Screenshot filename / portal verification note (required):')
    if not ok or not evidence.strip():return
    CON.execute('INSERT INTO itr_status(client_id,ay,status,evidence,reviewed) VALUES(?,?,?,?,1) ON CONFLICT(client_id,ay) DO UPDATE SET status=excluded.status,evidence=excluded.evidence,reviewed=1',(self.client_id,ay,status.strip(),evidence.strip()));CON.commit()
    QMessageBox.information(self,'Saved','Status saved with manual confirmation and evidence reference.')
 def save_itr(self):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Select a client first.')
    try:
        for i in range(self.itr_table.rowCount()):
            vals=[cell(self.itr_table,i,j) for j in range(6)]
            if not vals[0] or not vals[3]:continue
            CON.execute('INSERT INTO itr(client_id,ay,form,income,ack,filing,source) VALUES(?,?,?,?,?,?,?) ON CONFLICT(client_id,ay,ack) DO UPDATE SET form=excluded.form,income=excluded.income,filing=excluded.filing,source=excluded.source',(self.client_id,*vals))
        CON.commit();self.load_itr();QMessageBox.information(self,'Saved','ITR records saved.')
    except Exception as e:self.error(e)
 def remove_itr(self):
    i=self.itr_table.currentRow()
    if i<0:return
    ack=cell(self.itr_table,i,3);ay=cell(self.itr_table,i,0)
    if self.client_id:CON.execute('DELETE FROM itr WHERE client_id=? AND ay=? AND ack=?',(self.client_id,ay,ack));CON.commit()
    self.itr_table.removeRow(i)
 def export_itr(self):
    try:
        wb=Workbook();ws=wb.active;ws.title='ITR Details';ws.append(['Client','PAN','AY','Form','Total Income','Ack No','Filing Date','Source'])
        for i in range(self.itr_table.rowCount()):ws.append([self.cf['Name'].text(),self.cf['PAN'].text()]+[cell(self.itr_table,i,j) for j in range(5)])
        self.export_wb(wb,'ITR_Summary.xlsx')
    except Exception as e:self.error(e)
 def export_wb(self,wb,default):
    ws=wb.active
    for c in ws[1]:c.font=Font(color='FFFFFF',bold=True);c.fill=PatternFill('solid',fgColor='175C9E')
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col in ws.columns:
        letter=col[0].column_letter;ws.column_dimensions[letter].width=min(52,max(15,max(len(str(x.value or '')) for x in col)+2))
    path,_=QFileDialog.getSaveFileName(self,'Save Excel',str(ROOT/default),'Excel (*.xlsx)')
    if path:
        path=path if path.lower().endswith('.xlsx') else path+'.xlsx'
        wb.save(path);offer_open(self,path)
 def sync_cert_heading(self,*_):
    titles=['INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT VERIFICATION CERTIFICATE','TURNOVER CERTIFICATE','TURNOVER AND NET WORTH CERTIFICATE','NET WORTH CERTIFICATE']
    self.cert_heading.setCurrentText(titles[self._cert_kind()])
 def pick_letterhead_logo(self):
    path,_=QFileDialog.getOpenFileName(self,'Choose logo image',str(ROOT),'Images (*.png *.jpg *.jpeg)')
    if path:self.lh_logo.setText(path)
 def save_letterhead_preferences(self):
    cfg={key:widget.text().strip() for key,widget in [('logo',self.lh_logo),('firm',self.lh_firm),('address',self.lh_address),('phone',self.lh_phone),('email',self.lh_email),('footer',self.lh_footer)]}
    LETTERHEAD_CONFIG.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    QMessageBox.information(self,'Letterhead','Preferences saved for this Windows user.')
 def apply_professional_letterhead(self,d,signer):
    sec=d.sections[0]
    sec.header_distance=Inches(.28);sec.footer_distance=Inches(.30)
    firm=self.lh_firm.text().strip() or signer['firm']
    address=self.lh_address.text().strip() or signer['address']
    phone=self.lh_phone.text().strip() or signer['phone']
    email=self.lh_email.text().strip() or signer['email']
    logo=self.lh_logo.text().strip()
    header=sec.header
    hp=header.paragraphs[0];hp.alignment=WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after=Pt(1)
    if logo and Path(logo).is_file():
        hp.add_run().add_picture(logo,width=Inches(.80))
        hp.add_run('   ')
    run=hp.add_run(firm.upper());run.bold=True;run.font.size=Pt(12)
    hp2=header.add_paragraph('CHARTERED ACCOUNTANTS');hp2.paragraph_format.space_after=Pt(0)
    hp2.runs[0].font.size=Pt(8)
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.space_after=Pt(0)
    contact=' | '.join(x for x in (address,phone,email,self.lh_footer.text().strip()) if x)
    r=footer.add_run(contact);r.font.size=Pt(8)
    # Keep the page body separate from header/footer, avoiding overlapping text.
    sec.top_margin=Inches(1.25);sec.bottom_margin=Inches(.85)
 def normalize_certificate_paragraphs(self,d):
    from docx.enum.text import WD_LINE_SPACING
    for para in d.paragraphs:
        if para.alignment==WD_ALIGN_PARAGRAPH.JUSTIFY:
            para.alignment=WD_ALIGN_PARAGRAPH.LEFT
        para.paragraph_format.space_after=Pt(5)
        para.paragraph_format.line_spacing=1.12
    for t in d.tables:
        t.autofit=True
 def make_certificate(self):
    v=self.tab('Certificates');self.cert_layout=v;v.addWidget(QLabel('BLUE: imported / linked data    GREEN: manual entry completed    RED: required manual entry missing'))
    self.cert_type=QComboBox();self.cert_type.addItems(['Turnover Certificate','Net Worth Certificate','Income Tax Return Verification Certificate','Turnover and Net Worth Certificate']);v.addWidget(self.cert_type)
    v.addWidget(QLabel('Certificate heading (editable)'))
    self.cert_heading=QComboBox();self.cert_heading.setEditable(True)
    self.cert_heading.addItems(['TURNOVER CERTIFICATE','NET WORTH CERTIFICATE','TURNOVER AND NET WORTH CERTIFICATE','INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT VERIFICATION CERTIFICATE'])
    v.addWidget(self.cert_heading)
    self.cert_type.currentIndexChanged.connect(self.sync_cert_heading)
    self.cert_heading.setCurrentText('INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT VERIFICATION CERTIFICATE')
    self.recipient=field('Certificate issued to (bank / department / organization)');v.addWidget(QLabel('Issued To'));v.addWidget(self.recipient)
    self.purpose=field('Specific purpose (e.g., tender reference / loan application)');v.addWidget(QLabel('Purpose of issue'));v.addWidget(self.purpose)
    self.recipient_address=field('Full address of specified recipient');v.addWidget(QLabel('Recipient address (required)'));v.addWidget(self.recipient_address)
    self.engagement_date=field('DD-MM-YYYY');v.addWidget(QLabel('Engagement letter date (required)'));v.addWidget(self.engagement_date)
    self._assurance_section_start=v.count()
    self.criteria=QComboBox();self.criteria.setEditable(True);self.criteria.addItems(['Select basis after review','Annual turnover as per GSTR-3B returns filed for the relevant financial years','Annual turnover as per GSTR-1 returns filed for the relevant financial years','Annual turnover as per ITR Schedule BP / Trading Account for the relevant assessment years','Annual turnover as per audited financial statements for the relevant financial years','Net worth computed as total assets less outside liabilities as per accompanying statement','Owner / partner capital as per ITR financial particulars (business equity only; subject to reconciliation)','Proprietor’s fund (capital plus reserves less accumulated losses) as per ITR-3 balance sheet (subject to reconciliation)']);v.addWidget(QLabel('Applicable criteria / basis of preparation (required)'));v.addWidget(self.criteria)
    self.procedures=QComboBox();self.procedures.setEditable(True);self.procedures.addItems(['Select procedures actually completed','Examined the GSTR-3B returns for the stated periods and agreed the turnover figures to the accompanying statement.','Examined the GSTR-1 returns for the stated periods and reconciled the reported turnover to the accompanying statement.','Examined the filed ITR and relevant schedules and agreed the turnover figures to the accompanying statement.','Examined the audited financial statements and agreed the turnover figures to the relevant schedules.','Examined supporting asset and liability records, verified the arithmetic and agreed the net worth computation to the accompanying statement.']);v.addWidget(QLabel('Procedures actually performed (required)'));v.addWidget(self.procedures)
    self.assurance=QComboBox();self.assurance.addItems(['Select assurance level','Limited assurance','Reasonable assurance']);v.addWidget(QLabel('Assurance level — select only after evaluating evidence'));v.addWidget(self.assurance)
    self.conclusion=QComboBox();self.conclusion.addItems(['Unmodified','Qualified','Adverse','Disclaimer']);v.addWidget(QLabel('Conclusion type (requires CA judgment)'));v.addWidget(self.conclusion)
    self.conclusion_basis=QTextEdit();self.conclusion_basis.setPlaceholderText('Qualifications, limitations, key observations, or basis for modified conclusion');self.conclusion_basis.setMaximumHeight(75);v.addWidget(QLabel('Basis for conclusion / modification'));v.addWidget(self.conclusion_basis)
    self.check_evidence=QComboBox();self.check_evidence.addItems(['Not confirmed','Engagement letter, evidence and representation reviewed']);v.addWidget(QLabel('Evidence and engagement review'));v.addWidget(self.check_evidence)

    self._assurance_section_end=v.count()
    self.cert_date=field('Net worth as-on date (DD-MM-YYYY)');v.addWidget(self.cert_date)
    self.cert_basis=field('Internal verification notes (not printed on certificate)');v.addWidget(self.cert_basis)
    self.fin_table=table(['Assessment Year','Turnover / Income (₹)','ITR Form','Ack No.','Date of Filing'])
    self.fin_table.setMinimumHeight(190);v.addWidget(self.fin_table)
    v.addWidget(QLabel('Turnover source — choose ITR, GSTR-1 or GSTR-3B (GST years are mapped to the following assessment year)'))
    self.turnover_source=QComboBox()
    self.turnover_source.addItems(['ITR PDF / JSON','GSTR-1 monthly returns','GSTR-3B monthly returns'])
    self.turnover_source.setCurrentIndex(2)
    v.addWidget(self.turnover_source)
    r=QHBoxLayout();self.btn(r,'Add financial year',lambda:addrow(self.fin_table,['','','','','']));self.btn(r,'Fetch turnover from selected source',self.fetch_selected_turnover);self.btn(r,'Delete selected row',lambda:self.fin_table.removeRow(self.fin_table.currentRow()) if self.fin_table.currentRow()>=0 else None);v.addLayout(r)
    self._networth_section_start=v.count()
    self.nw_ay=QComboBox();v.addWidget(QLabel('Select assessment year for net worth (business capital is not automatically personal net worth)'));v.addWidget(self.nw_ay)
    self.nw_ay.currentIndexChanged.connect(self.load_selected_networth)
    self.cert_net=field('Net Worth (₹)');v.addWidget(QLabel('Net worth as at 31 March (only for combined certificate)'));v.addWidget(self.cert_net)
    self.cert_capital=field('Capital (₹)');self.cert_reserve=field('Reserve and surplus (₹)','0');self.cert_losses=field('Accumulated losses (₹)','0')
    for lbl,w in [('Capital as at certificate date',self.cert_capital),('Add: Reserves and surplus',self.cert_reserve),('Less: Accumulated losses',self.cert_losses)]:v.addWidget(QLabel(lbl));v.addWidget(w)
    self._networth_section_end=v.count()
    self.cert_ud=field('UDIN (enter after obtaining from ICAI portal)');v.addWidget(QLabel('UDIN for this certificate (manual)'));v.addWidget(self.cert_ud)
    v.addWidget(QLabel('Document appearance (choose a preset, font, size and table design)'))
    rstyle=QHBoxLayout()
    self.doc_preset=QComboBox();self.doc_preset.addItems(['1 • Classic Professional','2 • Modern Navy','3 • Minimal Black','4 • Elegant Serif','5 • Compact Formal']);rstyle.addWidget(self.doc_preset)
    self.doc_font=QComboBox();self.doc_font.addItems(['Calibri','Century Schoolbook','Aptos','Cambria','Georgia','Arial','Times New Roman']);rstyle.addWidget(self.doc_font)
    self.doc_size=QSpinBox();self.doc_size.setRange(9,14);self.doc_size.setValue(10);rstyle.addWidget(self.doc_size)
    self.doc_table_style=QComboBox();self.doc_table_style.addItems(['Shaded heading','Plain grid','Light horizontal']);rstyle.addWidget(self.doc_table_style)
    v.addLayout(rstyle)
    self.btn(v,'Generate Word Certificate',self.generate_certificate)
    self.btn(v,'Prepare Management Representation Letter',lambda:self.tabs.setCurrentIndex(self.representation_tab_index))
    self.cert_type.currentIndexChanged.connect(self.update_certificate_fields)
    self.update_certificate_fields()
    v.addWidget(QLabel('Turnover is NOT inferred from total income. ITR acknowledgement verification requires direct portal download witnessed by the CA.'))
 def update_certificate_fields(self, *_):
    kind=self._cert_kind()
    is_itr=kind==0
    combined=kind in (2,3)
    # All certificate inputs are on the Certificates tab. Unrelated inputs are hidden.
    if hasattr(self,'itr_group'):self.itr_group.setVisible(is_itr)
    layout=self.cert_layout
    for i in range(self._assurance_section_start,self._assurance_section_end):
        item=layout.itemAt(i)
        if item and item.widget():item.widget().setVisible(not is_itr)
    for i in range(self._networth_section_start,self._networth_section_end):
        item=layout.itemAt(i)
        if item and item.widget():item.widget().setVisible(combined)
    # Mark every visible editable field: green = manual entry; blue = linked/imported.
    self.refresh_certificate_colours()

 def refresh_certificate_colours(self):
    if not hasattr(self,'cert_type'):return
    kind=self._cert_kind()
    manual=[self.cert_heading,self.recipient,self.purpose,self.recipient_address,self.engagement_date,self.cert_ud]
    if kind!=0:manual.extend([self.criteria,self.procedures,self.assurance,self.conclusion,self.check_evidence])
    if kind in (2,3):manual.extend([self.cert_net,self.cert_capital,self.cert_reserve,self.cert_losses,self.cert_date])
    if kind==0 and hasattr(self,'itr_engager'):manual.extend([self.itr_engager,self.itr_submission,self.itr_unverified])
    for widget in manual:
        if not widget.isVisible():continue
        if isinstance(widget,QComboBox):
            value=widget.currentText().strip()
            empty=not value or value.lower().startswith('select') or (widget is self.assurance and widget.currentIndex()==0) or (widget is self.check_evidence and widget.currentIndex()==0)
        else:value=widget.text().strip();empty=not value
        colour='#ffe0e0' if empty else '#e1f6e7'
        widget.setStyleSheet('background-color:'+colour+';border:2px solid '+('#c83a3a' if empty else '#24924e')+';')
    for widget in (self.fin_table,self.itr_downloads if hasattr(self,'itr_downloads') else None,self.nw_ay):
        if widget is not None and widget.isVisible():widget.setStyleSheet('background-color:#e8f2ff;border:2px solid #2674bb;')

 def autofill_itr_parties(self):
    if not hasattr(self,'itr_engager'):return
    name=self.cf['Name'].text().strip()
    authority=self.recipient.text().strip()
    # A previous automatic value may be replaced; manual edits are preserved.
    for widget,value,key in ((self.itr_engager,name,'_last_auto_engager'),(self.itr_submission,authority,'_last_auto_submission')):
        old=getattr(self,key,'')
        if value and (not widget.text().strip() or widget.text().strip()==old):
            widget.setText(value)
            setattr(self,key,value)

 def make_itr_verification_inputs(self):
    self.itr_group=QGroupBox('ITR Acknowledgement — Verification Details')
    self.cert_layout.addWidget(self.itr_group)
    v=QVBoxLayout(self.itr_group)
    v.addWidget(QLabel('ICAI Handbook (October 2025), Annexure III (vi), pages 64–66. Complete these details before preparing the ITR acknowledgement certificate.'))
    v.addWidget(QLabel('The illustrative opinion is supported ONLY when the assessee downloads the acknowledgement from their income-tax portal login in the practitioner’s presence.'))
    self.itr_engager=field('Person / entity engaging the CA');v.addWidget(QLabel('Engaging authority / client name'));v.addWidget(self.itr_engager)
    self.itr_submission=field('Bank / Embassy / named authority');v.addWidget(QLabel('Authority to whom the certificate will be submitted'));v.addWidget(self.itr_submission)
    self.recipient.textChanged.connect(lambda _text:self.autofill_itr_parties())
    self.cf['Name'].textChanged.connect(lambda _text:self.autofill_itr_parties())
    self.autofill_itr_parties()
    self.itr_downloads=table(['Assessment Year','Download date (DD-MM-YYYY)','Downloaded from assessee login in CA presence? (YES/NO)','Acknowledgement verified against download? (YES/NO)','Total Income as per ITR (₹)'])
    self.itr_downloads.setMinimumHeight(230);v.addWidget(self.itr_downloads)
    r=QHBoxLayout();self.btn(r,'Load assessment years',self.populate_itr_downloads);self.btn(r,'Add assessment year',lambda:add_itr_verification_row(self.itr_downloads,['',date.today().strftime('%d-%m-%Y'),'YES','YES','']));self.btn(r,'Remove selected',lambda:self.itr_downloads.removeRow(self.itr_downloads.currentRow()) if self.itr_downloads.currentRow()>=0 else None);v.addLayout(r)
    self.itr_unverified=QComboBox();self.itr_unverified.addItems(['No — ITR was verified / submitted','Yes — ITR not yet verified / submitted'])
    v.addWidget(QLabel('ITR-V verification position — manual confirmation'));v.addWidget(self.itr_unverified)
    self.itr_note=QTextEdit();self.itr_note.setMaximumHeight(75);self.itr_note.setPlaceholderText('Any qualification, observation, or different procedure performed (for CA review)')
    v.addWidget(QLabel('Additional observations'));v.addWidget(self.itr_note)
    self.itr_group.setVisible(self._cert_kind()==0)
    for w in (self.criteria,self.procedures,self.assurance,self.conclusion,self.check_evidence,self.itr_unverified):
        w.currentIndexChanged.connect(lambda _=None:self.refresh_certificate_colours())
    for w in (self.recipient,self.purpose,self.recipient_address,self.engagement_date,self.cert_ud,self.itr_engager,self.itr_submission):
        w.textChanged.connect(lambda _=None:self.refresh_certificate_colours())
    self.update_certificate_fields()
    v.addWidget(QLabel('IMPORTANT: YES is preselected for convenience. Change to NO unless you actually performed each verification. The software cannot verify the portal itself.'))
 def populate_itr_downloads(self):
    old={cell(self.itr_downloads,i,0):[cell(self.itr_downloads,i,j) for j in range(1,5)] for i in range(self.itr_downloads.rowCount())}
    self.itr_downloads.setRowCount(0)
    for i in range(self.fin_table.rowCount()):
        ay=cell(self.fin_table,i,0)
        if ay:
            income=cell(self.fin_table,i,1) if self._cert_kind()==0 else ''
            if not income and self.client_id:
                r=CON.execute('SELECT income FROM itr WHERE client_id=? AND ay=? ORDER BY id DESC LIMIT 1',(self.client_id,ay)).fetchone()
                income=r[0] if r and r[0] is not None else ''
            previous=old.get(ay,[date.today().strftime('%d-%m-%Y'),'YES','YES',''])
            add_itr_verification_row(self.itr_downloads,[ay,previous[0] or date.today().strftime('%d-%m-%Y'),previous[1],previous[2],income or previous[3]])
 def fetch_selected_turnover(self):
    source=self.turnover_source.currentIndex()
    if source==0:
        return self.fill_from_itr()
    if self._cert_kind()==0:
        return QMessageBox.warning(self,'ITR verification','ITR acknowledgement certificates require ITR data, not GST turnover.')
    if not self.client_id:
        return QMessageBox.warning(self,'Select client','Select and save a client first.')
    kind='GSTR-1' if source==1 else 'GSTR-3B'
    records=CON.execute('SELECT fy,month,turnover FROM gst_monthly WHERE client_id=? AND return_type=? ORDER BY fy,month',(self.client_id,kind)).fetchall()
    if not records:
        return QMessageBox.warning(self,'No GST returns',f'No {kind} returns have been imported for this client. Import the monthly PDFs first.')
    from collections import defaultdict
    by_fy=defaultdict(dict)
    for fy,month,amount in records:
        by_fy[fy][int(month)]=gst_amount(amount)
    incomplete=[]
    rows=[]
    for fy,months in sorted(by_fy.items()):
        if not re.fullmatch(r'\d{4}-\d{2}',fy):continue
        ay=f'{int(fy[:4])+1}-{(int(fy[:4])+2)%100:02d}'
        total=sum(months.values(),Decimal('0'))
        if len(months)<12:incomplete.append(f'FY {fy} ({len(months)}/12 months)')
        rows.append((ay,total,fy,len(months)))
    if incomplete:
        message='Some GST financial years are incomplete:\n'+ '\n'.join(incomplete)+'\n\nPartial-year figures must not be described as full-year turnover. Import remaining returns or use the figures only as a clearly identified partial-period working. Continue loading these figures into the editable table?'
        choice=QMessageBox.question(self,'Incomplete GST periods',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if choice!=QMessageBox.StandardButton.Yes:return
    self.fin_table.setRowCount(0)
    for ay,total,fy,count in rows:
        addrow(self.fin_table,[ay,f'{total:.2f}',f'{kind} ({count}/12 months)','',f'FY {fy}'])
    basis=f'Annual turnover as per {kind} returns filed for the relevant financial years'
    self.criteria.setCurrentText(basis)
    procedure=('Examined the GSTR-1 returns for the stated periods and reconciled the reported turnover to the accompanying statement.' if source==1 else 'Examined the GSTR-3B returns for the stated periods and agreed the turnover figures to the accompanying statement.')
    self.procedures.setCurrentText(procedure)
    self.cert_basis.setText(f'Turnover figures imported from {kind} monthly returns. Check period completeness, amendments, credit notes, and reconciliation with books before issuing the certificate.')
    QMessageBox.information(self,'GST turnover loaded',f'{len(rows)} financial year(s) loaded from {kind}. The figures are editable. Review the corresponding Excel working and reconcile with books before certification.')

 def fill_from_itr(self):
    if not self.client_id:return QMessageBox.warning(self,'Client','Select and save a client first.')
    typ=self._cert_kind();self.fin_table.setRowCount(0)
    missing=[];net=[]
    records=CON.execute('SELECT i.ay,i.form,i.income,i.ack,i.filing,f.turnover,f.turnover_basis,f.networth,f.networth_basis FROM itr i LEFT JOIN itr_financials f ON f.client_id=i.client_id AND f.ay=i.ay AND f.ack=i.ack WHERE i.client_id=? ORDER BY i.ay',(self.client_id,)).fetchall()
    if not records:return QMessageBox.warning(self,'No saved ITR','Import PDFs in ITR Reader and click Save edited rows first.')
    for ay,form,income,ack,filing,turnover,basis,nw,nwb in records:
        amount=income if typ==0 else turnover
        if amount is None or amount=='':missing.append(f'{ay}: '+('total income' if typ==0 else 'turnover'))
        addrow(self.fin_table,[ay,amount or '',form,ack,filing])
        if nw and typ in (2,3):net.append((ay,nw,nwb))
    self.nw_ay.blockSignals(True)
    previous=self.nw_ay.currentData()
    self.nw_ay.clear()
    for year in sorted({r[0] for r in records if r[0]}):self.nw_ay.addItem(year,year)
    self.nw_ay.blockSignals(False)
    target=getattr(self,'_v54_last_imported_ay',None)
    if not target and self.nw_ay.count():
        target=self.nw_ay.itemData(self.nw_ay.count()-1)
    if target:
        ix=self.nw_ay.findData(target)
        if ix>=0:self.nw_ay.setCurrentIndex(ix)
    if net and typ in (2,3):
        self.load_selected_networth()
        missing.append('Business capital is not automatically personal net worth; reconcile assets and liabilities')
    message='Imported figures are NOT certified or portal-verified. Compare each value with the actual schedules and books.'
    if missing:message+='\n\nMissing (do not assume zero): '+', '.join(missing)
    if typ in (2,3) and not net:message+='\nNet worth not available from the supplied ITRs. Enter supported assets/liabilities manually.'
    QMessageBox.information(self,'Review required',message)
 def load_selected_networth(self, index=None):
    if hasattr(self,'v44_method') and self.v44_method.currentIndex()==1:return
    if not getattr(self,'client_id',None):return
    ay=self.nw_ay.currentData() if hasattr(self,'nw_ay') else None
    if not ay:return
    rec=CON.execute("SELECT networth,networth_basis FROM itr_financials WHERE client_id=? AND ay=? AND networth IS NOT NULL AND networth!='' ORDER BY ack DESC LIMIT 1",(self.client_id,ay)).fetchone()
    self.cert_net.clear();self.cert_capital.clear()
    self.cert_reserve.setText('0');self.cert_losses.setText('0')
    self.cert_date.setText('31-03-'+str(int(ay[:4])))
    if rec:
        self.cert_capital.setText(rec[0])
        reserve_match=re.search(r'reserves=(-?[0-9.]+)',rec[1] or '')
        reserves=reserve_match.group(1) if reserve_match else '0'
        self.cert_reserve.setText(reserves)
        self.cert_net.setText(str(Decimal(rec[0])+Decimal(reserves)))
        self.cert_basis.setText('Provisional business proprietor fund from '+(rec[1] or 'ITR')+'; NOT automatically personal net worth. Review and adjust all assets and liabilities before issue.')

 def selected_signer(self):
    sid=self.signer_select.currentData() if hasattr(self,'signer_select') else None
    if sid is None:return None
    row=CON.execute('SELECT firm,signer,designation,mrn,frn,address,phone,email,place FROM ca_signers WHERE id=?',(sid,)).fetchone()
    return dict(zip(['firm','signer','designation','mrn','frn','address','phone','email','place'],row)) if row else None
 def generate_itr_final_certificate(self):
    """ICAI October 2025 Handbook, Annexure III(vi), pp.64-66: acknowledgement-only report."""
    try:
        name=self.cf['Name'].text().strip()
        pan=self.cf['PAN'].text().strip()
        recipient=self.recipient.text().strip()
        addr=self.recipient_address.text().strip()
        engagement=self.engagement_date.text().strip()
        engager=self.itr_engager.text().strip()
        submission=self.itr_submission.text().strip()
        signer=self.selected_signer()
        if not signer:
            return QMessageBox.warning(self,'Signer','Select a CA signer profile.')
        if not all((name,pan,recipient,addr,engagement,engager,submission)):
            return QMessageBox.warning(self,'Missing particulars','Enter client name/PAN, addressee and address, engagement date, engaging authority and submission authority.')
        # Preserve entered verification data. Do NOT repopulate here, which could reset unsaved inputs.
        checks={cell(self.itr_downloads,i,0):[cell(self.itr_downloads,i,j) for j in range(1,5)] for i in range(self.itr_downloads.rowCount())}
        records=[]
        for i in range(self.fin_table.rowCount()):
            ay=cell(self.fin_table,i,0)
            if not ay:continue
            form=cell(self.fin_table,i,2);ack=cell(self.fin_table,i,3);filing=cell(self.fin_table,i,4)
            vals=checks.get(ay,['','YES','YES',''])
            if not ack or not filing or not vals[0] or vals[1].upper()!='YES' or vals[2].upper()!='YES':
                return QMessageBox.warning(self,'ITR verification incomplete',f'AY {ay}: acknowledgement, filing date, download date and both verification confirmations are mandatory.')
            income=vals[3].strip() if len(vals)>3 else ''
            if not income and self.client_id:
                r=CON.execute('SELECT income FROM itr WHERE client_id=? AND ay=? AND ack=? ORDER BY id DESC LIMIT 1',(self.client_id,ay,ack)).fetchone()
                income=str(r[0]) if r and r[0] is not None else ''
            if not income:
                return QMessageBox.warning(self,'Missing income',f'AY {ay}: Total Income was not extracted. Check the ITR acknowledgement and enter the amount manually.')
            records.append((ay,form,ack,filing,income,vals[0]))
        if not records:
            return QMessageBox.warning(self,'No assessment years','Load the ITR details into Certificates and complete the ITR Verification Inputs tab.')
        d=Document()
        configure_document(d,self.doc_preset.currentIndex(),self.doc_font.currentText(),self.doc_size.value())
        normal=d.styles['Normal']
        normal.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
        normal.paragraph_format.space_after=Pt(5)
        normal.paragraph_format.line_spacing=1.08
        sec=d.sections[0];sec.top_margin=Inches(.58);sec.bottom_margin=Inches(.55)
        def para(txt='',bold=False,center=False,after=5):
            q=d.add_paragraph();q.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
            q.paragraph_format.space_after=Pt(after)
            r=q.add_run(txt);r.bold=bold
            return q
        date_text=(self.v31_date.text().strip() if hasattr(self,'v31_date') else date.today().strftime('%d %B %Y'))
        pdate=para('Date: '+date_text,after=6);pdate.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        para(self.cert_heading.currentText().strip() or 'INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT VERIFICATION CERTIFICATE',True,True,9)
        # Separate addressee lines prevent Word justification from inserting huge gaps.
        para('To,',after=0)
        para(recipient,after=0)
        for line in addr.splitlines():
            if line.strip():para(line.strip(),after=0)
        para('',after=2)
        years=', '.join(r[0] for r in records)
        para('This certificate is issued in accordance with our engagement letter dated '+engagement+'. We have been engaged by '+engager+' to report on the Indian Income Tax Return Acknowledgement(s) of '+name+' (PAN: '+pan+') for Assessment Year(s) '+years+', for submission to '+submission+'. The enclosed acknowledgements are identified for reference.')
        para('Assessee’s Responsibility',True,after=2)
        para('The assessee is responsible for preparation and filing of the income-tax returns, the accuracy and completeness of information disclosed therein, maintaining relevant supporting records and compliance with the applicable provisions of the Income-tax Act, 1961 and rules thereunder.')
        para('Our Responsibility',True,after=2)
        para('Our responsibility is to examine the downloading of the acknowledgements from the Income Tax Department e-filing portal. We conducted our examination in accordance with the Guidance Note on Reports or Certificates for Special Purposes (Revised 2016) issued by ICAI and complied with applicable ethical, independence and quality-control requirements.')
        para('Opinion',True,after=2)
        para('Based on our examination of the downloading and the information and explanations provided to us, we report that the following Indian Income Tax Return Acknowledgement(s) were downloaded by the assessee, in our presence, from the assessee’s login on the Income Tax Department e-filing portal (https://www.incometax.gov.in/iec/foportal/):')
        financial_table_v6(d,['Assessment Year','ITR Form','Acknowledgement No.','Filing Date','Total Income as per ITR (₹)','Download Date'],records,self.doc_table_style.currentIndex())
        para('The total income figures above are reproduced from the respective ITR acknowledgements for identification and have not been independently audited or certified under this engagement.')
        if self.itr_note.toPlainText().strip():para('Observations: '+self.itr_note.toPlainText().strip())
        para('Restriction on Use',True,after=2)
        para('This certificate is issued at the request of '+engager+' for submission to '+submission+' for '+self.purpose.text().strip()+'. It is intended solely for the specified addressee and purpose and should not be used by any other person or for any other purpose without our prior written consent.')
        para('For '+signer['firm'],True,after=0)
        para('Chartered Accountants',after=0)
        para('FRN: '+signer['frn'],after=8)
        para('________________________',after=1)
        para('CA '+signer['signer'],True,after=0)
        para(signer['designation'] or 'Proprietor / Partner',after=0)
        para('Membership No.: '+signer['mrn'],after=0)
        para('UDIN: '+(self.cert_ud.text().strip() or '________________________'),after=0)
        para('Place: '+signer['place'],after=0)
        para('Date: '+date_text,after=4)
        para('Enclosure: Indian Income Tax Return Acknowledgement(s) for AY '+years+', initialled for identification purposes only.',after=0)
        # No draft labels, no software-generated disclaimers or footers in the issued document.
        footer=d.sections[0].footer.paragraphs[0];footer.text=''
        save_doc(d,self,'ITR_Acknowledgement_Certificate.docx')
    except Exception as e:self.error(e)
 def generate_certificate(self):
    if self._cert_kind()==0:
        return self.generate_itr_final_certificate()
    try:
        name=self.cf['Name'].text().strip();recipient=self.recipient.text().strip();purpose=self.purpose.text().strip()
        if not name or not recipient or not purpose:return QMessageBox.warning(self,'Missing details','Select a client and enter recipient and purpose.')
        if not self.recipient_address.text().strip() or not self.engagement_date.text().strip() or not self.criteria.currentText().strip() or not self.procedures.currentText().strip():
            return QMessageBox.warning(self,'Required ICAI reporting particulars','Complete recipient address, engagement date, applicable criteria and procedures actually performed.')
        if self.criteria.currentIndex()==0 and self.criteria.currentText().startswith('Select') or self.procedures.currentIndex()==0 and self.procedures.currentText().startswith('Select'):
            return QMessageBox.warning(self,'Basis and procedures','Choose or type the actual basis and procedures completed.')
        if self.assurance.currentIndex()==0 or self.check_evidence.currentIndex()==0:
            return QMessageBox.warning(self,'Professional review required','Select assurance level and confirm evidence/engagement review before generating a draft.')
        if self.conclusion.currentIndex()>0 and not self.conclusion_basis.toPlainText().strip():
            return QMessageBox.warning(self,'Basis required','Explain the reason for the modified conclusion.')
        signer=self.selected_signer()
        if not signer:return QMessageBox.warning(self,'Signing CA','Select a saved CA profile in the Signer Profiles tab.')
        kind=self._cert_kind();rows=[]
        for i in range(self.fin_table.rowCount()):
            ay,amount=cell(self.fin_table,i,0),cell(self.fin_table,i,1)
            if ay and kind!=3:
                if not amount:return QMessageBox.warning(self,'Missing amount',f'Enter supported figure for AY {ay}.')
                rows.append((ay,money(amount)))
        if not rows and kind!=3:return QMessageBox.warning(self,'Missing figures','Enter at least one assessment year.')
        if kind!=3 and hasattr(self,'turnover_source') and self.turnover_source.currentIndex() in (1,2):
            source_kind='GSTR-1' if self.turnover_source.currentIndex()==1 else 'GSTR-3B'
            for ay,_ in rows:
                try:fy=f'{int(ay[:4])-1}-{int(ay[:4])%100:02d}'
                except (ValueError,IndexError):return QMessageBox.warning(self,'Assessment year','Invalid assessment year in turnover table.')
                count=CON.execute('SELECT COUNT(*) FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=?',(self.client_id,source_kind,fy)).fetchone()[0]
                if count<12:
                    return QMessageBox.warning(self,'Incomplete GST financial year',f'AY {ay} corresponds to FY {fy}, but only {count}/12 {source_kind} monthly returns are imported. Import all months before issuing a full-year turnover certificate, or switch to another verified source.')
        if kind==0:
            self.populate_itr_downloads()
            checks={cell(self.itr_downloads,i,0):[cell(self.itr_downloads,i,j).strip() for j in range(1,4)] for i in range(self.itr_downloads.rowCount())}
            if not self.itr_engager.text().strip() or not self.itr_submission.text().strip():return QMessageBox.warning(self,'ITR inputs','Complete engaging party and submission authority in ITR Verification Inputs tab.')
            for ay,_ in rows:
                values=checks.get(ay,['','YES','YES'])
                if not values[0] or values[1].upper()!='YES' or values[2].upper()!='YES':
                    return QMessageBox.warning(self,'Verification evidence required',f'AY {ay}: record download date and confirm both portal download in CA presence and acknowledgement cross-check. The ICAI illustrative opinion cannot be used without this evidence.')
        if kind in (2,3) and (not self.cert_net.text().strip() or not self.cert_date.text().strip() or not self.cert_capital.text().strip()):return QMessageBox.warning(self,'Net worth','Enter capital, net worth and as-on date.')
        if kind in (2,3) and dec(self.cert_capital.text())+dec(self.cert_reserve.text())-dec(self.cert_losses.text())!=dec(self.cert_net.text()):return QMessageBox.warning(self,'Net worth mismatch','Capital + reserves - accumulated losses must equal total net worth. Reconcile figures before generation.')
        if kind in (2,3):
            confirm=QMessageBox.question(self,'Confirm net worth','Confirm that capital, reserves, accumulated losses and other relevant adjustments have been reviewed. The extracted capital is not automatically total net worth. Continue?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if confirm!=QMessageBox.StandardButton.Yes:return
        d=Document()
        title=self.cert_heading.currentText().strip() or ['ITR VERIFICATION CERTIFICATE','TURNOVER CERTIFICATE','TURNOVER AND NET WORTH CERTIFICATE','NET WORTH CERTIFICATE'][kind]
        configure_document(d,self.doc_preset.currentIndex(),self.doc_font.currentText(),self.doc_size.value())
        # Certificate is printed on the CA's physical letterpad: no digital header/logo/footer.
        d.sections[0].header.paragraphs[0].text=''
        d.sections[0].footer.paragraphs[0].text=''
        d.sections[0].top_margin=Inches(1.55)
        p=d.add_paragraph('Date: '+(self.v31_date.text().strip() if hasattr(self,'v31_date') else date.today().strftime('%d %B %Y')));p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;r=p.add_run(title);r.bold=True;r.font.size=Pt(self.doc_size.value()+3)
        d.add_paragraph('To,\n'+recipient+'\n'+self.recipient_address.text().strip())
        pan=self.cf['PAN'].text().strip();address=self.cf['Address'].text().strip();trade=self.cf['Business / Trade Name'].text().strip()
        entity=self.entity_type.currentText()
        # Client identity is taken from the editable client master, never inferred from an ITR name.
        # An individual PAN must not be described as the PAN of a company/LLP/firm.
        role_by_entity={
            'Proprietorship Firm':'Proprietor',
            'Partnership Firm':'Partner',
            'LLP':'Designated Partner',
            'Private Limited Company':'Director',
            'Public Limited Company':'Director',
            'HUF':'Karta',
            'Trust':'Trustee',
            'Society':'Authorised Representative',
            'AOP / BOI':'Member',
        }
        role=role_by_entity.get(entity,'')
        # Honor a manually selected role in the client master for partnership/LLP/company.
        selected_role=self.client_mrl_position.currentText().strip()
        if entity in ('Partnership Firm','LLP','Private Limited Company','Public Limited Company') and selected_role in ('Partner','Designated Partner','Director','Managing Director'):
            role=selected_role
        # The certificate is issued at the request of the responsible persons,
        # not at the request of a firm described as its own partner.
        requester_by_entity={
            'Proprietorship Firm':'the proprietor of',
            'Partnership Firm':'the partners of',
            'LLP':'the designated partners of',
            'Private Limited Company':'the directors of',
            'Public Limited Company':'the directors of',
            'HUF':'the Karta of',
            'Trust':'the trustees of',
            'Society':'the authorised representatives of',
            'AOP / BOI':'the members of',
        }
        # Keep the trade name only once if client name and trade name match.
        subject_name=(trade or name).strip()
        requester=requester_by_entity.get(entity,'')
        if entity=='Proprietorship Firm':
            # ITR is filed in the individual proprietor's name, while the
            # business may operate under a different trade name. Show BOTH.
            # The editable client master is the authoritative identity source.
            proprietor_name=(name or ' '.join(w.text().strip() for w in self.name_parts.values() if w.text().strip())).strip()
            if not proprietor_name:
                return QMessageBox.warning(self,'Proprietor name missing','Enter the proprietor’s full name in Clients before generating the certificate.')
            if trade and trade.casefold()!=proprietor_name.casefold():
                identity='the proprietor, '+proprietor_name+', of M/s. '+trade
            else:
                identity='the proprietor, '+proprietor_name
        else:
            identity=(requester+' '+subject_name).strip() if requester else name
        # For a company, the PAN and address refer to the entity, not its directors.
        pan_clause=', having PAN: '+pan if pan else ''
        address_clause=(', carrying on business at ' if entity in ('Proprietorship Firm','Partnership Firm','Individual','AOP / BOI') else ', having registered address at ')+address if address else ''

        if kind==0:
            intro=('We have examined the particulars of the income-tax returns furnished to us in respect of '+name+', PAN: '+pan+', Address: '+address+'. The particulars of the acknowledgements for the assessment years stated below are presented for identification of the documents examined.')
        else:
            intro=('At the request of '+identity+pan_clause+address_clause+', we certify the following particulars of '+('turnover and net worth' if kind==2 else 'net worth' if kind==3 else 'turnover')+(' as at '+self.cert_date.text().strip() if kind==3 else ' for the assessment years stated below')+', based on the records and explanations examined for this specific engagement.')
        d.add_paragraph(intro)
        if kind==0:
            data=[]
            for i in range(self.fin_table.rowCount()):
                if cell(self.fin_table,i,0):data.append([cell(self.fin_table,i,j) for j in range(5)])
            financial_table_v6(d,['Assessment Year','Date of Filing','ITR Form','Total Income (₹)','E-filing Ack. No.'],[[r[0],r[4],r[2],money(r[1]),r[3]] for r in data],self.doc_table_style.currentIndex())
        elif kind!=3:
            financial_table_v6(d,['Assessment Year','Turnover (₹)'],[(ay,money(amount)) for ay,amount in rows],self.doc_table_style.currentIndex())
        if kind in (2,3):
            d.add_paragraph('NET WORTH PARTICULARS')
            asof=self.cert_date.text().strip()
            if hasattr(self,'v44_method') and self.v44_method.currentIndex()==1:
                if not getattr(self,'v43_result',None):
                    return QMessageBox.warning(self,'Balance sheet missing','Import and reconcile the ITR-3/4/5 balance sheet before using Assets minus Liabilities method.')
                totals=self.v43_recalculate()
                if totals is None:return
                a,l,n,equity=totals
                if equity!=dec(self.cert_net.text()):
                    return QMessageBox.warning(self,'Net worth changed','Reapply the assets-liabilities calculation to the certificate before generating.')
                schedule=[(cell(self.v43_table,i,1),('+' if cell(self.v43_table,i,0).lower()=='asset' else '−')+' ₹'+money(cell(self.v43_table,i,2))) for i in range(self.v43_table.rowCount())]
                schedule += [('TOTAL ASSETS',money(a)),('LESS: TOTAL LIABILITIES',money(l)),('ASSETS LESS LIABILITIES',money(n)),('Less: Miscellaneous debit balances / accumulated losses',money(dec(self.v43_misc.text()))),(f'ADJUSTED BUSINESS NET WORTH AS ON {asof}',money(equity))]
                financial_table_v6(d,['Particulars','Amount (₹)'],schedule,self.doc_table_style.currentIndex())
                d.add_paragraph('Method: Business assets less outside liabilities, with disclosed miscellaneous debit balances adjusted where applicable. Source: '+(self.v43_result.get('basis','reviewed ITR balance sheet') if getattr(self,'v43_result',None) else 'reviewed financial particulars')+'. This does not automatically represent personal net worth.')
            else:
                capital_by_entity={
                    'Proprietorship Firm':'Proprietor’s capital',
                    'Partnership Firm':'Partners’ capital',
                    'LLP':'Partners’ capital',
                    'Private Limited Company':'Shareholders’ funds',
                    'Public Limited Company':'Shareholders’ funds',
                    'HUF':'HUF capital',
                    'Trust':'Trust fund',
                    'Society':'Members’ fund',
                    'AOP / BOI':'Members’ capital',
                }
                capital_label=capital_by_entity.get(entity,'Capital / owners’ funds')
                financial_table_v6(d,['Particulars','Amount (₹)'],[(f'{capital_label} as on {asof}',money(self.cert_capital.text())),('Add: Reserves and Surplus',money(self.cert_reserve.text())),('Less: Accumulated Losses',money(self.cert_losses.text())),(f'Total Business Net Worth as on {asof}',money(self.cert_net.text()))],self.doc_table_style.currentIndex())
                d.add_paragraph('Method: '+capital_label.lower()+' plus separately identified reserves and surplus less accumulated losses, based on the reviewed financial records / applicable ITR. Reserves already included in the entered capital or fund figure must not be added again. This does not automatically represent personal net worth.')
        d.add_heading('Engagement and Applicable Criteria',level=2)
        d.add_paragraph('This report has been prepared pursuant to the engagement letter dated '+self.engagement_date.text().strip()+'. The subject matter has been evaluated against the following criteria: '+self.criteria.currentText().strip()+'.')
        if kind==0:
            d.add_paragraph('This certificate is issued in accordance with the engagement letter dated '+self.engagement_date.text().strip()+'. We were engaged by '+self.itr_engager.text().strip()+' in relation to the income-tax return acknowledgements of '+name+' for submission to '+self.itr_submission.text().strip()+'. The acknowledgements are enclosed and identified for reference.')
        entity_role={'Individual':'Assessee','Proprietorship Firm':'Proprietor','Partnership Firm':'Partners','LLP':'Designated Partners','Private Limited Company':'Directors','Public Limited Company':'Directors','HUF':'Karta','Trust':'Trustees','Society':'Office Bearers','AOP / BOI':'Members'}.get(entity,'Responsible Person(s)')
        d.add_heading(('Assessee’s Responsibility' if kind==0 else entity_role+'’ Responsibility'),level=2)
        d.add_paragraph('The '+('assessee' if kind==0 else entity_role.lower())+' is responsible for preparing the accompanying statement and maintaining complete and accurate records, supporting documents, relevant controls and reasonable estimates, and for providing all relevant information and explanations.')
        if kind==0:
            d.add_paragraph('The assessee is responsible for preparing and filing the income-tax returns, maintaining supporting records and complying with the applicable provisions of the Income-tax Act, 1961 and rules thereunder.')
        d.add_heading('Our Responsibility and Work Performed',level=2)
        d.add_paragraph('Our responsibility is to express a '+('limited' if self.assurance.currentIndex()==1 else 'reasonable')+' assurance conclusion on the specified subject matter based on the procedures performed and evidence obtained. The engagement has been undertaken with reference to the Guidance Note on Reports or Certificates for Special Purposes (Revised 2016) issued by ICAI, subject to the engagement-specific applicability assessment.')
        d.add_paragraph('Procedures performed: '+self.procedures.currentText().strip())
        d.add_paragraph('We have complied with the applicable independence, ethical and quality-control requirements relevant to this engagement.')
        d.add_heading('Inherent Limitations',level=2)
        d.add_paragraph('The work is limited to the stated scope and evidence available for the relevant period. In particular, unaudited or self-reported information may contain inaccuracies not identified by the procedures performed. A filed income-tax return does not by itself establish independent verification of every reported financial figure.')
        d.add_heading('Opinion' if kind==0 else 'Conclusion',level=2)
        level=self.assurance.currentIndex();ctype=self.conclusion.currentIndex()
        if ctype==3:
            wording='Due to the significant limitations described below, sufficient appropriate evidence has not been obtained to express an assurance conclusion on the accompanying statement.'
        elif ctype==2:
            wording='In our opinion, because of the matters described below, the accompanying statement is not prepared, in all material respects, in accordance with the stated criteria.'
        elif level==1:
            wording=('Except for the effects or possible effects of the matters described below, ' if ctype==1 else '')+'Based on the procedures performed and evidence obtained, nothing has come to our attention that causes us to believe that the accompanying statement is not prepared, in all material respects, in accordance with the stated criteria.'
        else:
            wording=('Except for the effects or possible effects of the matters described below, ' if ctype==1 else '')+'In our opinion, the accompanying statement is prepared, in all material respects, in accordance with the stated criteria.'
        if kind==0:
            evidence={cell(self.itr_downloads,i,0):cell(self.itr_downloads,i,1) for i in range(self.itr_downloads.rowCount())}
            d.add_paragraph('Based on our examination of the downloading of the acknowledgements, and the information and explanations provided, we report that the enclosed Indian Income Tax Return Acknowledgement(s) were downloaded by the assessee, in our presence, from the assessee’s login at https://www.incometax.gov.in/iec/foportal/. The particulars are:')
            financial_table_v6(d,['Assessment Year','PAN','Acknowledgement No.','Filing date','Download date'],[[cell(self.fin_table,i,0),pan,cell(self.fin_table,i,3),cell(self.fin_table,i,4),evidence.get(cell(self.fin_table,i,0),'')] for i in range(self.fin_table.rowCount()) if cell(self.fin_table,i,0)],self.doc_table_style.currentIndex())
            if self.itr_unverified.currentIndex()==1:d.add_paragraph('IMPORTANT: The relevant income-tax return has not been verified / signed and submitted with the Income Tax Authority by the assessee as at the date of this certificate, as represented and reviewed for this engagement.')
            if self.itr_note.toPlainText().strip():d.add_paragraph('Additional observations: '+self.itr_note.toPlainText().strip())
            d.add_paragraph('Enclosure: Indian Income Tax Return Acknowledgement(s) for the above assessment year(s), initialled for identification purposes only and to be read with this certificate.')
        else:d.add_paragraph(wording)
        if self.conclusion_basis.toPlainText().strip():d.add_paragraph('Basis / observations: '+self.conclusion_basis.toPlainText().strip())
        d.add_heading('Restriction on Use',level=2)
        d.add_paragraph('This certificate has been issued at the specific request of the applicant, addressed to '+recipient+', for '+purpose+' only.')
        d.add_paragraph('It is intended solely for the specified recipient and purpose, and should not be relied upon by others without our prior written consent.')
        # Never justify a signature block; separate compact left-aligned paragraphs.
        for line_text,bold in [('For '+signer['firm'],True),('Chartered Accountants',False),('________________________',False),('CA '+signer['signer'],True),(signer['designation'] or 'Authorised Signatory',False),('MRN: '+signer['mrn']+'  |  FRN: '+signer['frn'],False),('UDIN: '+(self.cert_ud.text().strip() or '________________'),False),('Place: '+signer['place'],False)]:
            sp=d.add_paragraph();sp.alignment=WD_ALIGN_PARAGRAPH.LEFT
            sp.paragraph_format.space_before=Pt(0);sp.paragraph_format.space_after=Pt(1)
            sp.paragraph_format.keep_together=True
            sp.paragraph_format.keep_with_next=(line_text!='Place: '+signer['place'])
            rr=sp.add_run(line_text);rr.bold=bold
        finish_document_v6(d,self.doc_preset.currentIndex())
        d.sections[0].header.paragraphs[0].text=''
        d.sections[0].footer.paragraphs[0].text=''
        self.normalize_certificate_paragraphs(d)
        save_doc(d,self,re.sub(r'[^A-Za-z0-9_]+','_',title.title())+'.docx')
    except Exception as e:self.error(e)
 def make_representation(self):
    v=self.tab('Management Representation');self.representation_tab_index=self.tabs.count()-1
    v.addWidget(QLabel('Management Representation Letter — for the selected certificate; review before obtaining signature.'))
    v.addWidget(QLabel('Management signatory is automatically taken from Clients → MRL signatory name.'))
    v.addWidget(QLabel('Position is taken from Clients → MRL signatory position (Proprietor / Partner / Director / Karta etc.).'))
    self.rep_date=field('Date of representation (DD-MM-YYYY)',date.today().strftime('%d-%m-%Y'));v.addWidget(QLabel('Date'));v.addWidget(self.rep_date)
    self.rep_notes=QTextEdit();self.rep_notes.setMinimumHeight(100);self.rep_notes.setPlaceholderText('Additional specific representations / assumptions (optional)');v.addWidget(self.rep_notes)
    self.btn(v,'Generate Management Representation Letter (.docx)',self.generate_representation)
 def generate_representation(self):
    try:
        name=self.cf['Name'].text().strip();recipient=self.recipient.text().strip();purpose=self.purpose.text().strip();kind=self._cert_kind()
        signer=self.selected_signer()
        if not signer:return QMessageBox.warning(self,'Signer','Select a saved CA signer first.')
        if not name or not recipient or not purpose:return QMessageBox.warning(self,'Missing details','Select client, recipient and purpose in Certificate Workspace.')
        rows=[(cell(self.fin_table,i,0),cell(self.fin_table,i,1)) for i in range(self.fin_table.rowCount()) if cell(self.fin_table,i,0)]
        if kind!=3 and (not rows or any(not amount for ay,amount in rows)):return QMessageBox.warning(self,'Figures','Enter figures for each assessment year.')
        if not self.client_mrl_signer.text().strip():return QMessageBox.warning(self,'Client master','Enter the MRL signatory name in Clients and save the client.')
        typ=self.cert_type.currentText();d=Document()
        configure_document(d,self.doc_preset.currentIndex(),self.doc_font.currentText(),self.doc_size.value())
        sec=d.sections[0];sec.header.paragraphs[0].text='';sec.footer.paragraphs[0].text=''
        sec.top_margin=Inches(.75)
        normal=d.styles['Normal'];normal.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
        normal.paragraph_format.space_before=Pt(0);normal.paragraph_format.space_after=Pt(4)
        normal.paragraph_format.line_spacing=1.08
        def para(txt='',bold=False,center=False,after=4):
            q=d.add_paragraph();q.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
            q.paragraph_format.space_before=Pt(0);q.paragraph_format.space_after=Pt(after)
            r=q.add_run(txt);r.bold=bold
            return q
        para('MANAGEMENT REPRESENTATION LETTER',bold=True,center=True,after=7)
        para('Date: '+self.rep_date.text().strip(),after=5)
        para('To,',after=0);para(signer['firm'],after=0);para('Chartered Accountants',after=6)
        para('Subject: Representation for '+typ+' addressed to '+recipient+' for '+purpose,after=6)
        # Client identifiers are taken from the manually maintained client master.
        # Never derive a missing GSTIN from PAN or invent an identifier.
        client_pan=self.cf['PAN'].text().strip().upper()
        client_gstin=self.cf['GSTIN'].text().strip().upper()
        identifiers=[]
        if client_pan: identifiers.append('PAN: '+client_pan)
        if client_gstin: identifiers.append('GSTIN: '+client_gstin)
        identity_clause=(', having '+ ' and '.join(identifiers)) if identifiers else ''
        business_name=self.cf['Business / Trade Name'].text().strip()
        represented_name=business_name or name
        para('We, the undersigned, acting as '+self.client_mrl_position.currentText().strip()+' on behalf of '+represented_name+' ('+self.entity_type.currentText()+')'+identity_clause+', provide the following representations for the proposed '+typ.lower()+'.',after=5)
        base=['We have provided all records, particulars and explanations relevant to the certificate and have not withheld material information affecting the reported figures.', 'We accept responsibility for the completeness and accuracy of the information supplied to the certifying Chartered Accountant.', 'The certificate is requested for '+purpose+' and is intended for '+recipient+'.']
        if kind==0:
            specific=['The income and assessment-year particulars below correspond to the income-tax returns and acknowledgements supplied by us.', 'We have disclosed any revised or updated returns and material changes affecting these particulars.']
        elif kind==1:
            specific=['The turnover figures below relate to the stated assessment years and the records supplied for certification.', 'We have disclosed applicable sales returns, cancellations, amendments and other adjustments affecting turnover.', 'No turnover belonging to another entity or period has knowingly been included.']
        else:
            specific=([ 'We have disclosed all material assets and liabilities relevant to the net worth statement.', 'We understand that business capital does not necessarily represent total personal net worth.' ] if kind==3 else ['The turnover figures below relate to the stated assessment years and the records supplied for certification.', 'We have disclosed adjustments relevant to turnover, including sales returns and cancellations.', 'We have disclosed all material assets, liabilities, reserves and accumulated losses relevant to the net worth particulars.', 'We understand that business capital extracted from an income-tax return does not necessarily represent total personal net worth.'])
        for n,statement in enumerate(base+specific,1):para(str(n)+'. '+statement,after=3)
        if kind!=3:para('FINANCIAL PARTICULARS',bold=True,after=3)
        if kind==0:
            financial_table_v6(d,['Assessment Year','Date of Filing','ITR Form','Total Income (₹)','E-filing Ack. No.'],[[cell(self.fin_table,i,0),cell(self.fin_table,i,4),cell(self.fin_table,i,2),money(cell(self.fin_table,i,1)),cell(self.fin_table,i,3)] for i in range(self.fin_table.rowCount()) if cell(self.fin_table,i,0)],self.doc_table_style.currentIndex())
        elif kind!=3:
            financial_table_v6(d,['Assessment Year','Turnover (₹)'],[(ay,money(amount)) for ay,amount in rows],self.doc_table_style.currentIndex())
        if kind in (2,3):
            if not self.cert_net.text().strip():return QMessageBox.warning(self,'Net worth','Enter net worth in Certificate Workspace.')
            para('NET WORTH PARTICULARS',bold=True,after=3)
            asof=self.cert_date.text().strip()
            financial_table_v6(d,['Particulars','Amount (₹)'],[(f'Capital as on {asof}',money(self.cert_capital.text())),('Add: Reserves and Surplus',money(self.cert_reserve.text())),('Less: Accumulated Losses',money(self.cert_losses.text())),(f'Total Net Worth as on {asof}',money(self.cert_net.text()))],self.doc_table_style.currentIndex())
        extra=self.rep_notes.toPlainText().strip()
        if extra:para('Additional representations: '+extra,after=5)
        para('For '+(self.cf['Business / Trade Name'].text().strip() or name),bold=True,after=8)
        para('Signature: ____________________',after=2)
        para('Name: '+self.client_mrl_signer.text().strip(),after=2)
        para('Designation: '+self.client_mrl_position.currentText().strip(),after=2)
        para('Place: ____________________',after=0)
        # Keep the MRL free of the automatic software footer and excessive blank lines.
        sec.header.paragraphs[0].text='';sec.footer.paragraphs[0].text=''
        for t in d.tables:
            t.autofit=True
            for row in t.rows:
                for c in row.cells:
                    for q in c.paragraphs:
                        q.alignment=WD_ALIGN_PARAGRAPH.LEFT
                        q.paragraph_format.space_before=Pt(0);q.paragraph_format.space_after=Pt(0)
                        q.paragraph_format.line_spacing=1.0
        save_doc(d,self,'MRL_'+typ.replace(' ','_').replace('/','_')+'.docx')
    except Exception as e:self.error(e)
 def make_networth(self):
    v=self.tab('Net Worth');v.addWidget(QLabel('Enter assets and liabilities. Net worth = total assets − total liabilities.'))
    self.nw=table(['Category (Asset / Liability)','Particulars','Amount (₹)']);self.nw.setMinimumHeight(240);v.addWidget(self.nw)
    for x in [('Asset','Cash and bank','0'),('Asset','Investments','0'),('Asset','Fixed assets / Property','0'),('Asset','Other assets','0'),('Liability','Loans','0'),('Liability','Other liabilities','0')]:addrow(self.nw,x)
    r=QHBoxLayout();self.btn(r,'Add item',lambda:addrow(self.nw,['Asset','','0']));self.btn(r,'Calculate',self.calc_nw);self.btn(r,'Export Excel',self.export_nw);self.btn(r,'Generate Net Worth Certificate',self.generate_nw);v.addLayout(r)
    self.nw_result=QLabel('Net Worth: ₹0.00');v.addWidget(self.nw_result)
    v.addWidget(QLabel('Asset values and liabilities require independent verification. This is not an automatic valuation or audit.'))
 def calc_nw(self):
    assets=Decimal(0);liab=Decimal(0)
    for i in range(self.nw.rowCount()):
        cat=cell(self.nw,i,0).lower();value=dec(cell(self.nw,i,2))
        if cat=='asset':assets+=value
        elif cat=='liability':liab+=value
        else:raise ValueError(f'Row {i+1}: category must be Asset or Liability')
    net=assets-liab;self.nw_result.setText(f'Assets ₹{money(assets)}  |  Liabilities ₹{money(liab)}  |  NET WORTH ₹{money(net)}');return assets,liab,net
 def export_nw(self):
    try:
        a,l,n=self.calc_nw();wb=Workbook();ws=wb.active;ws.title='Net Worth';ws.append(['Category','Particulars','Amount (INR)'])
        for i in range(self.nw.rowCount()):ws.append([cell(self.nw,i,j) for j in range(3)])
        ws.append(['','Total Assets',float(a)]);ws.append(['','Total Liabilities',float(l)]);ws.append(['','Net Worth',float(n)]);self.export_wb(wb,'Net_Worth.xlsx')
    except Exception as e:self.error(e)
 def generate_nw(self):
    QMessageBox.information(self,'ICAI-compliant net worth report','Please prepare the supporting asset/liability statement here, then generate the assurance report through the Certificates tab after completing engagement particulars, assurance selection and evidence review. A standalone net-worth statement must not be mistaken for a signed assurance certificate.')
    try:
        a,l,n=self.calc_nw()
        d=Document();d.add_heading('Management Statement of Assets and Liabilities — NOT A CA CERTIFICATE',0)
        d.add_paragraph('Client: '+self.cf['Name'].text()+' | PAN: '+self.cf['PAN'].text())
        d.add_paragraph('Total assets: INR '+money(a)+'; Total liabilities: INR '+money(l)+'; Net assets: INR '+money(n))
        financial_table_v6(d,['Category','Particulars','Amount (INR)'],[[cell(self.nw,i,j) for j in range(3)] for i in range(self.nw.rowCount())],0)
        d.add_paragraph('This is an unverified working statement. It does not constitute a certificate or assurance conclusion by a Chartered Accountant.')
        save_doc(d,self,'Net_Worth_Working_Statement.docx')
    except Exception as e:self.error(e)
 def make_deed(self):
    v=self.tab('Partnership Deed');v.addWidget(QLabel('Generate a draft deed. Legal clauses, stamp duty and registration require professional review.'))
    self.deed_fields={k:field(k) for k in ['Firm Name','Firm Address','Nature of Business','Commencement Date (DD-MM-YYYY)','Partner 1 Name','Partner 1 Address','Partner 1 PAN','Partner 1 Profit Share %','Partner 2 Name','Partner 2 Address','Partner 2 PAN','Partner 2 Profit Share %','Interest on Capital % p.a.','Remuneration Clause']}
    self.deed_fields['Partner 1 Profit Share %'].setText('50');self.deed_fields['Partner 2 Profit Share %'].setText('50');self.deed_fields['Interest on Capital % p.a.'].setText('12');self.deed_fields['Remuneration Clause'].setText('As mutually agreed and subject to applicable Income-tax provisions')
    form=QFormLayout()
    for k,w in self.deed_fields.items():form.addRow(k,w)
    v.addLayout(form);self.btn(v,'Generate Draft Partnership Deed (.docx)',self.generate_deed)
 def generate_deed(self):
    try:
        f={k:w.text().strip() for k,w in self.deed_fields.items()}
        p1=dec(f['Partner 1 Profit Share %']);p2=dec(f['Partner 2 Profit Share %'])
        if p1+p2!=100:return QMessageBox.warning(self,'Profit shares','Profit-sharing percentages must total 100%.')
        if not all(f[k] for k in ['Firm Name','Firm Address','Commencement Date (DD-MM-YYYY)','Partner 1 Name','Partner 2 Name']):return QMessageBox.warning(self,'Missing fields','Enter firm name, address, commencement date and both partner names.')
        d=Document();d.add_heading('DRAFT PARTNERSHIP DEED',0)
        d.add_paragraph(f'This Deed of Partnership is made on {f["Commencement Date (DD-MM-YYYY)"]} between:')
        d.add_paragraph(f'FIRST PARTNER: {f["Partner 1 Name"]}, Address: {f["Partner 1 Address"]}, PAN: {f["Partner 1 PAN"]}.')
        d.add_paragraph(f'SECOND PARTNER: {f["Partner 2 Name"]}, Address: {f["Partner 2 Address"]}, PAN: {f["Partner 2 PAN"]}.')
        clauses=[('Name of Firm',f'The firm shall carry on business as {f["Firm Name"]}.'),('Principal Place of Business',f['Firm Address']),('Commencement and Duration',f'The partnership shall commence on {f["Commencement Date (DD-MM-YYYY)"]} and shall be a partnership at will unless otherwise agreed.'),('Nature of Business',f['Nature of Business']),('Capital Contributions','Partners shall contribute capital as mutually agreed and properly recorded in the books.'),('Interest on Capital',f'Interest on capital, if any, shall be at {f["Interest on Capital % p.a."]}% per annum, subject to applicable law and the terms agreed by the partners.'),('Remuneration',f['Remuneration Clause']),('Profit and Loss Sharing',f'{f["Partner 1 Name"]}: {p1}% and {f["Partner 2 Name"]}: {p2}%.'),('Books and Accounts','Proper books of account shall be maintained. The accounting year shall end on 31 March. Each partner may inspect the books.'),('Bank Accounts','Bank accounts shall be operated as jointly authorised in writing by the partners.'),('Admission / Retirement','Admission and retirement of partners shall be governed by mutual written agreement and applicable law.'),('Disputes','Disputes shall first be resolved amicably; failing that, the parties may pursue remedies under applicable law.'),('Governing Law','The Indian Partnership Act, 1932 and other applicable laws shall govern matters not expressly provided herein.')]
        for i,(heading,body) in enumerate(clauses,1):d.add_heading(f'{i}. {heading}',level=2);d.add_paragraph(body)
        d.add_paragraph('\nSignatures:\n\nFirst Partner: __________________\nSecond Partner: __________________\n\nWitness 1: __________________\nWitness 2: __________________')
        d.add_paragraph('DRAFT ONLY — obtain legal review of remuneration, interest, death, succession, dissolution, arbitration and state stamp requirements before execution.')
        save_doc(d,self,'Partnership_Deed_Draft.docx')
    except Exception as e:self.error(e)
 def make_signers(self):
    v=self.tab('Signer Profiles')
    v.addWidget(QLabel('Maintain multiple CA / firm profiles. Select the signer for each certificate and representation letter.'))
    self.signer_select=QComboBox();v.addWidget(self.signer_select)
    self.signer_fields={k:field(k) for k in ['Firm Name','CA Name','Designation','MRN','FRN','Office Address','Phone','Email','Place']}
    f=QFormLayout()
    for k,w in self.signer_fields.items():f.addRow(k,w)
    v.addLayout(f)
    r=QHBoxLayout();self.btn(r,'New / Clear',self.clear_signer);self.btn(r,'Save CA Profile',self.save_signer);self.btn(r,'Delete Selected Profile',self.delete_signer);v.addLayout(r)
    self.signer_select.currentIndexChanged.connect(self.show_signer)
 def load_signers(self):
    self.signer_select.blockSignals(True);self.signer_select.clear()
    for sid,firm,signer in CON.execute('SELECT id,firm,signer FROM ca_signers ORDER BY firm,signer'):
        self.signer_select.addItem(f'{firm} — CA {signer}',sid)
    self.signer_select.blockSignals(False);self.show_signer()
 def show_signer(self):
    profile=self.selected_signer()
    if not profile:return
    for k,val in zip(self.signer_fields,profile.values()):self.signer_fields[k].setText(val or '')
 def clear_signer(self):
    self.signer_select.setCurrentIndex(-1)
    for w in self.signer_fields.values():w.clear()
 def save_signer(self):
    vals=[w.text().strip() for w in self.signer_fields.values()]
    if not vals[0] or not vals[1] or not vals[3]:return QMessageBox.warning(self,'Required','Enter firm name, CA name and MRN.')
    sid=self.signer_select.currentData()
    if sid is None:CON.execute('INSERT INTO ca_signers(firm,signer,designation,mrn,frn,address,phone,email,place) VALUES (?,?,?,?,?,?,?,?,?)',vals)
    else:CON.execute('UPDATE ca_signers SET firm=?,signer=?,designation=?,mrn=?,frn=?,address=?,phone=?,email=?,place=? WHERE id=?',vals+[sid])
    CON.commit();self.load_signers();QMessageBox.information(self,'Saved','CA signer profile saved locally.')
 def delete_signer(self):
    sid=self.signer_select.currentData()
    if sid is None:return
    if QMessageBox.question(self,'Delete','Delete selected signer profile?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
    CON.execute('DELETE FROM ca_signers WHERE id=?',(sid,));CON.commit();self.load_signers()
 def make_settings(self):
    v=self.tab('Settings');self.settings={'CA Firm Name':field('CA Firm Name','My CA Firm')};f=QFormLayout()
    for k,w in self.settings.items():f.addRow(k,w)
    v.addLayout(f);v.addWidget(QLabel('Data directory: '+str(ROOT)))
    self.btn(v,'Open Data Folder',lambda:__import__('os').startfile(str(ROOT)) if sys.platform=='win32' else QMessageBox.information(self,'Folder',str(ROOT)))
    self.btn(v,'Backup SQLite Database',self.backup)
    v.addWidget(QLabel('Privacy: All information remains local. The app does not contact the Income Tax Portal, ICAI or UDIN service.'))
 def backup(self):
    p,_=QFileDialog.getSaveFileName(self,'Save database backup',str(ROOT/'clients_backup.sqlite3'),'SQLite (*.sqlite3)')
    if p:
        dest=sqlite3.connect(p)
        with dest:CON.backup(dest)
        dest.close();QMessageBox.information(self,'Backup','Backup completed.')


# -------- V28 GST monthly return import / annual turnover working --------
from calendar import month_name
from collections import defaultdict
from openpyxl.utils import get_column_letter

GST_MONTHS = [month_name[m] for m in range(4,13)] + [month_name[m] for m in range(1,4)]
GST_MONTH_INDEX = {month_name[m].lower():m for m in range(1,13)}
GST_NUM = r'[-+]?\(?[\d,]+(?:\.\d+)?\)?'

CON.execute('''CREATE TABLE IF NOT EXISTS gst_monthly (
 client_id INTEGER NOT NULL, return_type TEXT NOT NULL, fy TEXT NOT NULL,
 month INTEGER NOT NULL, gstin TEXT, taxable TEXT NOT NULL, exempt TEXT NOT NULL,
 nongst TEXT NOT NULL, turnover TEXT NOT NULL, source TEXT, details TEXT,
 PRIMARY KEY(client_id,return_type,fy,month))''')
CON.commit()

def gst_amount(raw):
    t=str(raw).strip().replace(',','')
    if t in ('','-','—'):return Decimal('0')
    return Decimal(t.strip('()')) * (-1 if t.startswith('(') else 1)

def gst_first_amount_after(lines, marker, stop=None):
    for i,line in enumerate(lines):
        if marker(line):
            for follow in lines[i+1:i+6]:
                if stop and stop(follow):break
                if re.fullmatch(GST_NUM,follow.strip()):return gst_amount(follow)
    return None

def gst_extract(path, kind):
    doc=fitz.open(path)
    try: pages=[page.get_text(sort=False) for page in doc]
    finally:doc.close()
    text='\n'.join(pages); lines=[x.strip() for x in text.splitlines() if x.strip()]
    expected='GSTR-1' if kind=='GSTR-1' else 'GSTR-3B'
    if not re.search(r'GSTR\s*[-–]?\s*'+('1(?!\d)' if kind=='GSTR-1' else '3B'),text[:450],re.I):
        raise ValueError('This file does not appear to be '+expected)
    fy_match=re.search(r'(?:Financial year|Year)\s*\n\s*(20\d{2})\s*[-–/]\s*(\d{2,4})',text[:1000],re.I)
    period_match=re.search(r'(?:Tax period|Period)\s*\n\s*('+ '|'.join(month_name[1:])+r')\b',text[:1000],re.I)
    if not fy_match or not period_match:raise ValueError('Financial year or tax period could not be identified')
    fy=fy_match.group(1)+'-'+fy_match.group(2)[-2:]
    month=GST_MONTH_INDEX[period_match.group(1).lower()]
    gstin_match=re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b',text)
    if not gstin_match:gstin_match=re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b',Path(path).name)
    gstin=gstin_match.group(0) if gstin_match else ''
    details={}
    if kind=='GSTR-3B':
        # Only section 3.1 and 3.1.1: do not count reverse-charge purchases or ITC.
        section=text.split('3.1 Details of Outward',1)[-1].split('3.2 Out of supplies',1)[0]
        section_lines=[x.strip() for x in section.splitlines() if x.strip()]
        for key,pattern in [('taxable',r'^\(a\)\s*Outward taxable supplies'),('zero',r'^\(b\)\s*Outward taxable supplies'),('exempt',r'^\(c\s*\)\s*Other outward supplies'),('nongst',r'^\(e\)\s*Non-GST outward supplies'),('eco',r'^\(ii\)\s*Taxable supplies made by registered person through')]:
            v=gst_first_amount_after(section_lines,lambda line,p=pattern:bool(re.search(p,line,re.I)))
            if v is None:raise ValueError('Missing GSTR-3B outward-supply row '+key+'; please inspect PDF')
            details[key]=v
        # 3.1.1(ii) may be included separately for supplies where ECO pays tax.
        taxable=details['taxable']+details['zero']+details['eco']
        exempt=details['exempt'];nongst=details['nongst']
    else:
        # Parse section headings and their FIRST summary line; do not use HSN totals (duplicate).
        # The heading-to-heading grouping prevents counting detail rows twice.
        headings=[]
        for i,line in enumerate(lines):
            if re.match(r'^(?:4A|4B|5\s*-|6A|6B|6C|7\s*-|8\s*-|9A|9B|9C|10\s*-|11A|11B|12\s*-|13\s*-|14\s*-|14A|15\s*-|15A)',line,re.I):
                headings.append((i,line))
        if not headings:raise ValueError('No GSTR-1 outward supply sections found')
        sections={}
        for idx,(i,head) in enumerate(headings):
            end=headings[idx+1][0] if idx+1<len(headings) else len(lines)
            sections.setdefault(re.match(r'^(4A|4B|5|6A|6B|6C|7|8|9A|9B|9C|10|11A|11B|12|13|14|14A|15|15A)',head,re.I).group(1).upper(),[]).append(lines[i+1:end])
        def summary(sec, prefix='Total', value_position=2):
            blocks=sections.get(sec,[])
            if not blocks:return Decimal('0')
            block=blocks[0]
            for i,line in enumerate(block):
                if line.lower().startswith(prefix.lower()):
                    nexts=block[i+1:i+12]
                    if prefix=='Total':
                        # Total, count, document type, taxable value; for nil-rated table no count/type.
                        if sec=='8':
                            nums=[x for x in nexts if re.fullmatch(GST_NUM,x)]
                            return gst_amount(nums[0]) if nums else Decimal('0')
                        for j,x in enumerate(nexts):
                            if x in ('Invoice','Net Value','Note','Document/Net Value'):
                                if j+1<len(nexts) and re.fullmatch(GST_NUM,nexts[j+1]):return gst_amount(nexts[j+1])
                    else:
                        nums=[x for x in nexts if re.fullmatch(GST_NUM,x)]
                        return gst_amount(nums[0]) if nums else Decimal('0')
            return Decimal('0')
        for key in ['4A','4B','5','6A','6B','6C','7','8','9B','9C','10']:
            details[key]=summary(key)
        # Amended 9A/9C: use net differential (not amended gross amount), where possible.
        for key in ('9A','9C'):
            dif=Decimal('0')
            for block in sections.get(key,[]):
                for i,line in enumerate(block):
                    if 'Net differential amount' in line or 'Net Differential amount' in line:
                        nums=[x for x in block[i+1:i+8] if re.fullmatch(GST_NUM,x)]
                        if nums:dif+=gst_amount(nums[0])
                        break
            details[key+'_differential']=dif
        taxable=sum((details[k] for k in ['4A','4B','5','6A','6B','6C','7','9B','10']),Decimal('0'))+details['9A_differential']+details['9C_differential']
        exempt=details['8'];nongst=Decimal('0') # Table 8 includes nil/exempt/non-GST; do not double count.
    turnover=taxable+exempt+nongst
    return {'fy':fy,'month':month,'gstin':gstin,'taxable':taxable,'exempt':exempt,'nongst':nongst,'turnover':turnover,'details':details}

def gst_make_tab(self,kind):
    v=self.tab(kind+' Import')
    v.addWidget(QLabel('Select client in Clients tab. Import multiple monthly '+kind+' PDF files (April to March).'))
    row=QHBoxLayout()
    self.btn(row,'Import monthly PDFs',lambda _,k=kind:self.gst_import(k))
    self.btn(row,'Export 12-month Excel working',lambda _,k=kind:self.gst_excel(k))
    self.btn(row,'Remove selected month',lambda _,k=kind:self.gst_remove(k))
    v.addLayout(row)
    fy=QComboBox();fy.setEditable(True)
    fy.setMinimumWidth(160)
    fy.currentTextChanged.connect(lambda _,k=kind:self.gst_refresh(k))
    v.addWidget(QLabel('Financial year (April–March):'));v.addWidget(fy)
    t=table(['Month','Taxable outward supplies (₹)','Nil / exempt / non-GST (₹)','Net turnover (₹)','Source PDF'])
    t.setMinimumHeight(350);v.addWidget(t)
    status=QLabel('Import returns to calculate financial-year totals.');v.addWidget(status)
    setattr(self,'gst_'+kind.replace('-','')+'_fy',fy)
    setattr(self,'gst_'+kind.replace('-','')+'_table',t)
    setattr(self,'gst_'+kind.replace('-','')+'_status',status)
    self.gst_refresh(kind)

def gst_widgets(self,kind):
    k=kind.replace('-','')
    return (getattr(self,'gst_'+k+'_fy'),getattr(self,'gst_'+k+'_table'),getattr(self,'gst_'+k+'_status'))

def gst_refresh(self,kind):
    fy,t,status=self.gst_widgets(kind)
    selected=fy.currentText().strip()
    years=[]
    if self.client_id:
        years=[r[0] for r in CON.execute('SELECT DISTINCT fy FROM gst_monthly WHERE client_id=? AND return_type=? ORDER BY fy DESC',(self.client_id,kind))]
    if not selected or (selected not in years and not re.fullmatch(r'20\d{2}-\d{2}',selected)):
        selected=years[0] if years else f'{date.today().year if date.today().month>=4 else date.today().year-1}-{(date.today().year+1 if date.today().month>=4 else date.today().year)%100:02d}'
    fy.blockSignals(True);fy.clear();fy.addItems(years)
    if selected not in years:fy.addItem(selected)
    fy.setCurrentText(selected);fy.blockSignals(False)
    t.setRowCount(0)
    records={}
    if self.client_id:
        records={r[0]:r for r in CON.execute('SELECT month,taxable,exempt,nongst,turnover,source FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=?',(self.client_id,kind,selected))}
    total=Decimal('0')
    for mon in GST_MONTHS:
        m=GST_MONTH_INDEX[mon.lower()];r=records.get(m)
        if r:
            vals=[mon, f'{gst_amount(r[1]):,.2f}',f'{gst_amount(r[2])+gst_amount(r[3]):,.2f}',f'{gst_amount(r[4]):,.2f}',Path(r[5]).name if r[5] else '']
            total+=gst_amount(r[4])
        else:vals=[mon,'MISSING','MISSING','MISSING','']
        addrow(t,vals)
        if not r:
            for c in range(t.columnCount()):t.item(t.rowCount()-1,c).setBackground(__import__('PyQt6').QtGui.QColor('#ffe4e4'))
    count=len(records)
    status.setText(f'{kind} | FY {selected} | {count}/12 months imported | Total ₹{total:,.2f} | '+('FULL YEAR' if count==12 else 'PARTIAL YEAR — do not certify as annual turnover'))
    status.setStyleSheet('color:#12693a;font-weight:bold' if count==12 else 'color:#b42318;font-weight:bold')

def gst_import(self,kind):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Create or select a client first in Clients tab.')
    paths,_=QFileDialog.getOpenFileNames(self,'Select '+kind+' monthly returns','','PDF files (*.pdf)')
    if not paths:return
    ok=[];bad=[]
    client_gstin=self.cf['GSTIN'].text().strip().upper()
    for path in paths:
        try:
            r=gst_extract(path,kind)
            if client_gstin and r['gstin'] and client_gstin!=r['gstin']:
                raise ValueError('GSTIN mismatch with selected client')
            old=CON.execute('SELECT source FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=? AND month=?',(self.client_id,kind,r['fy'],r['month'])).fetchone()
            if old and QMessageBox.question(self,'Duplicate month',f'{kind} {month_name[r["month"]]} {r["fy"]} already exists. Replace it?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
                bad.append(Path(path).name+': existing period retained');continue
            CON.execute('INSERT OR REPLACE INTO gst_monthly(client_id,return_type,fy,month,gstin,taxable,exempt,nongst,turnover,source,details) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (self.client_id,kind,r['fy'],r['month'],r['gstin'],*[str(r[x]) for x in ('taxable','exempt','nongst','turnover')],path,json.dumps({k:str(v) for k,v in r['details'].items()})))
            ok.append(r)
        except Exception as e:bad.append(Path(path).name+': '+str(e))
    CON.commit()
    if ok:self.gst_widgets(kind)[0].setCurrentText(ok[-1]['fy'])
    self.gst_refresh(kind)
    QMessageBox.information(self,'GST import results',f'{len(ok)} imported; {len(bad)} skipped.\n'+('\n'.join(bad[:12]) if bad else ''))

def gst_remove(self,kind):
    if not self.client_id:return
    fy,t,_=self.gst_widgets(kind);i=t.currentRow()
    if i<0:return
    month=GST_MONTH_INDEX[t.item(i,0).text().lower()]
    if QMessageBox.question(self,'Delete month','Remove saved '+kind+' for '+month_name[month]+'?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
    CON.execute('DELETE FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=? AND month=?',(self.client_id,kind,fy.currentText(),month));CON.commit();self.gst_refresh(kind)

def gst_excel(self,kind):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Select client first.')
    fy,_,_=self.gst_widgets(kind);year=fy.currentText().strip()
    path,_=QFileDialog.getSaveFileName(self,'Save Excel working',str(ROOT/(kind.replace('-','')+'_'+year+'_Turnover_Working.xlsx')),'Excel Workbook (*.xlsx)')
    if not path:return
    records={r[0]:r for r in CON.execute('SELECT month,taxable,exempt,nongst,turnover,source FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=?',(self.client_id,kind,year))}
    wb=Workbook();ws=wb.active;ws.title='12 Month Working'
    ws.merge_cells('A1:G1');ws['A1']=kind+' | FY '+year+' | MONTHLY TURNOVER WORKING'
    ws.merge_cells('A2:G2');ws['A2']='Client: '+self.cf['Name'].text()+' | GSTIN: '+self.cf['GSTIN'].text()
    ws.append(['Month','Taxable outward','Nil / exempt','Non-GST','Net turnover','Status','Source PDF'])
    for index,mon in enumerate(GST_MONTHS,4):
        m=GST_MONTH_INDEX[mon.lower()];r=records.get(m)
        if r:ws.append([mon,float(r[1]),float(r[2]),float(r[3]),f'=SUM(B{index}:D{index})','IMPORTED',r[5]])
        else:ws.append([mon,None,None,None,None,'MISSING',''])
    ws.append(['TOTAL', '=SUM(B4:B15)','=SUM(C4:C15)','=SUM(D4:D15)','=SUM(E4:E15)',f'{len(records)}/12 months',''])
    ws.append(['CERTIFICATION STATUS', 'FULL YEAR' if len(records)==12 else 'INCOMPLETE — PARTIAL YEAR ONLY'])
    ws.freeze_panes='B4';ws.auto_filter.ref='A3:G15'
    for row in (1,3,16):
        for c in ws[row]:c.fill=PatternFill('solid',fgColor='174A78');c.font=Font(color='FFFFFF',bold=True)
    for row in range(4,17):
        for col in range(2,6):ws.cell(row,col).number_format='#,##0.00;[Red](#,##0.00)'
        if row<16 and ws.cell(row,6).value=='MISSING':
            for c in ws[row]:c.fill=PatternFill('solid',fgColor='FFE5E5')
    for col,width in {'A':19,'B':22,'C':20,'D':18,'E':22,'F':25,'G':70}.items():ws.column_dimensions[col].width=width
    notes=wb.create_sheet('Notes')
    notes.append(['Method','This working is prepared from the imported return PDFs, not independent verification of books.'])
    notes.append(['Period','Financial year April to March; blank months are NOT treated as zero.'])
    notes.append(['GSTR-1','Outward supply tables and net amendments; HSN summary excluded to prevent duplication.'])
    notes.append(['GSTR-3B','Outward supplies under Table 3.1 and ECO supplies under 3.1.1(ii), excluding inward reverse charge.'])
    notes.append(['Review','Reconcile GSTR-1 versus GSTR-3B, amendments, ECO, advances, and books before issuing turnover certificate.'])
    notes.column_dimensions['A'].width=25;notes.column_dimensions['B'].width=125
    wb.save(path)
    QMessageBox.information(self,'Excel working exported',path)

Main.make_gst_tab=gst_make_tab
Main.gst_widgets=gst_widgets
Main.gst_refresh=gst_refresh
Main.gst_import=gst_import
Main.gst_remove=gst_remove
Main.gst_excel=gst_excel
_old_load_client=Main.load_client
def _gst_load_client(self, *args):
    _old_load_client(self)
    if hasattr(self,'gst_GSTR1_fy'):
        self.gst_refresh('GSTR-1');self.gst_refresh('GSTR-3B')
Main.load_client=_gst_load_client


# V31: workspace navigation, document selection, GST summary and preview.
from html import escape as html_escape
from PyQt6.QtWidgets import QCheckBox

_old_main_init_v31 = Main.__init__
def _main_init_v31(self):
    _old_main_init_v31(self)
    self._v31_configure_workspace()
Main.__init__ = _main_init_v31

def _v31_configure_workspace(self):
    tabs=self.tabs
    # Reuse original widgets and database. Rearranging does not reset data.
    for name,index in [('Clients',0),('Signer Profiles',1),('Certificates',2)]:
        for j in range(tabs.count()):
            if tabs.tabText(j)==name:
                page=tabs.widget(j);tabs.removeTab(j);tabs.insertTab(index,page,name);break
    tabs.setTabText(1,'CA Profile')
    tabs.setTabText(2,'Certificate Workspace')
    # The separate visa net-worth worksheet is no longer in the main navigation.
    for j in range(tabs.count()-1,-1,-1):
        if tabs.tabText(j)=='Net Worth':tabs.removeTab(j)
    # Put the existing certificate choice at the top of its own workspace.
    layout=self.cert_layout
    layout.removeWidget(self.cert_type)
    layout.insertWidget(0,self.cert_type)
    layout.insertWidget(0,QLabel('STEP 1  •  SELECT CERTIFICATE TYPE'))
    self.v31_suggestion=QLabel('')
    self.v31_suggestion.setWordWrap(True)
    self.v31_suggestion.setStyleSheet('background:#e9f2ff;color:#173f68;padding:12px;border-radius:6px;font-weight:600;')
    layout.insertWidget(2,self.v31_suggestion)
    self.v31_import=QPushButton('Import recommended documents')
    self.v31_import.clicked.connect(self._v31_import_recommended)
    layout.insertWidget(3,self.v31_import)
    self.v31_purpose_preset=QComboBox()
    self.v31_purpose_preset.addItems(['Select purpose','Bank loan','Bank finance','Tender documentation','Visa / immigration','Other — type manually'])
    self.v31_purpose_preset.currentIndexChanged.connect(self._v31_set_purpose)
    layout.insertWidget(4,QLabel('Purpose of issue — choose a preset or enter your own wording below'))
    layout.insertWidget(5,self.v31_purpose_preset)
    self.cert_type.currentIndexChanged.connect(self._v31_update_suggestion)
    self._v31_update_suggestion()
    # CA date/place/UDIN are on CA page, with the existing certificate UDIN mirrored.
    ca_page=tabs.widget(1)
    ca_content=ca_page.findChild(QScrollArea).widget().layout()
    ca_content.insertWidget(0,QLabel('CA DETAILS  •  Certificate date, place and UDIN'))
    self.v31_date=QLineEdit(date.today().strftime('%d-%m-%Y'))
    self.v31_place=QLineEdit()
    self.v31_udin=QLineEdit()
    ca_content.insertWidget(1,QLabel('Certificate date (DD-MM-YYYY)'))
    ca_content.insertWidget(2,self.v31_date)
    ca_content.insertWidget(3,QLabel('Place of issue (editable)'))
    ca_content.insertWidget(4,self.v31_place)
    ca_content.insertWidget(5,QLabel('UDIN (certificate-specific; manually obtained)'))
    ca_content.insertWidget(6,self.v31_udin)
    self.v31_udin.textChanged.connect(self.cert_ud.setText)
    self.cert_ud.textChanged.connect(lambda t:self.v31_udin.setText(t) if self.v31_udin.text()!=t else None)
    self.v31_place.setText(self.signer_fields['Place'].text())
    self.signer_select.currentIndexChanged.connect(lambda _=None:self.v31_place.setText(self.signer_fields['Place'].text()))
    # New GST turnover overview; existing separate GSTR-1 and GSTR-3B import tabs retained.
    v=self.tab('GST Turnover')
    v.addWidget(QLabel('GST TURNOVER WORKING  •  Choose return and financial year. Monthly and quarterly filings are supported where imported records provide the correct period.'))
    self.v31_gst_source=QComboBox();self.v31_gst_source.addItems(['GSTR-3B','GSTR-1']);v.addWidget(self.v31_gst_source)
    self.v31_gst_fy=QComboBox();v.addWidget(self.v31_gst_fy)
    self.v31_gst_table=table(['Period','Taxable outward supplies (₹)','Other outward supplies (₹)','Total turnover (₹)','Source'])
    self.v31_gst_table.setMinimumHeight(340);v.addWidget(self.v31_gst_table)
    self.v31_gst_total=QLabel('Select a client and financial year');v.addWidget(self.v31_gst_total)
    r=QHBoxLayout()
    self.btn(r,'Refresh GST data',self._v31_refresh_gst)
    self.btn(r,'Import GSTR-1',lambda:self._v31_open_tab('GSTR-1 Import'))
    self.btn(r,'Import GSTR-3B',lambda:self._v31_open_tab('GSTR-3B Import'))
    self.btn(r,'Fetch into certificate',self._v31_fetch_gst)
    v.addLayout(r)
    self.v31_gst_source.currentIndexChanged.connect(self._v31_refresh_gst)
    self.v31_gst_fy.currentIndexChanged.connect(self._v31_display_gst)
    self._v31_refresh_gst()
    # Display GST summary immediately after certificate workspace.
    j=tabs.indexOf(self.v31_gst_table.window())
    for j in range(tabs.count()):
        if tabs.tabText(j)=='GST Turnover':
            page=tabs.widget(j);tabs.removeTab(j);tabs.insertTab(3,page,'GST Turnover');break
    tabs.setCurrentIndex(0)

def _v31_open_tab(self,name):
    for i in range(self.tabs.count()):
        if self.tabs.tabText(i)==name:self.tabs.setCurrentIndex(i);return

def _v31_set_purpose(self,*_):
    selected=self.v31_purpose_preset.currentText()
    if selected=='Other — type manually':self.purpose.setFocus()
    elif selected!='Select purpose':self.purpose.setText(selected)

def _v31_update_suggestion(self,*_):
    kind=self._cert_kind()
    suggestions=[
        'ITR acknowledgement certificate: import the ITR acknowledgement PDF for each AY, then confirm the portal download and acknowledgement verification details below.',
        'Turnover certificate: import ITR-3 / ITR-4 PDF or JSON, OR import GSTR-1 / GSTR-3B monthly or quarterly returns. Select the turnover source below.',
        'Turnover and net worth certificate: import ITR PDF / JSON with business balance sheet, plus GST returns if turnover is to be sourced from GST. Review net worth adjustments manually.',
        'Net worth certificate: import ITR-3 PDF / JSON to extract business capital; review and enter all assets and liabilities before certifying net worth.'
    ]
    self.v31_suggestion.setText(suggestions[kind])
    self.v31_import.setText('Import ITR acknowledgement PDF' if kind==0 else 'Choose ITR PDF/JSON or GST return import')

def _v31_import_recommended(self):
    if self._cert_kind()==0:
        self._v31_open_tab('Step 1 • Import ITR PDF')
    else:
        choices=['ITR PDF / JSON','GSTR-1 PDF','GSTR-3B PDF']
        choice,ok=QInputDialog.getItem(self,'Select source','Which supporting documents do you want to import?',choices,0,False)
        if not ok:return
        self._v31_open_tab({'ITR PDF / JSON':'Step 1 • Import ITR PDF','GSTR-1 PDF':'GSTR-1 Import','GSTR-3B PDF':'GSTR-3B Import'}[choice])

def _v31_refresh_gst(self,*_):
    if not hasattr(self,'v31_gst_fy'):return
    self.v31_gst_fy.blockSignals(True)
    current=self.v31_gst_fy.currentText();self.v31_gst_fy.clear()
    if self.client_id:
        rows=CON.execute('SELECT DISTINCT fy FROM gst_monthly WHERE client_id=? AND return_type=? ORDER BY fy DESC',(self.client_id,self.v31_gst_source.currentText())).fetchall()
        for (fy,) in rows:self.v31_gst_fy.addItem(fy)
    idx=self.v31_gst_fy.findText(current)
    if idx>=0:self.v31_gst_fy.setCurrentIndex(idx)
    self.v31_gst_fy.blockSignals(False)
    self._v31_display_gst()

def _v31_display_gst(self,*_):
    if not hasattr(self,'v31_gst_table'):return
    self.v31_gst_table.setRowCount(0)
    fy=self.v31_gst_fy.currentText()
    if not self.client_id or not fy:
        self.v31_gst_total.setText('No GST returns available for this client and return type.');return
    # Read schema names dynamically; earlier versions may differ in column naming.
    cols=[x[1] for x in CON.execute('PRAGMA table_info(gst_monthly)').fetchall()]
    rows=CON.execute('SELECT * FROM gst_monthly WHERE client_id=? AND return_type=? AND fy=?',(self.client_id,self.v31_gst_source.currentText(),fy)).fetchall()
    total=Decimal('0')
    for row in rows:
        item=dict(zip(cols,row))
        def get(*names):
            for name in names:
                if name in item:return item[name]
            return ''
        amount=get('total','turnover','net_turnover','sales')
        try:total+=Decimal(str(amount or 0).replace(',',''))
        except Exception:pass
        addrow(self.v31_gst_table,[(month_name[int(get('month'))] if str(get('month')).isdigit() and 1<=int(get('month'))<=12 else str(get('month','period','tax_period'))),str(get('taxable','taxable_value','outward_taxable')),str(get('exempt','other','other_outward')),str(amount),str(get('source','filename'))])
    self.v31_gst_total.setText(f'FY {fy}  |  {len(rows)} period records imported  |  Sum of saved turnover ₹{total:,.2f}. Confirm complete FY coverage before certification.')

def _v31_fetch_gst(self):
    if self.v31_gst_fy.currentText():
        self.turnover_source.setCurrentIndex(2 if self.v31_gst_source.currentText()=='GSTR-3B' else 1)
        self.tabs.setCurrentIndex(2)
        self.fetch_selected_turnover()

for name,fn in [(' _v31_configure_workspace',_v31_configure_workspace),('_v31_open_tab',_v31_open_tab),('_v31_set_purpose',_v31_set_purpose),('_v31_update_suggestion',_v31_update_suggestion),('_v31_import_recommended',_v31_import_recommended),('_v31_refresh_gst',_v31_refresh_gst),('_v31_display_gst',_v31_display_gst),('_v31_fetch_gst',_v31_fetch_gst)]:
    setattr(Main,name.strip(),fn)

_old_load_client_v31=Main.load_client
def _load_client_v31(self,*args):
    result=_old_load_client_v31(self,*args)
    if hasattr(self,'v31_gst_fy'):self._v31_refresh_gst()
    return result
Main.load_client=_load_client_v31

# Preview is shown BEFORE saving. The editable review table covers every paragraph
# and table cell; edited text is applied to the Word document on confirmation.
def _v31_preview_save_doc(doc,parent,name):
    dialog=QDialog(parent);dialog.setWindowTitle('Certificate preview and edit — '+name);dialog.resize(1080,760)
    lay=QVBoxLayout(dialog)
    lay.addWidget(QLabel('PREVIEW • Select an item below to edit its text. Tables remain structured in the Word file.'))
    preview=QTextEdit();preview.setReadOnly(True);lay.addWidget(preview,3)
    editor=QTableWidget(0,3);editor.setHorizontalHeaderLabels(['Type','Location','Editable text']);editor.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
    editor.setMinimumHeight(210);lay.addWidget(editor,2)
    targets=[]
    for idx,p in enumerate(doc.paragraphs):
        if p.text.strip():targets.append(('Paragraph',str(idx+1),p))
    for ti,t in enumerate(doc.tables):
        for ri,row in enumerate(t.rows):
            for ci,c in enumerate(row.cells):targets.append(('Table cell',f'{ti+1}.{ri+1}.{ci+1}',c))
    for typ,location,obj in targets:addrow(editor,[typ,location,obj.text])
    for i in range(editor.rowCount()):
        for j in (0,1):editor.item(i,j).setFlags(editor.item(i,j).flags() & ~Qt.ItemFlag.ItemIsEditable)
    def show_preview():
        pieces=[]
        for p in doc.paragraphs:
            if p.text.strip():pieces.append('<p>'+html_escape(p.text)+'</p>')
        for t in doc.tables:
            pieces.append('<table border="1" cellpadding="5" cellspacing="0">')
            for row in t.rows:pieces.append('<tr>'+''.join('<td>'+html_escape(c.text)+'</td>' for c in row.cells)+'</tr>')
            pieces.append('</table>')
        preview.setHtml('<div style="font-family:Calibri;font-size:11pt;">'+''.join(pieces)+'</div>')
    show_preview()
    buttons=QHBoxLayout()
    def apply_changes():
        for i,(_,_,obj) in enumerate(targets):
            text=cell(editor,i,2)
            if text!=obj.text:
                if hasattr(obj,'paragraphs'):obj.paragraphs[0].text=text
                else:obj.text=text
        show_preview()
    apply_btn=QPushButton('Apply edits to preview');apply_btn.clicked.connect(apply_changes);buttons.addWidget(apply_btn)
    save_btn=QPushButton('Save editable Word (.docx)');buttons.addWidget(save_btn)
    cancel_btn=QPushButton('Cancel');cancel_btn.clicked.connect(dialog.reject);buttons.addWidget(cancel_btn)
    lay.addLayout(buttons)
    def save():
        apply_changes()
        path,_=QFileDialog.getSaveFileName(dialog,'Save Word certificate',str(ROOT/(Path(name).stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.docx')),'Word (*.docx)')
        if not path:return
        if not path.lower().endswith('.docx'):path+='.docx'
        try:
            for sec in doc.sections:
                sec.header.paragraphs[0].text='';sec.footer.paragraphs[0].text=''
                sec.top_margin=Inches(1.4);sec.bottom_margin=Inches(.8)
            for p in doc.paragraphs:
                if p.alignment==WD_ALIGN_PARAGRAPH.JUSTIFY:p.alignment=WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_after=Pt(4)
                p.paragraph_format.line_spacing=1.08
            for t in doc.tables:t.autofit=True
            doc.save(path);dialog.accept();offer_open(parent,path)
        except Exception as exc:QMessageBox.critical(dialog,'Unable to save',str(exc))
    save_btn.clicked.connect(save)
    dialog.exec()

save_doc=_v31_preview_save_doc

# V32: Prevent uncaught Qt slot errors from terminating the desktop process.
# Keep an actionable error log rather than silently exiting on client selection.
import logging
from logging.handlers import RotatingFileHandler
_V32_LOG = ROOT / 'smart_certifictes_errors.log'
_v32_logger = logging.getLogger('smart_certifictes')
_v32_logger.setLevel(logging.ERROR)
if not _v32_logger.handlers:
    _v32_logger.addHandler(RotatingFileHandler(str(_V32_LOG), maxBytes=1000000, backupCount=2, encoding='utf-8'))

def _v32_show_error(self, title, exc):
    _v32_logger.exception('%s: %s', title, exc)
    try:
        QMessageBox.critical(self, title, f'{type(exc).__name__}: {exc}\n\nDiagnostic log: {_V32_LOG}')
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)

def _v32_safe_client_load(self, *args):
    try:
        # Execute the original V31 client selection, including GST and ITR refresh.
        return _load_client_v31(self, *args)
    except Exception as exc:
        _v32_show_error(self, 'Unable to load client', exc)
        return None
Main.load_client = _v32_safe_client_load

# Guard the client-screen creation path and GST summary, which depend on
# the selected client's saved returns. A malformed older record must not crash.
_v32_old_gst_refresh = Main._v31_refresh_gst
def _v32_safe_gst_refresh(self, *args):
    try:
        return _v32_old_gst_refresh(self, *args)
    except Exception as exc:
        _v32_show_error(self, 'Unable to refresh GST summary', exc)
Main._v31_refresh_gst = _v32_safe_gst_refresh

# Also capture uncaught exceptions raised from any other PyQt callback.
def _v32_exception_hook(exc_type, exc, tb):
    _v32_logger.error('Unhandled application exception', exc_info=(exc_type, exc, tb))
    try:
        QMessageBox.critical(QApplication.activeWindow(), 'Smart Certifictes error',
            f'{exc_type.__name__}: {exc}\n\nDiagnostic log: {_V32_LOG}')
    except Exception:
        traceback.print_exception(exc_type, exc, tb)
sys.excepthook = _v32_exception_hook



# V33: Client deletion manager.  No existing client or return is modified on startup.
from PyQt6.QtWidgets import QAbstractItemView
import time

_v33_previous_init = Main.__init__
def _v33_init(self):
    _v33_previous_init(self)
    self.setWindowTitle('Smart Certifictes V33 — Client Management Fix')
    self._v33_build_delete_tab()
Main.__init__ = _v33_init

def _v33_build_delete_tab(self):
    v=self.tab('Delete Clients')
    v.addWidget(QLabel('SELECT CLIENTS TO DELETE • Supports one or multiple selections'))
    v.addWidget(QLabel('Deletion includes associated ITR, financial, GST and verification records. A database backup is created first.'))
    self.v33_delete_table=QTableWidget(0,4)
    self.v33_delete_table.setHorizontalHeaderLabels(['Client ID','Client Name','PAN','GSTIN'])
    self.v33_delete_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.v33_delete_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    self.v33_delete_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.v33_delete_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
    self.v33_delete_table.setMinimumHeight(350)
    v.addWidget(self.v33_delete_table)
    r=QHBoxLayout()
    self.btn(r,'Refresh client list',self._v33_refresh_delete)
    self.btn(r,'Select all clients',self.v33_delete_table.selectAll)
    self.btn(r,'Clear selection',self.v33_delete_table.clearSelection)
    v.addLayout(r)
    self.btn(v,'Delete selected client(s)…',self._v33_delete_selected)
    v.addWidget(QLabel('Use Ctrl+click or Shift+click to select multiple rows. Deletion cannot be undone except by restoring the backup.'))
    self._v33_refresh_delete()

def _v33_refresh_delete(self):
    t=self.v33_delete_table
    t.setRowCount(0)
    for cid,name,pan,gstin in CON.execute('SELECT id,name,pan,gstin FROM clients ORDER BY name,id'):
        addrow(t,[str(cid),name or '',pan or '',gstin or ''])

def _v33_delete_selected(self):
    t=self.v33_delete_table
    rows=sorted({index.row() for index in t.selectionModel().selectedRows()})
    if not rows:
        return QMessageBox.information(self,'Select client','Select one or more clients first.')
    ids=[int(t.item(r,0).text()) for r in rows]
    names=[t.item(r,1).text() for r in rows]
    summary='\n'.join(names[:12])
    if len(names)>12:summary+=f'\n... and {len(names)-12} more'
    reply=QMessageBox.warning(self,'Confirm permanent deletion',
        f'Delete {len(ids)} client(s) and ALL their saved returns?\n\n{summary}\n\nA database backup will be saved before deletion.',
        QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
    if reply!=QMessageBox.StandardButton.Yes:return
    # SQLite online backup avoids inconsistent copies of a live database.
    backup_dir=ROOT/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/('clients_before_delete_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sqlite3')
    try:
        with sqlite3.connect(str(backup)) as target:CON.backup(target)
        tables=[r[0] for r in CON.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        child_tables=[]
        for name in tables:
            if name=='clients':continue
            cols=[r[1] for r in CON.execute('PRAGMA table_info("'+name.replace('"','""')+'")')]
            if 'client_id' in cols:child_tables.append(name)
        with CON:
            for name in child_tables:
                escaped=name.replace('"','""')
                CON.executemany('DELETE FROM "'+escaped+'" WHERE client_id=?',[(cid,) for cid in ids])
            CON.executemany('DELETE FROM clients WHERE id=?',[(cid,) for cid in ids])
        self.refresh_clients()
        self.new_client()
        self.load_itr()
        if hasattr(self,'gst_GSTR1_fy'):
            self.gst_refresh('GSTR-1');self.gst_refresh('GSTR-3B')
        self._v33_refresh_delete()
        QMessageBox.information(self,'Clients deleted',f'{len(ids)} client(s) deleted.\nBackup: {backup}')
    except Exception as exc:
        _v32_show_error(self,'Client deletion failed',exc)
        QMessageBox.warning(self,'Backup location',f'Check backup file before retrying: {backup}')

Main._v33_build_delete_tab=_v33_build_delete_tab
Main._v33_refresh_delete=_v33_refresh_delete
Main._v33_delete_selected=_v33_delete_selected

# V34: direct ITR acknowledgement loading and visible certificate preview controls.
# The GST Turnover page is a consolidated summary; GSTR-3B Import is the input page.
def _v34_load_itr_acknowledgements(self):
    if self._cert_kind()!=0:
        self.cert_type.setCurrentIndex(0)
    if not self.client_id:
        return QMessageBox.warning(self,'Select client','Select a client in the Clients tab first.')
    # Use the already persisted ITR records; do not demand a new import.
    rows=CON.execute('SELECT ay,form,income,ack,filing FROM itr WHERE client_id=? ORDER BY ay',(self.client_id,)).fetchall()
    if not rows:
        return QMessageBox.warning(self,'No ITR acknowledgements','No saved ITR records for this client. Import an ITR acknowledgement PDF first.')
    self.fin_table.setRowCount(0)
    for ay,form,income,ack,filing in rows:
        addrow(self.fin_table,[ay, '' if income is None else str(income),form or '',ack or '',filing or ''])
    self.populate_itr_downloads()
    self.autofill_itr_parties()
    if hasattr(self,'itr_group'):
        self.itr_group.setVisible(True)
    missing=[str(r[0]) for r in rows if not r[3] or not r[4] or r[2] is None]
    if missing:
        QMessageBox.warning(self,'Review incomplete records','Missing acknowledgement number, filing date or income for: '+', '.join(missing)+'. Review before issuance.')
    else:
        QMessageBox.information(self,'ITR details loaded',f'{len(rows)} assessment-year record(s) loaded. Check portal download dates and YES/NO verification before preview.')

def _v34_preview_certificate(self):
    # The existing generation path opens the V31 editable preview dialog BEFORE saving.
    # Keep all certificate validations intact.
    return self.generate_certificate()

_v34_original_init=Main.__init__
def _v34_init(self):
    _v34_original_init(self)
    layout=self.cert_layout
    # Put actions immediately after certificate selection, rather than below a long form.
    self.v34_load_btn=QPushButton('Load imported ITR acknowledgement details')
    self.v34_load_btn.clicked.connect(lambda:self._v34_load_itr_acknowledgements())
    layout.insertWidget(5,self.v34_load_btn)
    self.v34_preview_btn=QPushButton('Preview & Edit Certificate (before saving Word)')
    self.v34_preview_btn.clicked.connect(lambda:self._v34_preview_certificate())
    layout.insertWidget(6,self.v34_preview_btn)
    self.v34_load_btn.setStyleSheet('background:#185a98;color:white;padding:10px;font-weight:bold;')
    self.v34_preview_btn.setStyleSheet('background:#167245;color:white;padding:10px;font-weight:bold;')
    self.cert_type.currentIndexChanged.connect(lambda *_:self.v34_load_btn.setVisible(self._cert_kind()==0))
    self.v34_load_btn.setVisible(self._cert_kind()==0)
    # Name the two distinct GST pages to remove ambiguity.
    for i in range(self.tabs.count()):
        label=self.tabs.tabText(i)
        if label=='GST Turnover':self.tabs.setTabText(i,'GST Turnover Summary')
        elif label=='GSTR-3B Import':self.tabs.setTabText(i,'GSTR-3B Import / Edit')
    # Keep navigation compatible with the renamed tab.
    self.v31_gst_source.setToolTip('This page reviews GST records already imported; import and edit in the GSTR-3B Import / Edit tab.')

Main._v34_load_itr_acknowledgements=_v34_load_itr_acknowledgements
Main._v34_preview_certificate=_v34_preview_certificate
Main.__init__=_v34_init


# V35: Separate Preview & Edit from Generate Word, with explicit Save Changes.
# The Word document is only written after the user clicks Generate Word Certificate.

def _v35_review_document(doc, parent, name):
    dialog=QDialog(parent)
    dialog.setWindowTitle('Preview & Edit Certificate — '+name)
    dialog.resize(1100, 790)
    layout=QVBoxLayout(dialog)
    layout.addWidget(QLabel('Review the certificate. Edit text in the lower table, click Save Changes, then Generate Word Certificate.'))
    preview=QTextEdit()
    preview.setReadOnly(True)
    layout.addWidget(preview, 3)
    editor=QTableWidget(0, 3)
    editor.setHorizontalHeaderLabels(['Type', 'Location', 'Editable text'])
    editor.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    editor.setMinimumHeight(230)
    layout.addWidget(editor, 2)
    targets=[]
    for idx, paragraph in enumerate(doc.paragraphs):
        if paragraph.text.strip():
            targets.append(('Paragraph',str(idx+1),paragraph))
    for ti, tbl in enumerate(doc.tables):
        for ri, row in enumerate(tbl.rows):
            for ci, item in enumerate(row.cells):
                targets.append(('Table cell',f'{ti+1}.{ri+1}.{ci+1}',item))
    for typ, position, obj in targets:
        addrow(editor,[typ,position,obj.text])
    for i in range(editor.rowCount()):
        for j in (0,1):
            item=editor.item(i,j)
            if item is not None:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def refresh_preview():
        parts=[]
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append('<p style="margin:3px 0">'+html_escape(para.text)+'</p>')
        for tbl in doc.tables:
            parts.append('<table border="1" cellspacing="0" cellpadding="4" width="100%">')
            for row in tbl.rows:
                parts.append('<tr>'+''.join('<td>'+html_escape(item.text)+'</td>' for item in row.cells)+'</tr>')
            parts.append('</table>')
        preview.setHtml('<div style="font-family:Calibri;font-size:10pt">'+''.join(parts)+'</div>')

    def apply_changes():
        for i, (_, _, obj) in enumerate(targets):
            new_text=cell(editor,i,2)
            if new_text!=obj.text:
                if hasattr(obj,'paragraphs'):
                    # Keep the table cell's existing formatting wherever possible.
                    first=obj.paragraphs[0]
                    if first.runs:
                        first.runs[0].text=new_text
                        for run in first.runs[1:]:run.text=''
                    else:first.add_run(new_text)
                    for extra in obj.paragraphs[1:]:extra.text=''
                else:
                    if obj.runs:
                        obj.runs[0].text=new_text
                        for run in obj.runs[1:]:run.text=''
                    else:obj.add_run(new_text)
        refresh_preview()
        status.setText('Changes saved in preview. Click Generate Word Certificate to export the .docx file.')

    refresh_preview()
    status=QLabel('Edits are not exported until you generate the Word document.')
    layout.addWidget(status)
    actions=QHBoxLayout()
    save_changes=QPushButton('Save Changes')
    generate=QPushButton('Generate Word Certificate (.docx)')
    close=QPushButton('Close')
    save_changes.clicked.connect(apply_changes)
    close.clicked.connect(dialog.reject)
    actions.addWidget(save_changes)
    actions.addWidget(generate)
    actions.addWidget(close)
    layout.addLayout(actions)

    def generate_word():
        apply_changes()
        initial=str(ROOT/(Path(name).stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.docx'))
        path,_=QFileDialog.getSaveFileName(dialog,'Generate Word Certificate',initial,'Word Documents (*.docx)')
        if not path:return
        if not path.lower().endswith('.docx'):path+='.docx'
        try:
            for section in doc.sections:
                section.header.paragraphs[0].text=''
                section.footer.paragraphs[0].text=''
                section.top_margin=Inches(1.4)
                section.bottom_margin=Inches(.8)
            for para in doc.paragraphs:
                # Preserve full justification for narrative paragraphs.
                # Do not stretch headings, addresses, dates or signatures.
                _v37_format_paragraph(para)

            for tbl in doc.tables:tbl.autofit=True
            _v37_prepare_doc(doc)
            doc.save(path)
            QMessageBox.information(dialog,'Word certificate generated','Saved successfully:\n'+path)
            dialog.accept()
            offer_open(parent,path)
        except Exception as exc:
            QMessageBox.critical(dialog,'Word generation failed',str(exc))
    generate.clicked.connect(generate_word)
    dialog.exec()

# V37: Professional paragraph wrapping and justification for certificates and MRL.
def _v37_format_paragraph(p):
    value=' '.join(p.text.split())
    if not value:
        p.paragraph_format.space_after=Pt(0)
        return
    fmt=p.paragraph_format
    fmt.space_before=Pt(0)
    fmt.space_after=Pt(3)
    fmt.line_spacing=1.10
    fmt.widow_control=True
    # Word's JUSTIFY keeps the final line left aligned, unlike DISTRIBUTE.
    # Short lines and labels must not be stretched across the page.
    low=value.lower()
    heading=(low in ('assessees responsibility','assessee’s responsibility',
                     'our responsibility','our responsibility and work performed',
                     'opinion','conclusion','restriction on use','inherent limitations',
                     'engagement and applicable criteria','financial particulars',
                     'net worth particulars','management representation letter')
             or low.startswith(('subject:', 'date:', 'place:', 'signature:', 'designation:',
                                'name:', 'for ', 'to,', 'udin:', 'frn:', 'membership no.'))
             or (len(value)<90 and value.isupper())
             or p.alignment in (WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT))
    if heading or len(value)<85:
        if p.alignment not in (WD_ALIGN_PARAGRAPH.CENTER,WD_ALIGN_PARAGRAPH.RIGHT):
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    else:
        p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY

def _v37_prepare_doc(d):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    for p in d.paragraphs:
        _v37_format_paragraph(p)
    for t in d.tables:
        t.autofit=True
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    p.alignment=WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.space_before=Pt(0)
                    p.paragraph_format.space_after=Pt(0)
                    p.paragraph_format.line_spacing=1.0
    return d

# All certificate generators call save_doc; route that output to the new review dialog.
def _v37_review_document(doc,parent,name):
    _v37_prepare_doc(doc)
    return _v35_review_document(doc,parent,name)
save_doc=_v37_review_document

# Both buttons use the same validation and preview. The preview button no longer
# masquerades as a Word-export action; export happens explicitly inside the dialog.
def _v35_preview_certificate(self):
    return self.generate_certificate()
Main._v34_preview_certificate=_v35_preview_certificate

# Rename the original button so its behaviour is clear: it opens review and
# requires a second explicit action to save a Word document.
_v35_original_init=Main.__init__
def _v35_init(self):
    _v35_original_init(self)
    for button in self.findChildren(QPushButton):
        if button.text()=='Generate Word Certificate':
            button.setText('Review & Generate Word Certificate')
        elif button.text().startswith('Preview & Edit Certificate'):
            button.setText('Preview & Edit Certificate')
Main.__init__=_v35_init

# V39: Repair certificate form visibility after V31/V34 insertWidget changes.
# The old numeric layout positions became invalid when widgets were inserted.
# Always use widget identities instead of positional slices.
def _v39_toggle_certificate_fields(self, *_):
    kind=self._cert_kind()
    is_itr=(kind==0)
    combined=(kind in (2,3))
    if hasattr(self,'itr_group'):
        self.itr_group.setVisible(is_itr)
    # Each label belongs to the widget immediately after it in the original form.
    # Identify those pairs dynamically, independent of later layout insertions.
    layout=self.cert_layout
    assurance_widgets=(self.criteria,self.procedures,self.assurance,
                       self.conclusion,self.conclusion_basis,self.check_evidence)
    networth_widgets=(self.nw_ay,self.cert_net,self.cert_capital,
                      self.cert_reserve,self.cert_losses)
    for widget in assurance_widgets+networth_widgets:
        visible=(not is_itr) if widget in assurance_widgets else combined
        widget.setVisible(visible)
        for index in range(layout.count()):
            item=layout.itemAt(index)
            if item and item.widget() is widget:
                if index>0:
                    previous=layout.itemAt(index-1)
                    label=previous.widget() if previous else None
                    if isinstance(label,QLabel):label.setVisible(visible)
                break
    # Financial-year table and GST source selection must remain visible.
    self.fin_table.setVisible(True)
    self.turnover_source.setVisible(not is_itr)
    self.refresh_certificate_colours()

Main.update_certificate_fields=_v39_toggle_certificate_fields

# Reapply visibility once all workspace tabs and dynamically inserted buttons exist.
_v39_previous_init=Main.__init__
def _v39_init(self):
    _v39_previous_init(self)
    self.update_certificate_fields()
    self.cert_type.currentIndexChanged.connect(self.update_certificate_fields)
    # Restore accessible controls if earlier positional hiding affected them.
    for w in (self.assurance,self.conclusion,self.conclusion_basis,self.check_evidence):
        if self._cert_kind()!=0:w.show()
Main.__init__=_v39_init

# V40: Refresh financial schedules from the original saved JSON files without
# modifying client identity or confusing total income with business turnover.
def _v40_refresh_saved_json_financials(self):
    if not self.client_id:
        return QMessageBox.warning(self,'Select client','Select an existing client first.')
    records=CON.execute('SELECT ay,ack,source FROM itr WHERE client_id=? ORDER BY ay',(self.client_id,)).fetchall()
    if not records:
        return QMessageBox.warning(self,'No ITR records','Import ITR JSON files for the selected client first.')
    updated=[];skipped=[]
    for ay,ack,source in records:
        source_path=Path(source or '')
        if source_path.suffix.lower()!='.json' or not source_path.is_file():
            skipped.append(f'{ay}: original JSON file unavailable (or source is PDF)')
            continue
        try:
            d=extract_itr_json(str(source_path))
            if d.get('ay') and d['ay']!=ay:
                skipped.append(f'{ay}: source assessment year does not match');continue
            if d.get('ack') and d['ack']!=ack:
                skipped.append(f'{ay}: source acknowledgement number does not match');continue
            if d.get('pan'):
                saved_pan=CON.execute('SELECT pan FROM clients WHERE id=?',(self.client_id,)).fetchone()
                if saved_pan and saved_pan[0] and saved_pan[0].strip().upper()!=d['pan'].strip().upper():
                    skipped.append(f'{ay}: PAN mismatch');continue
            turnover=d.get('turnover','')
            capital=d.get('networth','')
            CON.execute("""INSERT INTO itr_financials(client_id,ay,ack,turnover,turnover_basis,networth,networth_basis,source) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(client_id,ay,ack) DO UPDATE SET turnover=CASE WHEN excluded.turnover!='' THEN excluded.turnover ELSE itr_financials.turnover END, turnover_basis=CASE WHEN excluded.turnover!='' THEN excluded.turnover_basis ELSE itr_financials.turnover_basis END, networth=CASE WHEN excluded.networth!='' THEN excluded.networth ELSE itr_financials.networth END, networth_basis=CASE WHEN excluded.networth!='' THEN excluded.networth_basis ELSE itr_financials.networth_basis END, source=excluded.source""",(self.client_id,ay,ack,turnover,d.get('turnover_basis',''),capital,d.get('networth_basis',''),str(source_path)))
            updated.append(f'{ay}: Total Income ₹{d.get("income") or "not identified"}; Turnover ₹{turnover or "not identified"}; Business capital ₹{capital or "not identified"}')
        except Exception as e:
            skipped.append(f'{ay}: {e}')
    CON.commit()
    if self._cert_kind() in (1,2,3):
        self.turnover_source.setCurrentIndex(0)
        self.fill_from_itr()
    else:
        self.load_itr()
    summary='\n'.join(updated) if updated else 'No JSON financial schedules were refreshed.'
    if skipped:summary+='\n\nSkipped:\n'+'\n'.join(skipped)
    QMessageBox.information(self,'ITR financial schedules',summary+'\n\nBusiness capital is NOT personal net worth.')

Main.refresh_saved_json_financials=_v40_refresh_saved_json_financials
_v40_old_init=Main.__init__
def _v40_init(self):
    _v40_old_init(self)
    btn=QPushButton('Refresh turnover and owner capital from saved ITR JSON')
    btn.setToolTip('Re-read original saved JSON files for the selected client and AY. Does not change client name or PAN.')
    btn.clicked.connect(self.refresh_saved_json_financials)
    self.cert_layout.insertWidget(self.cert_layout.indexOf(self.fin_table),btn)
    self._v40_json_refresh_button=btn
    self.setWindowTitle('Smart Certifictes V40 — ITR Turnover and Capital Fix')
Main.__init__=_v40_init

# V41: Four independent certificate choices, with stable legacy logical IDs.
def _v41_cert_kind(self):
    return {0:1,1:3,2:0,3:2}.get(self.cert_type.currentIndex(),0)
Main._cert_kind=_v41_cert_kind

_v41_old_init=Main.__init__
def _v41_init(self):
    _v41_old_init(self)
    self.cert_type.setCurrentIndex(0)
    self.setWindowTitle('Smart Certifictes V42 — Capital Basis Options')
    self.cert_type.currentIndexChanged.connect(lambda *_:self._v41_networth_ui())
    self._v41_networth_ui()

def _v41_networth_ui(self):
    kind=self._cert_kind()
    # Hide the turnover table and its source controls for a standalone net worth certificate.
    self.fin_table.setVisible(kind!=3)
    if hasattr(self,'turnover_source'):self.turnover_source.setVisible(kind!=3)
    if kind==3:
        self.cert_heading.setCurrentText('NET WORTH CERTIFICATE')
Main._v41_networth_ui=_v41_networth_ui
Main.__init__=_v41_init

# V43: Business balance-sheet assets less liabilities, sourced from ITR-3 PARTA_BS.
# Independent of the personal-net-worth question. Source JSON is never modified.
from PyQt6.QtWidgets import QAbstractItemView

def v43_extract_balance_sheet(path):
    """ITR-3/4/5 JSON: itemised business assets, outside liabilities and equity reconciliation."""
    raw=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    itr=raw.get('ITR',raw)
    matches=[(k,v) for k,v in itr.items() if k in ('ITR3','ITR4','ITR5') and isinstance(v,dict)]
    if len(matches)!=1:raise ValueError('Select a JSON containing exactly one ITR-3, ITR-4 or ITR-5 return.')
    key,node=matches[0]
    def amount(obj,*keys):
        cur=obj
        for k in keys:
            if not isinstance(cur,dict) or k not in cur:
                raise ValueError('Missing balance sheet field: '+'.'.join(keys))
            cur=cur[k]
        if isinstance(cur,bool) or not isinstance(cur,(int,float,str)):
            raise ValueError('Invalid balance sheet number: '+'.'.join(keys))
        try:return Decimal(str(cur).replace(',',''))
        except Exception:raise ValueError('Invalid balance sheet amount: '+'.'.join(keys))
    if key=='ITR4':
        bp=node.get('ScheduleBP',{})
        fp=bp.get('FinanclPartclrOfBusiness')
        if not isinstance(fp,dict):raise ValueError('ITR-4 ScheduleBP financial particulars are unavailable.')
        items=[
            ('Asset','Fixed assets',amount(fp,'FixedAssets')),
            ('Asset','Investments',amount(fp,'Investments') if 'Investments' in fp else Decimal(0)),
            ('Asset','Inventories',amount(fp,'Inventories')),
            ('Asset','Sundry debtors',amount(fp,'SundryDebtors')),
            ('Asset','Bank balances',amount(fp,'BalWithBanks')),
            ('Asset','Cash in hand',amount(fp,'CashInHand')),
            ('Asset','Loans and advances given',amount(fp,'LoansAndAdvances')),
            ('Asset','Other assets',amount(fp,'OtherAssets')),
            ('Liability','Secured loans',amount(fp,'SecuredLoans')),
            ('Liability','Unsecured loans',amount(fp,'UnSecuredLoans')),
            ('Liability','Advances received',amount(fp,'Advances')),
            ('Liability','Sundry creditors',amount(fp,'SundryCreditors')),
            ('Liability','Other current liabilities',amount(fp,'OthrCurrLiab')),
        ]
        proprietor=amount(fp,'PartnerMemberOwnCapital')
        sources=amount(fp,'TotCapLiabilities'); application=amount(fp,'TotalAssets')
        misc=Decimal(0)
        pan=node.get('PersonalInfo',{}).get('PAN','')
        basis='ITR-4 Schedule BP financial particulars (limited disclosures)'
    else:
        bs=node.get('PARTA_BS')
        if not isinstance(bs,dict):raise ValueError('PARTA_BS missing: cannot calculate assets and liabilities.')
        fund='PropFund' if key=='ITR3' else 'PartnerOrMemberFund'
        eq='TotPropFund' if key=='ITR3' else 'TotPartnerOrMemberFund'
        items=[
            ('Asset','Fixed assets (net block and capital WIP)',amount(bs,'FundApply','FixedAsset','TotFixedAsset')),
            ('Asset','Investments',amount(bs,'FundApply','Investments','TotInvestments')),
            ('Asset','Current assets',amount(bs,'FundApply','CurrAssetLoanAdv','CurrAsset','TotCurrAsset')),
            ('Asset','Loans and advances given',amount(bs,'FundApply','CurrAssetLoanAdv','LoanAdv','TotLoanAdv')),
            ('Liability','Secured and unsecured loans',amount(bs,'FundSrc','LoanFunds','TotLoanFund')),
            ('Liability','Current liabilities and provisions',amount(bs,'FundApply','CurrAssetLoanAdv','CurrLiabilitiesProv','TotCurrLiabilitiesProvision')),
            ('Liability','Deferred tax liability',amount(bs,'FundSrc','DeferredTax')),
            ('Liability','Advances received (sources of funds)',amount(bs,'FundSrc','Advances','TotalAdvances')),
        ]
        proprietor=amount(bs,'FundSrc',fund,eq)
        sources=amount(bs,'FundSrc','TotFundSrc')
        application=amount(bs,'FundApply','TotFundApply')
        misc=amount(bs,'FundApply','MiscAdjust','TotMiscAdjust')
        pan=node.get('PartA_GEN1',{}).get('PersonalInfo' if key=='ITR3' else 'OrgFirmInfo',{}).get('PAN','')
        basis='ITR-'+key[-1]+' Part A-BS'
    assets=sum((v for cat,_,v in items if cat=='Asset'),Decimal(0))
    liabilities=sum((v for cat,_,v in items if cat=='Liability'),Decimal(0))
    net=assets-liabilities
    reconciled=net+misc
    errors=[]
    if sources!=application:errors.append('Total sources of funds do not match total application of funds.')
    if assets!=application and key=='ITR4':errors.append('ITR-4 total assets do not match sum of asset details.')
    if reconciled!=proprietor:errors.append('Assets - liabilities + miscellaneous debit balances do not match reported owner/partner capital.')
    year=node.get('Form_'+key,{}).get('AssessmentYear','')
    ay=f'{year}-{(int(year)+1)%100:02d}' if str(year).isdigit() and len(str(year))==4 else ''
    if not ay:errors.append('Assessment year not identified.')
    if key in ('ITR3','ITR5') and assets==0 and liabilities==0 and proprietor==0:
        errors.append('Zero-filled regular-books balance sheet: no reliable net worth can be certified from these fields.')
    return dict(items=items,assets=assets,liabilities=liabilities,net=net,misc=misc,
                reconciled=reconciled,proprietor=proprietor,errors=errors,ay=ay,
                source=str(path),pan=pan,form='ITR-'+key[-1],basis=basis)

def v45_extract_pdf_balance_sheet(path):
    """Extract explicitly labelled ITR-3 Part A-BS totals, not arbitrary PDF amounts."""
    with fitz.open(path) as pdf:
        pages=[page.get_text('text',sort=True) for page in pdf]
    whole='\n'.join(pages)
    start=re.search(r'PART\s*A\s*[-–]?\s*BS\s*[-–]?\s*BALANCE\s*SHEET',whole,re.I)
    if not start:raise ValueError('ITR-3 PART A-BS balance sheet not found in searchable PDF. Upload the complete ITR-3 form, not only its acknowledgement.')
    section=whole[start.end():]
    # Stop at the next ITR schedule to avoid accidentally using other balance sheets.
    stop=re.search(r'\n\s*PART\s*A\s*[-–]?\s*(?:P\s*&\s*L|P&L|OI)\b',section,re.I)
    if stop:section=section[:stop.start()]
    # Page headers/footers can appear between labels; anchor the specific row and its printed field code.
    def val(label, code, required=True, subsection=None):
        matches=[]
        for line in (section[section.find(subsection):] if subsection and subsection in section else section).splitlines():
            line=' '.join(line.split())
            if re.search(label,line,re.I):
                m=re.search(r'(?<!\w)'+re.escape(code)+r'\s+(-?[\d,]+(?:\.\d+)?)\s*$',line,re.I)
                if m:matches.append(Decimal(m.group(1).replace(',','')))
        if len(matches)!=1:
            if not required and not matches:return Decimal(0)
            raise ValueError('Cannot uniquely identify '+label+' (code '+code+') in ITR-3 Part A-BS PDF. Found '+str(len(matches))+'. Please check the original PDF.')
        return matches[0]
    items=[
      ('Asset','Fixed assets (net block and capital WIP)',val(r'^.*Total\s*\(1c\s*\+\s*1d\s*\)', '1e')),
      ('Asset','Investments',val(r'Total investments\s*\(', '2c')),
      ('Asset','Current assets',val(r'Total current assets\s*\(', 'av')),
      ('Asset','Loans and advances given',val(r'Total\s*\(bi\s*\+\s*bii\s*\+\s*biii\s*\)', 'biv', subsection='Current assets, loans and advances')),
      ('Liability','Secured and unsecured loans',val(r'Total Loan Funds\s*\(', '2c')),
      ('Liability','Current liabilities and provisions',val(r'Total\s*\(iE\s*\+\s*iiD\s*\)', 'diii')),
      ('Liability','Deferred tax liability',val(r'Deferred tax liability', '3')),
      ('Liability','Advances received (sources of funds)',val(r'Total Advances\s*\(', '4iii')),
    ]
    assets=sum((x[2] for x in items if x[0]=='Asset'),Decimal(0))
    liabilities=sum((x[2] for x in items if x[0]=='Liability'),Decimal(0))
    proprietor=val(r'Total proprietor.s fund\s*\(', '1c')
    sources=val(r'Sources of funds\s*\(', '5')
    application=val(r'Total, application of funds\s*\(', '5')
    misc=val(r'Total\s*\(4a\s*\+\s*4b\s*\+\s*4c\s*\)', '4d')
    ay_match=re.search(r'Assessment\s*Year\s*[:\-]?\s*(20\d{2}\s*[-–]\s*\d{2,4})',whole,re.I)
    ay=ay_match.group(1).replace(' ','') if ay_match else ''
    if not ay:
        fy=re.search(r'BALANCE SHEET AS ON 31ST DAY OF MARCH,?\s*(20\d{2})',whole,re.I)
        if fy:ay=f'{int(fy.group(1))}-{(int(fy.group(1))+1)%100:02d}'
    pan_match=re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',whole)
    net=assets-liabilities
    errors=[]
    if sources!=application:errors.append('Sources of funds differ from application of funds.')
    if net-misc!=proprietor:errors.append('Assets less liabilities and miscellaneous balances do not match proprietor fund.')
    return dict(items=items,assets=assets,liabilities=liabilities,net=net,misc=misc,reconciled=net-misc,
      proprietor=proprietor,errors=errors,ay=ay,source=str(path),pan=pan_match.group(0) if pan_match else '',format='PDF',form='ITR-3',basis='ITR-3 PDF Part A-BS')

def v43_import_bs(self):
    path,_=QFileDialog.getOpenFileName(self,'Import ITR-3/4/5 JSON or ITR-3 PDF balance sheet','','ITR PDF or JSON (*.pdf *.json)')
    if not path:return
    try:
        result=v45_extract_pdf_balance_sheet(path) if path.lower().endswith('.pdf') else v43_extract_balance_sheet(path)
        if result['errors']:raise ValueError('\n'.join(result['errors']))
        if self.client_id:
            saved=CON.execute('SELECT pan FROM clients WHERE id=?',(self.client_id,)).fetchone()
            if saved and saved[0] and result['pan'] and saved[0].upper()!=result['pan'].upper():
                raise ValueError('Selected client PAN differs from imported ITR PAN. Select correct client.')
        self.v43_result=result
        self.v43_table.setRowCount(0)
        for cat,label,value in result['items']:addrow(self.v43_table,[cat,label,str(value)])
        self.v43_misc.setText(str(result['misc']))
        self.v43_status.setText('Imported '+result['ay']+' | Business net worth: ₹'+money(result['reconciled'])+' | Reconciled to owner / partner capital')
        self.v43_recalculate()
    except Exception as e:QMessageBox.critical(self,'ITR balance sheet import',str(e))

def v43_recalculate(self):
    try:
        a,l,n=self.v43_totals()
        misc=dec(self.v43_misc.text())
        equity=n+misc
        self.v43_status.setText('Assets ₹'+money(a)+'  −  Liabilities ₹'+money(l)+'  =  ₹'+money(n)+'  | Less miscellaneous debit balances ₹'+money(misc)+'  | Adjusted business equity ₹'+money(equity))
        if self.v43_result:
            ref=self.v43_result['proprietor']
            self.v43_check.setText(('MATCH' if equity==ref else 'MISMATCH')+' with ITR owner / partner capital ₹'+money(ref))
        return a,l,n,equity
    except Exception as e:QMessageBox.warning(self,'Check entries',str(e));return None

def v43_totals(self):
    a=l=Decimal(0)
    for i in range(self.v43_table.rowCount()):
        cat=cell(self.v43_table,i,0).strip().lower()
        raw=cell(self.v43_table,i,2).replace(',','').strip()
        if not raw:raise ValueError('Blank amount on row '+str(i+1))
        value=Decimal(raw)
        if cat=='asset':a+=value
        elif cat=='liability':l+=value
        else:raise ValueError('Category must be Asset or Liability on row '+str(i+1))
    return a,l,a-l

def v43_apply(self):
    result=self.v43_recalculate()
    if result is None:return
    a,l,n,equity=result
    if not self.v43_result:return QMessageBox.warning(self,'Import first','Import an ITR-3/4/5 JSON or ITR-3 PDF first.')
    if equity!=self.v43_result['proprietor']:
        return QMessageBox.warning(self,'Reconciliation mismatch','Reconcile edited figures with the ITR reported owner / partner capital before applying.')
    self.cert_capital.setText(str(equity));self.cert_reserve.setText('0');self.cert_losses.setText('0');self.cert_net.setText(str(equity))
    if self.v43_result.get('ay'):
        yr=int(str(self.v43_result['ay'])[:4])-1
        self.cert_date.setText(f'31-03-{yr+1}')
    self.criteria.setCurrentText('Net worth computed as total assets less outside liabilities as per accompanying statement')
    if hasattr(self,'v44_method'):self.v44_method.setCurrentIndex(1)
    self.tabs.setCurrentIndex(2)
    QMessageBox.information(self,'Applied to certificate','Reconciled BUSINESS net worth applied to certificate fields. Confirm certificate scope and evidence before issuance. This is not total personal net worth.')

def v43_export_schedule(self):
    result=self.v43_recalculate()
    if result is None:return
    a,l,n,equity=result
    try:
        doc=Document();sec=doc.sections[0];sec.top_margin=Inches(.65);sec.bottom_margin=Inches(.65)
        style=doc.styles['Normal'];style.font.name='Calibri';style.font.size=Pt(10)
        p=doc.add_paragraph('STATEMENT OF BUSINESS ASSETS AND LIABILITIES');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.runs[0].bold=True
        if self.v43_result:doc.add_paragraph('Assessment Year: '+self.v43_result['ay']+' | Source: '+self.v43_result.get('basis','ITR-3 PDF Part A-BS'))
        t=doc.add_table(rows=1,cols=3);t.style='Light Shading Accent 1'
        for c,s in zip(t.rows[0].cells,['Category','Particulars','Amount (₹)']):c.text=s
        for i in range(self.v43_table.rowCount()):
            c=t.add_row().cells
            for j in range(3):c[j].text=money(cell(self.v43_table,i,j)) if j==2 else cell(self.v43_table,i,j)
        for label,amount in [('Total assets',a),('Total liabilities',l),('Assets less liabilities',n),('Add: Miscellaneous debit balances for equity reconciliation',dec(self.v43_misc.text())),('Adjusted business equity',equity)]:
            c=t.add_row().cells;c[1].text=label;c[2].text=money(amount)
        doc.add_paragraph('Source: taxpayer-supplied ITR-3/4/5 JSON or ITR-3 PDF. Values are editable and must be verified with books and supporting evidence. This working statement is NOT an assurance certificate or total personal net worth.')
        path,_=QFileDialog.getSaveFileName(self,'Save supporting schedule','Business_Net_Worth_Working.docx','Word (*.docx)')
        if path:doc.save(path);QMessageBox.information(self,'Saved','Word working statement saved successfully.')
    except Exception as e:QMessageBox.critical(self,'Word export',str(e))

def v43_init(self):
    _v43_prior_init(self)
    page=QWidget();layout=QVBoxLayout(page)
    info=QLabel('ITR-3 / ITR-4 / ITR-5 • Business assets less outside liabilities (NOT automatically personal net worth). Import JSON for all forms; PDF for ITR-3. Review and reconcile before applying.');info.setWordWrap(True);layout.addWidget(info)
    btn=QPushButton('Import ITR-3 / ITR-4 / ITR-5 JSON (or ITR-3 PDF)');btn.clicked.connect(lambda:self.v43_import_bs());layout.addWidget(btn)
    self.v43_table=table(['Category (Asset / Liability)','Particulars','Amount (₹)']);self.v43_table.setMinimumHeight(330);layout.addWidget(self.v43_table)
    line=QHBoxLayout();line.addWidget(QLabel('Miscellaneous debit balances / accumulated losses (add for equity reconciliation):'))
    self.v43_misc=QLineEdit('0');line.addWidget(self.v43_misc);layout.addLayout(line)
    self.v43_status=QLabel('Import ITR-3/4/5 JSON or ITR-3 PDF to begin.');self.v43_status.setWordWrap(True);layout.addWidget(self.v43_status)
    self.v43_check=QLabel('Reconciliation not yet performed');layout.addWidget(self.v43_check)
    line=QHBoxLayout()
    for label,fn in [('Add row',lambda:addrow(self.v43_table,['Asset','Other asset','0'])),('Remove selected row',lambda:self.v43_table.removeRow(self.v43_table.currentRow()) if self.v43_table.currentRow()>=0 else None),('Recalculate',lambda:self.v43_recalculate()),('Apply to certificate',lambda:self.v43_apply()),('Export Word working',lambda:self.v43_export_schedule())]:
        b=QPushButton(label);b.clicked.connect(fn);line.addWidget(b)
    layout.addLayout(line)
    layout.addWidget(QLabel('Note: For personal net worth, add personal property, investments, loans and other items outside business. Verify valuations and ownership.'))
    self.v43_result=None
    self.tabs.insertTab(3,page,'Assets − Liabilities')
    self.setWindowTitle('Smart Certifictes V43 — Assets Less Liabilities')
Main.v43_import_bs=v43_import_bs
Main.v43_totals=v43_totals
Main.v43_recalculate=v43_recalculate
Main.v43_apply=v43_apply
Main.v43_export_schedule=v43_export_schedule
_v43_prior_init=Main.__init__
Main.__init__=v43_init


# V44: explicit selection of net-worth computation method, kept for both net-worth certificate types.
def v44_method_changed(self,index):
    if index==0:
        self.criteria.setCurrentText('Owner / partner capital as per ITR financial particulars (business equity only; subject to reconciliation)')
        self.procedures.setCurrentText('Examined the relevant ITR financial particulars, owner / partner capital and applicable adjustments; reconciled reported business equity.')
        if self.client_id and self.nw_ay.count():self.load_selected_networth()
    else:
        self.criteria.setCurrentText('Net worth computed as total assets less outside liabilities as per accompanying statement')
        self.procedures.setCurrentText('Examined supporting asset and liability records, verified the arithmetic and agreed the net worth computation to the accompanying statement.')
        if getattr(self,'v43_result',None):
            totals=self.v43_recalculate()
            if totals:
                a,l,n,equity=totals
                self.cert_capital.setText(str(equity));self.cert_reserve.setText('0');self.cert_losses.setText('0');self.cert_net.setText(str(equity))

def v44_init(self):
    _v44_prior_init(self)
    self.v44_method=QComboBox()
    self.v44_method.addItems(['Method 1 — Owner / Partner capital (ITR-3/4/5)','Method 2 — Total Assets − Outside Liabilities (ITR-3/4/5)'])
    self.v44_method.setToolTip('Choose the computation method for Net Worth and Turnover & Net Worth certificates.')
    layout=self.cert_type.parentWidget().layout()
    if layout is not None:
        position=layout.indexOf(self.cert_type)
        layout.insertWidget(position+1,QLabel('NET WORTH CERTIFICATE — CHOOSE CALCULATION METHOD'))
        layout.insertWidget(position+2,self.v44_method)
    self.v44_method.currentIndexChanged.connect(lambda i:self.v44_method_changed(i))
    self.cert_type.currentIndexChanged.connect(lambda *_:self.v44_method.setEnabled(self._cert_kind() in (2,3)))
    self.v44_method.setEnabled(self._cert_kind() in (2,3))
    self.setWindowTitle('Smart Certificates V50 — ITR-3/4/5 + Presumptive ITR-3')
Main.v44_method_changed=v44_method_changed
_v44_prior_init=Main.__init__
Main.__init__=v44_init

# V46: form-specific ITR-3 / ITR-4 / ITR-5 JSON extraction.
# Keep original identity/acknowledgement processing and overwrite only reliably parsed financials.
from itr_schema_parser import extract as _v46_schema_extract
_v46_original_json_extract = extract_itr_json
def extract_itr_json(path):
    result=_v46_original_json_extract(path)
    parsed=_v46_schema_extract(path)
    result.update({k:parsed[k] for k in ('form','ay','turnover','turnover_basis','networth','networth_basis')})
    result['accounting_method']={'ITR-3':'ITR-3 regular books / verify schedules',
                                  'ITR-4':'ITR-4 presumptive / verify 44AD or 44ADA',
                                  'ITR-5':'ITR-5 firm / entity books'}.get(parsed['form'],'Review manually')
    result['financial_warnings']=parsed['warnings']
    return result



# V51: guided certificate workspace. Financial extraction and Word generation remain unchanged.
def _v51_source_changed(self,*_):
    kind=self._cert_kind()
    self.v51_source.blockSignals(True)
    old=self.v51_source.currentText()
    self.v51_source.clear()
    if kind==0:
        self.v51_source.addItem('ITR acknowledgement / ITR PDF or JSON','ACK')
    elif kind==3:
        self.v51_source.addItem('ITR-3 / ITR-4 / ITR-5 JSON (business capital)','ITR')
    else:
        self.v51_source.addItem('ITR PDF / JSON — turnover from filed return','ITR')
        self.v51_source.addItem('GSTR-3B PDF — turnover from GST returns','GSTR-3B')
        self.v51_source.addItem('GSTR-1 PDF — turnover from GST returns','GSTR-1')
    index=self.v51_source.findText(old)
    self.v51_source.setCurrentIndex(index if index>=0 else 0)
    self.v51_source.blockSignals(False)
    self._v51_source_help()

def _v51_source_help(self,*_):
    source=self.v51_source.currentData()
    messages={
      'ACK':'Import filed ITR PDF / JSON, then load assessment years. For verification, separately confirm portal download and evidence.',
      'ITR':'Import ITR-3/4/5 JSON (or supported ITR PDF). Previously imported data is reused automatically for this client.',
      'GSTR-3B':'Import GSTR-3B PDFs for the relevant financial year; review missing months before certifying annual turnover.',
      'GSTR-1':'Import GSTR-1 PDFs for the relevant financial year; review missing months before certifying annual turnover.'}
    self.v51_help.setText(messages.get(source,''))
    self.v51_import.setText({'ACK':'Import ITR / acknowledgement','ITR':'Import ITR PDF / JSON','GSTR-3B':'Import GSTR-3B PDFs','GSTR-1':'Import GSTR-1 PDFs'}.get(source,'Import documents'))
    self.v51_reuse.setText('Use saved '+('ITR' if source in ('ITR','ACK') else source)+' data')

def _v51_import_here(self):
    source=self.v51_source.currentData()
    if source in ('ITR','ACK'):
        self.import_pdfs()
        if self.client_id:
            self.load_itr()
            if hasattr(self,'nw_ay'):self.load_selected_networth()
    elif source in ('GSTR-3B','GSTR-1'):
        self.gst_import(source)
    self._v51_reuse_saved(silent=True)

def _v51_reuse_saved(self,silent=False):
    if not self.client_id:
        if not silent:QMessageBox.warning(self,'Client required','Select or create a client first.')
        return
    source=self.v51_source.currentData()
    if source in ('ITR','ACK'):
        self.turnover_source.setCurrentIndex(0)
        self.fill_from_itr()
        if hasattr(self,'nw_ay'):self.load_selected_networth()
        if source=='ACK':self.populate_itr_downloads()
    else:
        self.turnover_source.setCurrentIndex(2 if source=='GSTR-3B' else 1)
        self.fetch_selected_turnover()
    if hasattr(self,'v31_gst_source'):self._v31_refresh_gst()

def _v51_defaults(self):
    # No invented engagement evidence, assurance level, recipient or UDIN.
    if not self.engagement_date.text().strip():self.engagement_date.setText(date.today().strftime('%d-%m-%Y'))
    if hasattr(self,'v31_date') and not self.v31_date.text().strip():self.v31_date.setText(date.today().strftime('%d-%m-%Y'))
    self.sync_cert_heading()
    source=self.v51_source.currentData()
    if source in ('ITR','ACK'):
        self.criteria.setCurrentText('Annual turnover as per ITR Schedule BP / Trading Account for the relevant assessment years' if self._cert_kind() in (1,2) else 'Owner / partner capital as per ITR financial particulars (business equity only; subject to reconciliation)')
        self.procedures.setCurrentText('Examined the filed ITR and relevant schedules and agreed the turnover figures to the accompanying statement.')
    elif source=='GSTR-3B':
        self.criteria.setCurrentText('Annual turnover as per GSTR-3B returns filed for the relevant financial years')
        self.procedures.setCurrentText('Examined the GSTR-3B returns for the stated periods and agreed the turnover figures to the accompanying statement.')
    elif source=='GSTR-1':
        self.criteria.setCurrentText('Annual turnover as per GSTR-1 returns filed for the relevant financial years')
        self.procedures.setCurrentText('Examined the GSTR-1 returns for the stated periods and reconciled the reported turnover to the accompanying statement.')
    self.refresh_certificate_colours()

def _v51_clear_form(self):
    if QMessageBox.question(self,'Clear certificate form','Clear current certificate inputs and working tables? Saved client and imported return records will NOT be deleted.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
    for w in (self.recipient,self.purpose,self.recipient_address,self.engagement_date,self.cert_ud,self.cert_basis,self.cert_net,self.cert_capital,self.cert_reserve,self.cert_losses):w.clear()
    self.fin_table.setRowCount(0)
    if hasattr(self,'itr_downloads'):self.itr_downloads.setRowCount(0)
    self.assurance.setCurrentIndex(0);self.check_evidence.setCurrentIndex(0)
    self.refresh_certificate_colours()

def _v51_reset_imports(self):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Select a client first.')
    options=['ITR records + saved JSON financials','GSTR-1 returns','GSTR-3B returns','All imported ITR and GST data']
    selection,ok=QInputDialog.getItem(self,'Remove imported records','Remove records for the selected client only:',options,0,False)
    if not ok:return
    if QMessageBox.warning(self,'Confirm removal','Permanently remove '+selection+' for the selected client? A database backup will be created first.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
    backup=ROOT/'backups'/('before_v51_reset_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sqlite3')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(str(backup)) as dest:CON.backup(dest)
    with CON:
        if selection.startswith('ITR') or selection.startswith('All'):
            for tbl in ('itr','itr_financials','itr_accounting_method','itr_status'):
                CON.execute('DELETE FROM '+tbl+' WHERE client_id=?',(self.client_id,))
        if selection.startswith('GSTR-1') or selection.startswith('All'):
            CON.execute('DELETE FROM gst_monthly WHERE client_id=? AND return_type=?',(self.client_id,'GSTR-1'))
        if selection.startswith('GSTR-3B') or selection.startswith('All'):
            CON.execute('DELETE FROM gst_monthly WHERE client_id=? AND return_type=?',(self.client_id,'GSTR-3B'))
    self.load_itr();self.fin_table.setRowCount(0)
    if hasattr(self,'v31_gst_source'):self._v31_refresh_gst()
    QMessageBox.information(self,'Records removed','Selected records removed. Backup saved at:\n'+str(backup))

def _v51_show_help(self):
    QMessageBox.information(self,'How to use Smart Certificates','1. Select and save client in Clients.\n2. Select certificate type above.\n3. Select ITR or GST as applicable.\n4. Import documents here OR click Use saved data.\n5. Review year-wise turnover, business capital and evidence.\n6. Fill recipient, purpose and address.\n7. Review & Generate Word Certificate.\n\nRefresh saved JSON financials: use ONLY when previously imported original JSON files need to be re-read.\nAdd financial year: manual row. Fetch turnover: populate from saved selected source.\n\nBusiness capital is not automatically personal net worth. CA verification is mandatory.')

def _v51_init(self):
    _v51_prior_init(self)
    layout=self.cert_layout
    self.v51_source=QComboBox()
    self.v51_help=QLabel();self.v51_help.setWordWrap(True)
    self.v51_help.setStyleSheet('background:#e9f2ff;padding:10px;color:#123b64;')
    self.v51_import=QPushButton('Import documents here')
    self.v51_reuse=QPushButton('Use already imported data')
    self.v51_import.clicked.connect(self._v51_import_here)
    self.v51_reuse.clicked.connect(lambda:self._v51_reuse_saved())
    guide=QGroupBox('DOCUMENTS — import or reuse without changing tabs')
    group=QVBoxLayout(guide)
    group.addWidget(QLabel('Choose evidence / certificate basis'))
    group.addWidget(self.v51_source);group.addWidget(self.v51_help)
    buttons=QHBoxLayout();buttons.addWidget(self.v51_import);buttons.addWidget(self.v51_reuse);group.addLayout(buttons)
    pos=layout.indexOf(self.cert_type)
    layout.insertWidget(pos+1,guide)
    self.v51_source.currentIndexChanged.connect(self._v51_source_help)
    self.cert_type.currentIndexChanged.connect(self._v51_source_changed)
    self._v51_source_changed()
    actions=QGroupBox('QUICK ACTIONS — defaults, help and data management')
    action_layout=QHBoxLayout(actions)
    for title,func in [('Fill safe defaults',self._v51_defaults),('Clear current form',self._v51_clear_form),('Remove imported records…',self._v51_reset_imports),('How to use',self._v51_show_help)]:
        btn=QPushButton(title);btn.clicked.connect(func);action_layout.addWidget(btn)
    layout.insertWidget(layout.indexOf(self.fin_table),actions)
    if hasattr(self,'v31_import'):self.v31_import.hide()
    if hasattr(self,'v31_suggestion'):self.v31_suggestion.hide()
    if hasattr(self,'_v40_json_refresh_button'):
        self._v40_json_refresh_button.setText('Advanced: Re-read original saved ITR JSON files')
        self._v40_json_refresh_button.setToolTip('Only needed if source JSON changed or was imported using an older version; requires original file paths.')
    for b in self.findChildren(QPushButton):
        if b.text()=='Preview & Edit Certificate':b.hide()  # The final Review & Generate button opens the same editor.
    self.setWindowTitle('Smart Certificates V51 — Guided Certificate Workspace')

Main._v51_source_changed=_v51_source_changed
Main._v51_source_help=_v51_source_help
Main._v51_import_here=_v51_import_here
Main._v51_reuse_saved=_v51_reuse_saved
Main._v51_defaults=_v51_defaults
Main._v51_clear_form=_v51_clear_form
Main._v51_reset_imports=_v51_reset_imports
Main._v51_show_help=_v51_show_help
_v51_prior_init=Main.__init__
Main.__init__=_v51_init


# V53 — User-friendly workflow layer over V51. No financial parser modifications.
from PyQt6.QtWidgets import QFrame

_V53_INIT_BEFORE = Main.__init__
def _v53_init(self):
    _V53_INIT_BEFORE(self)
    self._v53_setup()
Main.__init__ = _v53_init

def _v53_page(self, title):
    for i in range(self.tabs.count()):
        if self.tabs.tabText(i)==title:return self.tabs.widget(i)
    return None

def _v53_go(self, title, step=None):
    page=self._v53_page(title)
    if page is not None:self.tabs.setCurrentWidget(page)
    # Navigation is direct and unobtrusive; no step pop-ups.

def _v53_step_text(self,step):
    descriptions={
        1:'Select or create the client. Check PAN and business / trade name before importing records.',
        2:'Choose certificate type and ITR / GST source. Import the relevant PDF / JSON here or use saved data.',
        3:'For net worth based on assets less liabilities, import the ITR balance sheet, reconcile and Apply to certificate.',
        4:'Review year-wise turnover, total income, acknowledgements and filing dates. Never treat total income as turnover.',
        5:'Open Defaults & Certificate Generation. Fill safe defaults; confirm recipient, purpose, engagement evidence and UDIN before issuing.',
        6:'Review the Word document and generate the certificate. Then prepare the MRL if required.',
        7:'For ITR acknowledgement verification, load the saved acknowledgement details and confirm portal verification evidence.',
        8:'For GST turnover, import GSTR-1 / GSTR-3B for each relevant period, then review GST Turnover Summary.'}
    return descriptions.get(step,'Review the information and continue to the next step.')

def _v53_orange_button(self,layout,text,fn,step):
    b=QPushButton('STEP '+str(step)+'  •  '+text)
    b.setStyleSheet('QPushButton{background:#e87917;color:white;font-weight:bold;border-radius:6px;padding:12px;}QPushButton:hover{background:#c85e0a;}')
    b.setToolTip(self._v53_step_text(step))
    b.clicked.connect(fn)
    layout.addWidget(b)
    return b

def _v53_guide(self):
    page=self._v53_page('Clients')
    if page is None:return
    content=page.findChild(QScrollArea).widget()
    layout=content.layout()
    panel=QGroupBox('START HERE — Complete User Guide (all certificates)')
    v=QVBoxLayout(panel)
    info=QLabel("""<b>1. CLIENTS:</b> Create/select the correct client, PAN, entity type and business name; save the record.<br>
<b>2. CA PROFILE:</b> Select or save the issuing CA/signatory.<br>
<b>3. CERTIFICATE WORKSPACE:</b> Select Turnover, Net Worth, ITR Verification, or Combined certificate. Select source (ITR / GSTR-1 / GSTR-3B). Import here, or use already saved records.<br>
<b>4. ITR PDF IMPORT:</b> Use for ITR PDFs, JSON and acknowledgement records. Confirm AY, income, acknowledgement number and filing date. For verification, use “Load acknowledgement to certificate”.<br>
<b>5. ASSETS – LIABILITIES:</b> For net worth by assets less outside liabilities, import ITR-3/4/5 JSON (or supported ITR-3 PDF); review, recalculate, then Apply to certificate. Capital alone is not automatically personal net worth.<br>
<b>6. GST IMPORT:</b> Import GSTR-1 or GSTR-3B for each relevant month/quarter. Review missing periods. GST Turnover Summary reads already saved GST records; no duplicate import required.<br>
<b>7. FINANCIAL WORKING:</b> “Use saved data” retrieves previously imported information; “Fetch turnover” updates the year-wise working for the chosen source; “Add financial year” inserts a manual row; “Delete selected row” removes only the selected working row. “Advanced: Re-read original saved ITR JSON files” reprocesses original files if earlier imports need refreshing.<br>
<b>8. DEFAULTS & GENERATION:</b> Fill safe defaults; enter recipient, purpose and address; confirm engagement evidence, criteria, procedures, assurance and UDIN as applicable. Review & Generate Word Certificate; prepare MRL if needed.<br>
<b>9. RESET:</b> “Clear current form” clears unsaved working inputs only. “Remove imported records” deletes selected stored return types for the current client AFTER creating a database backup. “Backup SQLite Database” in Settings saves the full local database.<br>
<b>10. SETTINGS / DELETE CLIENT:</b> Review data location, create backup, or delete clients only when appropriate.<br><br>
<b>IMPORTANT:</b> This software does not access the Income Tax portal, GST portal or UDIN service automatically. All certification facts, source completeness, verification, and professional conclusions require CA review.""")
    info.setWordWrap(True);info.setTextFormat(Qt.TextFormat.RichText)
    info.setStyleSheet('background:#fff8eb;color:#4b3418;padding:14px;border:1px solid #f5c27c;')
    v.addWidget(info)
    self._v53_orange_button(v,'Continue to CA Profile',lambda:self._v53_go('CA Profile',1),1)
    layout.insertWidget(0,panel)

def _v53_move_range(self, source_layout, target_layout, first_widget, last_widget):
    # Move the contiguous layout items, including their labels, not just field widgets.
    first=source_layout.indexOf(first_widget);last=source_layout.indexOf(last_widget)
    if first<0 or last<first:raise RuntimeError('Certificate form controls not found for layout migration')
    for _ in range(last-first+1):
        item=source_layout.takeAt(first)
        if item.widget():target_layout.addWidget(item.widget())
        elif item.layout():target_layout.addLayout(item.layout())
        elif item.spacerItem():target_layout.addSpacerItem(item.spacerItem())

def _v53_setup(self):
    self.setWindowTitle('Smart Certificates V54 — Simplified Workflow')
    self._v54_guide_page()
    # Create a dedicated final-details page, moving the original widgets, so all
    # existing signals, validations and Word generation functions are preserved.
    layout=self.tab('Defaults & Certificate Generation')
    self._v53_final_layout=layout
    header=QLabel('CERTIFICATE DETAILS, REVIEW & GENERATION')
    header.setStyleSheet('background:#fff1d8;color:#934400;padding:12px;font-weight:bold;')
    layout.addWidget(header)
    self.btn(layout,'Fill safe defaults',self._v51_defaults)
    self.btn(layout,'Clear current form (does not delete imports)',self._v51_clear_form)
    layout.addWidget(QLabel('Complete and review the recipient, purpose, address, engagement and assurance details below.'))
    original=self.cert_layout
    # Move from Issued To label to Evidence and engagement review combo, including
    # all associated labels and fields. The original object references remain valid.
    idx=original.indexOf(self.recipient)
    first=original.itemAt(idx-1).widget() if idx>0 else self.recipient
    self._v53_move_range(original,layout,first,self.check_evidence)
    # Move existing Review & Generate and MRL buttons from the original workspace.
    for button in list(self.findChildren(QPushButton)):
        if button.text() in ('Review & Generate Word Certificate','Generate Word Certificate','Prepare Management Representation Letter'):
            p=original.indexOf(button)
            if p>=0:
                original.removeWidget(button)
                layout.addWidget(button)
                button.show()
    self.btn(layout,'Back to Certificate Workspace',lambda:self._v53_go('Certificate Workspace'))
    # Rename ITR import and provide a one-click return to certificate workspace.
    itr=self._v53_page('Step 1 • Import ITR PDF')
    if itr:
        self.tabs.setTabText(self.tabs.indexOf(itr),'Import ITR PDF')
        v=itr.findChild(QScrollArea).widget().layout()
        self.btn(v,'Load imported ITR / ACK to certificate',self._v53_load_ack)
    # The GST summary must follow the GSTR-3B import tab.
    titles=['User Guide','Clients','CA Profile','Certificate Workspace','Defaults & Certificate Generation',
            'Import ITR PDF','Assets − Liabilities','GSTR-1 Import','GSTR-3B Import / Edit',
            'GST Turnover Summary','Management Representation','Settings','Delete Clients']
    # Existing labels differ across earlier revisions; map without destroying tabs.
    for i in range(self.tabs.count()):
        if self.tabs.tabText(i)=='GST Turnover':self.tabs.setTabText(i,'GST Turnover Summary')
        if self.tabs.tabText(i)=='Management Representation':self.tabs.setTabText(i,'Management Representation')
    for position,name in enumerate(titles):
        page=self._v53_page(name)
        if page is None:continue
        old=self.tabs.indexOf(page)
        if old!=position:
            self.tabs.removeTab(old);self.tabs.insertTab(position,page,name)
    # Tab indices changed; use current location for the old MRL button callback.
    page=self._v53_page('Management Representation')
    if page:self.representation_tab_index=self.tabs.indexOf(page)
    # Direct access to a contextual next-step prompt, without forcing users to hunt.
    self.tabs.setCurrentWidget(self._v53_page('User Guide'))

def _v53_load_ack(self):
    if not self.client_id:return QMessageBox.warning(self,'Select client','Select a client first.')
    self.cert_type.setCurrentIndex(2)
    self._v34_load_itr_acknowledgements()
    self._v53_go('Certificate Workspace',7)

def _v53_add_navigation(self):
    # Existing import functions stay in place; step buttons route to the correct tab.
    routes=[('Assets − Liabilities','Recalculate / Apply net worth then return to certificate',
             lambda:self._v53_go('Certificate Workspace',4),3),
            ('GSTR-1 Import','Next: Review GST Turnover Summary',lambda:self._v53_sync_gst(),8),
            ('GSTR-3B Import / Edit','Next: Review GST Turnover Summary',lambda:self._v53_sync_gst(),8),
            ('GST Turnover Summary','Use saved GST turnover in certificate',lambda:self._v53_apply_gst(),4)]
    for name,caption,fn,step in routes:
        page=self._v53_page(name)
        if page:
            scroll=page.findChild(QScrollArea)
            v=scroll.widget().layout() if scroll else page.layout()
            self._v53_orange_button(v,caption,fn,step)

def _v53_sync_gst(self):
    self._v31_refresh_gst()
    self._v53_go('GST Turnover Summary',8)

def _v53_apply_gst(self):
    self._v31_fetch_gst()
    self._v53_go('Certificate Workspace',4)

def _v54_select_networth_ay(self,ay):
    """Keep the net-worth assessment-year selector in sync with a newly imported ITR."""
    self._v54_last_imported_ay=ay
    if not getattr(self,'client_id',None) or not hasattr(self,'nw_ay'):return
    years=[r[0] for r in CON.execute('SELECT DISTINCT ay FROM itr WHERE client_id=? ORDER BY ay',(self.client_id,)) if r[0]]
    self.nw_ay.blockSignals(True)
    self.nw_ay.clear()
    for year in years:self.nw_ay.addItem(year,year)
    idx=self.nw_ay.findData(ay)
    if idx>=0:self.nw_ay.setCurrentIndex(idx)
    self.nw_ay.blockSignals(False)
    if idx>=0 and (not hasattr(self,'v44_method') or self.v44_method.currentIndex()==0):
        self.load_selected_networth()

def _v54_guide_page(self):
    """Independent first tab, leaving client data entry uncluttered."""
    layout=self.tab('User Guide')
    heading=QLabel('SMART CERTIFICATES — COMPLETE USER GUIDE')
    heading.setStyleSheet('font-size:19px;font-weight:bold;color:#174b79;padding:12px;')
    layout.addWidget(heading)
    guide=QLabel("""<b>1. CLIENTS:</b> Create or select a client. Check the full legal name, business name, PAN and entity type. Save.<br><br>
<b>2. CA PROFILE:</b> Select or add the CA signing the certificate.<br><br>
<b>3. CERTIFICATE WORKSPACE:</b> Choose Turnover, Net Worth, Combined, or ITR Acknowledgement Verification. Select ITR, GSTR-1 or GSTR-3B as applicable. Import PDF/JSON or reuse saved data.<br><br>
<b>4. ITR IMPORT:</b> Import ITR-3/4/5 JSON or supported PDF. Check assessment year, total income, acknowledgement number, date of filing and turnover. Importing a newer ITR automatically selects its assessment year for net worth.<br><br>
<b>5. NET WORTH:</b> Method 1 uses owner/partner capital from the return. Method 2 uses assets minus outside liabilities: open Assets – Liabilities, import the balance-sheet JSON, review/recalculate and apply. Business equity is not automatically personal net worth.<br><br>
<b>6. GST:</b> Import GSTR-1 or GSTR-3B for each applicable period. Review GST Turnover Summary and period completeness. Use saved GST data in Certificate Workspace; do not double-count periods.<br><br>
<b>7. FINANCIAL-YEAR BUTTONS:</b> Use saved ITR data loads the imported figures. Fetch turnover from selected source updates the year-wise table. Add financial year creates a manual row. Delete selected row removes only that working row. Advanced re-read JSON is needed only when previously saved JSON source files must be reprocessed.<br><br>
<b>8. DEFAULTS & CERTIFICATE GENERATION:</b> Fill safe defaults, complete recipient/purpose/address and confirm the engagement, procedures, evidence, assurance and UDIN. Review and generate the Word certificate and Management Representation Letter (MRL).<br><br>
<b>9. RESET:</b> Clear current form resets the unsaved certificate working fields, not stored returns. Remove imported records permanently deletes the chosen stored data for the selected client after backup. Back up the database in Settings before major changes.<br><br>
<b>10. IMPORTANT:</b> The software does not automatically verify portal filing status, authenticity, professional evidence or UDIN. A CA must review all inputs before issuing a certificate.""")
    guide.setWordWrap(True)
    guide.setTextFormat(Qt.TextFormat.RichText)
    guide.setStyleSheet('background:#f0f6fc;color:#23374d;padding:18px;border:1px solid #c5d9ed;')
    layout.addWidget(guide)
    self.btn(layout,'Open Clients',lambda:self._v53_go('Clients'))

Main._v54_select_networth_ay=_v54_select_networth_ay
Main._v54_guide_page=_v54_guide_page

Main._v53_page=_v53_page
Main._v53_go=_v53_go
Main._v53_step_text=_v53_step_text
Main._v53_orange_button=_v53_orange_button
Main._v53_guide=_v53_guide
Main._v53_move_range=_v53_move_range
Main._v53_setup=_v53_setup
Main._v53_load_ack=_v53_load_ack
Main._v53_add_navigation=_v53_add_navigation
Main._v53_sync_gst=_v53_sync_gst
Main._v53_apply_gst=_v53_apply_gst

if __name__=='__main__':
    app=QApplication(sys.argv);app.setStyle('Fusion');win=Main();win.show();sys.exit(app.exec())
