# Mukhota - Private Notice Desk

**Mask it. Check it. Answer it.**

Mukhota removes personal and client-identifying data (PII) from tax notices before they are shared, and can draft a reply from the redacted notice. Redaction and verification work completely offline: no telemetry, no auto-update. The original PDF is only ever read, never changed. The only network use is the **Draft Reply** step, which talks only to the AI provider you choose (Claude at `api.anthropic.com` by default); every other connection is blocked inside the app.

## Install (once)

1. Install **Python 3.12 (64-bit)** from python.org if it isn't already installed.
2. Double-click **install.bat**. It creates `venv`, installs every library through pip and creates the icon. This is the only step that needs the internet.

## Run

Double-click **run.bat**. Mukhota opens in your browser at a `127.0.0.1` address that only this computer can reach. File and folder pickers are normal Windows windows (they may open behind the browser). Click **Quit** when done; if you just close the tab, Mukhota stops by itself after about 5 minutes. Replies due within 7 days are shown in a reminder bar when the page opens.

The older desktop window is still available through **run_desktop.bat**; both work on the same files, lists and register.

**Try it safely:** `samples\Specimen_Notice_271B_FICTITIOUS.pdf` is a made-up two-page notice (every name, PAN, GSTIN, account and mobile number in it is invented). Open it, click **Detect PII**, review, **Apply Redaction**, then **Verify**. The `docs\` folder has the project presentation and screenshots.

## Buttons

| Button | What it does |
|---|---|
| **Open PDF** | Choose a notice. Each page is classed as a *text* page or a *scanned* page; scanned pages are read with OCR. A page with low OCR confidence shows a red **Manual review required** badge in the page navigator. |
| **Detect PII** | Finds PAN, GSTIN (checksum-validated), TAN, Aadhaar (Verhoeff-validated, plus masked forms), mobile, landline, e-mail, IFSC, bank account numbers (only near A/c, Account, Bank... labels), CIN, LLPIN, director DIN, Udyam, IEC, passport, vehicle numbers, PIN codes in addresses, names and addresses (To-block, M/s, Shri, Smt, Mr, Ms, Name:, Address:), officer name and ward/circle, entries from your client master list, QR codes, barcodes, and likely signatures and stamps. Each confident value is also looked for everywhere else in the notice. |
| **Draw Box** | Toggle on, then drag a rectangle on the page to redact anything by hand. |
| **Add Term** | Type a word or phrase; every occurrence in the notice is added. |
| **Apply Redaction** | Creates the redacted copy. Text under each box is **removed**, not just covered, and a token such as `[PAN_1]` is written in the box. Scanned pages are rebuilt as flat images with no hidden text layer. Metadata, XMP, annotations, links, attachments, JavaScript and form fields are stripped; Producer is set to "Mukhota". Verification then runs automatically. |
| **Verify** | Re-checks a redacted PDF (the latest one, or one you pick). Shows a green **VERIFIED - SAFE TO SHARE** or red **VERIFICATION FAILED** banner. Click a failure to jump to that page. |
| **Draft Reply** | Sends a **verified** redacted notice to Claude (or another AI provider you set up) and returns a draft. It refuses any PDF without a matching PASS report. See *Draft Reply* below. |
| **Open Output Folder** | Opens the folder with the results. |
| **Settings** | General options, the do-not-redact list (`allowlist.yaml`) and the client master list (`client_master.csv`). |

### The right-hand list

- Each detected item has a tick box: ticked items are redacted, unticked ones stay visible.
- Values are shown partly masked (e.g. `ABCPX****K`).
- Items below the pre-tick confidence (default 60%) start unticked for you to judge. These include name hits from the language model, place names, signatures and stamps.
- Colour chips filter the list by type. **Select all** / **Clear all** act on the rows that are visible.
- Colours: PAN orange, GSTIN purple, Aadhaar red, mobile/e-mail blue, bank green, name/address pink, QR/signature grey.

### Tokens

Every unique value gets one stable token, e.g. `[ASSESSEE]`, `[PAN_1]`, `[GSTIN_1]`, `[DIRECTOR_1]`, `[ADDRESS_1]`, `[MOBILE_1]`, `[BANK_AC_1]`, `[OFFICER_1]` or `[QR_1]`. The same value gets the same token everywhere; case, spacing, M/s, Pvt/Private and Ltd/Limited are ignored when deciding what counts as the same value. Token sources:

- `role` in the client master list (assessee, director, partner...);
- the first addressee in the To-block becomes `[ASSESSEE]`, unless the master list already names one.

## Draft Reply

1. **Save your API key once:** go to Settings > AI providers, paste the key and click Save. The key is stored in Windows Credential Manager. (To use a provider other than Claude, see *Other AI providers* below.)
2. **Verify the redacted PDF**, then click **Draft Reply**.
3. **Choose:**
   - **Notice type:** Income-tax, GST or Other.
   - **What you want back (tick any):**
     - *Draft reply:* the pure filing text with no ratings or notes (Reply .docx).
     - *Advisory:* internal note: a citation confidence table (anything below 8 marked VERIFY), issue-wise risk, the five-angle bench, missing documents, time limits, and what the officer may challenge (Advisory .docx).
     - *Law research note:* law on each issue, no reply (Law Note .docx).
     Only the ticked sections are requested and saved.
   - **How to get it:**
     - *Send to AI:* Claude or the provider set up in Settings (steps below).
     - *Make a prompt (any AI chat):* no API, no key, no cost. Click **Make prompt**, then **Copy prompt** (or **Save as .txt**, saved as `<notice>_PROMPT_<time>.txt`) and paste it into ChatGPT, Claude.ai, Gemini, DeepSeek or any AI chat. The prompt holds tokens only, never real names; the notice goes in as text. Paste the chat's whole answer in the **Paste AI answer** tab and click **Use this answer**: real names are restored on this computer, then fill placeholders and **Save as Word** as usual. This also works after closing and reopening Draft Reply for the same notice.
   - **What to send:** the redacted PDF plus its text, the PDF only, or the text only.
   - **Web search:** on by default, so Claude can confirm sections, circulars and case law. Limited to 6 searches per draft; you can change this in Settings.
4. **Type any facts or instructions.** Values already in the vault are swapped for their tokens. New PANs, names after M/s / Shri, and so on get new tokens. Client-master entries are also replaced.
   - *Optional add-on: Frame the issues first (six-box method).* Off unless ticked. Six boxes appear: Issue, Period, Provision, Fact gap, Evidence, Objective. Fill any you know and leave the rest blank; the AI completes them from the notice (leave all blank and it does it all). The answer gets an extra **Issue framing** tab first (six-box table per allegation, allegations classified, facts vs assumptions, research questions, evidence checklist; saved as Framing .docx), and the reply marks every fact gap as [[TO CONFIRM]] instead of assuming. Works with Send to AI and Make a prompt. Box text is tokenised like the facts. The section wording is in `prompts/section_framing.md`.
5. **Click Preview what will be sent.** This shows exactly what leaves the computer. Then click **Send**.
6. **Read the draft** (shown with real values restored).
7. **Fill in the gaps.** Facts Claude did not have appear as `[[TO CONFIRM: ...]]` / `[[ATTACH: ...]]`. The **Fill placeholders** tab lists each one once; type the value next to it. These values are used only on this computer and are never sent to Claude. ATTACH rows are pre-filled with their description, and blank rows stay as placeholders.
8. **Edit if needed.** The Reply, Advisory and Law note tabs are editable. Change wording directly before saving.
9. **Click Save as Word.** A `<notice>_CHANGES_<time>.txt` file records what you changed compared with Claude's draft. Claude's original stays in the `_DRAFT_tokens_` file.

**Client facts sheet**
- Click **Client facts…** in the Draft Reply window to keep, per client: status, business, auditor, signatory, place, and year-wise turnover, audit and ITR dates and acknowledgements.
- The sheet is linked by PAN (or GSTIN), encrypted in `clients\` with the vault key, and **never sent to Claude**.
- Saved facts pre-fill matching placeholders.
- With "Remember the values I type here" ticked, new answers are saved back to the sheet, so the next notice for that client needs less typing.

**Cost guard**
- Before sending, Mukhota counts the request size using Anthropic's free token-count call. It shows an estimated cost (typical and maximum) and this month's spend.
- Set a **Monthly spending limit** in Settings > AI providers (0 = no limit). A draft that would exceed it asks again, with "No" as the default answer.
- Spend is logged in `usage.json`, which holds amounts and dates only.

**Tips:**
- Facts typed in step 4 (status, turnover, dates) reach Claude in tokenised form, so the draft needs fewer placeholders.
- **Model** can be chosen in the dialog or set as the default in Settings:
  - Opus 5.5: best quality.
  - Sonnet 5.5: about half the cost.
  - Haiku 5.5: a few cents per run; useful for testing.

Model: Claude Opus 5.5, at medium effort by default (changeable in Settings). Typical cost is about US$0.30–1.00 per notice; web search results add to the input size. The exact figure is shown after each draft. Prompts live in `prompts/` and can be edited: `reply_system.md` (shared rules) and one `section_*.md` per output (reply, advisory, law).

**Other AI providers** (Settings > AI providers > Other providers)

| Provider | Redacted PDF | Web search | Notes |
|---|---|---|---|
| Claude | Yes | Yes | Default |
| OpenAI (GPT) | Yes | Yes | Responses API |
| Google Gemini | Yes | Yes (Google Search) | |
| DeepSeek, Mistral, Groq, OpenRouter, Custom | No | No | OpenAI-compatible; the notice text and your law library are sent instead |
| Local - Ollama / LM Studio | No | No | Runs on this computer: nothing leaves it; no key needed |

- Pick the provider, type the **model name** (e.g. `gpt-5`, `gemini-3.8-flash`), paste its API key, and enter its prices so the cost guard works. A provider appears in Draft Reply once it has a model name.
- Each provider's key is kept separately in Windows Credential Manager.
- The network guard opens only the chosen provider's address. Custom addresses must be `https://` (or `http://localhost` for local models).
- OpenAI and Gemini count tokens exactly before sending; the others show an estimate. Draft quality, citation accuracy and the `<<<REPLY>>>` / `<<<ADVISORY>>>` split depend on the model you choose.

**Files added to the output folder:**
- `<notice>_REPLY_<time>.docx` and `<notice>_ADVISORY_<time>.docx`, or `<notice>_LAW_NOTE_<time>.docx`. These contain real names: never share the Advisory.
- `<notice>_DRAFT_tokens_<time>.txt`: Claude's answer exactly as received, tokens only.
- `<notice>_draft.vault`: encrypted tokens, including any new ones created from your facts.

Word files use Bookman Old Style with justified paragraphs.

## Review and record-keeping

**Side by side**
After redaction, click **Side by side** above the preview. The original and the redacted copy appear next to each other, scrolling together. Zoom and Fit width apply to both.

**Case register**
- **Case Register** in the left toolbar lists every notice opened, with client, section, AY, notice date, **reply due date**, days left and status (Opened → Redacted → Verified → Drafted → Filed).
- The section, AY and dates are read from the notice text. Double-click a row to correct the client, due date or status. **Mark filed** closes a case.
- Rows due within 7 days are amber; overdue rows are red.
- When Mukhota starts, a **Windows notification** lists replies due within 7 days or overdue; clicking it opens the register. Turn this off with `notifications: due_reminders: false` in `config.yaml`.
- Stored in `register.db`, with client names, file names and folders encrypted with the vault key.

## Law library
- Put your own reference material in `law_library\`: PDF (with a text layer), `.txt` or `.md`. This means sections, circulars, notifications, case notes.
- Mukhota indexes it automatically and keeps it up to date when files change.
- When drafting, **Use my law library** picks the 8 passages that best match the notice's sections and wording.
- Those passages are sent to Claude marked as your library, after tokenising, in case old client material is in there. They appear in the preview.
- Claude relies on them first and marks them "(library [L#])" in the Advisory. Web search fills the gaps.
- Scanned PDFs without a text layer are not read; OCR them first or use text versions.

## Where files are saved

A folder is created next to the notice. You can choose another location in Settings.

```
<notice_name>_mukhota/
  <notice_name>_REDACTED.pdf   the file to share
  <notice_name>.vault          encrypted map of token -> original value (never share)
  verify_report.txt            human-readable audit report (no values)
  verify_report.json           same, machine-readable, with the verified flag
  candidates.json              types, pages and tokens only (no values)
```

- The vault is encrypted with Fernet. Its key is kept in **Windows Credential Manager** under the service name `Mukhota`, so a vault can be opened only on the same Windows login.
- Logs are written to `logs\mukhota.log`. They contain types and counts only; anything that looks like an ID, number, e-mail or document path is masked.

## What verification checks

1. No original vault value remains in the text layer.
2. No original value appears in a fresh OCR of every page.
3. No normalised variant appears (no spaces, lower case). A 4-digit tail of an Aadhaar or account number:
   - is a **failure** if it sits next to an account/Aadhaar label;
   - is otherwise a **note** to glance at.
4. Re-running all detectors on the redacted PDF finds nothing new. Items you rejected during review are listed as notes, not failures.
5. Metadata, XMP, annotations, links, attachments, JavaScript and form fields are empty.
6. Every page has a redaction or is marked **Reviewed - no PII**, using the tick box above the preview.

The report records the SHA-256 of the original and of the redacted PDF. `mukhota.core.verify.is_verified(pdf)` returns True only when a PASS report matches the file's current SHA-256. Later phases must use it before any upload.

## Known limitations

- **OCR word boxes are estimated.** RapidOCR gives one box per text line, and Mukhota splits it into words by character position. Boxes are padded, so very tight layouts may lose a neighbouring character.
- **Signature and stamp detection is heuristic.** It looks for ink near "Signature" / "Authorised Signatory", small embedded images and blue/red/purple seals. Check every page and use Draw Box for anything missed.
- **Name detection is weak on Indian names.** The language model (spaCy `en_core_web_sm`) is not trained on them. The client master list and the salutation rules matter most, so keep the master list up to date.
- **Rotated pages.** Pages saved with a rotation flag are supported, but the token text inside redaction boxes on such text pages may appear rotated.
- **Images inside text pages are not OCR'd.** For example, a scanned letterhead embedded in a digital notice. Image pixels under a redaction box are still removed. Check such pages visually.
- **Notice DIN formats** in `allowlist.yaml` are best-effort. Check them against recent CBIC, ITBA and GST portal notices and adjust them in Settings.
- **Verification is strict.** A value you redacted in one place but which also appears elsewhere unredacted will fail verification. Use Add Term, or tick the extra occurrences.
- Password-protected PDFs must be unlocked first.
- **Draft Reply restores tokens only when Claude copies them exactly.** Any token it alters stays as-is, and the dialog lists it as a warning.
- **The facts box catches IDs and labelled names, not every free-text name.** Add regular counterparties to the client master list, and always read the preview before sending.
- **The Draft Reply step needs internet access.** A corporate proxy or VPN that blocks `api.anthropic.com` will stop it.
- **Drafts are a starting point.** Check every citation the Advisory marks VERIFY.
- Python 3.12 is used because the OCR engine does not support newer Python versions yet.
