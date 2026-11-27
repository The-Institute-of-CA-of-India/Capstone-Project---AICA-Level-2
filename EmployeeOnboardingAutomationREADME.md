# Payroll and Hiring Automation: Project Overview

From CTC entry to appointment letter, with one record of every offer.

Last updated: 27 November 2026 (version 13)

---

## 1. Purpose

This project automates the paperwork that runs from deciding a candidate's salary to issuing their appointment letter. HR enters a candidate's CTC (cost to company) and job details once. The system then works out the full salary structure, creates the offer letter, records the offer, issues an employee ID when the candidate accepts, and sends the appointment letter.

## 2. The problem it solves

Before this project:

- Salary structures were built by hand for each candidate.
- Offer and appointment letters were typed one by one.
- Employee IDs were issued manually.
- There was no single record of who had been offered, who had accepted and who had declined.

After this project:

- Formulas work out the salary structure, and it always adds back to CTC.
- Letters are created as PDFs in one click, with the salary structure attached as Annexure A.
- The next employee ID (RK001, RK002 and so on) is issued automatically on acceptance and is never reused.
- One Google Sheet holds the record of every offer, its status and its employee ID.

## 3. How it works, end to end

```
CTC Master Excel  ->  Dashboard (Chrome or Edge)  ->  Offer letter PDF
                                |
                                +-> n8n Letters workflow  -> Gmail (draft or send)
                                +-> n8n Tracker workflow  -> Google Sheet (status: Pending)

Candidate accepts -> Accept in dashboard -> next Employee ID -> Appointment letter emailed
                                                             -> Google Sheet updated
```

**Stage 1: Offer**

1. **Enter in Excel.** HR fills the yellow input cells in the CTC Master. Formulas work out every salary component and the monthly in-hand salary.
2. **Upload.** HR opens the dashboard and uploads the Excel. The dashboard recalculates every row and shows the salary breakup.
3. **Check flags.** Any row with an error is shown in red and cannot be sent until it is fixed in the Excel.
4. **Send offer.** One click creates the offer letter PDFs. They are saved as Gmail drafts by default, or emailed after HR confirms the recipient list.
5. **Logged as Pending.** Each emailed offer is added to the Google Sheet Offer Tracker with status Pending.

**Stage 2: Appointment**

6. **Candidate accepts.** HR clicks Accept in the dashboard (or Decline if the candidate declines).
7. **ID issued.** The tracker gives the candidate the next permanent employee ID.
8. **Appointment letter.** The dashboard creates the appointment letter with Annexure A and emails it, or saves it as a Gmail draft.
9. **Download list.** The list of appointed employees can be exported to Excel at any time.

## 4. Tools used

| Tool | What it does | Where it runs |
|---|---|---|
| Microsoft Excel (CTC Master) | HR fills the input cells. Formulas build the salary structure and in-hand salary. Holds the job descriptions and assumptions. | HR's computer |
| HTML dashboard | A single file opened in Chrome or Edge. Reads the Excel, checks every row, shows totals and charts, creates the PDF letters and calls n8n. Uses two libraries built into the file: SheetJS (reads Excel) and jsPDF (creates PDFs). | HR's computer, works offline until a letter is sent |
| PDF letters | Offer letter and appointment letter, each with Annexure A (salary structure). | Created inside the dashboard |
| n8n: Letters workflow | Receives the letters from the dashboard and creates Gmail drafts or sends the emails. | n8n cloud |
| n8n: Tracker workflow | Adds offers to the Google Sheet, records Accepted or Declined, and issues the next employee ID. | n8n cloud |
| Gmail | Sends letters from the company's own Gmail account. A copy stays in Sent. | Google |
| Google Sheets (RK Offer Tracker) | The permanent record of every offer, status and employee ID. | Google |
| Google Apps Script | Optional. Issues employee IDs if staff change a status by typing directly in the sheet. | Inside the Google Sheet |

## 5. Salary rules built into the system

| Component | Rule |
|---|---|
| Basic | 50% x (CTC less variable pay) / 1.025, monthly Basic rounded up to the next 1,000 |
| HRA | 50% of Basic |
| Special Allowance | Balancing figure, so all components add back to CTC |
| Bonus (Monthly) | Entered monthly, part of gross salary |
| Yearly Bonus | Entered annually, shown in the Annual column only |
| Variable Pay | Self performance plus company performance, annual only |
| Reimbursements | Food allowance (Nil, 4,400 or 8,800 a month) plus employer NPS (Nil, 10% or 14% of Basic) |
| Employer PF | 12% of Basic, capped at 25,000 Basic a month (company policy) |
| Employer ESIC | 3.25% when monthly Basic is below 21,000 |
| Gratuity | 5% of Basic |
| Insurance | As entered (monthly) |
| Monthly in-hand | Monthly gross less employee PF (12%), employee ESIC (0.75%) and professional tax (200 a month) |

Total CTC = Gross Salary (A) + Yearly Bonus (B) + Reimbursements (C) + Variable Pay (D) + Employer Contributions (E).

Probation is 12 months for Trainees and 6 months for all other roles. All rates can be changed in the dashboard Settings and on the Assumptions sheet in the Excel.

## 6. Controls and safeguards

1. **Salary must reconcile.** Every row must add back to CTC and meet the 50% Basic rule, or it is flagged.
2. **Errors block the row.** A negative special allowance, an invalid email, a duplicate name, a designation outside its department, or a difference between the Excel and the dashboard stops that row from going out.
3. **Drafts by default.** Letters are saved as Gmail drafts unless HR chooses to send them and confirms the recipient list.
4. **No duplicate offers.** A candidate whose email is already in the tracker is skipped with a warning, and an accepted candidate is never sent another offer. Re-offers to people who declined are counted and kept in the offer history.
5. **IDs never reused.** Employee IDs come from a counter held in n8n and stay fixed, even if a candidate later declines.
6. **Only emailed letters count.** Gmail drafts are not recorded in the tracker, so the dashboard counts show only letters actually sent.
7. **Data stays in our accounts.** Salary inputs stay in the Excel and the browser. Letters go out from our own Gmail, and the Google Sheet holds the offer record and a salary summary.

## 7. Where the data goes

| Stays on HR's computer | Sent to the cloud (only when HR clicks Email or Accept) |
|---|---|
| The Excel file with full salary inputs and formulas | Letter PDF and email text, to Gmail through n8n |
| Rows loaded in the dashboard | Offer record: name, email, department, designation, CTC, status, employee ID |
| Company settings: rates, letterhead, signatory | Offer history: times offered and status changes |
| Draft PDFs until downloaded or emailed | Salary summary: annual gross, bonus and variable, reimbursements, employer contributions, monthly in-hand |

## 8. Files

All files are in the `ctc-automation/` folder.

| File | Purpose |
|---|---|
| `CTC_Master_RK_Associates_v13.xlsx` | Blank CTC Master template with sheets: CTC Master, Read Me, Assumptions, Job Descriptions, CTC Breakup |
| `RK_CTC_Dashboard_v13_clean.html` | The dashboard. Opens empty and removes data saved by earlier versions each time it opens |
| `OfferTracker_AppsScript.gs` | Optional Apps Script for the Google Sheet |
| `SETUP_GUIDE.md` | Setup and day-to-day instructions |
| `PROJECT_OVERVIEW.md` | This document |
| `presentation/Payroll_Automation_Deck_v13.pptx` | 15-slide presentation with technical section, closing remarks and thank you slide |
| `presentation/How_to_Explain_the_Steps.md` | Speaking notes for the steps |
| `sample_output/` | Sample offer and appointment letters (produced by an earlier version) |
| `archive/` | Earlier versions of the Excel, dashboard, guide and deck |

**Online parts**

- n8n workflow "RK Offer and Appointment Letters: Email from Dashboard"
- n8n workflow "RK Offer Tracker: Sync from Dashboard"
- Google Sheet "RK Offer Tracker": Offers tab (18 columns, A to R), Appointed Employees tab, How it works tab

### CTC Master columns

- **Inputs (A to N):** Employee Name, Email ID, Department, Designation, Start Date, Location, Annual CTC, Yearly Bonus (Annual), Bonus (Monthly), Variable Pay: Self, Variable Pay: Company, Food Allowance (Monthly), NPS Option, Insurance (Monthly)
- **Calculated (O to AO):** total variable pay, Basic, HRA, Special Allowance, gross, reimbursements, employer contributions, total CTC, reconciliation difference, 50% rule check, employee PF and ESIC, professional tax, net in-hand (annual and monthly), probation, Flag
- **Letter details (AP):** Candidate Address

The template holds up to 100 employees. Departments: Sales, Finance, Development, Marketing, QA and Professional Service, with dependent designation dropdowns and draft job descriptions for each role.

## 9. Setup summary

1. Open `RK_CTC_Dashboard_v13_clean.html` in Chrome or Edge by double-clicking it.
2. Check Settings once: company name, letterhead address, contact line, HR name and designation, working hours. The two n8n web addresses are already filled in, and the connection to n8n needs no further setup.
3. Download the CTC Master from the dashboard (top right) or use the v13 Excel in the folder.
4. Test once by putting your own email on one row and creating a Gmail draft.
5. Both n8n workflows must stay published (active) in n8n.

See `SETUP_GUIDE.md` for full details.

## 10. Current status (27 November 2026)

| Item | Status |
|---|---|
| CTC Master Excel | Version 13, blank template, no records |
| Dashboard | Version 13 clean file, opens empty |
| n8n Letters workflow | Published |
| n8n Tracker workflow | Published (version 13) |
| Google Sheet | No records, next employee ID RK001 |
| Presentation | 15-slide deck ready |
| Testing | Excel and dashboard in-hand salary matched exactly on 6 test salaries from 2.4 lakh to 36 lakh. Offer, accept and appointment steps tested against simulated n8n replies. |

**Points still to confirm**

1. The PF cap of 25,000 Basic is company policy. The statutory ceiling is 15,000.
2. ESIC is tested on Basic. The law tests gross wages up to 21,000.
3. Gratuity is set at 5% of Basic. The statutory accrual is about 4.81%.
4. Food allowance is treated as a meal card outside gross salary. If it is paid in cash, it should sit in gross.
