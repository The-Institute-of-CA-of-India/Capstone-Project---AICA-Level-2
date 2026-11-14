# End-to-End User Guide

1. **Install:** Extract project. On Windows install Python 3.10+ once, then double-click `RUN_PYTHON_WINDOWS.bat`. Internet is required to download missing packages. For no-Python use, build the EXE first.
2. **User Guide tab:** Read instructions in the application.
3. **Clients:** Create/select a client; verify assessee legal name, trade name, PAN, GSTIN, entity type and address.
4. **CA Profile:** Save firm/signatory name, MRN, FRN and address.
5. **Certificate Workspace:** Choose one of four certificates and select ITR or GST as appropriate. Select correct net-worth method.
6. **Import ITR PDF:** Import supported ITR PDF/acknowledgement, check assessment year, filing date, ACK and income. ITR-3/4/5 JSON import is available from workspace where supported.
7. **Assets – Liabilities:** For supported ITR JSON, import balance sheet and reconcile assets minus outside liabilities; this is **business** equity, not necessarily personal net worth.
8. **GSTR-1 Import / GSTR-3B Import:** Import relevant period PDFs. Verify all months/quarters and amendments; avoid mixing financial years.
9. **GST Turnover Summary:** Review totals and reconcile differences between GSTR-1 and GSTR-3B before certification.
10. **Saved ITR financials:** Use saved-data refresh to repopulate year-wise turnover, income and business capital. Confirm correct AY, especially for multi-year certificates.
11. **Defaults & Certificate Generation:** Review purpose, recipient, date, address, scope, wording and financial values; generate editable Word certificate and MRL.
12. **Management Representation:** Review representation letter, have client authorise/sign where appropriate.
13. **Review and issue:** Check evidence, calculations, name/PAN, reporting date, professional requirements and UDIN as applicable; save signed copy separately.
14. **Reset:** Clear only intended current form/imported records. Back up the local database before deletion or upgrade.

**Files:** JSON is preferred for schema-based ITR extraction; searchable PDFs may work; scanned PDFs may require Tesseract OCR. Do not assume unsupported formats are automatically recognised. Avoid actual client documents in public demonstrations.
