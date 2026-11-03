# Excel for Everyone

A local Flask learning application with a vibrant emerald, violet, coral and gold interface. Core learning needs no paid service or API key. Created for the Artificial Intelligence for Chartered Accountants capstone, with examples for everyday learners as well as the workplace.

## Implementation plan and assumptions

1. Build a responsive navigation shell, overview and learner dashboard.
2. Define a four-level curriculum map and publish five complete beginner lessons.
3. Add quizzes, browser answer checks, bookmarks, profiles and milestones in SQLite.
4. Supply practice workbooks and separate solutions, plus a formula library and course-based offline coach.
5. Verify the full learning journey, then expand future levels using the same content structure.

This first version assumes one trusted local machine. Each browser cookie identifies one learner profile. No sign-in, recovery or cross-device sync is provided. Later lessons are explicitly marked Coming soon. This is a local Python application, not a hosted deployment.

## Quick start on Windows

1. Install Python 3.10 or later from python.org, including pip and IDLE. Enable the option to add Python to PATH. SQLite is included with Python.
2. Extract the project folder from the ZIP. Keep `app.py`, `content.py`, `practice.py`, `templates`, `static` and `downloads` together.
3. In File Explorer, open the project folder. Type `powershell` in the address bar and press Enter.
4. Install the only required package in that Python installation:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Open IDLE using the same Python installation. Choose **File → Open**, select `app.py`, then choose **Run → Run Module** (F5).
6. Keep IDLE running. Open **http://127.0.0.1:5000** in your browser. The overview contains Start learning, the placement quiz and all navigation.
7. To stop, return to the IDLE Shell and press Ctrl+C. Reopen the same app and browser to continue with saved progress.

You can also run `python app.py` in PowerShell. If `python` is not recognised, try `py`; use that same command for installation and execution. If Flask is missing in IDLE, run `import sys; print(sys.executable)` in the IDLE Shell and use that executable with `-m pip install -r requirements.txt`. If port 5000 is busy, stop the previous instance or change `port=5000` at the bottom of app.py and use the matching browser URL. This Flask server is intended for local learning; it binds to loopback with debugging disabled.

Optional isolated environment for terminal users:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

If using IDLE with this environment, launch it with `.venv\Scripts\python.exe -m idlelib`.

## Folder structure

```text
excel-for-everyone/
  app.py                 Flask routes, SQLite and local profile handling
  content.py             Lessons, quizzes, formula reference and curriculum map
  practice.py            Restricted formula parser and explicit grading criteria
  requirements.txt       Flask; remaining Python modules are standard library
  test_app.py            End-to-end Flask client and grader checks
  templates/             Jinja HTML templates
  static/style.css       Responsive visual design; no external font dependency
  static/app.js          Search, copy and asynchronous practice feedback
  downloads/             5 practice .xlsx files and 5 separate solutions
  instance/              Created at runtime; SQLite database and session secret
  README.md              Setup, demonstration, scope and extension guide
  VERIFICATION.md        Checks performed and verification limits
```

## What is ready

- Welcoming overview, optional placement quiz, searchable curriculum and formula catalogue.
- Five lessons: spreadsheet vocabulary; data entry; number formats; arithmetic formulas; references and essential functions.
- Every lesson includes an objective, explanation, worked example, guided activity, independent challenge, common mistakes, explanatory quiz, recap, next step, practice file and solution.
- Practice + best quiz score of at least 80% completes a lesson. Each lesson has two quiz questions, so both must be right. Attempts are stored; lower retakes do not reduce a best score. Placement is advisory and does not complete lessons.
- Bookmarks, suggested next lesson, local display name, attempt history and three stored achievement badges.
- Complete outline covering every topic requested across Beginner, Intermediate, Advanced and Applied projects. Path prerequisites, outcomes, suggested order and compatibility notes appear in Learning paths.
- Offline course coach: simpler explanation, deeper worked example, progressive hints, solution reveal, common error explanations, challenge and performance-based revision suggestions.
- Responsive layout, semantic navigation, skip link, visible focus, native keyboard forms, radio groups and live practice feedback. No external assets are needed at runtime.

## Demonstration guide (about five minutes)

1. Open the overview and show the four color-coded paths and honest Coming soon labels.
2. Select Find my level. Submit four responses and show explanations and the suggested level. Intermediate content is not yet available; beginners can skip placement.
3. Open lesson 1. Bookmark it, read the objective and example, then download both files. Open the practice in Excel and identify B2 and B2:B5.
4. In the browser challenge enter `B2:B5`. Take the quiz: choose **Column B, row 3** and **A1:B3**. Show immediate explanations and the completed lesson.
5. Open My progress: show 1/5 complete, the First steps badge and the bookmark. Change the display name. Reload to demonstrate persistence.
6. Open lesson 4. Submit `=(B2+B3)*2`; also try `=B2*2+B3*2` to show an accepted equivalent. `=120` is rejected because it fails changed inputs.
7. Search the formula library for SUM. Copy an example. Open Learning coach, select lesson 4 and request the gentle hint, then more help.
8. Close and restart the app. Return in the same browser to show saved progress. Back up `instance` while the app is stopped if the records need preserving.

## Browser practice and grading limits

The browser displays a fixed four-record sample table and one answer field; it does not emulate Excel. It does not allow cell editing, formula fill, charts, PivotTables, formatting, file uploads or VBA execution.

Lessons 1–3 compare normalised text answers (range, Enter, percentage). Lessons 4–5 parse only numeric constants, B2:B5 references with optional dollar signs, arithmetic `+ - * /`, parentheses, and SUM/AVERAGE/MIN/MAX/COUNT with one contiguous range inside B2:B5. Formula input is limited to 160 characters. Python `eval` is not used. Other functions, names, exponentiation, calls and uploaded code are rejected. Each formula is tested on four input sets, including zero and decimal cases, at an absolute tolerance of 1e-8. This permits some equivalent formulas but is not a complete algebraic or Excel-equivalence proof. The checker does not grade correct reference locking when a formula is copied; compare the workbook solution manually for that skill. Dollar signs in a single-cell calculation have no effect on its current value.

Quizzes are marked server-side on submission with explanations for chosen and correct answers. Practice responses save immediately when correct. Excel-only actions use manual review against the separate solution. The five solution files contain working formulas where relevant and recalculate when opened in Excel.

## Data, secrets and optional future AI

`instance/learning.sqlite3` stores local learner IDs, names, placement suggestions, progress, bookmarks, quiz scores, attempts and badges. `instance/session-secret.txt` stores a random signing secret so cookies remain valid after restarting. Both are created locally, excluded by `.gitignore`, and must not be published. A session cookie identifies the local profile. Clearing it loses access to that profile through this UI. Use a separate browser profile for another learner.

You may set `FLASK_SECRET_KEY` in the operating-system environment before launching. Keep its value stable to preserve sessions; never put it in source control. Forms use CSRF tokens, SQL values are parameterised, and names are HTML-escaped. No uploads or outgoing AI calls are implemented.

This version deliberately supplies the requested **clearly labelled fallback**, not a paid AI integration. A future adapter should read a provider key from an environment variable such as `AI_API_KEY`, send only necessary lesson material with consent, enforce timeouts, ground answers in the selected lesson and label all generated output as AI-generated with uncertainty. On provider failure, return the existing offline guidance. Never put keys in browser JavaScript, source code or example files.

## Extend the course

Add a dictionary to `LESSONS` in content.py using the existing fields and quiz helper. Provide an appropriate explicit practice grader in practice.py and matching workbook files in downloads. Update the curriculum and remove Coming soon only after the new lesson is complete. The current navigation, 5-lesson progress denominator and milestone thresholds intentionally describe this first edition; update these alongside any expansion. Planned order: remaining Beginner lessons → Intermediate → Advanced → Applied projects. The outlined future topics do not yet have full teaching content or assessments.

Run checks with `python -m unittest -v` from this folder. Tests use a temporary database and never reset real progress.

## Reference notes

Examples use English Excel function names; regional settings may change names and formula separators. Compatibility varies by release, operating system, subscription and build. Version guidance was checked against Microsoft support; see the links in the Learning paths page. Useful primary references:

- Flask installation: https://flask.palletsprojects.com/en/stable/installation/
- XLOOKUP availability: https://support.microsoft.com/en-us/excel/functions/xlookup-function
- Power Query availability: https://support.microsoft.com/en-us/excel/about-power-query-in-excel
- LAMBDA: https://support.microsoft.com/en-us/office/lambda-function-bd212d27-1cd1-4321-a34a-ccbf254b8b67

This application is an independent learning project and is not affiliated with Microsoft.
