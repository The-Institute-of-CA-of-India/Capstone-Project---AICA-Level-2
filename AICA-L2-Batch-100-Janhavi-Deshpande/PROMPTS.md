# Key Prompts

The tool was built with Claude (Anthropic) over several conversations. Below are the key prompts in the order they were given. They have been lightly edited for spelling, and the replies are summarised. All testing used made-up demo data. No client data or portal password was shared with the AI.

## 1. The idea

> My AICA Level 2 capstone: a GST automation tool for a mid-size CA firm.
> 1. A Chrome extension downloads GSTR-1, 3B and 2B (my existing extension does 2A; tweak it for 2B).
> 2. If the returns are already downloaded, skip step 1; combine the returns in Excel, including 12 months of 2B.
> 3. Upload the purchase register (Excel / CSV) and reconcile it with 2B.
> 4. Match on invoice no., invoice date, GSTIN, taxable value and tax as Matched / Likely matched (only invoice no. and/or date differ) / Unmatched.
> 5. Give details of unmatched and likely matched invoices.
> 6. Send an automatic mail to vendors.
> Look at earlier capstones, suggest what else a mid-size firm would need, and keep it **100% offline except for getting data from the website**.

*Result: the plan; the extension updated for GSTR-2B; the offline page with steps 1–5.*

## 2. Purchase register format

> Can you share a format for the purchase register?
> Can we include columns for HSN/SAC code, description and the ledger head as per books?

*Result: `Purchase_Register_Format.xlsx`, plus HSN-wise and ledger-wise reports.*

## 3. Fixing the GSTR-2B download (live testing)

> It is getting stuck on 2B downloading as it takes time. *(screenshot)*
> It is just waiting here, nothing happening. *(screenshot)*
> Here is the link: gstr2b.gst.gov.in/gstr2b/auth/gstr2bdwld
> Let's not do a manual download, because auto download is an important step in the project.

*Result: extension versions 2.5.1 to 2.5.4. They wait for slow builds, follow the 2B site, and never log in twice. Tested together on the live portal, with the participant typing the password and captcha. Q1 and Q2 GSTR-2B downloaded.*

## 4. Annual return

> What should we include for GSTR annual returns? *(then)* Yes, build items 1–3.

*Result: Step 6, the GSTR-9 working paper. It covers Tables 4–8, 12, 13 and 18, explains 8D invoice by invoice, and raises risk flags.*

## 5. Documentation

> Give me a Word / .md document of everything we have developed till this point. Keep it exact and hand over all the details; don't miss a single point.

*Result: `docs/GST_Automation_Tool_Handover.docx` / `.md`.*

## 6. Technology choice

> Would Python / Streamlit be better for large data? Don't rush to write a Python program; let us first decide.
> Let us stick to .html for the capstone, but I would surely like to test it further for large data on Python. Certainly not now.

## 7. Refinements, agreed before changing

> Don't rush into making any changes; first arrive at a common conclusion.
> 1. Keep the vendor-wise sheet risk-first; make the supplier-wise ITC sheet A–Z.
> 2. The .eml file gives a security warning.
> 3. Compose writes in paragraph format; I want a neat table.
> 4. Add a column for the month in which ITC was claimed in GSTR-3B.

*Result:*

- *the supplier sheet sorted A–Z;*
- *the single .eml button removed (the ZIP of drafts kept);*
- *Compose pastes a formatted table with Ctrl+V;*
- *the "ITC Claimed in GSTR-3B (Month)" column, used for 6A1, 8C, Table 13 and the monthly 3B check.*

## 8. Submission

> This looks good for a capstone-level project. Now help me with the video and presentation to be uploaded on GitHub.

*Result: the presentation deck, `VIDEO_SCRIPT.md`, and this repository folder.*
