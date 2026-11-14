"""Form-specific ITR-3/4/5 JSON financial parser. No third-party dependencies."""
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation

def number(v):
    if isinstance(v,bool) or v is None:return None
    try:return Decimal(str(v).replace(',',''))
    except (InvalidOperation,ValueError):return None

def at(obj,*keys):
    for k in keys:
        if not isinstance(obj,dict):return None
        obj=obj.get(k)
    return obj

def getnum(obj,*keys):return number(at(obj,*keys))

def extract(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if isinstance(obj,str):obj=json.loads(obj)
    forms=obj.get('ITR',obj)
    matches=[(k,v) for k,v in forms.items() if k in ('ITR3','ITR4','ITR5') and isinstance(v,dict)]
    if len(matches)!=1:raise ValueError('Expected exactly one ITR3, ITR4 or ITR5 JSON form')
    key,root=matches[0]; form='ITR-'+key[-1]
    year=at(root,'Form_'+key,'AssessmentYear')
    if not str(year).isdigit() or len(str(year))!=4:raise ValueError('Assessment year not identified')
    ay=f'{year}-{(int(year)+1)%100:02d}'
    turnover=None; basis=''; capital=None; cbasis=''; warning=[]
    if form in ('ITR-3','ITR-5'):
        tr=at(root,'TradingAccount') or {}
        primary=getnum(tr,'SalesGrossReceiptsTotal')
        goods=getnum(tr,'SaleOfGoods');services=getnum(tr,'SaleOfServices')
        professional=getnum(tr,'GrossRcptFromProfession')
        if primary is not None and primary!=0:
            turnover=primary;basis='TradingAccount.SalesGrossReceiptsTotal'
            if goods is not None and services is not None and primary!=goods+services:
                warning.append('Sales total differs from goods + services: review professional receipts and schedule')
        elif goods is not None and services is not None and goods+services!=0:
            turnover=goods+services;basis='TradingAccount.SaleOfGoods + SaleOfServices'
        elif professional is not None and professional!=0:
            turnover=professional;basis='TradingAccount.GrossRcptFromProfession'
        else:
            warning.append('No positive regular-books turnover identified; review no-books and presumptive schedules')
        fund='PropFund' if form=='ITR-3' else 'PartnerOrMemberFund'
        capkey='PropCap' if form=='ITR-3' else 'PartnerOrMemberCap'
        totkey='TotPropFund' if form=='ITR-3' else 'TotPartnerOrMemberFund'
        capital=getnum(root,'PARTA_BS','FundSrc',fund,totkey)
        if capital is None:capital=getnum(root,'PARTA_BS','FundSrc',fund,capkey)
        if capital is not None:
            cbasis=f'PARTA_BS.FundSrc.{fund}.{totkey if getnum(root,"PARTA_BS","FundSrc",fund,totkey) is not None else capkey} (business equity only)'
        if capital==0 and turnover is None:capital=None;cbasis='';warning.append('Zero-filled regular balance sheet; do not infer net worth')
    else:
        bp=at(root,'ScheduleBP') or {}
        ad=at(bp,'PersumptiveInc44AD') or {};ada=at(bp,'PersumptiveInc44ADA') or {}
        adturn=getnum(ad,'GrsTotalTrnOver');adaturn=getnum(ada,'GrsReceipt')
        if adturn not in (None,Decimal(0)) and adaturn not in (None,Decimal(0)):
            turnover=adturn+adaturn;basis='ScheduleBP: 44AD GrsTotalTrnOver + 44ADA GrsReceipt'
        elif adturn is not None and adturn!=0:turnover=adturn;basis='ScheduleBP.PersumptiveInc44AD.GrsTotalTrnOver'
        elif adaturn is not None and adaturn!=0:turnover=adaturn;basis='ScheduleBP.PersumptiveInc44ADA.GrsReceipt'
        else:warning.append('44AD/44ADA gross receipts absent; 44AE presumptive income is not turnover')
        fp=at(bp,'FinanclPartclrOfBusiness') or {}
        capital=getnum(fp,'PartnerMemberOwnCapital')
        if capital is not None:cbasis='ScheduleBP.FinanclPartclrOfBusiness.PartnerMemberOwnCapital (limited disclosure; not complete net worth)'
    return {'form':form,'ay':ay,'turnover':str(turnover) if turnover is not None else '',
            'turnover_basis':basis,'networth':str(capital) if capital is not None else '',
            'networth_basis':cbasis,'warnings':warning}
