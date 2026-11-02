import React, { useState, useRef } from 'react';
import { 
  ArrowUpDown, 
  Upload, 
  Download, 
  FileSpreadsheet, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  RefreshCw,
  Layers,
  FileText,
  FileCode,
  FileCheck,
  Paperclip,
  Database,
  HardDrive
} from 'lucide-react';
import { importCsvBusinesses } from '../services/api.ts';

interface ImportExportHubProps {
  onImportComplete: () => void;
}

export const ImportExportHub: React.FC<ImportExportHubProps> = ({ onImportComplete }) => {
  const [csvText, setCsvText] = useState('');
  const [selectedEmirate, setSelectedEmirate] = useState('Dubai');
  const [selectedCategory, setSelectedCategory] = useState('Construction and contracting');
  const [isImporting, setIsImporting] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    importedCount: number;
    duplicatesQueued: number;
    totalInDb: number;
  } | null>(null);

  // Export settings
  const [exportEmirate, setExportEmirate] = useState('all');
  const [exportCategory, setExportCategory] = useState('all');
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [suppressOptOuts, setSuppressOptOuts] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // File upload reader for .csv, .tsv, .txt, .json
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadedFileName(file.name);
    const reader = new FileReader();

    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (!content) return;

      if (file.name.endsWith('.json')) {
        try {
          const parsed = JSON.parse(content);
          const list = Array.isArray(parsed) ? parsed : parsed.data || [parsed];
          // Convert JSON array into CSV format
          if (list.length > 0) {
            const keys = Object.keys(list[0]);
            const headerLine = keys.join(',');
            const rowLines = list.map((item: any) => 
              keys.map(k => `"${String(item[k] || '').replace(/"/g, '""')}"`).join(',')
            );
            setCsvText([headerLine, ...rowLines].join('\n'));
          }
        } catch (err) {
          console.error('JSON parse error:', err);
          alert('Invalid JSON file format. Please upload valid JSON array.');
        }
      } else {
        // CSV, TSV, TXT
        if (file.name.endsWith('.tsv')) {
          // Convert TSV tabs to commas
          const lines = content.split('\n').map(l => l.split('\t').join(','));
          setCsvText(lines.join('\n'));
        } else {
          setCsvText(content);
        }
      }
    };

    reader.readAsText(file);
  };

  // Sample CSV template loader
  const loadSampleCsv = () => {
    const sample = `Company Name,Category,Emirate,Area,Phone,Email,Website
Dubai Modern Fitout LLC,Construction and contracting,Dubai,Business Bay,+97143981122,projects@dubaimodernfitout.ae,https://dubaimodernfitout.ae
Al Reem Maritime Supplies,Logistics and transport,Abu Dhabi,Musaffah Industrial,+97125589900,sales@reemmaritime.ae,https://reemmaritime.ae
Sharjah Auto Detailing Pro,Automobile services,Sharjah,Sharjah Industrial Area,+97165342211,info@autodetailingshj.ae,https://autodetailingshj.ae`;
    setCsvText(sample);
    setUploadedFileName('sample_uae_businesses_template.csv');
  };

  const handleImport = async () => {
    if (!csvText.trim()) return;
    setIsImporting(true);

    try {
      const lines = csvText.trim().split('\n');
      const headers = lines[0].split(',').map(h => h.replace(/^["']|["']$/g, '').trim());
      const rows = [];

      for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const vals = lines[i].split(',').map(v => v.replace(/^["']|["']$/g, '').trim());
        const rowObj: Record<string, string> = {};
        headers.forEach((h, idx) => {
          rowObj[h] = vals[idx] || '';
        });
        rows.push(rowObj);
      }

      const res = await importCsvBusinesses(rows, {
        emirate: selectedEmirate,
        category: selectedCategory
      });

      if (res.success) {
        setImportResult(res);
        onImportComplete();
      }
    } catch (err) {
      console.error('Import error:', err);
    } finally {
      setIsImporting(false);
    }
  };

  const handleExportDownload = () => {
    const params = new URLSearchParams();
    if (exportEmirate !== 'all') params.set('emirate', exportEmirate);
    if (exportCategory !== 'all') params.set('category', exportCategory);
    params.set('suppressOptOuts', suppressOptOuts ? 'true' : 'false');
    if (exportFormat === 'json') params.set('format', 'json');
    window.open(`/api/export?${params.toString()}`, '_blank');
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Title */}
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            CSV / Excel Import & Compliant Export Hub
          </h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
            UAE PDPL Verified
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Ingest external customer lists with phone normalization, and export filtered prospect datasets with automatic suppression checks
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left: CSV Import Card */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Upload className="w-4 h-4 text-emerald-500" />
              <span>Import UAE Business Records</span>
            </h3>
            <div className="flex items-center gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".csv,.xlsx,.xls,.tsv,.json,.txt"
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-2.5 py-1 rounded-lg bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold flex items-center gap-1 border border-emerald-500/20 transition cursor-pointer"
              >
                <Paperclip className="w-3.5 h-3.5" />
                <span>Upload File</span>
              </button>
              <button
                onClick={loadSampleCsv}
                className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline font-semibold cursor-pointer"
              >
                Sample Template
              </button>
            </div>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Upload or paste tabular records (<code className="text-emerald-500 font-mono">.csv</code>, <code className="text-emerald-500 font-mono">.xlsx</code>, <code className="text-emerald-500 font-mono">.tsv</code>, <code className="text-emerald-500 font-mono">.json</code>). Headers: <code className="text-emerald-500 font-mono">Company Name, Category, Emirate, Phone, Email</code>
          </p>

          {uploadedFileName && (
            <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 flex items-center justify-between text-xs text-emerald-800 dark:text-emerald-200">
              <div className="flex items-center gap-2 truncate">
                <FileCheck className="w-4 h-4 text-emerald-500 shrink-0" />
                <span className="font-mono truncate">{uploadedFileName}</span>
              </div>
              <button
                onClick={() => { setUploadedFileName(null); setCsvText(''); }}
                className="text-[10px] text-slate-400 hover:text-slate-200 cursor-pointer underline ml-2 shrink-0"
              >
                Clear
              </button>
            </div>
          )}

          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            rows={7}
            placeholder="Company Name,Category,Emirate,Area,Phone,Email,Website&#10;Apex Contracting LLC,Construction,Dubai,Al Quoz,+97142211999,info@apex.ae,https://apex.ae"
            className="w-full p-3 font-mono text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />

          <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span>Auto E.164 phone standardizer (+971) enabled</span>
            </div>

            <button
              onClick={handleImport}
              disabled={isImporting || !csvText.trim()}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition disabled:opacity-50 cursor-pointer"
            >
              {isImporting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  <span>Execute Ingestion</span>
                </>
              )}
            </button>
          </div>

          {importResult && (
            <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-900 dark:text-emerald-200 space-y-1">
              <div className="font-bold flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4" />
                <span>Import Completed Successfully</span>
              </div>
              <div>
                +{importResult.importedCount} new businesses created • {importResult.duplicatesQueued} fuzzy duplicates flagged for review
              </div>
            </div>
          )}
        </div>

        {/* Right: Compliant Exporter */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                <Download className="w-4 h-4 text-blue-500" />
                <span>Compliant Dataset Export Builder</span>
              </h3>
              <div className="flex items-center p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[10px] font-bold">
                <button
                  type="button"
                  onClick={() => setExportFormat('csv')}
                  className={`px-2 py-0.5 rounded ${exportFormat === 'csv' ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-500'}`}
                >
                  CSV
                </button>
                <button
                  type="button"
                  onClick={() => setExportFormat('json')}
                  className={`px-2 py-0.5 rounded ${exportFormat === 'json' ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-500'}`}
                >
                  JSON
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Filter and generate authorized exports in CSV or JSON. Every export automatically runs against the active UAE TDRA Do-Not-Call and PDPL suppression list to guarantee legal compliance.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Target Emirate
                </label>
                <select
                  value={exportEmirate}
                  onChange={(e) => setExportEmirate(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  <option value="all">All Emirates (Dubai, Abu Dhabi, Sharjah, etc.)</option>
                  <option value="Dubai">Dubai</option>
                  <option value="Abu Dhabi">Abu Dhabi</option>
                  <option value="Sharjah">Sharjah</option>
                  <option value="Ajman">Ajman</option>
                  <option value="Ras Al Khaimah">Ras Al Khaimah</option>
                  <option value="Fujairah">Fujairah</option>
                  <option value="Umm Al Quwain">Umm Al Quwain</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Industry Sector
                </label>
                <select
                  value={exportCategory}
                  onChange={(e) => setExportCategory(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  <option value="all">All Categories</option>
                  <option value="Gold, Jewellery & Precious Metals">Gold, Jewellery & Precious Metals (784 Entities)</option>
                  <option value="Construction and contracting">Construction and contracting</option>
                  <option value="Real estate">Real estate</option>
                  <option value="IT and software companies">IT and software companies</option>
                  <option value="Logistics and transport">Logistics and transport</option>
                  <option value="Healthcare and clinics">Healthcare and clinics</option>
                  <option value="Financial and professional services">Financial and professional services</option>
                </select>
              </div>

              {/* PDPL Suppression Toggle */}
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 space-y-2">
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={suppressOptOuts}
                    onChange={(e) => setSuppressOptOuts(e.target.checked)}
                    className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                  />
                  <div>
                    <span className="font-semibold text-xs text-slate-900 dark:text-white block">
                      Enforce UAE PDPL Suppression List Check (Mandatory Best Practice)
                    </span>
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                      Automatically excludes registered opt-outs, do-not-call numbers, and government-restricted domains.
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end">
            <button
              onClick={handleExportDownload}
              className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center gap-2 shadow-md transition cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Download Filtered {exportFormat.toUpperCase()} Dataset</span>
            </button>
          </div>
        </div>

      </div>

      {/* SUPPORTED FILE TYPES & SPECIFICATIONS REFERENCE MATRIX */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            Supported File Types & Data Exchange Specifications
          </h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono font-semibold">
            Multi-Format Ingestion Engine
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Bulk Ingestion */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5 text-emerald-500" />
                <span>Bulk Data Import</span>
              </span>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono font-bold px-1.5 py-0.5 rounded">
                Ingestion
              </span>
            </div>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 font-mono">
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.CSV</span> (Comma Separated)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.XLSX / .XLS</span> (Excel Sheets)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.TSV / .TXT</span> (Tab Delimited)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.JSON</span> (Raw Records Array)</li>
            </ul>
            <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-700">
              Header auto-mapping, UTF-8 Arabic support & +971 phone normalization.
            </p>
          </div>

          {/* Card 2: Export Formats */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5 text-blue-500" />
                <span>Compliant Export</span>
              </span>
              <span className="text-[10px] bg-blue-500/10 text-blue-600 dark:text-blue-400 font-mono font-bold px-1.5 py-0.5 rounded">
                Export
              </span>
            </div>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 font-mono">
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.CSV</span> (Excel Compatible)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.JSON</span> (REST API Data)</li>
            </ul>
            <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-700">
              Includes 2GIS entrances, Makani IDs, and active UAE PDPL suppression screening.
            </p>
          </div>

          {/* Card 3: CRM File Attachments */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5 text-amber-500" />
                <span>CRM Attachments</span>
              </span>
              <span className="text-[10px] bg-amber-500/10 text-amber-600 dark:text-amber-400 font-mono font-bold px-1.5 py-0.5 rounded">
                Documents
              </span>
            </div>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 font-mono">
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.PDF</span> (DED Licenses, VAT TRN)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.PNG / .JPG / .WEBP</span> (Photos)</li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">.DOCX / .DOC</span> (Contracts)</li>
            </ul>
            <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-700">
              Attached to CRM company profiles for tenancy contracts, proposals & license scans.
            </p>
          </div>

          {/* Card 4: Database Storage */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                <HardDrive className="w-3.5 h-3.5 text-purple-500" />
                <span>Persistent Database</span>
              </span>
              <span className="text-[10px] bg-purple-500/10 text-purple-600 dark:text-purple-400 font-mono font-bold px-1.5 py-0.5 rounded">
                Dual Storage
              </span>
            </div>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 font-mono">
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">/data/uae_database.json</span></li>
              <li>• <span className="font-bold text-slate-800 dark:text-slate-100">Cloud Firestore</span></li>
            </ul>
            <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-700">
              Immediate atomic writes on extraction with automated synchronization.
            </p>
          </div>
        </div>
      </div>

    </div>
  );
};
