# Test Checklist

Last tested on 26-10-2026 on Windows 11, Python 3.14.8 (Tk 9.0, SQLite 3.50.4, PyKCS11 1.5.20).

**Automated** means a test in `tests/test_core.py` (63 tests, all passing).
**GUI** means `tests/smoke_gui.py`, which opens the real window, drives the screens with a simulated
token and passes.
**Real token** means a check with an actual ePass2003 token (Capricorn certificate) plugged into
this PC.
The **Manual** column is for the firm's own acceptance run.

## Original checks (from the brief)

| # | Check | Result | How it was verified | Manual |
|---|---|---|---|---|
| 1 | Add a client and record an inward transaction | Pass | `test_1_to_4_...`; GUI: inward saved through the form | ☐ |
| 2 | Token appears in DSC in Custody | Pass | `test_1_to_4_...`; GUI: dashboard Live Custody card went up by 1 | ☐ |
| 3 | Outward entry removes the token from live custody | Pass | `test_1_to_4_...`; GUI: saved through the DSC Outward form | ☐ |
| 4 | Inward and outward entries remain in their registers | Pass | `test_1_to_4_...` | ☐ |
| 5 | An expected DSC appears in DSC Awaited from Clients | Pass | `test_5_6_awaited_until_received` | ☐ |
| 6 | After its inward receipt, it is no longer awaited | Pass | `test_5_6_...`, `test_auto_link_by_token_serial` | ☐ |
| 7 | Expiry yesterday / today / +7 / +15 / +30 / +31 days | Pass | `test_7_classification_boundaries`, `test_7_alert_lists_and_counts` | ☐ |
| 8 | A blank expiry date shows under Expiry Date Unknown | Pass | `test_7_alert_lists_and_counts` | ☐ |
| 9 | An expired DSC still shows in live custody if not returned | Pass | `test_9_expired_token_still_in_custody` | ☐ |
| 10 | Renewing a certificate keeps the previous certificate's history | Pass | `test_10_renewal_preserves_history`, `test_inward_cert_conflict` | ☐ |
| 11 | CSV exports and database backup | Pass | `test_11_backup_and_csv`; GUI: 7 exports and a dated backup written | ☐ |
| 12 | Close and reopen: all records still there | Pass | `test_12_reopen_keeps_records` | ☐ |

## Changes of 26-10-2026

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| PAN whose 4th character isn't "P" is rejected with a clear message | Pass | `test_pan_must_be_individual` (C, F, T and H PANs rejected; P accepted) | ☐ |
| Every inward entry goes to the custodian automatically; no inward without a custodian | Pass | `test_inward_needs_custodian_and_goes_to_custodian`; GUI | ☐ |
| Only one custodian at a time; appointing a new one relieves the old one and hands over his tokens | Pass | `test_one_custodian_and_handover` (also enforced by the database) | ☐ |
| Issue to staff and return, stamped with the system time; default due back at end of day | Pass | `test_staff_issue_and_return_with_system_time`; GUI: return recorded from the DSC in Custody screen | ☐ |
| No staff-to-staff transfers; consultant and outward only via the custodian | Pass | `test_no_staff_to_staff_and_everything_through_custodian`; GUI: Issue disabled while with staff, outward refused | ☐ |
| Client collected token from consultant ends custody; history shows the full chain | Pass | `test_client_collected_from_consultant` | ☐ |
| Only the latest movement can be cancelled; history kept | Pass | `test_cancel_only_latest_movement` | ☐ |
| Overdue back to the custodian is flagged and counted on the dashboard | Pass | `test_overdue_back_to_custodian` | ☐ |
| Expiry to the minute: 11:00 AM expiry shows Expired at 1:00 PM the same day | Pass | `test_expiry_time_of_day`, `test_expiry_time_stored_and_listed` | ☐ |
| Expiry without a time is taken as 12:00 AM | Pass | `test_expiry_time_of_day` | ☐ |
| A database from the earlier version is upgraded automatically | Pass | `test_old_database_is_upgraded` | ☐ |
| Certificate decoding (dates in Indian time, holder, issuer, serial) | Pass | `test_parse_certificate_times_in_local_time`; all 87 Windows root certificates decode | ☐ |
| Read from Token with any PKCS#11 driver; same token through two drivers counted once | Pass | `test_read_tokens_from_simulated_pkcs11_driver` | ☐ |
| No PyKCS11 / no driver: clear message, no crash | Pass | `test_no_pkcs11_falls_back_without_crashing` | ☐ |
| Read from Token with a real token | Pass | Real token: the ePass2003 driver was found automatically. The DSC Inward screen filled the token serial (16 characters), holder name, certificate serial, issuer and issue/expiry date and time. | ☐ |
| Every screen opens without errors and fits a 1366×768 screen | Pass | GUI smoke test; screenshots reviewed | ☐ |

## Changes of 26-10-2026 (second set)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| Filters reset when the user leaves a screen and comes back; dashboard cards still apply their period | Pass | GUI smoke test (inward register, custody, alerts, movement register) | ☐ |
| Report search matches DSC holder and client names only (not token numbers) | Pass | `test_report_search_by_holder_and_client_name_only` | ☐ |
| Left menu: no subtitle, "Designed by ABJ@2026" at the bottom; PIN note in the status bar | Pass | Screenshot of the trial .exe | ☐ |

## Changes of 26-10-2026 (third set)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| PAN optional, mobile required, "PAN pending" filter | Pass | `test_pan_optional_mobile_required` | ☐ |
| Same mobile allowed only with a different name (case, spaces, dots ignored) | Pass | `test_same_mobile_only_with_a_different_name` | ☐ |
| Older database with mandatory PAN is upgraded with all data kept | Pass | `test_old_database_with_mandatory_pan_is_upgraded`; also tried on a copy of the previous real database | ☐ |
| Token lost while with staff: custody ends, recorded who had it, leaves expiry alerts | Pass | `test_lost_while_with_staff_ends_custody_and_leaves_alerts` | ☐ |
| Inactive token received again: asked to reactivate | Pass | `test_inactive_token_received_again` | ☐ |
| New token replaces the client's old token (old one made Inactive, linked) | Pass | `test_new_token_replaces_old_one`; GUI | ☐ |
| Inward screen shows NEW TOKEN / SAME CERTIFICATE / RENEWED CERTIFICATE from the token plugged in | Pass | GUI smoke test (renewed certificate saved as renewal; new token with replacement) | ☐ |
| Status changes need a reason and appear in Token History | Pass | `test_status_changes_need_a_reason`, `test_inactive_token_received_again` | ☐ |

## Changes of 29-10-2026

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| Excel template downloads with Clients and Instructions sheets; filled file reads back (numbers kept as text, empty rows ignored); other workbooks refused | Pass | `test_template_round_trip`; GUI smoke test downloads and imports a template | ☐ |
| Import rules: skip missing name or mobile, invalid mobile, same name and mobile (in app or file), existing or duplicate PAN; import without an invalid PAN or email, with a note | Pass | `test_import_rules` (12 rows covering every case; re-import adds nobody) | ☐ |
| Mobile number structure (10 digits starting 6–9, +91 or 0 allowed) in the client form too | Pass | `test_mobile_structure_in_client_form` | ☐ |
| Preview window lists every row with its result before saving | Pass | Screenshot reviewed | ☐ |
| Client boxes suggest matching names as you type (name, firm, client ID, PAN); arrows and Enter choose | Pass | Simulated typing in Add Expected DSC and DSC Inward; GUI smoke test | ☐ |
| Search boxes filter their tables as you type | Pass | Wired on every report and list search box | ☐ |

## Changes of 29-10-2026 (second set)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| WhatsApp messages (received, returned, collected, expiry) with editable wording; unknown blanks kept; invalid mobile refused | Pass | `test_messages_and_editable_wording`, `test_collected_and_expiry_messages`; GUI: 5 WhatsApp links prepared, none sent with the box unticked | ☐ |
| WhatsApp opens on a real PC with the client's number and text | Pass | User, 29-10-2026: WhatsApp Web worked for the first message, but the second opened a new "Share on WhatsApp" page with a prompt. Fixed: the Desktop app is used when installed (whatsapp:// link, detected on this PC); Web links go straight to the chat. User's test reached the Desktop app via a browser page, because the app was still running the old version (started before the fix). After restarting, the user confirmed the message opens directly in WhatsApp Desktop with no browser window | ☐ |
| "Needs attention today" summary when the app opens (expiry, overdue, awaited, backup age) | Pass | `test_attention_summary`; screenshot | ☐ |
| Automatic daily backup: one file per day, last 30 kept | Pass | `test_auto_backup_one_per_day_keeps_last_30` | ☐ |
| Single user: a second copy of the app cannot open the same database | Pass | `test_single_user_lock` | ☐ |
| Excel export with filters and frozen headings; numbers stay numbers | Pass | `test_excel_export_with_firm_heading`; GUI: 7 Excel exports | ☐ |
| Dates typed without dashes (29102026, 291026, 29-10-26) | Pass | `test_parse_and_display` | ☐ |
| Client Details view, Settings screen, short success messages, empty-list hints, right-click menus, Ctrl+S / F5 / Enter | Pass | GUI smoke test and screenshots; Ctrl+S, F5 and Enter checked with simulated key presses | ☐ |

## Fix of 29-10-2026: Read from Token without a driver

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| Windows-store fallback offers only Indian DSC certificates (CCA policy 2.16.356.100.*); Microsoft/Adobe certificates are never offered | Pass | `test_windows_store_fallback_offers_only_dsc_certificates`, `test_indian_dsc_recognised_by_cca_policy`; on this PC the Microsoft and Adobe certificates are no longer offered | ☐ |
| Missing driver: message names the token's own installer (e.g. F:\HyperPKI_HYP2003_Setup.exe) | Pass | `test_missing_driver_points_to_the_tokens_own_installer`; on this PC with a HYP2003 token plugged in | ☐ |
| Details read without a token serial: DSC Inward says so and puts the cursor in Token Serial | Pass | Code path added; not yet seen with a real DSC in the store | ☐ |
| HYP2003 (HyperSecu) token read after installing its driver | Pass | Real token on 29-10-2026: driver eps2003csp11v2.dll found; serial, holder, certificate serial, issuer and expiry date/time filled on DSC Inward; certificate recognised as Indian DSC (policy 2.16.356.100.2.3) | ☐ |

## Changes of 29-10-2026 (UI/UX round 2)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| Search box at the top finds clients (name, PAN, mobile, ID) and tokens (serial, holder) | Pass | `test_search_index_finds_clients_and_tokens`; GUI | ☐ |
| Today strip counts (received, returned, due back, expiring, awaited today) | Pass | `test_today_summary` | ☐ |
| Undo on the success message reverses the outward entry | Pass | GUI smoke test (custody count restored) | ☐ |
| Menu counts, sample-data strip, Help screen, quick actions, Read Token first on Inward, Save & Add Another | Pass | GUI smoke test and screenshots | ☐ |
| New colours, striped rows, cell hover tips, no section headings on the dashboard, dashboard fits 1366×768 | Pass | Screenshots; measured 668 of 671 px with the sample strip showing | ☐ |
| Column widths remembered; tests never touch the real settings file | Pass | GUI smoke test (separate settings file) | ☐ |
| App icon on window, taskbar and .exe | Pass | An .exe of 30-10-2026: icon extracted from the .exe; title bar and taskbar show it (screenshot) | ☐ |

## Changes of 29-10-2026 (Movements merged into DSC in Custody)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| "5. Movements" removed; "5. DSC in Custody" on the main menu with its count and late count | Pass | GUI smoke test | ☐ |
| Issue / return / hand-over / client collected from consultant / return to client / lost / cancel / history buttons on DSC in Custody, enabled only when they apply to the selected token | Pass | GUI smoke test; screenshot | ☐ |
| Dashboard quick action and cards, alerts and messages open DSC in Custody | Pass | GUI smoke test | ☐ |
| Screen fits 1366×768 (buttons in two rows, legend visible) | Pass | Screenshot at 1366×768 | ☐ |

## Changes of 29-10-2026 (Google Sheet for the partners)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| All 8 reports and the dashboard are sent; every row has as many cells as headings | Pass | `test_payload_has_every_report_and_no_full_pan_or_mobile` | ☐ |
| PAN and mobile numbers are masked; full numbers appear nowhere in what is sent | Pass | `test_masking`, `test_payload_...` | ☐ |
| Only a script.google.com link is accepted; the key is made once and written into the script | Pass | `test_link_key_and_script` | ☐ |
| Google's redirect is followed; a wrong key, a wrong link and no internet each give a clear message | Pass | `test_post_follows_google_redirect_and_reports_problems` (local server) | ☐ |
| Script writes 9 tabs with filters, one chart, removes "Sheet1"; repeat updates don't duplicate; empty data works; wrong key refused | Pass | `test_sheet_script_with_node_mock` (mock of Google Sheets, not real Google) | ☐ |
| An entry schedules an update; Update Now sends in the background; no internet is recorded and retried | Pass | GUI smoke test (local server in place of Google) | ☐ |
| Settings → Google Sheet for Partners fits 1366×768 | Pass | Screenshot | ☐ |
| Real Google Sheet: setup steps, tabs, filters, dashboard chart, date formats, partner Viewer access | Not run yet | Needs the firm's Google account - to be done together | ☐ |

## Changes of 29-10-2026 (Restore from Backup and Correct Entry)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| Restore brings back the backup's data; entries made after it disappear; a DSC_BeforeRestore copy keeps them | Pass | `test_restore_brings_back_the_backup_and_keeps_a_safety_copy`; GUI smoke test (Backup screen) | ☐ |
| Restore refuses the database in use and a file that is not a DSC Manager backup, and changes nothing | Pass | `test_restore_refuses_wrong_files` | ☐ |
| A backup from before Correct Entry existed is brought up to date when restored | Pass | `test_restore_of_older_backup_is_upgraded` | ☐ |
| Correct inward: values change, old values kept, "(corrected)" in the register, line in Token History, custody unchanged | Pass | `test_correct_inward_keeps_old_values_and_shows_in_history`; GUI smoke test (dialog) | ☐ |
| Correction rules: reason required, nothing-changed, future date, expected return, purpose, date after first hand-over, cancelled entry | Pass | `test_inward_correction_rules` | ☐ |
| Correct outward: date and Returned To; date checks; corrected entry can still be cancelled | Pass | `test_correct_outward`; GUI smoke test (reason required, then saved) | ☐ |
| Date of a return collected from a consultant cannot be changed; remarks can | Pass | `test_outward_date_fixed_when_collected_from_consultant` | ☐ |
| Correct Entry dialog and Backup screen layout | Pass | Screenshots | ☐ |

**Not yet tested with real tokens of other brands** (ProxKey, mToken, Trust Key and others). They use the same
PKCS#11 method; test each brand with **Backup Database → Test: Read Tokens Now**. If a brand isn't detected, add its
driver DLL there.

## Changes of 1-11-2026 (Custodian, Staff & Consultants tab)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| "8. Custodian & Consultants" removed from the menu; Settings opens on a first tab "Custodian, Staff & Consultants" with the custodian, staff and consultants | Pass | GUI smoke test; screenshot | ☐ |
| Staff list removed from Backup Database; adding and removing staff works from the new tab | Pass | GUI smoke test | ☐ |

## Changes of 1-11-2026 (small screens)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| A page taller than the window shows a scrollbar; one that fits does not; the form's buttons are never squeezed | Pass | GUI smoke test; screenshots at 1366x700 and 1093x560 | ☐ |
| Inward and Outward forms fit at a 1366x768 screen with Save fully visible, no scrolling | Pass | Measured and screenshots | ☐ |
| On the firm's other PC: Save, Save & Add Another and Clear Form can be read on DSC Inward | Not run yet | Needs that PC | ☐ |

## Changes of 5-11-2026 (first start of the .exe)

| Check | Result | How it was verified | Manual |
|---|---|---|---|
| First start in an empty folder, Yes to the default location: no error; `data` folder and database created | Pass | `test_first_start_makes_the_database_folder_for_the_lock`; the real .exe started from an empty folder, before and after the fix | ☐ |
| Next start after a first start that stopped with the error: carries on with the default folder | Pass | `test_interrupted_first_start_goes_on_with_the_default_folder` | ☐ |

## Suggested manual walk-through (about 15 minutes)

1. **Settings → Custodian, Staff & Consultants:** appoint a custodian. Add a staff member. Add a CS as a consultant.
2. **DSC Inward:** plug in a token and click **Read from Token**. Check the details, pick the client
   and purpose, and save. The token should show "with custodian".
3. **DSC in Custody → Issue to Staff:** issue the token to a staff member. Try issuing it again; it
   should be refused. Then click **Return from Staff**.
4. **Hand to Consultant:** hand the token to the CS. Then click **Client Collected from Consultant**. The
   token should leave custody, and **Token History** should show the whole chain.
5. **Settings → Custodian, Staff & Consultants:** appoint a new custodian. The Movement Register should show the
   hand-over entries.
6. **Clients:** try a PAN with "C" as the 4th character. It should be rejected.
7. **Expiry Alerts:** check a certificate expiring today shows **Expired** once its time has passed.
8. **Backups and persistence:** export a report to CSV, back up the database, and close and reopen
   the app.
