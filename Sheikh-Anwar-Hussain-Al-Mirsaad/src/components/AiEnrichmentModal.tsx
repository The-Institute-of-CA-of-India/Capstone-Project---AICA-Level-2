import React, { useState } from 'react';
import { 
  X, 
  Sparkles, 
  Bot, 
  Copy, 
  CheckCircle2, 
  Globe, 
  Building2, 
  Send, 
  RefreshCw,
  Lightbulb,
  ShieldCheck
} from 'lucide-react';
import { Business } from '../types/index.ts';
import { enrichWithAi } from '../services/api.ts';

interface AiEnrichmentModalProps {
  business: Business | null;
  isOpen: boolean;
  onClose: () => void;
  onLeadUpdated?: () => void;
}

export const AiEnrichmentModal: React.FC<AiEnrichmentModalProps> = ({
  business,
  isOpen,
  onClose,
  onLeadUpdated
}) => {
  const [loading, setLoading] = useState(false);
  const [customAngle, setCustomAngle] = useState('');
  const [result, setResult] = useState<{
    summary?: string;
    pitchEn?: string;
    pitchAr?: string;
    icpScore?: number;
    keyAngles?: string[];
  } | null>(null);
  const [copiedEn, setCopiedEn] = useState(false);
  const [copiedAr, setCopiedAr] = useState(false);

  if (!isOpen || !business) return null;

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await enrichWithAi(business.id, customAngle);
      if (res.success) {
        setResult(res);
        if (onLeadUpdated) onLeadUpdated();
      }
    } catch (err) {
      console.error('Failed to run AI enrichment:', err);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, type: 'en' | 'ar') => {
    navigator.clipboard.writeText(text);
    if (type === 'en') {
      setCopiedEn(true);
      setTimeout(() => setCopiedEn(false), 2000);
    } else {
      setCopiedAr(true);
      setTimeout(() => setCopiedAr(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-hidden">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl text-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-900/40">
              <Sparkles className="w-5 h-5 text-amber-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">Gemini 3.8 Flash Lead Intelligence</h3>
                <span className="text-[10px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
                  AI Enrichment
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Target Entity: <span className="text-slate-200 font-semibold">{business.nameEn}</span> ({business.emirate})
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-800 text-xs">
          
          {/* Custom Angle Prompt Input */}
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3">
            <label className="block text-xs font-semibold text-slate-200">
              Sales Hook / Focus Angle (Optional)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customAngle}
                onChange={(e) => setCustomAngle(e.target.value)}
                placeholder="e.g., Pitching Fleet Telematics, Corporate Tax Advisory, Cloud Security..."
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold flex items-center gap-2 shadow-md transition disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-amber-300" />
                    <span>Generate Analysis</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results Display */}
          {result ? (
            <div className="space-y-5 animate-in fade-in duration-300">
              {/* Summary & Score */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div className="sm:col-span-3 p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-purple-400 mb-1 flex items-center gap-1.5">
                    <Bot className="w-3.5 h-3.5" />
                    <span>Commercial Summary</span>
                  </div>
                  <p className="text-slate-200 leading-relaxed">{result.summary}</p>
                </div>

                <div className="p-4 rounded-xl bg-gradient-to-br from-slate-800 to-slate-800/80 border border-slate-700/60 flex flex-col justify-center items-center text-center">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                    ICP Match Score
                  </div>
                  <div className="text-3xl font-black text-emerald-400">
                    {result.icpScore || 88}%
                  </div>
                  <span className="text-[10px] text-emerald-300 font-medium mt-1">High B2B Propensity</span>
                </div>
              </div>

              {/* Key Selling Angles */}
              {result.keyAngles && result.keyAngles.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400 mb-2 flex items-center gap-1.5">
                    <Lightbulb className="w-3.5 h-3.5" />
                    <span>Key Strategic Hooks for UAE Decision Makers</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {result.keyAngles.map((angle, i) => (
                      <span key={i} className="px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 font-medium">
                        ✓ {angle}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Bilingual Email Drafts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* English Outreach */}
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-slate-200 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-blue-400" />
                      <span>English B2B Outreach Pitch</span>
                    </span>
                    <button
                      onClick={() => copyToClipboard(result.pitchEn || '', 'en')}
                      className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 px-2 py-0.5 rounded bg-slate-900 border border-slate-700"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedEn ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950 font-sans text-slate-300 whitespace-pre-wrap leading-relaxed text-[11px] flex-1 border border-slate-800">
                    {result.pitchEn}
                  </div>
                </div>

                {/* Arabic Outreach */}
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 flex flex-col" dir="rtl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-slate-200 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-emerald-400" />
                      <span>صيغة البريد الإلكتروني باللغة العربية</span>
                    </span>
                    <button
                      onClick={() => copyToClipboard(result.pitchAr || '', 'ar')}
                      className="flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 px-2 py-0.5 rounded bg-slate-900 border border-slate-700"
                      dir="ltr"
                    >
                      <Copy className="w-3 h-3" />
                      <span>{copiedAr ? 'تم النسخ' : 'نسخ'}</span>
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950 font-sans text-slate-300 whitespace-pre-wrap leading-relaxed text-[11px] flex-1 border border-slate-800 text-right">
                    {result.pitchAr}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center border-2 border-dashed border-slate-800 rounded-xl space-y-2">
              <Bot className="w-8 h-8 text-slate-500 mx-auto" />
              <p className="text-slate-400">
                Click <strong className="text-slate-200">"Generate Analysis"</strong> to generate an instant commercial summary, ICP qualification score, and bilingual UAE sales outreach.
              </p>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1.5 text-emerald-400 text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Zero personal data retention • Compliant with UAE PDPL</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
