"""Allocate contract-note charges to each scrip/side row and reconcile.

Rules (agreed with the user):
* BUY and SELL rows are never netted and nothing is treated as speculative.
  All quantity goes to holdings / FIFO.
* For STT and stamp duty only, the broker's own basis is copied so each row
  carries what was really charged: on the same note, the quantity of an ISIN
  both bought and sold ("matched") is charged at intraday rates by the broker.
      Equity  delivery : STT 0.1% on buy and sell, stamp 0.015% on buy
      Equity  matched  : STT 0.025% on sell only,  stamp 0.003% on buy
      MF / ETF units   : STT 0.001% on sell only (equity ETFs; debt ETFs nil)
  The statutory amounts are used as weights and scaled to the printed total,
  so the allocation always ties to the note. Where the note prints STT per
  scrip (IIFL old layout) that figure is used for the scrip.
* Brokerage: brokerage visible in the per-unit rates is used as the weight;
  if none is visible, by turnover.
* Exchange, clearing, SEBI, IPF and other charges: by turnover (gross value).
* GST: in proportion to each row's taxable charges (brokerage + exchange +
  clearing + SEBI + IPF).
* Paise are kept for each charge (largest-remainder rounding so totals tie).
* Final Net Cost / Net Sale Value per row is in whole rupees, rounded so the
  rows add up to the note's net amount rounded to the rupee.
"""
from __future__ import annotations

import math

from .models import CHARGE_KEYS, ContractNote

RATES = {
    "equity": {"stt_del": 0.001, "stt_matched_sell": 0.00025, "stamp_del": 0.00015, "stamp_matched": 0.00003},
    "fund": {"stt_sell": 0.00001, "stamp_del": 0.00015, "stamp_matched": 0.00003},
}


def _split(total: float, weights: list[float], unit: float = 0.01) -> list[float]:
    """Largest-remainder split of total into len(weights) parts, multiples of unit."""
    n = len(weights)
    if n == 0:
        return []
    steps = round(total / unit)
    wsum = sum(weights)
    if wsum <= 0:
        weights, wsum = [1.0] * n, float(n)
    raw = [steps * w / wsum for w in weights]
    base = [math.floor(x) for x in raw]
    rem = steps - sum(base)
    order = sorted(range(n), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:rem] if rem >= 0 else []:
        base[i] += 1
    if rem < 0:  # negative totals (should not happen, but stay safe)
        for i in order[::-1][: -rem]:
            base[i] -= 1
    return [round(b * unit, 2) for b in base]


def _statutory_weights(cn: ContractNote):
    by_isin = {}
    for s in cn.scrips:
        by_isin.setdefault(s.isin, {})[s.side] = s
    stt_w, stamp_w = {}, {}
    for isin, sides in by_isin.items():
        b, s = sides.get("BUY"), sides.get("SELL")
        matched = min(b.qty if b else 0, s.qty if s else 0)
        fund = len(isin) == 12 and isin[2] == "F"
        if b:
            del_val, m_val = (b.qty - matched) * b.avg_rate, matched * b.avg_rate
            r = RATES["fund" if fund else "equity"]
            stamp_w[id(b)] = del_val * r["stamp_del"] + m_val * r["stamp_matched"]
            stt_w[id(b)] = 0.0 if fund else del_val * RATES["equity"]["stt_del"]
            b.basis["stt_stamp"] = (f"Matched qty {matched:g} at broker's intraday rates" if matched else "Delivery rates")
        if s:
            del_val, m_val = (s.qty - matched) * s.avg_rate, matched * s.avg_rate
            stamp_w[id(s)] = 0.0
            stt_w[id(s)] = (s.gross * RATES["fund"]["stt_sell"] if fund else
                            del_val * RATES["equity"]["stt_del"] + m_val * RATES["equity"]["stt_matched_sell"])
            s.basis["stt_stamp"] = (f"Matched qty {matched:g} at broker's intraday rates" if matched else "Delivery rates")
        # per-scrip STT printed on the note: scale this ISIN's sides to it
        hint = next((x.stt_hint for x in sides.values() if x.stt_hint is not None), None)
        if hint is not None:
            parts = [x for x in sides.values()]
            wsum = sum(stt_w[id(x)] for x in parts)
            for x in parts:
                stt_w[id(x)] = hint * (stt_w[id(x)] / wsum) if wsum else hint / len(parts)
                x.basis["stt_stamp"] += "; STT per scrip as printed"
    return stt_w, stamp_w


def allocate(cn: ContractNote) -> None:
    rows = cn.scrips
    gross = [s.gross for s in rows]
    c = cn.charges

    # brokerage
    direct = [s.brokerage_direct for s in rows]
    if c["brokerage"] == 0 and sum(direct) > 0:
        c["brokerage"] = round(sum(direct), 2)
    use_direct = sum(direct) > 0
    for s, v in zip(rows, _split(c["brokerage"], direct if use_direct else gross)):
        s.alloc["brokerage"] = v
        s.basis["brokerage"] = "Per-unit rate on note" if use_direct else "By turnover"

    for key in ("exchange", "clearing", "sebi", "ipf", "other"):
        for s, v in zip(rows, _split(c[key], gross)):
            s.alloc[key] = v

    stt_w, stamp_w = _statutory_weights(cn)
    for key, w in (("stt", stt_w), ("stamp", stamp_w)):
        weights = [w.get(id(s), 0.0) for s in rows]
        if c[key] and sum(weights) == 0:
            weights = gross
        for s, v in zip(rows, _split(c[key], weights)):
            s.alloc[key] = v

    taxable = [sum(s.alloc[k] for k in ("brokerage", "exchange", "clearing", "sebi", "ipf")) for s in rows]
    for key in ("cgst", "sgst", "igst"):
        for s, v in zip(rows, _split(c[key], taxable if sum(taxable) else gross)):
            s.alloc[key] = v

    # exact net per row (+ cash out for buy, + cash in for sell)
    for s in rows:
        s.alloc["total"] = round(sum(s.alloc[k] for k in CHARGE_KEYS), 2)
        s.alloc["net_exact"] = round(s.gross + s.alloc["total"] if s.side == "BUY" else s.gross - s.alloc["total"], 2)

    # reconciliation against printed net (positive = payable by client)
    calc = sum(s.alloc["net_exact"] * (1 if s.side == "BUY" else -1) for s in rows)
    cn.recon_diff = round(calc - cn.net_amount, 2)

    _round_rupees(cn)


def _round_rupees(cn: ContractNote) -> None:
    """Whole-rupee net per row; signed rows sum to the note net rounded to the rupee."""
    rows = cn.scrips
    # signed, payable positive; half-rupee rounds away from zero
    target = int(math.floor(abs(cn.net_amount) + 0.5)) * (1 if cn.net_amount >= 0 else -1)
    signed = [s.alloc["net_exact"] * (1 if s.side == "BUY" else -1) for s in rows]
    base = [math.floor(x) for x in signed]
    frac = [x - b for x, b in zip(signed, base)]
    need = target - sum(base)
    order = sorted(range(len(rows)), key=lambda i: frac[i], reverse=True)
    if abs(need) > len(rows):        # only when the note did not reconcile
        biggest = max(range(len(rows)), key=lambda i: abs(signed[i]))
        step = 1 if need > 0 else -1
        surplus = need - step * len(rows)
        base[biggest] += surplus
        need -= surplus
    if need >= 0:
        for i in order[:need]:
            base[i] += 1
    else:
        for i in order[::-1][: -need]:
            base[i] -= 1
    for s, b in zip(rows, base):
        val = b if s.side == "BUY" else -b
        s.alloc["net_rupees"] = int(val)
        s.alloc["rounding"] = round(val - s.alloc["net_exact"], 2)
