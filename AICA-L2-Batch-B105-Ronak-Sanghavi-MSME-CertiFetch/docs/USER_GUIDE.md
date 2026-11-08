# MSME CertiFetch: User Guide

MSME CertiFetch verifies Udyam registration numbers in bulk on the official portal. It saves each certificate as a PDF and builds an Excel report. You only type each captcha, and the tool handles the rest.

See `MSME_CertiFetch_Image_Guide.png` for a picture-by-picture version.

## What you need

- A Windows 10 or 11 PC with an internet connection
- Google Chrome. Get it from [google.com/chrome](https://www.google.com/chrome/) if you do not have it.

Nothing else needs to be installed.

## Install

1. Double-click `MSME_CertiFetch_Setup_v1.0.exe`.
2. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.
3. Click **Next**, then **Install**, then **Finish**. You do not need administrator rights.

To remove it later, use **Settings > Apps > Installed apps**.

## How to use

1. Open **MSME CertiFetch** from the desktop or the Start menu.
2. Click **Get Excel template** and save the file. It is selected for you automatically.
3. Enter one Udyam number per row in column A, in the format `UDYAM-XX-00-0000000`. Leave column B (Status) empty. Save and close the file.
4. Click **Browse** next to **Save certificates to** and choose a folder.
5. Click **Start processing**. Chrome opens the portal and fills in the number. Leave that window alone. The first run can take a little longer.
6. When a captcha appears, the cursor is already in the box. Type it exactly as shown (it is case sensitive) and press **Enter**.
7. The app minimises while it works and comes back for the next number.

## Keyboard and buttons

| Key or button | What it does |
|---|---|
| Enter or **Submit** | Sends the captcha |
| F5 or **Refresh** | Gets a new captcha, without using up an attempt |
| **Skip** | Marks the number Skipped and moves to the next one |
| **Stop** | Ends the run and marks the current number Pending |

## Results

| Output | Where |
|---|---|
| Certificates | Your chosen folder, named `Enterprise Name - UDYAM-XX-00-0000000.pdf` |
| Report | `UDYAM_Report.xlsx` in the same folder, with one row per number and the latest two classification years |
| Status of each number | Column B of your Excel file: Done, Failed, Skipped or Pending |

The report builds up across runs in the same folder. If a number is processed again, its row is updated. If the report is open in Excel when a run ends, the tool saves a new dated copy.

## Continuing a stopped run

Run the same Excel file again. Rows marked Done are left out, and Failed, Skipped and Pending rows are tried again.

## Troubleshooting

| What you see | What to do |
|---|---|
| "Found 0 number(s) to process" | Column B already says Done. Clear it, or use a new template. |
| "Verification did not reach result page" | Wrong captcha, an invalid number or a portal error. The tool tries up to 3 times, then marks the row Failed. |
| "Close input Excel to save status" | Close the Excel file while the tool is running. |
| Chrome does not open | Update Chrome, check your internet connection, then restart the app. |
| The portal will not load | The government site may be down or busy. Try again later. |
