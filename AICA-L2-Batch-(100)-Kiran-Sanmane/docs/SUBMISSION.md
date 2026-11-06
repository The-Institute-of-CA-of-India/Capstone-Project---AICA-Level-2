# ICAI submission — AICA Level 2 Projects

Submission folder: **`AICA-L2-Batch-(100)-Kiran-Sanmane`**

Pre-submission checks (done 02-11-2026 on tag `v1.0.0`):

- [x] No real client data: `data/` is git-ignored; samples are fictitious (`scripts/make_samples.py`).
- [x] No `.env`, `config/settings.yaml`, logs or diagnostic output committed.
- [x] No file over 10 MB (largest: sample PDFs and screenshots, each under 1 MB).
- [x] Samples and golden files present (`samples/`); classifier models are rebuilt by `setup.bat`.
- [x] Clean-clone test: clone → `setup.bat` → 671 tests pass → app starts on 127.0.0.1.
- [ ] Replace `<<VIDEO_LINK>>` in `README.md` with the demo video link.

## Commands (Windows PowerShell)

Run each block in order. Replace `<your-github-id>` with your GitHub user name. First fork `aiinicai/AICA-Level-2-Projects` on GitHub (Fork button), or with the GitHub CLI:

```bash
gh repo fork aiinicai/AICA-Level-2-Projects --clone=false
```

Clone your fork next to this project and create a branch:

```bash
cd D:\AI
git clone https://github.com/<your-github-id>/AICA-Level-2-Projects.git
cd AICA-Level-2-Projects
git checkout -b add-kiran-sanmane-appealiq
```

Export the tagged release of AppealIQ (tracked files only — no `.venv`, `data/` or settings) into the submission folder:

```bash
git -C D:\AI\AppealIQ archive --format=zip -o D:\AI\appealiq-v1.0.0.zip v1.0.0
```

```bash
Expand-Archive D:\AI\appealiq-v1.0.0.zip -DestinationPath "AICA-L2-Batch-(100)-Kiran-Sanmane"
```

Commit and push to your fork:

```bash
git add "AICA-L2-Batch-(100)-Kiran-Sanmane"
```

```bash
git commit -m "Add AICA Level 2 Project - Kiran Sanmane (AppealIQ)"
```

```bash
git push -u origin add-kiran-sanmane-appealiq
```

Open the pull request against `aiinicai/AICA-Level-2-Projects`:

```bash
gh pr create --repo aiinicai/AICA-Level-2-Projects --base main --head <your-github-id>:add-kiran-sanmane-appealiq --title "Add AICA Level 2 Project - Kiran Sanmane" --body "AppealIQ - ITAT Appeal Readiness Analyser. Offline-first Streamlit app that reads CIT(A) / 263 / CIT(E) / DRP orders and produces a verified, para-referenced appeal readiness report, draft grounds, paper book index and issue register. Batch 100, Pune. Demo video: <<VIDEO_LINK>>. See README.md in the folder."
```

Check the target repository's README for any naming or folder rules before pushing; if its default branch is not `main`, change `--base`.
