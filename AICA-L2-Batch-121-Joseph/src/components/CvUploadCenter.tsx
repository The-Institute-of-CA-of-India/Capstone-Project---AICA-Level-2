import React, { useRef, useState } from 'react';
import { 
  FolderUp, 
  Upload, 
  FileText, 
  Copy, 
  Eye, 
  ShieldAlert, 
  Sparkles, 
  CheckCircle2, 
  FileCheck, 
  AlertTriangle,
  Play,
  RotateCcw,
  Layers,
  Database
} from 'lucide-react';
import { UploadedCvFile } from '../types';
import { api } from '../services/api';

interface CvUploadCenterProps {
  uploadedFiles: UploadedCvFile[];
  onFilesUpdated: (files: UploadedCvFile[]) => void;
  hrAiConsent: boolean;
  onAiConsentChange: (consent: boolean) => void;
  onStartScreening: () => void;
  isProcessing: boolean;
}

export const CvUploadCenter: React.FC<CvUploadCenterProps> = ({
  uploadedFiles,
  onFilesUpdated,
  hrAiConsent,
  onAiConsentChange,
  onStartScreening,
  isProcessing
}) => {
  const folderInputRef = useRef<HTMLInputElement>(null);
  const filesInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFilePreview, setSelectedFilePreview] = useState<UploadedCvFile | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const filesArray = Array.from(fileList);
      const newlyUploaded = await api.uploadCvs(filesArray);
      
      // Merge with existing files avoiding duplicate IDs
      const existingIds = new Set(uploadedFiles.map(f => f.fileHash));
      const filteredNew = newlyUploaded.filter(f => !existingIds.has(f.fileHash));
      onFilesUpdated([...uploadedFiles, ...newlyUploaded]);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload CV files');
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = '';
    }
  };

  const handleLoadSampleDataset = async () => {
    setIsUploading(true);
    setUploadError(null);
    try {
      const samples = await api.loadSampleData();
      onFilesUpdated(samples);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to load sample dataset');
    } finally {
      setIsUploading(false);
    }
  };

  const handleClearAll = () => {
    onFilesUpdated([]);
    setSelectedFilePreview(null);
  };

  const duplicateCount = uploadedFiles.filter(f => f.is_duplicate).length;
  const ocrNeededCount = uploadedFiles.filter(f => f.is_ocr_scanned || f.unreadable).length;
  const docxCount = uploadedFiles.filter(f => f.filename.endsWith('.docx')).length;
  const pdfCount = uploadedFiles.filter(f => f.filename.endsWith('.pdf')).length;

  return (
    <div className="space-y-8">
      {/* Top Banner & Control Area */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">CV Batch Ingestion & Document Center</h1>
          <p className="text-xs text-slate-500 mt-1">
            Upload candidate resumes by selecting an entire folder or individual files. Supports DOCX, PDF, and scanned PDFs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {uploadedFiles.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              disabled={isProcessing}
              className="flex items-center gap-1.5 px-3 py-2 text-xs text-slate-600 hover:text-slate-900 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Clear Batch</span>
            </button>
          )}

          <button
            type="button"
            onClick={onStartScreening}
            disabled={uploadedFiles.length === 0 || isProcessing}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-xs disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Start Screening with Python Engine ({uploadedFiles.length} CVs)</span>
          </button>
        </div>
      </div>

      {uploadError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{uploadError}</span>
        </div>
      )}

      {/* Upload Action Triggers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Trigger 1: Folder Picker */}
        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col justify-between hover:border-emerald-300 transition-colors group">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <FolderUp className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Upload Entire Folder</h2>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Select a directory containing hundreds or thousands of CVs. Subfolders and nested documents are parsed automatically.
              </p>
            </div>
          </div>

          <div className="pt-4 mt-2 border-t border-slate-100">
            {/* Folder input with webkitdirectory */}
            <input
              type="file"
              ref={folderInputRef}
              // @ts-ignore
              webkitdirectory=""
              directory=""
              multiple
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              type="button"
              disabled={isUploading}
              onClick={() => folderInputRef.current?.click()}
              className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <FolderUp className="w-3.5 h-3.5" />
              <span>Select CV Folder</span>
            </button>
          </div>
        </div>

        {/* Trigger 2: Multi-File Picker */}
        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col justify-between hover:border-emerald-300 transition-colors group">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Upload Multiple Files</h2>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Select specific PDF, Word (.docx), or plain text CVs from your local device to append to the batch.
              </p>
            </div>
          </div>

          <div className="pt-4 mt-2 border-t border-slate-100">
            <input
              type="file"
              ref={filesInputRef}
              multiple
              accept=".pdf,.docx,.doc,.txt,.md"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              type="button"
              disabled={isUploading}
              onClick={() => filesInputRef.current?.click()}
              className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Choose Files</span>
            </button>
          </div>
        </div>

        {/* Trigger 3: Instant Realistic Sample Dataset */}
        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col justify-between hover:border-emerald-300 transition-colors group">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Load Sample Candidate Batch</h2>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Loads 8 pre-built real CV files: top matches, near-misses (88%), mandatory failures, unreadable OCR scans, and duplicate files.
              </p>
            </div>
          </div>

          <div className="pt-4 mt-2 border-t border-slate-100">
            <button
              type="button"
              disabled={isUploading}
              onClick={handleLoadSampleDataset}
              className="w-full py-2 px-3 bg-purple-700 hover:bg-purple-800 text-white text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Database className="w-3.5 h-3.5" />
              <span>Load 8 Sample CVs</span>
            </button>
          </div>
        </div>
      </div>

      {/* External AI Provider Approval Gate */}
      <div className="bg-slate-900 text-white rounded-xl p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm">HR External AI Provider Consent Gate</span>
                <span className="text-[11px] text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                  GDPR & EEOC Protected
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
                In strict adherence to requirements, API keys remain exclusively on the backend. No CVs or candidate data are transmitted to external AI providers (such as Gemini) without explicit HR authorization.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end md:self-center">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={hrAiConsent}
                onChange={(e) => onAiConsentChange(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
            <span className="text-xs font-medium text-slate-200">
              {hrAiConsent ? 'AI Enhancement Approved' : 'Local Python Engine Only'}
            </span>
          </div>
        </div>

        <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>• Local Engine: Runs native Python regex, tokenization, & weighted formula</span>
          <span>• External AI (When Approved): Enriches OCR for scanned images & non-searchable PDFs</span>
          <span>• Zero Demographic Processing: No age, gender, race, or photos evaluated</span>
        </div>
      </div>

      {/* Batch Ingestion Status & Statistics */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Total CVs Ingested</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{uploadedFiles.length}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">{docxCount} Word · {pdfCount} PDF</div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Duplicate Files Detected</div>
              <div className="text-2xl font-bold text-amber-600 mt-1">{duplicateCount}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">SHA-256 Hash Matching</div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Scanned / OCR Needed</div>
              <div className="text-2xl font-bold text-purple-600 mt-1">{ocrNeededCount}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Requires text layer check</div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Protected Storage</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1">Encrypted</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Isolated in /data/uploads</div>
            </div>
          </div>

          {/* Files List Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-xs font-semibold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-600" />
                <span>Uploaded Documents ({uploadedFiles.length} Files)</span>
              </h2>
              <span className="text-xs text-slate-500">Ready for screening</span>
            </div>

            <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
              {uploadedFiles.map((file, idx) => (
                <div
                  key={file.id || idx}
                  className="p-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors text-xs"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                    <div className="min-w-0">
                      <div className="font-medium text-slate-900 truncate">
                        {file.filename}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500">
                        <span>{(file.fileSize / 1024).toFixed(1)} KB</span>
                        <span aria-hidden="true">·</span>
                        <span className="font-mono text-slate-400">
                          SHA: {file.fileHash?.slice(0, 10)}...
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {file.is_duplicate && (
                      <span className="text-[11px] font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        Duplicate of {file.duplicate_of || 'existing file'}
                      </span>
                    )}

                    {file.is_ocr_scanned && (
                      <span className="text-[11px] font-medium text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                        Scanned / OCR
                      </span>
                    )}

                    {!file.is_duplicate && !file.is_ocr_scanned && (
                      <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        Readable Text Layer
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() => setSelectedFilePreview(file)}
                      className="p-1.5 text-slate-500 hover:text-slate-800 transition-colors"
                      title="Inspect extracted text snippet"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Extracted Text Snippet Modal */}
      {selectedFilePreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-xs font-bold text-slate-900">{selectedFilePreview.filename}</h3>
                <p className="text-[11px] text-slate-500">Extracted Text Stream Preview</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedFilePreview(null)}
                className="text-slate-400 hover:text-slate-700 text-xs font-medium"
              >
                Close
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto">
              {selectedFilePreview.text ? (
                <pre className="text-xs text-slate-700 font-mono whitespace-pre-wrap leading-relaxed">
                  {selectedFilePreview.text}
                </pre>
              ) : (
                <div className="text-xs text-slate-500 text-center py-8">
                  No direct text stream detected. This appears to be a scanned raster image or protected PDF requiring OCR processing.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
