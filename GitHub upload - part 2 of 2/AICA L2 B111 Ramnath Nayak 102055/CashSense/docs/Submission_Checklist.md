# ICAI capstone submission checklist (AICA Level 2, Annexure D)

Deadline: within 10 days of the batch end. Individual project. All data is fictitious and marked SAMPLE.

## 1. Build the upload folder (no secrets)
```powershell
python scripts\build_upload.py
```
Creates `ICAI_Upload\CashSense` next to the project: code, skills, plugin, n8n workflows, Apps Script, tests,
docs, LICENSE (all rights reserved) and `data.zip` (sample data). It refuses to finish if any value from `.env`
or a key-like string is found. Rename the folder if ICAI asks for a naming pattern (for example name or
membership number) - check the batch WhatsApp group / repository README.

## 2. GitHub (fork + pull request)
1. Sign in at github.com. Open the target repository given in the ICAI guide
   (Capstone-Project---AICA-Level-2) and click **Fork**.
2. In your fork: **Add file > Upload files**, drag the `CashSense` folder contents. GitHub accepts up to 100 files
   per upload and the folder has about 100 - upload in two goes (for example everything except `tests` and
   `plugin`, then those two folders). Commit message: "CashSense - AICA L2 capstone".
3. **Contribute > Open pull request** to the ICAI repository. Copy your fork's folder link.
4. Note: the ICAI repository may be public. The LICENSE states that the work is shared for evaluation only.

## 3. Video
Record with `docs/Video_Script.md` (face + screen), upload to Google Drive (or YouTube unlisted) and set the link
to "Anyone with the link can view", as the guide requires.

## 4. Google Form
Submit the form link from the ICAI guide with: your GitHub folder / pull-request link and the video link.

## 5. Before you submit
- [ ] `python -m unittest discover -s tests -t .` passes
- [ ] `build_upload.py` says "Secret scan: clean"
- [ ] Video plays from a private browser window (link sharing works)
- [ ] README and `docs/BUILD_LOG.md` open correctly on GitHub
