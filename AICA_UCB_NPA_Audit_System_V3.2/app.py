import streamlit as st, pandas as pd
from io import BytesIO
from datetime import date
from openpyxl.styles import Font, PatternFill, Alignment

st.set_page_config(page_title="UCB NPA Audit System V3.2",layout="wide")
st.title("UCB NPA Classification, Provisioning & Audit System – V3.2")
st.caption("Modular optional-upload architecture | RBI UCB IRAC Directions, 2025 and Amendment effective 01-Jul-2026")
st.warning("Audit-assistance prototype. Outputs depend on completeness and accuracy of uploaded CBS records. Auditor verification and applicable bank policy remain necessary.")
review=date.today()
with st.sidebar:
    review=st.date_input("Review date",value=review)
    st.write("2026 amendment:", "Applicable" if review>=date(2026,7,1) else "Not yet effective")

def n(x): return " ".join(str(x).lower().strip().replace("_"," ").replace("-"," ").split())
def mapcols(df, aliases):
    ren={}
    for std, al in aliases.items():
        for c in df.columns:
            if n(c) in [n(std)]+[n(a) for a in al]: ren[c]=std; break
    return df.rename(columns=ren)
def read(f): return pd.read_excel(f) if f else None
def outxlsx(sheets):
    b=BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w:
        for sn,d in sheets.items():
            d.to_excel(w,sheet_name=sn[:31],index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
            for c in ws[1]:
                c.font=Font(bold=True,color="FFFFFF"); c.fill=PatternFill("solid",fgColor="1F4E78")
                c.alignment=Alignment(wrap_text=True)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width=min(max(14,max(len(str(x.value or "")) for x in col[:100])+3),40)
    return b.getvalue()

aliases={
"Account No":["account number","a/c no","loan account no"],"Borrower Name":["customer name","party name"],
"Facility Type":["loan type","facility","product"],"Sanction Limit":["sanctioned limit","limit"],
"Outstanding":["outstanding balance","balance outstanding"],"System Classification":["asset classification","npa status","classification"],
"Drawing Power":["dp"],"DP Validity Date":["dp valid upto","dp expiry date"],"Renewal Due Date":["renewal date","limit expiry date"],
"Overdue Amount":["total overdue","amount overdue"],"DPD":["days past due","days overdue","overdue days"],
"CIF":["cif id","customer id","borrower id"],"NPA Date":["date of npa","npa classification date"],
"Asset Category":["npa category"],"Sector":["sector category"],"NPA Provision Held":["provision held","existing provision"]
}
st.header("1. Single consolidated input workbook")
st.caption("Upload ONE Excel workbook containing the tabs: Primary Loan Dump, Daily Position, Transactions, Security and NPA History. Supporting tabs may be blank only where the relevant test is genuinely not applicable.")
f=st.file_uploader("Upload complete UCB NPA input workbook (.xlsx)",type=["xlsx"])
if not f: st.info("Upload the consolidated input workbook. All supporting data is read from its worksheets."); st.stop()
book=pd.ExcelFile(f)
def sheet_by_name(candidates):
    for name in book.sheet_names:
        if n(name) in [n(x) for x in candidates]: return pd.read_excel(book,sheet_name=name)
    return None
raw=sheet_by_name(["Primary Loan Dump","Loan Dump","Loan Master","01 Loan Master"])
if raw is None: st.error("Missing required worksheet: Primary Loan Dump."); st.stop()
df=mapcols(raw,aliases); source_sheet="Primary Loan Dump"
if not all(c in df.columns for c in ["Account No","Borrower Name","Facility Type","Outstanding"]):
    st.error("Primary Loan Dump must contain Account No, Borrower Name, Facility Type and Outstanding."); st.stop()
if "System Classification" not in df.columns: df["System Classification"]="Unclassified"
for c in aliases:
    if c not in df: df[c]=pd.NA
for c in ["Sanction Limit","Outstanding","Drawing Power","Overdue Amount","DPD","NPA Provision Held"]:
    df[c]=pd.to_numeric(df[c].astype(str).str.replace(",","",regex=False).str.replace("₹","",regex=False),errors="coerce")
for c in ["DP Validity Date","Renewal Due Date","NPA Date"]:
    df[c]=pd.to_datetime(df[c],errors="coerce",dayfirst=True)
df["Account No"]=df["Account No"].fillna("").astype(str).str.strip()
df["CIF"]=df["CIF"].fillna("").astype(str).str.strip()
st.success(f"Recognised {source_sheet}: {len(df):,} rows")

st.header("2. Term Loan CBS overdue / DPD classification")
def tl(v):
    s=n(v)
    return s in ["tl","term","term loan"] or "term loan" in s
def cc(v):
    s=n(v).replace(" ","")
    return any(z in s for z in ["cc","cashcredit","od","overdraft"])
def tltest(r):
    if not tl(r["Facility Type"]): return "Not applicable"
    o,d=r["Overdue Amount"],r["DPD"]
    if pd.isna(o) or pd.isna(d): return "Data unavailable"
    if o<=0 and d<=0: return "No overdue reported"
    if o<=0 or d<=0: return "CBS data inconsistency"
    if d<=30:return "SMA-0"
    if d<=60:return "SMA-1"
    if d<=90:return "SMA-2"
    return "NPA trigger >90 DPD"
df["Term Loan DPD result"]=df.apply(tltest,axis=1)
tl_df=df[df["Term Loan DPD result"]!="Not applicable"]
if len(tl_df):
    st.dataframe(tl_df.groupby("Term Loan DPD result").agg(Accounts=("Account No","count"),Overdue=("Overdue Amount","sum")).reset_index(),use_container_width=True)
st.caption("DPD-based screening applies only to clearly identified Term Loans. Reconcile CBS DPD and overdue amount to day-end records; no repayment schedule upload is required for this screening.")

st.header("3. CC/OD 90-day out-of-order tests – optional uploads")
d=sheet_by_name(["Daily Position","CC OD Daily Position","02 CC OD Daily Position"])
t=sheet_by_name(["Transactions","CC OD Transactions","03 CC OD Transactions"])
ccrows=[]
if d is not None and len(d):
    d=mapcols(d,{"Account No":["account number","a/c no"],"Position Date":["date","as on date"],"Outstanding":["balance outstanding"],"Sanction Limit":["sanctioned limit","limit"],"Drawing Power":["dp"]})
    req=["Account No","Position Date","Outstanding","Sanction Limit","Drawing Power"]
    if all(c in d for c in req):
        d["Position Date"]=pd.to_datetime(d["Position Date"],errors="coerce",dayfirst=True)
        for c in req[2:]: d[c]=pd.to_numeric(d[c],errors="coerce")
        for a,g in d.dropna(subset=["Position Date"]).groupby("Account No"):
            g=g[g["Position Date"].dt.date<=review].sort_values("Position Date").tail(90)
            if len(g)<90: ccrows.append([a,"Not tested – fewer than 90 observations",len(g),"Obtain complete daily series"])
            else:
                ex=(g["Outstanding"]>g[["Sanction Limit","Drawing Power"]].min(axis=1)).all()
                ccrows.append([a,"Continuous excess indicator" if ex else "Continuous excess test not triggered",len(g),"Verify 90 consecutive calendar days and operative limit/DP"])
    else: st.error("Daily file missing one or more required columns.")
if t is not None and len(t):
    t=mapcols(t,{"Account No":["account number","a/c no"],"Transaction Date":["date","value date"],"Credit Amount":["credit","credits","deposit"],"Interest Debit":["interest debited","interest debit"]})
    if all(c in t for c in ["Account No","Transaction Date","Credit Amount"]):
        t["Transaction Date"]=pd.to_datetime(t["Transaction Date"],errors="coerce",dayfirst=True)
        t["Credit Amount"]=pd.to_numeric(t["Credit Amount"],errors="coerce").fillna(0)
        if "Interest Debit" in t: t["Interest Debit"]=pd.to_numeric(t["Interest Debit"],errors="coerce").fillna(0)
        t=t[t["Transaction Date"].dt.date.between((pd.Timestamp(review)-pd.Timedelta(days=89)).date(),review)]
        for a,g in t.groupby("Account No"):
            if g["Credit Amount"].sum()==0: ccrows.append([a,"No credits in uploaded period",len(g),"Confirm full 90-day transaction coverage"])
            elif "Interest Debit" in g and g["Credit Amount"].sum()<g["Interest Debit"].sum(): ccrows.append([a,"Credits below interest debited",len(g),"Verify completeness and 90-day inclusive period"])
    else: st.warning("Transaction file needs Account No, Transaction Date and Credit Amount; Interest Debit is needed for interest-coverage test.")
cc_df=pd.DataFrame(ccrows,columns=["Account No","CC/OD indicator","Records","Audit verification"])
if len(cc_df): st.dataframe(cc_df,use_container_width=True)
else: st.info("CC/OD out-of-order assessment not tested without optional complete 90-day daily-position and transaction history.")

st.header("4. Borrower-wise consolidation – optional CIF")
if df["CIF"].ne("").any():
    borrower=df.groupby("CIF").agg(Borrower=("Borrower Name","first"),Facilities=("Account No","count"),Outstanding=("Outstanding","sum"),CBS_Classification=("System Classification",lambda x:" | ".join(sorted(set(x.dropna().astype(str)))))).reset_index()
    st.dataframe(borrower,use_container_width=True)
    st.caption("CIF consolidation shown as a screening view. Facility-level NPA status and borrower-level classification must be validated under the applicable RBI borrower-wise rules and exceptions.")
else:
    borrower=pd.DataFrame(columns=["CIF","Borrower","Facilities","Outstanding","CBS_Classification"])
    st.info("Not tested: reliable CIF/customer ID not supplied. Borrower name is not used as a unique key.")

st.header("5. NPA ageing, security and provisioning – optional inputs")
sec=sheet_by_name(["Security","Security Valuation","04 Security Valuation"])
hist=sheet_by_name(["NPA History","05 NPA History"])
sec=pd.DataFrame() if sec is None else sec.copy(); hist=pd.DataFrame() if hist is None else hist.copy()
if len(sec):
    sec=mapcols(sec,{"Account No":["account number","a/c no"],"Realisable Value":["security value","net realisable value"],"Valuation Date":["date of valuation"]})
    if "Realisable Value" in sec: sec["Realisable Value"]=pd.to_numeric(sec["Realisable Value"],errors="coerce")
    st.dataframe(sec,use_container_width=True)
if len(hist):
    hist=mapcols(hist,{"Account No":["account number","a/c no"],"NPA Date":["date of npa"],"Asset Category":["npa category"],"Provision Held":["existing provision"]})
    if "NPA Date" in hist:
        hist["NPA Date"]=pd.to_datetime(hist["NPA Date"],errors="coerce",dayfirst=True)
        hist["NPA Age Days"]=(pd.Timestamp(review)-hist["NPA Date"]).dt.days
        hist["NPA Age Years"]=hist["NPA Age Days"]/365.25
    st.dataframe(hist,use_container_width=True)

st.subheader("Indicative provision calculations")
st.caption("Doubtful provisions use uploaded security realisable value and NPA date. This is an audit-assistance calculation; validate security eligibility, valuation, guarantees, special cases and RBI amendments before booking.")
rates={"Direct agriculture / SME":0.0025,"CRE":0.01,"CRE-RH":0.0075,"Other advances":0.004}
# Prepare one security value per account; if duplicate rows exist, use latest valuation date.
sec_lookup={}
if len(sec) and "Account No" in sec and "Realisable Value" in sec:
    sx=sec.copy()
    sx["Account No"]=sx["Account No"].astype(str).str.strip()
    if "Valuation Date" in sx:
        sx["Valuation Date"]=pd.to_datetime(sx["Valuation Date"],errors="coerce",dayfirst=True)
        sx=sx.sort_values("Valuation Date")
    for _,sr in sx.dropna(subset=["Account No"]).iterrows():
        if pd.notna(sr["Realisable Value"]):
            sec_lookup[str(sr["Account No"])]=max(0,float(sr["Realisable Value"]))
# NPA history supplies prior NPA date/category where the primary dump does not.
hist_lookup={}
if len(hist) and "Account No" in hist:
    hx=hist.copy()
    hx["Account No"]=hx["Account No"].astype(str).str.strip()
    for _,hr in hx.iterrows():
        hist_lookup[str(hr["Account No"])]=hr
prov=[]
for _,r in df.iterrows():
    cl=str(r["System Classification"]).strip().lower()
    amt=r["Outstanding"]
    if pd.isna(amt): continue
    acc=str(r["Account No"]).strip()
    npa_date=r.get("NPA Date")
    category="" if pd.isna(r.get("Asset Category")) else str(r.get("Asset Category")).strip()
    if acc in hist_lookup:
        hr=hist_lookup[acc]
        if pd.isna(npa_date) and pd.notna(hr.get("NPA Date")): npa_date=pd.to_datetime(hr.get("NPA Date"),errors="coerce")
        if not category and pd.notna(hr.get("Asset Category")): category=str(hr.get("Asset Category"))
    security=min(float(amt),sec_lookup.get(acc,0.0))
    unsecured=max(0.0,float(amt)-security)
    if "loss" in cl or category.lower()=="loss":
        rate=1.0; amount=float(amt); bucket="Loss"
        basis="Para 79: 100% of outstanding (subject to eligible special treatment)"
    elif "doubtful" in cl or category.lower()=="doubtful":
        if pd.isna(npa_date):
            bucket="Doubtful – ageing unavailable"; amount=None; rate=None
            basis="NPA date required to determine doubtful period; no provision computed"
        else:
            doubtful_from=pd.Timestamp(npa_date)+pd.DateOffset(months=12)
            yrs=max(0,(pd.Timestamp(review)-doubtful_from).days/365.25)
            if yrs<=1: bucket="D1"; secured_rate=.20
            elif yrs<=3: bucket="D2"; secured_rate=.30
            else: bucket="D3"; secured_rate=1.00
            amount=security*secured_rate+unsecured*1.00
            rate=None
            basis=f"Paras 75-77: secured {secured_rate:.0%} + unsecured 100%; security value from upload"
        prov.append([acc,bucket,float(amt),security,unsecured,rate,amount,basis])
        continue
    elif "substandard" in cl or category.lower()=="substandard":
        rate=.10; amount=float(amt)*rate; bucket="Substandard"
        basis="Para 74: 10% of total outstanding; no security/guarantee deduction"
    elif "standard" in cl or cl=="std":
        sector=str(r["Sector"]).upper()
        cat="Direct agriculture / SME" if ("AGRI" in sector or "SME" in sector) else ("CRE-RH" if "CRE-RH" in sector else ("CRE" if "CRE" in sector else "Other advances"))
        rate=rates[cat]; amount=float(amt)*rate; bucket="Standard – "+cat
        basis="Para 70; verify sector tagging and eligible exposure base"
    else:
        bucket="Unclassified / review"; rate=None; amount=None
        basis="Classification not mapped; manual review required"
    prov.append([acc,bucket,float(amt),security,unsecured,rate,amount,basis])
prov_df=pd.DataFrame(prov,columns=["Account No","Calculated Category / Doubtful Bucket","Outstanding","Realisable Security","Unsecured Portion","Provision Rate (where single rate)","Indicative Provision","Calculation basis / control"])
st.dataframe(prov_df,use_container_width=True)
st.header("6. Audit exceptions")
exc=[]
for _,r in df.iterrows():
    if r["Term Loan DPD result"]=="NPA trigger >90 DPD" and ("standard" in str(r["System Classification"]).lower() or "sma" in str(r["System Classification"]).lower()):
        exc.append([r["Account No"],r["Borrower Name"],"Term Loan DPD >90 vs Standard/SMA CBS classification","Critical","Reconcile overdue ageing, day-end tag, borrower-wise status and permitted exceptions"])
    if pd.notna(r["Outstanding"]) and pd.notna(r["Drawing Power"]) and r["Outstanding"]>r["Drawing Power"]:
        exc.append([r["Account No"],r["Borrower Name"],"Outstanding exceeds point-in-time DP","High","Not by itself NPA; obtain CC/OD 90-day record"])
    if pd.notna(r["Renewal Due Date"]) and r["Renewal Due Date"].date()<review:
        exc.append([r["Account No"],r["Borrower Name"],"Renewal due date passed","High","Verify actual review/renewal within 90 days; date alone is not NPA"])
exc_df=pd.DataFrame(exc,columns=["Account No","Borrower Name","Exception","Priority","Auditor action"])
st.dataframe(exc_df,use_container_width=True)

summary=pd.DataFrame([["Review date",str(review)],["Source worksheet",source_sheet],["Loan rows",len(df)],["Term Loan >90 DPD triggers",int(df["Term Loan DPD result"].eq("NPA trigger >90 DPD").sum())],["CC/OD tests","Only where optional 90-day history uploaded"],["Borrower consolidation","Only where CIF supplied"],["Doubtful/Loss provisioning","Calculated where classification, NPA date and security value are available; otherwise flagged"]],columns=["Particulars","Result"])
parameters=pd.DataFrame([
["Reporting date",str(review),"User-selected review date"],
["NPA threshold (days)",90,"Screening threshold; apply facility-specific rule and day-end convention"],
["Standard - Direct agriculture / SME",0.0025,"RBI UCB IRAC Directions 2025, para 70"],
["Standard - CRE",0.01,"RBI UCB IRAC Directions 2025, para 70"],
["Standard - CRE-RH",0.0075,"RBI UCB IRAC Directions 2025, para 70"],
["Standard - Other advances",0.004,"RBI UCB IRAC Directions 2025, para 70"],
["Substandard",0.10,"RBI UCB IRAC Directions 2025, para 74"],
["Doubtful secured D1",0.20,"RBI UCB IRAC Directions 2025, para 77"],
["Doubtful secured D2",0.30,"RBI UCB IRAC Directions 2025, para 77"],
["Doubtful secured D3",1.00,"RBI UCB IRAC Directions 2025, para 77"],
["Doubtful unsecured",1.00,"RBI UCB IRAC Directions 2025, para 75"],
["Loss",1.00,"RBI UCB IRAC Directions 2025, para 79"],
],columns=["Parameter","Value","Source / basis"])
# Annex I Summary – preserve the exact 50-row structure and labels of the supplied proforma.
provx=prov_df.copy(); cat=provx["Calculated Category / Doubtful Bucket"].astype(str)
stdmask=cat.str.startswith("Standard"); submask=cat.eq("Substandard"); d1=cat.eq("D1"); d2=cat.eq("D2"); d3=cat.eq("D3"); lossmask=cat.eq("Loss"); npamask=submask|d1|d2|d3|lossmask
total_out=float(pd.to_numeric(df["Outstanding"],errors="coerce").fillna(0).sum())
def sums(mask):
    z=provx[mask]; return int(z["Account No"].nunique()),float(z["Outstanding"].sum()),float(z["Indicative Provision"].sum(skipna=True))
def detail(mask):
    z=provx[mask]; return float(z["Outstanding"].sum()),float(z["Realisable Security"].sum()),float(z["Unsecured Portion"].sum()),float(z["Indicative Provision"].sum(skipna=True))
annex_rows=[[None]*6 for _ in range(50)]
def put(r,label,count=None,amt=None,pct=None,prov=None,remark=None): annex_rows[r-1]=[label,count,amt,pct,prov,remark]
put(1,"Classification of Assets and Provisioning against NPAs - Annex I proforma (Rs)")
put(2,"UCB IRAC Directions, 2025 (Annex I, para 40) - reporting date")
put(4,"Classification of Assets","No. of A/cs","Amount outstanding (Rs)","% of total loans","Provision required (Rs)","Remarks / source")
ct,am,pv=sums(pd.Series([True]*len(provx))); put(5,"Total loans and advances",ct,am,(am/total_out if total_out else 0),pv,"Standard asset provision + NPA provision")
ct,am,pv=sums(stdmask); put(6,"A. Standard assets",ct,am,(am/total_out if total_out else 0),pv,"Para 70; contingent provision against Standard Assets")
put(7,"B. Non-performing assets")
ct,am,pv=sums(submask); put(8,"1. Sub-standard",ct,am,(am/total_out if total_out else 0),pv,"Para 74: 10% of total outstanding")
ct,am,pv=sums(d1); put(9,"2. Doubtful",ct,am,(am/total_out if total_out else 0),pv,"Paras 75-77")
for row,lab,mask,rate in [(10,"   i) Up to 1 year",d1,.20),(13,"   ii) Above 1 year and up to 3 years",d2,.30),(16,"   iii) Above 3 years",d3,1.00)]:
    c,a,pv=sums(mask); put(row,lab,c,a,(a/total_out if total_out else 0),pv,f"Secured portion provision {rate:.0%}; unsecured 100%")
    a,secv,unsec,pv=detail(mask); put(row+1,"        Secured",None,secv,None,secv*rate,"Secured portion")
    put(row+2,"        Unsecured",None,unsec,None,unsec,"Unsecured 100%; guarantee adjustments require separate review")
ct,am,pv=sums(lossmask); put(19,"3. Loss assets",ct,am,(am/total_out if total_out else 0),pv,"Para 79: 100% (or write off under para 78)")
ct,am,pv=sums(npamask); put(20,"Gross NPAs (B1 + B2 + B3)",ct,am,(am/total_out if total_out else 0),pv,"")
put(21,"Reconciliation: Standard + NPA = total advances",None,total_out,None,None,"Mechanical cross-check; pending/unclassified balances require review")
put(23,"Provisioning position (Rs)")
put(24,"NPA provision required (BDDR)",None,None,None,float(provx.loc[npamask,"Indicative Provision"].sum(skipna=True)),"Calculated from available data")
put(25,"NPA provision held as per books (BDDR / other head, charged to P&L)",None,None,None,None,"Input from books - para 67")
put(26,"Shortfall / (excess) - NPA provision",None,None,None,None,"Requires provision-held input")
put(27,"Standard asset provision required",None,None,None,float(provx.loc[stdmask,"Indicative Provision"].sum(skipna=True)),"Para 70")
put(28,"Contingent provision against standard assets held as per books",None,None,None,None,"Input from books - paras 71-72")
put(29,"Shortfall / (excess) - standard asset provision",None,None,None,None,"Requires book input")
put(31,"Position of Net Advances / Net NPAs (Rs) - Annex I, second table")
put(32,"1. Gross Advances",None,total_out,None,None,"")
npag=float(provx.loc[npamask,"Outstanding"].sum()); put(33,"2. Gross NPAs",None,npag,None,None,"")
put(34,"3. Gross NPAs as % of Gross Advances",None,(npag/total_out if total_out else 0),None,None,"")
put(35,"4. Deductions:")
put(36,"     - Balance in interest suspense / OIR",None,None,None,None,"Per books; not inferred")
put(37,"     - DICGC / ECGC claims received and held pending adjustment",None,None,None,None,"Per books; not inferred")
put(38,"     - Part payment of NPA accounts received and kept in suspense",None,None,None,None,"Per books; not inferred")
put(39,"     Total deductions",None,None,None,None,"Requires rows 36-38")
put(40,"5. Total NPA provisions held",None,None,None,None,"Per books; not inferred")
put(41,"6. Net Advances (1 - 4 - 5)",None,None,None,None,"Requires book inputs")
put(42,"7. Net NPAs (2 - 4 - 5)",None,None,None,None,"Requires book inputs")
put(43,"8. Net NPAs as % of Net Advances",None,None,None,None,"Requires book inputs")
put(45,"Income recognition entries on NPAs (Chapter V)")
put(46,"Reversal of unrealised interest taken to income: Dr Profit & Loss A/c, Cr Overdue Interest Reserve",None,None,None,None,"Requires interest ledger / book data")
put(47,"Interest accrued after NPA: Dr Interest Receivable A/c, Cr Overdue Interest Reserve",None,None,None,None,"Requires interest ledger / book data")
put(48,"Total Overdue Interest Reserve (not part of owned funds, para 103)",None,None,None,None,"Requires book inputs")
put(50,"CERTIFIED that the non-performing assets have been worked out as per RBI instructions and provisions made accordingly - to be signed by CEO and Statutory Auditors (Annex I).")
annex=pd.DataFrame(annex_rows,columns=["Classification of Assets","No. of A/cs","Amount outstanding (Rs)","% of total loans","Provision required (Rs)","Remarks / source"])
verification=pd.DataFrame([
["Provision output generated",len(prov_df)>0,"Review Provision Review and Annex I Summary outputs"],
["Doubtful accounts with missing NPA date",int(prov_df["Calculated Category / Doubtful Bucket"].astype(str).str.contains("ageing unavailable").sum()),"Upload NPA date or NPA History"],
["Accounts with missing security value",int(((prov_df["Calculated Category / Doubtful Bucket"].isin(["D1","D2","D3"])) & (prov_df["Realisable Security"]<=0)).sum()),"Confirm whether account is unsecured or security data is missing"],
["Accounts with blank provision",int(prov_df["Indicative Provision"].isna().sum()),"Resolve classification / ageing inputs"],
["Annex I total agrees to provision register",abs(float(pd.to_numeric(annex.loc[annex["Classification of Assets"].eq("Total loans and advances"), "Provision required (Rs)"], errors="coerce").fillna(0).iloc[0])-float(pd.to_numeric(prov_df["Indicative Provision"], errors="coerce").sum(skipna=True)))<0.01,"Compares Annex I total loans and advances row with provision register; mechanical check only"],
],columns=["Verification check","Result / count","Action / interpretation"])
st.download_button("Download UCB NPA Audit System V3.2 Report",outxlsx({"Summary":summary,"Parameters":parameters,"Loan Review":df,"Term Loan DPD":tl_df,"CCOD Tests":cc_df,"Borrower Consolidation":borrower,"Security":sec,"NPA History":hist,"Provision Review":prov_df,"Annex I Summary":annex,"Verification":verification,"Audit Exceptions":exc_df}),"UCB_NPA_Audit_System_V30.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with st.expander("RBI rule register"):
    st.markdown("""
    - IRAC Directions 2025 para 25: day-end SMA/NPA tagging.
    - Para 34(1): Term Loan principal/interest overdue >90 days.
    - Para 34(2) and definition 6(7): CC/OD out-of-order tests (continuous excess 90 days; no credits 90 days; credits insufficient for interest debited in previous 90 days).
    - Para 34(5): regular/ad-hoc limit not reviewed/renewed within 90 days from due date/ad-hoc sanction.
    - Paras 34(6)-(7): specified direct agricultural advances: two crop seasons for short-duration crops / one crop season for long-duration crops.
    - Para 36: borrower-wise asset classification.
    - Para 38: temporary deficiencies alone do not make an account NPA.
    - Paras 48-51: agricultural, guarantee, staff housing and gold loan treatment.
    - Paras 54-60: substandard/doubtful/loss classification and security erosion.
    - Paras 63-65: upgradation.
    - Para 70: standard provisions 0.25% direct agriculture/SME, 1.00% CRE, 0.75% CRE-RH, 0.40% other advances.
    - Para 74: substandard provision 10%.
    - Paras 75-77: doubtful asset provision; secured/unsecured split and doubtful ageing.
    - 29-Apr-2026 Amendment effective 01-Jul-2026: paras 53A/53B, 89A-89D, 113A/113B for specified calamity resolution-plan cases.
    """)
