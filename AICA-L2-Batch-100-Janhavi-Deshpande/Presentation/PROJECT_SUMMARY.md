# Project Summary

**Title:** GST Automation Tool for a Mid-size CA Firm: from the GST portal to the GSTR-9 working paper, offline  
**Participant:** CA Janhavi Deshpande · AICA Level 2 · Batch 100 · Pune  
**Video:** https://youtu.be/842Hn1RyBLE  
**Built with:** Claude (Anthropic), an AI assistant. The participant defined the requirements, tax rules and tests. The AI wrote the code.

## Problem

A mid-size CA firm repeats the same GST work for every client:

- downloading GSTR-1, 3B and 2B, which is 36 files a year per client;
- matching the purchase register with GSTR-2B using VLOOKUPs, which fail on small typing differences;
- writing to each vendor about missing invoices;
- at year end, rebuilding GSTR-9 Tables 6 and 8 and explaining 8D.

The work is repetitive, prone to errors, and needs no judgment until the differences are found.

## Solution

| Stage | Component | What it does |
|---|---|---|
| 1. Download | Chrome extension v2.5.4 | Logs in (the user types the captcha) and downloads GSTR-1, 3B and 2B for chosen quarters. Skips files already downloaded and waits for slow GSTR-2B builds. |
| 2. Reconcile returns | Offline HTML page | Reads the PDFs and Excel files. Compares GSTR-1 with 3B and 3B ITC with 2B, and combines 12 months of 2B. |
| 3. Match books | Offline HTML page | Six passes, strictest first, sort each invoice into Matched, Likely matched (only invoice number or date differs) or Unmatched, with a reason. Gives vendor-wise, supplier-wise and ledger-wise sheets. |
| 4. Email vendors | Offline HTML page | One draft per vendor with a formatted table of their invoices (Compose, then Ctrl+V, or a ZIP of drafts). Vendors are ordered by ITC at risk. |
| 5. GSTR-9 | Offline HTML page | Excel working paper with formulas: Tables 4–8, 12, 13, 18 (HSN); 8D explained invoice by invoice; risk flags for 17(5), 16(4), Rule 37, RCM, and 3B against books. |

## Design principles

- **Offline:** client data never leaves the computer. Only the download touches the internet, and a browser test showed no network requests from the page.
- **Professional in control:** the user types the captcha. The password is kept in memory only, and mails are drafts the user sends.
- **No installation:** one HTML file. All outputs are ordinary Excel workbooks.

## Results (made-up demo data)

- Q1 demo: 46 matched, 3 likely matched and 9 unmatched, as planted.
- Full-year demo:
  - 6A1 ₹9,000
  - 8C ₹14,067.98
  - 8E ₹8,010
  - 8F ₹90,720
  - 8G ₹36,000
  - 8D unexplained: nil
- 18 ITC risk flags were raised, plus 1 month where 3B differs from the books.
- Live portal: GSTR-2B for Q1 and Q2 of FY 2025-26 downloaded by the extension.

## How AI was used

1. **Describe:** the six-point idea and the rules for matching and GSTR-9, given in plain English.
2. **Build:** the AI wrote the extension and the page.
3. **Test:** made-up data with planted errors, a mock portal, then a live session in which the participant typed the password and captcha.
4. **Refine:** each problem reported became a new extension version, up to v2.5.4.

The tax law and every judgment call stayed with the CA.

## Limitations and next steps

The current version:

- handles one client at a time;
- needs updating if the portal changes;
- has not been tested on large or real data.

Next steps:

- pilot inside the firm;
- a Python version for large data;
- Outlook testing;
- GSTR-9C.
