"""Configurable audit analytics. Flags guide audit work; they are not conclusions."""
from __future__ import annotations
import re
import pandas as pd
import numpy as np


def col(df, *names):
    lower={str(c).strip().lower():c for c in df.columns}
    for n in names:
        if n.lower() in lower:return lower[n.lower()]
    return None

def num(s): return pd.to_numeric(s,errors="coerce")
def findings(df: pd.DataFrame, topic: str, materiality: float=0, variance_pct: float=20.0) -> list[dict]:
    out=[]
    amount=col(df,"amount","closing","current year","current_year","balance","value")
    prev=col(df,"previous year","previous_year","prior year","prior_year","opening")
    ref=col(df,"invoice no","invoice number","voucher no","account","customer","vendor","name","asset id")
    reference=lambda i: str(df.iloc[i][ref]) if ref else f"Row {i+1}"
    if amount:
        a=num(df[amount])
        for i,v in a[a.isna()].items():out.append({"severity":"Medium","rule":"Invalid numeric amount","item":reference(i),"description":f"'{amount}' is blank or non-numeric.","amount":None})
        for i,v in a[(a<0)].items():out.append({"severity":"Medium","rule":"Negative balance","item":reference(i),"description":"Negative balance flagged for audit evaluation.","amount":float(v)})
        if materiality:
            for i,v in a[a.abs()>=materiality].items():out.append({"severity":"High","rule":"Above materiality","item":reference(i),"description":f"Balance meets/exceeds configured materiality ({materiality:,.0f}).","amount":float(v)})
        rounded=a.dropna()[np.isclose(a.dropna()%1000,0)]
        for i,v in rounded.items():out.append({"severity":"Low","rule":"Round number","item":reference(i),"description":"Round-number item; evaluate based on risk assessment.","amount":float(v)})
    if amount and prev:
        a,p=num(df[amount]),num(df[prev]); change=a-p; pct=np.where(p.abs()>0,change/p.abs()*100,np.nan)
        for i in df.index[(np.abs(pct)>=variance_pct) & a.notna() & p.notna()]:
            out.append({"severity":"High" if materiality and abs(change[i])>=materiality else "Medium","rule":"Variance threshold","item":reference(i),"description":f"Current/prior change {change[i]:,.2f} ({pct[i]:,.1f}%), exceeds {variance_pct}% threshold.","amount":float(change[i])})
    inv=col(df,"invoice no","invoice number","voucher no","document no")
    if inv:
        dupe=df[df[inv].duplicated(keep=False)]
        for i,r in dupe.iterrows():out.append({"severity":"High","rule":"Duplicate document number","item":str(r[inv]),"description":"Duplicate number detected; validate source and accounting treatment.","amount":None})
        vals=df[inv].dropna().astype(str)
        nums=[]
        for x in vals:
            m=re.search(r"(\d+)$",x)
            if m:nums.append((int(m.group(1)),x))
        if len(nums)>2:
            nums.sort()
            for (a_num,a_txt),(b_num,b_txt) in zip(nums,nums[1:]):
                if b_num-a_num>1:out.append({"severity":"Medium","rule":"Document sequence gap","item":f"{a_txt} → {b_txt}","description":f"Potential missing sequence numbers {a_num+1}–{b_num-1}.","amount":None})
    # caption specific
    if topic=="3.1":
        dep=col(df,"depreciation","dep"); gross=col(df,"gross block","cost","opening")
        if dep and gross:
            rate=num(df[dep])/num(df[gross])*100
            for i in rate[rate>50].items():out.append({"severity":"Medium","rule":"High depreciation rate","item":reference(i[0]),"description":f"Computed depreciation rate is {i[1]:.1f}%; inspect useful life/method.","amount":None})
    if topic in ("3.7","3.15"):
        age=col(df,"age days","ageing days","days outstanding")
        if age:
            for i,v in num(df[age])[num(df[age])>180].items():out.append({"severity":"High","rule":"Long outstanding ageing","item":reference(i),"description":f"Outstanding for {v:.0f} days; evaluate recoverability/settlement.","amount":None})
    if topic=="3.20":
        date=col(df,"date","invoice date")
        if date:
            dates=pd.to_datetime(df[date],errors="coerce")
            # User must assess actual reporting date; report last/first five dates as cut-off candidates.
            for i in list(dates.nsmallest(3).index)+list(dates.nlargest(3).index):out.append({"severity":"Low","rule":"Cut-off candidate","item":reference(i),"description":f"Transaction date {dates[i].date() if pd.notna(dates[i]) else 'invalid'}; assess period cut-off.","amount":None})
    return out

def going_concern_metrics(df: pd.DataFrame) -> dict:
    """Uses a two-column uploaded financial-statement table: Particulars, Current Year/Prior Year."""
    label=col(df,"particulars","account","description","name"); cur=col(df,"current year","current_year","amount","current")
    if not label or not cur:return {}
    lookup={str(r[label]).lower():float(num(pd.Series([r[cur]])).iloc[0]) if pd.notna(num(pd.Series([r[cur]])).iloc[0]) else 0 for _,r in df.iterrows()}
    def find(*words):
        return sum(v for k,v in lookup.items() if any(w in k for w in words))
    ca=find("current asset"); cl=find("current liabil"); inv=find("inventor"); debt=find("borrow"); equity=find("share capital","reserve","equity"); pat=find("profit after tax","profit/(loss)"); revenue=find("revenue","sales")
    return {"Current ratio":ca/cl if cl else None,"Quick ratio":(ca-inv)/cl if cl else None,"Debt-equity ratio":debt/equity if equity else None,"Net profit ratio":pat/revenue if revenue else None,"Net worth":equity}
