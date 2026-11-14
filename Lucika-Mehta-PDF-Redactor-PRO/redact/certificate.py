"""
Certificate of Redaction - A4 portrait report kept with the engagement file.

Statutory references were checked on 25-10-2026:
  * Information Technology Act, 2000 - ss. 43A and 72A; Information Technology (Reasonable
    security practices and procedures and sensitive personal data or information) Rules, 2011
    (G.S.R. 313(E), 11-04-2011) - Rules 3, 6, 7 and 8.
  * Digital Personal Data Protection Act, 2023 - ss. 2, 6(1), 8, 16, 33 and the Schedule;
    Digital Personal Data Protection Rules, 2025 (G.S.R. 846(E), 13-11-2025) - Rule 6.
    Sections 2 and 44(1), (3) in force from 13-11-2025; ss. 3-17, 33 and 44(2) and Rule 6 from
    the expiry of eighteen months, i.e. 13-05-2027 (G.S.R. 843(E)). Section 44(2)(a) omits s. 43A
    of the Information Technology Act, 2000 from that date.
"""

from __future__ import annotations

import io
from collections import Counter
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import detect as D
from .model import APP_NAME, AUTHOR, VERSION

NAVY = "#2A3A8D"
SKY = "#EBF4FD"
INK = "#282828"
DPDP_OPERATIVE = date(2027, 5, 13)
DPDP_NOTIFIED = date(2025, 11, 13)


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _blank(width: int = 60) -> str:
    return f"<span class='blank'>{'&#160;' * width}</span>"


def _statutes(on: date) -> list[tuple[str, str, str, str]]:
    """(provision, requirement in brief, status on the certificate date, how the procedure responds)."""
    dpdp_live = on >= DPDP_OPERATIVE
    later = "In force" if dpdp_live else "In force from 13-05-2027"
    s43a = ("Omitted w.e.f. 13-05-2027 by s. 44(2)(a), DPDP Act, 2023" if dpdp_live
            else "In force (to be omitted w.e.f. 13-05-2027 by s. 44(2)(a), DPDP Act, 2023)")
    spdi = ("Rule-making power omitted w.e.f. 13-05-2027 by s. 44(2)(c), DPDP Act, 2023" if dpdp_live
            else "In force")
    return [
        ("Information Technology Act, 2000 - section 43A",
         "A body corporate (including a firm or sole proprietorship engaged in professional activities) "
         "handling sensitive personal data on a computer resource must implement reasonable security "
         "practices; negligence causing wrongful loss or gain attracts liability to pay compensation.",
         s43a,
         "Sensitive personal data in client documents is removed before the documents are made available "
         "to an external AI service."),
        ("IT (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) "
         "Rules, 2011 - Rules 3 and 8",
         "Rule 3 treats passwords and financial information such as bank account, credit and debit card "
         "details as sensitive personal data. Rule 8 requires documented security practices and "
         "procedures.",
         spdi,
         "Account, card, UPI, IFSC, MICR and customer identifiers are detected and redacted; this "
         "certificate documents the procedure applied and its verification."),
        ("IT Rules, 2011 - Rules 6 and 7",
         "Disclosure of sensitive personal data to a third party, or its transfer, requires prior "
         "permission or a contractual or legal basis, and the recipient must ensure the same level of "
         "protection.",
         spdi,
         "The AI service provider is treated as a third party; the redacted copies withhold the sensitive "
         "personal data, limiting what is disclosed or transferred."),
        ("Information Technology Act, 2000 - section 72A",
         "Disclosure, without consent or in breach of a lawful contract, of personal information obtained "
         "while providing services under that contract is punishable with imprisonment up to three years, "
         "fine up to Rs. 5,00,000, or both.",
         "In force",
         "Personal information obtained under the professional engagement is withheld from the copies "
         "shared beyond the engagement."),
        ("Digital Personal Data Protection Act, 2023 - section 2(i), (k), (t), (u) and (x)",
         "Defines Data Fiduciary, Data Processor, personal data (data about an identifiable individual), "
         "personal data breach and processing.",
         f"In force from {DPDP_NOTIFIED:%d-%m-%Y}",
         "Identifiers of individuals (directors, partners, proprietors, counterparties) are treated as "
         "personal data; the AI service provider would act as a Data Processor in respect of anything it "
         "receives."),
        ("DPDP Act, 2023 - section 6(1)",
         "Consent is limited to such personal data as is necessary for the specified purpose.",
         later,
         "Only the content needed for the analysis is shared; identifiers not required for it are "
         "removed (data minimisation)."),
        ("DPDP Act, 2023 - section 8(1), (2) and (4)",
         "The Data Fiduciary remains responsible for processing undertaken by a Data Processor on its "
         "behalf, may engage a processor only under a valid contract, and must adopt appropriate technical "
         "and organisational measures.",
         later,
         "Redaction on the local computer before any upload is a technical measure; the reviewer's "
         "touch-ups and this record are organisational measures."),
        ("DPDP Act, 2023 - section 8(5); DPDP Rules, 2025 - Rule 6(1)(a)",
         "Reasonable security safeguards to prevent a personal data breach, including data security "
         "measures such as encryption, obfuscation, masking or virtual tokens.",
         later,
         "Identifiers are masked (black boxes) or replaced with virtual tokens (consistent labels such as "
         "[ACCT-1]); the key to the tokens is retained locally."),
        ("DPDP Act, 2023 - section 33 read with the Schedule, item 1",
         "Failure to take reasonable security safeguards to prevent a personal data breach may attract a "
         "penalty of up to Rs. 250 crore.",
         later,
         "The safeguards applied are recorded in this certificate."),
        ("DPDP Act, 2023 - section 16",
         "Processing outside India is permitted except to countries or territories restricted by "
         "notification of the Central Government; stricter sectoral laws continue to apply.",
         later,
         "Where the AI service processes data outside India, only redacted copies are made available; "
         "the reviewer should confirm that no restriction has been notified for the relevant country."),
    ]


C_NAVY = colors.HexColor(NAVY)
C_SKY = colors.HexColor(SKY)
C_INK = colors.HexColor(INK)
C_MUTED = colors.HexColor("#4A5565")
C_RULE = colors.HexColor("#D5DAE3")
C_LIGHT = colors.HexColor("#F5F7FB")


def _styles():
    base = dict(fontName="Helvetica", fontSize=8.8, leading=11.6, textColor=C_INK)
    S = {
        "body": ParagraphStyle("body", **base),
        "just": ParagraphStyle("just", **base, alignment=TA_JUSTIFY),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.6, "leading": 9.6}),
        "smallm": ParagraphStyle("smallm", **{**base, "fontSize": 7.6, "leading": 9.6, "textColor": C_MUTED}),
        "note": ParagraphStyle("note", **{**base, "fontSize": 8, "leading": 10.4, "textColor": C_MUTED}, alignment=TA_JUSTIFY),
        "kicker": ParagraphStyle("kicker", **{**base, "fontSize": 8, "textColor": C_MUTED}),
        "title": ParagraphStyle("title", fontName="Times-Bold", fontSize=19, leading=23, textColor=C_NAVY),
        "lede": ParagraphStyle("lede", **{**base, "fontSize": 9.2, "textColor": C_MUTED}),
        "h2": ParagraphStyle("h2", fontName="Times-Bold", fontSize=12, leading=15, textColor=C_NAVY, spaceBefore=10, spaceAfter=4),
        "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.8, leading=9.6, textColor=colors.white),
        "td": ParagraphStyle("td", **{**base, "fontSize": 7.9, "leading": 9.9}),
        "tdb": ParagraphStyle("tdb", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7.9, "leading": 9.9, "textColor": C_NAVY}),
        "tdc": ParagraphStyle("tdc", **{**base, "fontSize": 7.9, "leading": 9.9}, alignment=TA_CENTER),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=5.7, leading=7.4, textColor=C_INK),
        "fig": ParagraphStyle("fig", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=C_NAVY, alignment=TA_CENTER),
        "figl": ParagraphStyle("figl", **{**base, "fontSize": 7.6, "leading": 9, "textColor": C_MUTED}, alignment=TA_CENTER),
        "ref": ParagraphStyle("ref", **{**base, "fontSize": 8.2, "leading": 11}, alignment=TA_RIGHT),
    }
    return S


def _rule_h2(text, S):
    t = Table([[Paragraph(text, S["h2"])]], colWidths=["100%"])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.7, C_NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    return [CondPageBreak(30 * mm), t, Spacer(1, 5)]


def _grid(rows, widths, header=True, zebra=False, valign="TOP"):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), valign), ("LINEBELOW", (0, 0), (-1, -1), 0.4, C_RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), C_NAVY), ("LINEBELOW", (0, 0), (-1, 0), 0, C_NAVY)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), C_LIGHT))
    t.setStyle(TableStyle(st))
    return t


def certificate_pdf(b, details: dict | None = None) -> bytes:
    from .outputs import STATUS_TEXT, output_names      # local import (avoids a cycle)
    details = details or {}
    S = _styles()
    P = lambda text, st="td": Paragraph(text, S[st])
    o = b.opts
    names = output_names(b)
    now = datetime.now()
    issued = now.date()
    ref = f"RDC/{now:%Y%m%d}/{now:%H%M%S}"
    results = b.results
    redacted = [r for r in results if r.output is not None]
    n_items = sum(len(r.findings) for r in results)
    clean = sum(1 for r in redacted if r.residual + r.residual_ocr == 0 and not r.layout_pages)
    pages = sum(r.pages for r in results if r.kind == "pdf")
    edited = len(b.overrides)
    cats = Counter(D.rule_short(f.rule) for r in results for f in r.findings).most_common()
    W = A4[0] - 2 * 17 * mm

    def val(key, blank="&#160;"):
        v = (details.get(key) or "").strip()
        return _esc(v) if v else blank

    story = []
    # ---- title block
    title = Table([[
        [P("Chartered Accountant's record", "kicker"), Spacer(1, 2),
         P("Certificate of Redaction of Client Documents", "title"), Spacer(1, 3),
         P("Prepared before client documents are made available for analysis with an artificial intelligence tool", "lede")],
        P(f"<b>Reference</b><br/>{ref}<br/><br/><b>Date</b><br/>{issued:%d-%m-%Y}", "ref")]],
        colWidths=[W - 34 * mm, 34 * mm])
    title.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEABOVE", (0, 0), (-1, 0), 3, C_NAVY),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [title, Spacer(1, 4)]

    # ---- 1. particulars
    story += _rule_h2("1. Particulars", S)
    blank_line = "&#160;"
    kv = [
        ("Client / engagement reference", val("client", blank_line)),
        ("Purpose of processing", "Review and analysis of the client's documents with the assistance of an artificial "
                                  "intelligence tool, in the course of a bona fide professional engagement"),
        ("AI tool to be used", val("ai_tool", blank_line)),
        ("Processing period", f"{_esc(b.started)} to {_esc(b.finished)}"),
        ("Place of processing", "Local computer of the undersigned; no document was transmitted to any external service "
                                "during redaction"),
        ("Software", f"{APP_NAME} v{VERSION} (by {AUTHOR})"),
    ]
    t = Table([[P(k, "smallm"), P(v, "td")] for k, v in kv], colWidths=[48 * mm, W - 48 * mm])
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, C_RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5), ("LEFTPADDING", (0, 0), (0, -1), 0)]
    for i, (k, v) in enumerate(kv):
        if v == blank_line:
            st.append(("LINEBELOW", (1, i), (1, i), 0.7, colors.HexColor("#555555")))
    t.setStyle(TableStyle(st))
    story.append(t)

    # ---- 2. summary
    story += _rule_h2("2. Summary", S)
    figs = [(len(results), "documents received"), (len(redacted), "documents redacted"), (pages, "PDF pages"),
            (n_items, "items redacted"), (f"{clean} / {len(redacted)}", "re-checked clean")]
    ft = Table([[[P(str(v), "fig"), P(l, "figl")] for v, l in figs]], colWidths=[W / 5] * 5)
    ft.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C_SKY), ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [ft, Spacer(1, 7)]
    half = (len(cats) + 1) // 2
    crow = [[P("Category of information", "th"), P("Items", "th"), P("Category of information", "th"), P("Items", "th")]]
    for i in range(half):
        a = cats[i]
        bb = cats[i + half] if i + half < len(cats) else ("", "")
        crow.append([P(_esc(a[0])), P(str(a[1]), "tdc"), P(_esc(bb[0])), P(str(bb[1]), "tdc")])
    if len(crow) == 1:
        crow.append([P("None"), P(""), P(""), P("")])
    story.append(_grid(crow, [W * 0.36, W * 0.14, W * 0.36, W * 0.14], zebra=True))

    # ---- 3. procedure
    story += _rule_h2("3. Procedure applied", S)
    langs = ", ".join({"eng": "English", "hin": "Hindi", "mar": "Marathi"}.get(l, l) for l in o.ocr_langs)
    ocr_txt = (f"Scanned pages were read by optical character recognition ({langs})"
               + (", and every redacted scanned page was read again to confirm that no identifier remained."
                  if o.verify_scans else ".")) if o.ocr_mode != "off" else "Optical character recognition was not used."
    style_txt = ("replaced with a consistent label (for example [ACCT-1]), the same value bearing the same label in "
                 "every document; the key to the labels is retained locally and is not shared"
                 if o.style == "label" else "covered with a solid black box")
    steps = [
        ("Detection", "Each document was examined for tax and KYC identifiers (PAN, TAN, GSTIN, Aadhaar, CIN, DIN, "
                      "passport and others), banking details (account and card numbers, IFSC, MICR, UPI IDs, customer "
                      "IDs and transaction references), names and addresses of individuals and entities and, where "
                      "enabled, QR codes, barcodes, photographs and signatures. Aadhaar and card numbers were validated "
                      "by their check digits. " + ocr_txt),
        ("Consistency across the batch", "A value found in any document was redacted wherever it appeared in every "
                                         "other document of the batch." if o.propagate else
                                         "Each document was treated independently."),
        ("Removal", "The underlying text of each identifier was deleted from the document, not merely overlaid, and "
                    "image pixels beneath each redaction were blanked; each redaction was " + style_txt + ". Document "
                    "metadata, attachments, embedded scripts, links and form data were "
                    + ("removed" if o.scrub_metadata else "retained") + ", and password protection was removed so that "
                    "the redacted copy can be read."),
        ("Verification", "Every redacted copy was read again and tested against the same criteria and against every "
                         "value found in the batch. The result for each document is shown in the Schedule."),
        ("Review", "The redacted copies were reviewed on screen against the originals; "
                   + (f"manual corrections were applied to {edited} document{'s' if edited != 1 else ''}."
                      if edited else "no manual corrections were required.")),
    ]
    pt = Table([[P(f"3.{i}", "tdb"), P(f"<b>{k}.</b> {_esc(v)}", "just")] for i, (k, v) in enumerate(steps, 1)],
               colWidths=[10 * mm, W - 10 * mm])
    pt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.append(pt)

    # ---- 4. schedule
    story += _rule_h2("4. Schedule of documents", S)
    rows = [[P("S. No.", "th"), P("Document and redacted copy", "th"), P("Type", "th"), P("Pages", "th"),
             P("Items", "th"), P("Re-check", "th")]]
    for i, r in enumerate(results, 1):
        n = r.residual + r.residual_ocr
        chk = (STATUS_TEXT.get(r.status, r.status) if r.output is None
               else ("Clean" if n == 0 and not r.layout_pages else f"{n} to review"))
        out = names.get(r.name, "")
        doc_cell = [P(_esc(r.name)), P(f"Redacted copy: {_esc(out)}", "smallm")] if out else P(_esc(r.name))
        rows.append([P(str(i), "tdc"), doc_cell, P(_esc(D.PROFILE_LABELS.get(r.profile, r.profile))),
                     P(str(r.pages) if r.kind == "pdf" else "-", "tdc"), P(str(len(r.findings)), "tdc"), P(chk, "tdc")])
    story.append(_grid(rows, [12 * mm, W - 12 * mm - 30 * mm - 13 * mm - 13 * mm - 20 * mm, 30 * mm, 13 * mm, 13 * mm, 20 * mm],
                       zebra=True))

    # ---- 5. statutes
    story += _rule_h2("5. Statutory framework", S)
    story.append(P(f"Position stated as on {issued:%d-%m-%Y}. The Digital Personal Data Protection Act, 2023 is being "
                   f"brought into force in stages from {DPDP_NOTIFIED:%d-%m-%Y}. Its operative obligations, the Digital "
                   "Personal Data Protection Rules, 2025 (other than Rules 1, 2 and 17 to 21) and the omission of section "
                   "43A of the Information Technology Act, 2000 take effect on 13-05-2027.", "note"))
    story.append(Spacer(1, 5))
    lrows = [[P("Provision", "th"), P("Requirement in brief", "th"), P("Status", "th"), P("How the procedure responds", "th")]]
    for prov, req, stt, how in _statutes(issued):
        lrows.append([P(_esc(prov), "tdb"), P(_esc(req)), P(_esc(stt), "smallm"), P(_esc(how))])
    story.append(_grid(lrows, [38 * mm, W - 38 * mm - 27 * mm - 52 * mm, 27 * mm, 52 * mm], zebra=True))

    # ---- 6. limitations
    story += _rule_h2("6. Limitations", S)
    story.append(P("Detection is based on patterns, labels and optical character recognition. Unusual formats, "
                   "handwriting and poor-quality scans may not be fully detected, which is why each document was "
                   "reviewed after redaction. Information that is not an identifier (amounts, dates, narrations, "
                   "assessment years and statutory references) is deliberately retained so that the documents remain "
                   "useful for analysis. This certificate records the safeguards applied to the documents listed; it "
                   "is not an opinion on the compliance of the engagement as a whole with the enactments referred to "
                   "above.", "just"))

    # ---- 7. certificate + signature
    sig_rows = [("For", "(name of firm)"), ("", "Chartered Accountants"), ("Firm Registration No.", ""),
                ("Name", ""), ("", "Partner / Proprietor"), ("Membership No.", ""), ("UDIN (if generated)", ""),
                ("Place", ""), ("Date", "")]
    sig = []
    for k, hint in sig_rows:
        filled = hint and not hint.startswith("(")
        sig.append([P(k, "smallm"), P(hint if filled else ("<font color='#8A94A6' size='6.5'>" + hint + "</font>" if hint else ""), "td")])
    stbl = Table(sig, colWidths=[34 * mm, 70 * mm], rowHeights=[15] * len(sig))
    sst = [("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
    for i, (k, hint) in enumerate(sig_rows):
        if k:
            sst.append(("LINEBELOW", (1, i), (1, i), 0.6, colors.HexColor("#555555")))
    stbl.setStyle(TableStyle(sst))
    seal = Table([[P("<font color='#8A94A6'>Signature and seal</font>", "tdc")]], colWidths=[48 * mm], rowHeights=[38 * mm])
    seal.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#8A94A6")), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    block = Table([[stbl, seal]], colWidths=[W - 52 * mm, 52 * mm])
    block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    cert_text = P("On the basis of the procedure described above and the review carried out, it is certified that the "
                  "documents listed in the Schedule were redacted on the local computer before being made available for "
                  "analysis with the artificial intelligence tool named above, and that the redacted copies so made "
                  "available are those identified by the fingerprints in Annexure A.", "just")
    story += [CondPageBreak(95 * mm)] + _rule_h2("7. Certificate", S)[1:] + [KeepTogether([cert_text, Spacer(1, 10), block])]

    # ---- annexure
    story += [PageBreak(), P("Annexure A", "kicker"), P("Document fingerprints (SHA-256)", "h2"),
              P("A fingerprint changes if even one character of a file changes. It identifies exactly which original "
                "and which redacted copy this certificate relates to, without containing any of the client's "
                "information.", "note"), Spacer(1, 6)]
    frows = [[P("S. No.", "th"), P("Original document", "th"), P("Redacted copy", "th")]]
    for i, r in enumerate(results, 1):
        frows.append([P(str(i), "tdc"), [P(_esc(r.name), "small"), P(r.sha_in or "-", "mono")],
                      [P(_esc(names.get(r.name, "-")), "small"), P(r.sha_out or "-", "mono")]])
    story.append(_grid(frows, [12 * mm, (W - 12 * mm) / 2, (W - 12 * mm) / 2], zebra=True))

    def decorate(canv, doc):
        canv.saveState()
        w, h = A4
        if doc.page > 1:
            canv.setFont("Times-Bold", 8)
            canv.setFillColor(C_NAVY)
            canv.drawString(17 * mm, h - 11 * mm, "Certificate of Redaction of Client Documents")
            canv.setFont("Helvetica", 7.5)
            canv.setFillColor(C_MUTED)
            canv.drawRightString(w - 17 * mm, h - 11 * mm, ref)
            canv.setStrokeColor(C_NAVY)
            canv.setLineWidth(0.5)
            canv.line(17 * mm, h - 12.8 * mm, w - 17 * mm, h - 12.8 * mm)
        canv.setStrokeColor(C_RULE)
        canv.setLineWidth(0.5)
        canv.line(17 * mm, 13 * mm, w - 17 * mm, 13 * mm)
        canv.setFont("Helvetica", 7)
        canv.setFillColor(C_MUTED)
        canv.drawString(17 * mm, 9 * mm, f"{ref}   |   Generated on the local computer by {APP_NAME} v{VERSION}")
        canv.drawRightString(w - 17 * mm, 9 * mm, f"Page {doc.page}")
        canv.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=17 * mm,
                            bottomMargin=18 * mm, title="Certificate of Redaction of Client Documents",
                            author="", creator=f"{APP_NAME} v{VERSION} by {AUTHOR}")
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return _page_x_of_y(buf.getvalue())


def _page_x_of_y(pdf: bytes) -> bytes:
    """Turn 'Page n' into 'Page n of N' (total known only after layout)."""
    import pymupdf
    d = pymupdf.open(stream=pdf, filetype="pdf")
    total = d.page_count
    for page in d:
        for inst in page.search_for(f"Page {page.number + 1}"):
            if inst.y0 > page.rect.height - 40:
                page.add_redact_annot(inst + (-1, -1, 1, 1))
                page.apply_redactions(images=0, graphics=0)
                txt = f"Page {page.number + 1} of {total}"
                x = page.rect.width - 17 * 72 / 25.4 - pymupdf.get_text_length(txt, "helv", 7)
                page.insert_text((x, inst.y1 - 1.6), txt, fontsize=7, fontname="helv", color=(0.29, 0.33, 0.4))
                break
    out = d.tobytes(garbage=3, deflate=True)
    d.close()
    return out
