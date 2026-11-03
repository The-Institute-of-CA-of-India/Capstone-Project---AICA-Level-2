import React from 'react';
import { X, Terminal, CheckCircle2, Server, Cpu, Shield, FileText } from 'lucide-react';

interface SetupInstructionsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SetupInstructionsModal: React.FC<SetupInstructionsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full border border-slate-200 overflow-hidden my-8">
        {/* Modal Header */}
        <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center">
              <Terminal className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold">JavaScript Frontend & Python Backend Architecture</h3>
              <p className="text-xs text-slate-400">Setup and operating instructions for the enterprise ATS engine</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 text-sm text-slate-700 max-h-[75vh] overflow-y-auto">
          {/* Architecture Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="flex items-center gap-2 font-semibold text-slate-900 mb-2">
                <Cpu className="w-4 h-4 text-indigo-600" />
                <span>Frontend: React 19 + TypeScript</span>
              </div>
              <ul className="text-xs space-y-1.5 text-slate-600">
                <li>• High-performance interactive UI built with Vite & Tailwind CSS</li>
                <li>• HTML5 Folder Picker (`webkitdirectory`) for batch uploads</li>
                <li>• Live progress streaming & score breakdown visualizations</li>
                <li>• Client-side validation ensuring weights total exactly 100%</li>
                <li>• Instant Excel (.xlsx) & Shortlist ZIP export triggers</li>
              </ul>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="flex items-center gap-2 font-semibold text-slate-900 mb-2">
                <Server className="w-4 h-4 text-emerald-600" />
                <span>Backend: Python 3.10 Screening Engine</span>
              </div>
              <ul className="text-xs space-y-1.5 text-slate-600">
                <li>• <code className="text-emerald-700 font-mono">ats_engine.py</code>: Core unbiased scoring engine</li>
                <li>• Native DOCX parser extracting XML paragraph streams</li>
                <li>• PDF text stream extractor & Scanned OCR detector</li>
                <li>• SHA-256 cryptographic duplicate file detection</li>
                <li>• Strict mandatory criteria qualification enforcement</li>
              </ul>
            </div>
          </div>

          {/* Setup Option 1: Integrated Full-Stack (Default) */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-semibold text-slate-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Option 1: Integrated Full-Stack Runner (Active)</span>
            </div>
            <p className="text-xs text-slate-600">
              Express runs on port 3000, serves the React application with Vite, and invokes the Python ATS engine directly via child process streams.
            </p>
            <div className="bg-slate-900 text-slate-200 p-3 rounded-lg font-mono text-xs overflow-x-auto space-y-1">
              <div className="text-slate-400"># 1. Install dependencies & launch</div>
              <div className="text-emerald-400">npm run dev</div>
              <div className="text-slate-400"># Runs server.ts on port 3000 with Python bridge</div>
            </div>
          </div>

          {/* Setup Option 2: Standalone Python Microservice */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-semibold text-slate-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Option 2: Standalone Python Microservice</span>
            </div>
            <p className="text-xs text-slate-600">
              You can also execute the standalone Python HTTP REST server directly:
            </p>
            <div className="bg-slate-900 text-slate-200 p-3 rounded-lg font-mono text-xs overflow-x-auto space-y-1">
              <div className="text-slate-400"># Run standalone Python ATS server on port 8000</div>
              <div className="text-emerald-400">python3 backend_server.py --port 8000</div>
              <div className="text-slate-400"># Test health check</div>
              <div>curl http://localhost:8000/health</div>
            </div>
          </div>

          {/* Compliance & Anti-Bias Standards */}
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg space-y-2">
            <div className="flex items-center gap-2 font-semibold text-emerald-900">
              <Shield className="w-4 h-4 text-emerald-700" />
              <span>Compliance & Data Privacy Principles</span>
            </div>
            <div className="text-xs text-emerald-800 space-y-1 leading-relaxed">
              <p>• <strong>Unbiased Algorithm:</strong> The Python engine filters out all demographic indicators (age, gender, nationality, photos). Scoring is strictly derived from verified skills, education, and years of experience.</p>
              <p>• <strong>HR Approval Gate:</strong> CVs are never sent to external AI providers without explicit HR approval. All API keys remain protected on the backend.</p>
              <p>• <strong>No Hallucinated Data:</strong> Scores are calculated with mathematical consistency and tied directly to verbatim evidence quotes extracted from original candidate files.</p>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-850 text-white text-xs font-medium rounded-lg transition-colors"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
};
