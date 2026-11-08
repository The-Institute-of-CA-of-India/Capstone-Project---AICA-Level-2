# Verification

Verified on 31 October 2026 using Python 3.14.8 and Flask 3.1.2.

## Automated application checks: passed

Run `python -m unittest -v` in the project folder. Four test methods cover:

- Every main page and all five lesson pages return successfully.
- All ten workbook endpoints return XLSX content with download headers.
- Missing pages, unavailable lessons, invalid download kinds, incomplete quizzes, invalid JSON and missing CSRF tokens return controlled errors.
- All five practice activities and quizzes can be completed, producing 5/5 progress and milestones.
- Lower retakes retain the previous best score; bookmarks and display names save correctly.
- HTML entered in a display name is escaped.
- Recreating the application with the same database and browser cookie preserves progress; a different browser profile starts independently.
- Placement scoring and all eight offline coaching actions work.
- Equivalent supported formulas are accepted; constants, wrong results, arbitrary code calls, exponentiation, invalid ranges and division by zero are rejected.

## Browser checks: passed

In the in-app browser, opened the overview, followed Start learning, submitted the first practice answer, completed the first quiz and observed the saved completion result. Searched the formula library for SUM, verified filtering and the Copied confirmation. Inspected desktop (1440 × 1080) and phone (390 × 844) layouts. At both widths the page content fits horizontally. The phone navigation wraps to expose all five sections. A screenshot is supplied beside the project ZIP.

## Workbook checks: passed with native-Excel verification limit

Created and rendered all ten files with Artifact Tool. Reviewed each sheet for readable headers, instructions and data. Checked calculated solutions: 60 and 120 in lesson 4; 80, 20, 8, 40 and 4 for the five summary functions in lesson 5. Changed the tax rate from 5% to 10%, verified recalculation, then restored 5%. Formula error scans found no matches. Independently inspected exported files using openpyxl in read-only verification: all ten files are valid, number formats are preserved, and cached values match expected results. No workbook was authored with openpyxl.

Microsoft Excel itself was not opened for native rendering or recalculation. The supplied solution formulas use standard arithmetic and established functions. The workbook renderer displayed some two-decimal values with a shortened trailing zero; the exported cells were checked to have the correct `0.00` format.

## Scope and remaining work

This is the requested first version: five complete beginner lessons, with the full future curriculum clearly labelled Coming soon. Intermediate, Advanced and Applied project lessons are outlines, not finished courses. The optional coach is an explicitly labelled offline fallback with prepared guidance; there is no AI provider integration or free-text understanding. Browser practice is deliberately limited and does not grade every Excel interaction. No cross-device accounts, public hosting or production authentication are included. Responsive and keyboard-friendly elements were inspected, but no formal accessibility audit or full browser/device matrix was performed.
