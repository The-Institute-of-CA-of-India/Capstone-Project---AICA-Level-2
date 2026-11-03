# ATS CV Shortlisting (Enterprise Talent Acquisition)

An enterprise automated applicant tracking system (ATS) engineered with **JavaScript/TypeScript for the frontend** and **Python for the backend**. Built for high-volume CV screening, 100% weighted criteria evaluation, OCR document extraction, unbiased scoring, and candidate shortlisting.

---

## Key Features

1. **Job Description & Weighted Criteria Builder**:
   - Paste or upload job descriptions (`.txt`, `.docx`, `.pdf`).
   - 4 customizable evaluation categories with strict 100% total weight validation:
     - **Qualifications** (Degrees, academic credentials, certifications).
     - **Skills** (Programming languages, frameworks, methodologies).
     - **Relevant Experience** (Timeline extraction, domain depth, seniority).
     - **Mandatory Requirements** (Dealbreakers: missing even one disqualifies the candidate).
   - Configurable minimum matching threshold (default **90%**) and target shortlist cap (default **10**).
   - Saved vacancies management with instant switching and historical screening records.

2. **High-Volume CV Batch Ingestion & Document Center**:
   - **Folder Picker** (`webkitdirectory`) to select folders containing hundreds or thousands of CVs.
   - Native support for **PDF**, **DOCX** (parsed via Python XML streams), and **scanned raster PDFs** with OCR detection.
   - **Cryptographic Duplicate-File Detection**: Computes SHA-256 hashes of all uploaded binaries to flag duplicate submissions.
   - **Protected Document Storage**: CVs stored in isolated protected storage (`/data/uploads/`).
   - One-click **Load Sample Candidate Batch** to immediately test realistic profiles (.docx, .pdf, OCR scans, duplicate files).

3. **Python Screening Engine (`ats_engine.py`)**:
   - Calculates consistent, deterministic weighted matching percentages:
     $$\text{Score} = \frac{W_q \cdot S_q + W_s \cdot S_s + W_e \cdot S_e + W_m \cdot S_m}{W_q + W_s + W_e + W_m} \times 100\%$$
   - **Unbiased Scoring Policy**: Strips demographic indicators (age, date of birth, gender, marital status, nationality, photographs) to prevent bias.
   - **Verbatim Evidence Quotes**: Extracts direct excerpt quotes from the CV supporting each match.
   - **Strengths & Gaps**: Identifies candidate strengths and specific missing requirements.
   - **Unreadable / OCR Flagging**: Flags unsearchable or corrupted CVs for HR manual review.

4. **Strict Shortlisting & Threshold Enforcement**:
   - Ranks candidates by matching percentage descending.
   - Proposes only candidates meeting the threshold (default $\ge 90\%$) AND satisfying all mandatory requirements.
   - **Integrity Guarantee**: If fewer qualify than the target cap (e.g., only 4 qualify for a 10-cap shortlist), displays the actual qualifying number without lowering the threshold.

5. **HR Approval, Export & Downloads**:
   - HR Review and sign-off with audit log notes.
   - Download individual original CV files.
   - Download all shortlisted CVs as a single **ZIP archive** with an audit manifest.
   - Export comprehensive **Excel report** (`.xlsx`) with two styled worksheets (Shortlisted Candidates and Full Audit Trail).

6. **External AI Provider Consent Gate**:
   - API keys remain strictly on the backend.
   - No CV data is transmitted to an external AI model without explicit HR authorization.
   - Final hiring decisions strictly remain with the HR manager.

---

## Setup & Running Instructions

### Method 1: Integrated Full-Stack (Default)

The applet runs as a unified full-stack application where Node/Express mounts Vite for the frontend and executes the Python ATS engine (`ats_engine.py`) for screening calculations.

```bash
# 1. Install dependencies
npm install

# 2. Start the development server
npm run dev
```

The app will be available at `http://localhost:3000` (or the Cloud Run assigned port).

### Method 2: Standalone Python Backend Server

You can also run the Python ATS engine as an independent REST API microservice:

```bash
# Start standalone Python HTTP server on port 8000
python3 backend_server.py --port 8000

# Test health check
curl http://localhost:8000/health
```

### Endpoints Overview

- `GET /api/vacancies` - List saved vacancies.
- `POST /api/vacancies` - Create new vacancy.
- `POST /api/screening/upload` - Ingest folder / multi-file batch of CVs with SHA-256 deduplication.
- `GET /api/screening/sample-data` - Load bundled realistic candidate dataset.
- `POST /api/screening/process` - Execute Python ATS screening engine.
- `POST /api/screening/approve` - HR formal shortlist approval and sign-off.
- `POST /api/screening/export-excel` - Download generated `.xlsx` workbook.
- `POST /api/screening/download-zip` - Download ZIP archive of shortlisted original CVs.
- `GET /api/screening/download-cv` - Download individual candidate's original CV.
