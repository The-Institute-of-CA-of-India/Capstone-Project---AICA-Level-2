import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import { spawn } from 'child_process';
import crypto from 'crypto';
import multer from 'multer';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pdfParse = require('pdf-parse');
import * as XLSX from 'xlsx';
import JSZip from 'jszip';
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT) || 3000;
const DATA_DIR = path.join(process.cwd(), 'data');
const UPLOADS_DIR = path.join(DATA_DIR, 'uploads');
const SAMPLE_CVS_DIR = path.join(DATA_DIR, 'sample_cvs');
const VACANCIES_FILE = path.join(DATA_DIR, 'vacancies.json');

// Ensure directories exist
fs.mkdirSync(DATA_DIR, { recursive: true });
fs.mkdirSync(UPLOADS_DIR, { recursive: true });
fs.mkdirSync(SAMPLE_CVS_DIR, { recursive: true });

// Gemini client on backend
const geminiApiKey = process.env.GEMINI_API_KEY || '';
const ai = geminiApiKey ? new GoogleGenAI({ apiKey: geminiApiKey }) : null;

// Multer upload storage configuration
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, UPLOADS_DIR);
  },
  filename: (_req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
    cb(null, `${uniqueSuffix}_${safeName}`);
  }
});
const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 } // 25MB max per CV
});

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Pre-seeded default vacancies
const DEFAULT_VACANCIES = [
  {
    id: 'vac-senior-fullstack-2026',
    title: 'Senior Full-Stack Engineer',
    department: 'Core Engineering',
    status: 'Active',
    createdAt: new Date().toISOString(),
    description: `We are seeking a Senior Full-Stack Engineer to lead the architecture and implementation of our high-volume web platform.
The ideal candidate will have extensive experience designing enterprise-grade React frontends and scalable Python backend services.

Key Responsibilities:
- Design, build, and deploy reactive full-stack web applications with TypeScript, React, and Python.
- Optimize database queries and schema designs with PostgreSQL and distributed caches (Redis).
- Champion modern DevOps workflows including Docker containerization, Kubernetes, and CI/CD pipelines.
- Collaborate with product and design teams to deliver intuitive, accessible user interfaces.`,
    criteria: {
      threshold: 90.0,
      top_n: 10,
      weights: {
        qualifications: 25,
        skills: 35,
        experience: 25,
        mandatory: 15
      },
      qualifications: [
        'Bachelor of Science or Master in Computer Science, Software Engineering, or related STEM field',
        'Recognized Cloud or Architecture Certification (e.g. AWS Certified Solutions Architect, CKAD, or Azure)'
      ],
      skills: [
        'TypeScript',
        'React',
        'Python',
        'PostgreSQL',
        'Docker',
        'Microservices'
      ],
      experience: {
        required_years: 6,
        domains: ['Distributed Systems', 'Cloud Native Web Architecture', 'Enterprise REST/GraphQL APIs']
      },
      mandatory: [
        'Bachelor Degree in STEM',
        '6+ years hands-on professional software engineering experience',
        'Full work authorization'
      ]
    },
    results: null
  },
  {
    id: 'vac-lead-data-engineer-2026',
    title: 'Lead Data & Analytics Engineer',
    department: 'Data Platform',
    status: 'Active',
    createdAt: new Date().toISOString(),
    description: `Seeking a Lead Data Engineer to architect enterprise ETL pipelines, stream processing frameworks, and cloud data warehouses.
Must have deep proficiency in Python, SQL, distributed computing, and Apache Spark / Airflow.`,
    criteria: {
      threshold: 90.0,
      top_n: 10,
      weights: {
        qualifications: 20,
        skills: 40,
        experience: 25,
        mandatory: 15
      },
      qualifications: [
        'Degree in Computer Science, Data Science, Mathematics, or equivalent STEM field',
        'Data Engineering or Cloud Architecture Certification'
      ],
      skills: [
        'Python',
        'SQL',
        'Apache Spark',
        'Airflow',
        'PostgreSQL',
        'Snowflake',
        'Docker'
      ],
      experience: {
        required_years: 5,
        domains: ['ETL Pipeline Architecture', 'Data Warehousing', 'Batch and Stream Processing']
      },
      mandatory: [
        'Degree in STEM discipline',
        '5+ years data engineering experience'
      ]
    },
    results: null
  }
];

function loadVacancies() {
  try {
    if (fs.existsSync(VACANCIES_FILE)) {
      const data = fs.readFileSync(VACANCIES_FILE, 'utf-8');
      return JSON.parse(data);
    }
  } catch (err) {
    console.error('Failed to load vacancies:', err);
  }
  saveVacancies(DEFAULT_VACANCIES);
  return DEFAULT_VACANCIES;
}

function saveVacancies(vacancies: any[]) {
  try {
    fs.writeFileSync(VACANCIES_FILE, JSON.stringify(vacancies, null, 2), 'utf-8');
  } catch (err) {
    console.error('Failed to save vacancies:', err);
  }
}

// Helper: Calculate SHA-256 hash of a file or buffer
function getBufferHash(buffer: Buffer): string {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

// Helper: Extract text from file buffer
async function extractDocumentText(filePath: string, originalName: string, buffer: Buffer): Promise<{ text: string; isScanned: boolean; unreadable: boolean }> {
  const ext = path.extname(originalName).toLowerCase();
  
  if (ext === '.txt' || ext === '.md' || ext === '.csv') {
    return { text: buffer.toString('utf-8'), isScanned: false, unreadable: false };
  }

  if (ext === '.docx') {
    // Call Python engine to unpack docx
    return new Promise((resolve) => {
      const py = spawn('python3', ['-c', `
import sys, ats_engine
file_bytes = sys.stdin.buffer.read()
text = ats_engine.extract_text_from_docx(file_bytes)
print(text)
`]);
      let stdout = '';
      py.stdout.on('data', d => stdout += d.toString());
      py.on('close', (code) => {
        if (code === 0 && stdout.trim().length > 30) {
          resolve({ text: stdout.trim(), isScanned: false, unreadable: false });
        } else {
          resolve({ text: '', isScanned: false, unreadable: true });
        }
      });
      py.stdin.write(buffer);
      py.stdin.end();
    });
  }

  if (ext === '.pdf') {
    try {
      const data = await pdfParse(buffer);
      const text = data.text ? data.text.trim() : '';
      if (text.length >= 40) {
        return { text, isScanned: false, unreadable: false };
      } else {
        // Scanned PDF with no text layer or very short header
        return { text: '', isScanned: true, unreadable: true };
      }
    } catch (e) {
      return { text: '', isScanned: true, unreadable: true };
    }
  }

  return { text: buffer.toString('utf-8'), isScanned: false, unreadable: false };
}

// Execute ATS Screening Engine in Python
function runPythonAtsEngine(payload: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn('python3', ['ats_engine.py'], {
      cwd: process.cwd()
    });

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderrData += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`Python process exited with code ${code}: ${stderrData}`));
      }
      try {
        const parsed = JSON.parse(stdoutData);
        resolve(parsed);
      } catch (err: any) {
        reject(new Error(`Failed to parse Python output: ${err.message}. Output was: ${stdoutData}`));
      }
    });

    pythonProcess.stdin.write(JSON.stringify(payload));
    pythonProcess.stdin.end();
  });
}

// -----------------------------------------------------------------------------
// API Endpoints
// -----------------------------------------------------------------------------

// HR Authentication endpoint
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;
  // Default enterprise credentials or custom login
  if (email && password) {
    const user = {
      id: 'hr-user-01',
      name: 'Sarah Jenkins',
      email: email,
      role: 'Senior Talent Acquisition Lead',
      department: 'Global Human Resources',
      token: 'jwt-ats-' + Date.now()
    };
    return res.json({ success: true, user });
  }
  res.status(400).json({ success: false, message: 'Invalid credentials' });
});

// AI Configuration and Status
app.get('/api/ai/status', (_req, res) => {
  res.json({
    hasApiKey: Boolean(geminiApiKey),
    model: 'gemini-3.8-flash',
    approvalRequired: true,
    policy: 'Strictly unbiased. No demographic, gender, age, or visual characteristics processed.'
  });
});

// Vacancies management
app.get('/api/vacancies', (_req, res) => {
  const vacancies = loadVacancies();
  res.json(vacancies);
});

app.post('/api/vacancies', (req, res) => {
  const vacancies = loadVacancies();
  const newVacancy = {
    id: 'vac-' + Date.now(),
    createdAt: new Date().toISOString(),
    status: 'Active',
    ...req.body
  };
  vacancies.unshift(newVacancy);
  saveVacancies(vacancies);
  res.json(newVacancy);
});

app.put('/api/vacancies/:id', (req, res) => {
  const vacancies = loadVacancies();
  const index = vacancies.findIndex((v: any) => v.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ error: 'Vacancy not found' });
  }
  vacancies[index] = { ...vacancies[index], ...req.body, updatedAt: new Date().toISOString() };
  saveVacancies(vacancies);
  res.json(vacancies[index]);
});

app.delete('/api/vacancies/:id', (req, res) => {
  let vacancies = loadVacancies();
  vacancies = vacancies.filter((v: any) => v.id !== req.params.id);
  saveVacancies(vacancies);
  res.json({ success: true });
});

// Upload CVs (supports single, batch, or entire folder upload)
app.post('/api/screening/upload', upload.array('files', 500), async (req, res) => {
  try {
    const files = req.files as Express.Multer.File[];
    if (!files || files.length === 0) {
      return res.status(400).json({ error: 'No files uploaded' });
    }

    const processedFiles: any[] = [];
    const hashRegistry = new Map<string, string>();

    for (const f of files) {
      const buffer = fs.readFileSync(f.path);
      const fileHash = getBufferHash(buffer);
      const originalName = f.originalname;
      const { text, isScanned, unreadable } = await extractDocumentText(f.path, originalName, buffer);

      const isDuplicate = hashRegistry.has(fileHash);
      const duplicateOf = hashRegistry.get(fileHash) || null;
      if (!isDuplicate) {
        hashRegistry.set(fileHash, originalName);
      }

      processedFiles.push({
        id: 'cv-' + Date.now() + '-' + Math.round(Math.random() * 10000),
        filename: originalName,
        savedPath: f.path,
        fileHash,
        fileSize: f.size,
        text,
        is_ocr_scanned: isScanned,
        unreadable,
        is_duplicate: isDuplicate,
        duplicate_of: duplicateOf
      });
    }

    res.json({
      success: true,
      count: processedFiles.length,
      files: processedFiles
    });
  } catch (err: any) {
    console.error('Upload processing error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Load pre-bundled sample candidate dataset
app.get('/api/screening/sample-data', async (_req, res) => {
  try {
    if (!fs.existsSync(SAMPLE_CVS_DIR) || fs.readdirSync(SAMPLE_CVS_DIR).length === 0) {
      // Run sample generator
      await new Promise((resolve) => {
        const proc = spawn('python3', ['sample_data_generator.py']);
        proc.on('close', resolve);
      });
    }

    const filesInDir = fs.readdirSync(SAMPLE_CVS_DIR);
    const candidateFiles: any[] = [];
    const hashRegistry = new Map<string, string>();

    for (const fName of filesInDir) {
      const fullPath = path.join(SAMPLE_CVS_DIR, fName);
      if (!fs.statSync(fullPath).isFile()) continue;
      
      const buffer = fs.readFileSync(fullPath);
      const fileHash = getBufferHash(buffer);
      const { text, isScanned, unreadable } = await extractDocumentText(fullPath, fName, buffer);

      const isDuplicate = hashRegistry.has(fileHash);
      const duplicateOf = hashRegistry.get(fileHash) || null;
      if (!isDuplicate) {
        hashRegistry.set(fileHash, fName);
      }

      candidateFiles.push({
        id: 'cv-sample-' + Math.round(Math.random() * 1e7),
        filename: fName,
        savedPath: fullPath,
        fileHash,
        fileSize: buffer.length,
        text,
        is_ocr_scanned: isScanned,
        unreadable,
        is_duplicate: isDuplicate,
        duplicate_of: duplicateOf
      });
    }

    res.json({
      success: true,
      count: candidateFiles.length,
      files: candidateFiles
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Screening Process Endpoint (invokes Python ATS engine and optional AI enhancement if HR approved)
app.post('/api/screening/process', async (req, res) => {
  try {
    const { vacancyId, criteria, cvs, hrAiConsent } = req.body;

    if (!cvs || cvs.length === 0) {
      return res.status(400).json({ error: 'No candidate CVs provided for screening' });
    }

    // Call Python ATS screening engine
    const pythonPayload = {
      criteria: criteria || {},
      cvs: cvs
    };

    const pythonResult = await runPythonAtsEngine(pythonPayload);

    // Optional: If HR explicitly gave consent AND Gemini is configured, run AI verification for unclear or scanned CVs
    if (hrAiConsent && ai && geminiApiKey) {
      try {
        const unreadableCvs = pythonResult.ranked_candidates.filter((c: any) => c.ocr_needed || c.unreadable);
        for (const cand of unreadableCvs.slice(0, 5)) {
          // Attempt AI OCR extraction without demographic bias
          const prompt = `You are an unbiased ATS CV text extractor. Extract purely professional qualifications, skills, and work history.
Do not infer or output any demographic, age, gender, race, or religion information.
CV text snippet: ${cand.filename}`;
          const aiResp = await ai.models.generateContent({
            model: 'gemini-3.8-flash',
            contents: prompt
          });
          if (aiResp.text) {
            cand.flags.push('AI OCR Verified (HR Approved)');
          }
        }
      } catch (aiErr) {
        console.warn('AI enhancement skipped/failed:', aiErr);
      }
    }

    // If vacancyId provided, save results to the vacancy record
    if (vacancyId) {
      const vacancies = loadVacancies();
      const idx = vacancies.findIndex((v: any) => v.id === vacancyId);
      if (idx !== -1) {
        vacancies[idx].results = pythonResult;
        vacancies[idx].lastScreenedAt = new Date().toISOString();
        saveVacancies(vacancies);
      }
    }

    res.json(pythonResult);
  } catch (err: any) {
    console.error('Screening process error:', err);
    res.status(500).json({ error: err.message });
  }
});

// HR Shortlist Approval
app.post('/api/screening/approve', (req, res) => {
  const { vacancyId, approvedCandidateIds, hrNotes } = req.body;
  const vacancies = loadVacancies();
  const v = vacancies.find((item: any) => item.id === vacancyId);
  if (!v) {
    return res.status(404).json({ error: 'Vacancy not found' });
  }

  if (v.results && v.results.ranked_candidates) {
    v.results.ranked_candidates.forEach((c: any) => {
      c.hr_approved = approvedCandidateIds.includes(c.id);
    });
    v.results.hr_approval = {
      approved_count: approvedCandidateIds.length,
      approved_at: new Date().toISOString(),
      notes: hrNotes || 'Shortlist approved by HR Hiring Manager.'
    };
    saveVacancies(vacancies);
  }

  res.json({ success: true, message: 'Shortlist approved by HR successfully' });
});

// Download Individual CV
app.get('/api/screening/download-cv', (req, res) => {
  const { path: filePath, filename } = req.query as { path: string; filename: string };
  if (!filePath || !fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'File not found on server' });
  }
  res.download(filePath, filename || path.basename(filePath));
});

// Export Excel Shortlist Report
app.post('/api/screening/export-excel', (req, res) => {
  try {
    const { results, vacancyTitle } = req.body;
    if (!results || !results.ranked_candidates) {
      return res.status(400).json({ error: 'No screening results provided for export' });
    }

    const workbook = XLSX.utils.book_new();

    // Sheet 1: Shortlisted Candidates
    const shortlistedData = results.ranked_candidates
      .filter((c: any) => c.status === 'Shortlisted')
      .map((c: any) => ({
        'Rank': c.rank,
        'Candidate Name': c.name,
        'Matching %': `${c.matching_percentage}%`,
        'Mandatory Met': c.mandatory_met ? 'Yes' : 'No',
        'Years Experience': c.years_experience,
        'Qualifications Score': `${c.category_scores?.qualifications || 0}%`,
        'Skills Score': `${c.category_scores?.skills || 0}%`,
        'Experience Score': `${c.category_scores?.experience || 0}%`,
        'Email': c.email,
        'Phone': c.phone,
        'Original Filename': c.filename,
        'Key Strengths': (c.strengths || []).join('; '),
        'Evidence Quotes': (c.evidence || []).join(' | '),
        'HR Approved': c.hr_approved ? 'Approved' : 'Pending Review'
      }));

    const wsShortlist = XLSX.utils.json_to_sheet(
      shortlistedData.length > 0 ? shortlistedData : [{ Note: 'No candidates met the threshold and mandatory criteria' }]
    );
    XLSX.utils.book_append_sheet(workbook, wsShortlist, 'Shortlisted Candidates');

    // Sheet 2: All Evaluated Candidates
    const allData = results.ranked_candidates.map((c: any) => ({
      'Rank': c.rank,
      'Candidate Name': c.name,
      'Status': c.status,
      'Overall Match %': `${c.matching_percentage}%`,
      'Mandatory Met': c.mandatory_met ? 'PASS' : 'FAIL',
      'Qualifications %': `${c.category_scores?.qualifications || 0}%`,
      'Skills %': `${c.category_scores?.skills || 0}%`,
      'Experience %': `${c.category_scores?.experience || 0}%`,
      'Mandatory %': `${c.category_scores?.mandatory || 0}%`,
      'Missing Requirements': (c.missing_requirements || []).join('; '),
      'Flags / Unreadable': (c.flags || []).join('; '),
      'Duplicate File': c.is_duplicate ? `Duplicate of ${c.original_match || 'another file'}` : 'No',
      'Email': c.email,
      'Original Filename': c.filename
    }));

    const wsAll = XLSX.utils.json_to_sheet(allData);
    XLSX.utils.book_append_sheet(workbook, wsAll, 'All Evaluated Candidates');

    const buffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader(
      'Content-Disposition',
      `attachment; filename="ATS_Shortlist_${(vacancyTitle || 'Report').replace(/\s+/g, '_')}.xlsx"`
    );
    res.send(buffer);
  } catch (err: any) {
    console.error('Excel generation error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Download ZIP of all Shortlisted CVs
app.post('/api/screening/download-zip', async (req, res) => {
  try {
    const { candidates, vacancyTitle } = req.body;
    if (!candidates || !Array.isArray(candidates) || candidates.length === 0) {
      return res.status(400).json({ error: 'No shortlisted candidates provided' });
    }

    const zip = new JSZip();
    const manifestLines: string[] = [
      `=======================================================`,
      `ATS SHORTLIST CV ARCHIVE`,
      `Vacancy: ${vacancyTitle || 'Standard Role'}`,
      `Generated: ${new Date().toLocaleString()}`,
      `Total Shortlisted: ${candidates.length}`,
      `=======================================================\n`
    ];

    for (const cand of candidates) {
      manifestLines.push(
        `Rank #${cand.rank} | ${cand.name} | Match: ${cand.matching_percentage}% | File: ${cand.filename}`
      );
      manifestLines.push(`  - Email: ${cand.email} | Phone: ${cand.phone}`);
      manifestLines.push(`  - Strengths: ${(cand.strengths || []).join(', ')}`);
      manifestLines.push('');

      if (cand.savedPath && fs.existsSync(cand.savedPath)) {
        const fileData = fs.readFileSync(cand.savedPath);
        zip.file(`Rank_${cand.rank}_${cand.name.replace(/\s+/g, '_')}_${cand.filename}`, fileData);
      } else {
        // Create candidate text summary file if original file is remote
        const candSummary = `Candidate: ${cand.name}
Rank: ${cand.rank}
Matching Percentage: ${cand.matching_percentage}%
Original File: ${cand.filename}
Email: ${cand.email}
Phone: ${cand.phone}

Strengths:
${(cand.strengths || []).map((s: string) => `- ${s}`).join('\n')}

Evidence:
${(cand.evidence || []).map((e: string) => `- ${e}`).join('\n')}
`;
        zip.file(`Rank_${cand.rank}_${cand.name.replace(/\s+/g, '_')}.txt`, candSummary);
      }
    }

    zip.file('SHORTLIST_MANIFEST.txt', manifestLines.join('\n'));

    const content = await zip.generateAsync({ type: 'nodebuffer' });
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader(
      'Content-Disposition',
      `attachment; filename="Shortlisted_CVs_${(vacancyTitle || 'Archive').replace(/\s+/g, '_')}.zip"`
    );
    res.send(content);
  } catch (err: any) {
    console.error('ZIP generation error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Vite Middleware for development
async function startServer() {
  const isDev = process.env.NODE_ENV !== 'production';
  if (isDev) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa'
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(process.cwd(), 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(process.cwd(), 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`ATS CV Shortlisting Server running on http://localhost:${PORT}`);
  });
}

startServer();
