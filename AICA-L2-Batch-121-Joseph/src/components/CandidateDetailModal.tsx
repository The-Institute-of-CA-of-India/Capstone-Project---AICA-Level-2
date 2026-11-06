import React, { useState } from 'react';
import { 
  X, 
  Download, 
  CheckCircle, 
  XCircle, 
  AlertTriangle, 
  ShieldCheck, 
  Quote, 
  Award, 
  Briefcase, 
  GraduationCap, 
  Wrench,
  FileText,
  User,
  Mail,
  Phone,
  Clock
} from 'lucide-react';
import { CandidateEvaluation } from '../types';
import { api } from '../services/api';

interface CandidateDetailModalProps {
  candidate: CandidateEvaluation | null;
  onClose: () => void;
  onUpdateCandidateDecision?: (id: string, approved: boolean, notes: string) => void;
}

export const CandidateDetailModal: React.FC<CandidateDetailModalProps> = ({
  candidate,
  onClose,
  onUpdateCandidateDecision
}) => {
  if (!candidate) return null;

  const [notes, setNotes] = useState(candidate.hr_notes || '');
  const [isApproved, setIsApproved] = useState(candidate.hr_approved || candidate.shortlisted || false);

  const handleSaveDecision = () => {
    if (onUpdateCandidateDecision) {
      onUpdateCandidateDecision(candidate.id, isApproved, notes);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full border border-slate-200 overflow-hidden my-6 max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="bg-slate-900 text-white p-6 flex items-start justify-between border-b border-slate-800">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              #{candidate.rank || '-'}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold tracking-tight">{candidate.name}</h2>
                <span
                  className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                    candidate.matching_percentage >= 90 && candidate.mandatory_met
                      ? 'bg-emerald-500 text-white'
                      : candidate.mandatory_met
                      ? 'bg-amber-500 text-white'
                      : 'bg-rose-500 text-white'
                  }`}
                >
                  {candidate.matching_percentage}% Match
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 mt-2">
                <span className="flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-slate-500" />
                  {candidate.email}
                </span>
                <span className="flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-slate-500" />
                  {candidate.phone}
                </span>
                {candidate.years_experience !== undefined && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    ~{candidate.years_experience} Years Exp
                  </span>
                )}
                <span className="flex items-center gap-1 text-slate-300">
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  {candidate.filename}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {candidate.savedPath && (
              <a
                href={api.getDownloadCvUrl(candidate.savedPath, candidate.filename)}
                download={candidate.filename}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 hover:text-white rounded-lg border border-slate-700 transition-colors"
                title="Download original CV document"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Original CV</span>
              </a>
            )}
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1.5 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-700">
          {/* Flags Alert */}
          {candidate.flags && candidate.flags.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-1">
              <div className="font-semibold text-amber-900 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-700" />
                <span>HR Audit Flags:</span>
              </div>
              <ul className="list-disc list-inside text-amber-800 pl-2 space-y-0.5">
                {candidate.flags.map((flag, idx) => (
                  <li key={idx}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Mandatory Check Banner */}
          <div
            className={`p-4 rounded-xl border flex items-center justify-between ${
              candidate.mandatory_met
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                : 'bg-rose-50 border-rose-200 text-rose-950'
            }`}
          >
            <div className="flex items-center gap-3">
              {candidate.mandatory_met ? (
                <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
              ) : (
                <XCircle className="w-6 h-6 text-rose-600 shrink-0" />
              )}
              <div>
                <div className="font-bold text-sm">
                  {candidate.mandatory_met
                    ? 'All Mandatory Requirements Satisfied'
                    : 'Disqualified: Missing Mandatory Requirement'}
                </div>
                <div className="text-[11px] opacity-80">
                  {candidate.mandatory_met
                    ? 'Candidate passed all mandatory dealbreaker filters and qualifies for threshold consideration.'
                    : 'Candidate cannot be shortlisted regardless of overall score per strict ATS criteria.'}
                </div>
              </div>
            </div>
            <div className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-white/80 border border-current">
              {candidate.mandatory_met ? 'PASS' : 'FAIL'}
            </div>
          </div>

          {/* Category Scores Breakdown */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-3.5 bg-blue-50/70 border border-blue-200 rounded-lg">
              <div className="flex items-center justify-between text-blue-900 font-semibold mb-1">
                <span className="flex items-center gap-1">
                  <GraduationCap className="w-3.5 h-3.5" />
                  Qualifications
                </span>
                <span>{candidate.category_scores?.qualifications || 0}%</span>
              </div>
              <div className="w-full h-1.5 bg-blue-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full"
                  style={{ width: `${candidate.category_scores?.qualifications || 0}%` }}
                />
              </div>
            </div>

            <div className="p-3.5 bg-emerald-50/70 border border-emerald-200 rounded-lg">
              <div className="flex items-center justify-between text-emerald-900 font-semibold mb-1">
                <span className="flex items-center gap-1">
                  <Wrench className="w-3.5 h-3.5" />
                  Key Skills
                </span>
                <span>{candidate.category_scores?.skills || 0}%</span>
              </div>
              <div className="w-full h-1.5 bg-emerald-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-600 rounded-full"
                  style={{ width: `${candidate.category_scores?.skills || 0}%` }}
                />
              </div>
            </div>

            <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-lg">
              <div className="flex items-center justify-between text-amber-900 font-semibold mb-1">
                <span className="flex items-center gap-1">
                  <Briefcase className="w-3.5 h-3.5" />
                  Experience
                </span>
                <span>{candidate.category_scores?.experience || 0}%</span>
              </div>
              <div className="w-full h-1.5 bg-amber-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-600 rounded-full"
                  style={{ width: `${candidate.category_scores?.experience || 0}%` }}
                />
              </div>
            </div>

            <div className="p-3.5 bg-purple-50/70 border border-purple-200 rounded-lg">
              <div className="flex items-center justify-between text-purple-900 font-semibold mb-1">
                <span className="flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Mandatory
                </span>
                <span>{candidate.category_scores?.mandatory || 0}%</span>
              </div>
              <div className="w-full h-1.5 bg-purple-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-600 rounded-full"
                  style={{ width: `${candidate.category_scores?.mandatory || 0}%` }}
                />
              </div>
            </div>
          </div>

          {/* Supporting Evidence Quotes (Real CV Excerpts) */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 flex items-center gap-1.5">
              <Quote className="w-4 h-4 text-emerald-600" />
              <span>Supporting CV Evidence Excerpts (Direct From Document)</span>
            </h3>

            {candidate.evidence && candidate.evidence.length > 0 ? (
              <div className="space-y-2">
                {candidate.evidence.map((ev, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-lg font-mono text-slate-800 text-[11px] leading-relaxed border-l-4 border-l-emerald-500"
                  >
                    {ev}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 italic">No extractable text evidence found in document.</p>
            )}
          </div>

          {/* Strengths & Missing Requirements Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Strengths */}
            <div className="p-4 bg-emerald-50/40 border border-emerald-200 rounded-xl space-y-2">
              <h4 className="font-semibold text-emerald-950 flex items-center gap-1.5">
                <Award className="w-4 h-4 text-emerald-700" />
                <span>Identified Strengths & Matches</span>
              </h4>
              <ul className="space-y-1.5 text-slate-700">
                {candidate.strengths && candidate.strengths.length > 0 ? (
                  candidate.strengths.map((str, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{str}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-slate-500 italic">No verified matching strengths identified.</li>
                )}
              </ul>
            </div>

            {/* Missing Requirements */}
            <div className="p-4 bg-rose-50/40 border border-rose-200 rounded-xl space-y-2">
              <h4 className="font-semibold text-rose-950 flex items-center gap-1.5">
                <XCircle className="w-4 h-4 text-rose-700" />
                <span>Missing Requirements & Skill Gaps</span>
              </h4>
              <ul className="space-y-1.5 text-slate-700">
                {candidate.missing_requirements && candidate.missing_requirements.length > 0 ? (
                  candidate.missing_requirements.map((miss, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <XCircle className="w-3.5 h-3.5 text-rose-500 shrink-0 mt-0.5" />
                      <span>{miss}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-emerald-700 font-medium">None! All target criteria satisfied.</li>
                )}
              </ul>
            </div>
          </div>

          {/* HR Decision & Notes */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
            <h4 className="font-semibold text-slate-900 flex items-center gap-1.5">
              <User className="w-4 h-4 text-slate-600" />
              <span>HR Recruiter Assessment & Decision</span>
            </h4>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="approval"
                  checked={isApproved}
                  onChange={() => setIsApproved(true)}
                  className="text-emerald-600 focus:ring-emerald-500"
                />
                <span className="font-medium text-slate-800">Approve for Shortlist</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="approval"
                  checked={!isApproved}
                  onChange={() => setIsApproved(false)}
                  className="text-slate-600 focus:ring-slate-500"
                />
                <span className="font-medium text-slate-800">Reject / Place On Hold</span>
              </label>
            </div>

            <div>
              <label className="block text-[11px] text-slate-500 font-medium mb-1">
                HR Evaluation Notes:
              </label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add confidential notes for hiring manager review..."
                className="w-full p-2.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <div className="text-[11px] text-slate-500">
            Unbiased ATS audit: Final decision rests with HR Manager.
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-100 text-xs font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveDecision}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm"
            >
              Save Decision
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
