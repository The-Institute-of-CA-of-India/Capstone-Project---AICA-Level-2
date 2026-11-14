# Project Report — Smart Certificates V54

## Candidate
CA Nimeshkumar Maheshbhai Patel | ICAI MRN 165969 | AICA Level-2 Batch 109, Gandhinagar.

## 1. Executive summary
Smart Certificates is a Windows desktop application to assist CAs with preparing certificates from supported income-tax and GST records. It imports data, identifies relevant year-wise financial values, provides review and adjustment interfaces, and creates editable Word certificates, MRL and Excel workings.

## 2. Problem statement
Manual extraction of ITR/GST figures and repetitive certificate drafting increase time and the risk of transcription errors. Multiple ITR schemas and financial years add complexity.

## 3. Objectives
Reduce repeated entry, standardise financial extraction, retain editable certificate templates, maintain local client data, and preserve professional review before certification.

## 4. Scope
- Client/CA profiles, ITR-3/4/5 JSON, supported PDF and GST import
- Turnover and business-equity computations
- Four certificate types and MRL; Word and Excel output
- V54 user guide and simplified workflow

## 5. Architecture
PyQt6 user interface -> import and extraction functions -> SQLite client/ITR financial tables -> certificate working/review -> python-docx/openpyxl output. Local file storage in the user's Documents/CA_Document_Manager folder.

## 6. Tools
Python: core programming. ChatGPT: iterative coding, debugging, testing assistance and documentation. PyQt6: GUI. SQLite: local database. PyMuPDF: text PDF extraction. JSON: structured ITR data. python-docx: Word documents. openpyxl: Excel files. Pillow/pytesseract: optional image OCR. PyInstaller: Windows distribution. GitHub: version control and submission.

## 7. Functional workflow
Choose client -> select certificate -> import relevant ITR/GST -> review assessment year, turnover, capital/assets/liabilities -> fill certificate details -> review -> generate Word -> issue only after professional checks.

## 8. Practical example
For ITR-3 with presumptive business income under section 44AD, turnover must come from gross turnover/receipts, **not** the presumptive profit figure. A partnership ITR-5 uses partner/member fund terminology; proprietorship uses proprietor capital. Verify assessment-year mapping.

## 9. Validation and limitations
Source compilation and parser import can be checked, but the complete GUI, Word formatting, PDF/OCR variants and Windows EXE require testing on the user's Windows PC. The program is primarily rule-based, not a live generative-AI application. Figures must be reconciled with returns and books; CA judgement and applicable certification requirements remain essential.

## 10. Benefits and future scope
Faster document preparation, consistent templates, less repeated entry; future improvements include broader PDF schema coverage, automated tests, installers, and robust issuance versioning.

## 11. Conclusion
The project demonstrates practical application of AI-assisted software development to accounting practice automation, with human review retained for professional certification.
