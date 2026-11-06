import React, { useEffect, useState } from 'react';
import { Loader2, CheckCircle, Cpu, ShieldCheck, Binary, Sliders } from 'lucide-react';

interface ScreeningProgressProps {
  totalCount: number;
  onComplete?: () => void;
}

export const ScreeningProgress: React.FC<ScreeningProgressProps> = ({ totalCount }) => {
  const [progress, setProgress] = useState(15);
  const [currentStage, setCurrentStage] = useState(0);

  const stages = [
    { title: 'Cryptographic Hashing & Duplicate Auditing', desc: 'Running SHA-256 integrity check across all uploaded CV binaries' },
    { title: 'Document Parsing & Unbiased Normalization', desc: 'Parsing DOCX XML, PDF streams, and stripping demographic indicators' },
    { title: 'Python ATS Weighted Formula Computation', desc: 'Evaluating Qualifications (25%), Skills (35%), and Experience (25%)' },
    { title: 'Mandatory Compliance & Threshold Ranking', desc: 'Enforcing strict dealbreakers and ranking candidates by matching %' }
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 95) {
          clearInterval(timer);
          return 95;
        }
        const next = prev + Math.floor(Math.random() * 12) + 5;
        if (next > 25 && currentStage === 0) setCurrentStage(1);
        if (next > 55 && currentStage === 1) setCurrentStage(2);
        if (next > 80 && currentStage === 2) setCurrentStage(3);
        return Math.min(next, 95);
      });
    }, 450);

    return () => clearInterval(timer);
  }, [currentStage]);

  return (
    <div className="bg-white rounded-xl p-8 border border-slate-200 shadow-md max-w-2xl mx-auto my-12 text-center space-y-6">
      <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto shadow-inner">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>

      <div>
        <h2 className="text-lg font-bold text-slate-900">Screening Candidate Batch</h2>
        <p className="text-xs text-slate-500 mt-1">
          Python ATS engine is evaluating {totalCount} candidate CVs against weighted selection criteria.
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs font-semibold text-slate-700">
          <span>{stages[currentStage].title}</span>
          <span className="text-emerald-700">{progress}%</span>
        </div>
        <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-600 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-[11px] text-slate-400 text-left">
          {stages[currentStage].desc}
        </p>
      </div>

      {/* Stages Checklist */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-slate-100 text-left">
        {stages.map((stage, idx) => {
          const isDone = currentStage > idx;
          const isCurrent = currentStage === idx;
          return (
            <div
              key={idx}
              className={`p-3 rounded-lg border text-xs flex items-center gap-2.5 ${
                isDone
                  ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                  : isCurrent
                  ? 'bg-slate-50 border-slate-300 text-slate-900 font-medium'
                  : 'bg-white border-slate-150 text-slate-400'
              }`}
            >
              {isDone ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="w-4 h-4 text-emerald-600 animate-spin shrink-0" />
              ) : (
                <div className="w-4 h-4 rounded-full border border-slate-300 shrink-0" />
              )}
              <span className="truncate">{stage.title}</span>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        <span>Unbiased algorithm active · Final shortlist decision reserved for HR</span>
      </div>
    </div>
  );
};
