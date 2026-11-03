import React, { useState } from 'react';
import { 
  Award, 
  FileSpreadsheet, 
  Archive, 
  CheckCheck, 
  Download, 
  Eye, 
  Filter, 
  Search, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Sparkles,
  Layers,
  ArrowUpDown,
  FileText
} from 'lucide-react';
import { CandidateEvaluation, ScreeningResult, Vacancy } from '../types';
import { api } from '../services/api';

interface ShortlistReviewProps {
  vacancy: Vacancy;
  screeningResult: ScreeningResult;
  onOpenCandidateDetail: (candidate: CandidateEvaluation) => void;
  onRefreshVacancy: () => Promise<void>;
}

export const ShortlistReview: React.FC<ShortlistReviewProps> = ({
  vacancy,
  screeningResult,
  onOpenCandidateDetail,
  onRefreshVacancy
}) => {
  const [filterTab, setFilterTab] = useState<'shortlisted' | 'all' | 'disqualified' | 'under_threshold' | 'unreadable'>('shortlisted');
  const [searchQuery, setSearchQuery] = useState('');
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isDownloadingZip, setIsDownloadingZip] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [hrNotes, setHrNotes] = useState('Reviewed by HR Recruitment Lead. Shortlist validated against job specification.');
  const [approvedIds, setApprovedIds] = useState<string[]>(
    screeningResult.ranked_candidates.filter(c => c.status === 'Shortlisted').map(c => c.id)
  );

  const candidates = screeningResult.ranked_candidates || [];

  // Filter candidates based on active tab & search
  const filteredCandidates = candidates.filter((c) => {
    // Search query filter
    const matchesSearch =
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.strengths || []).some(s => s.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterTab === 'shortlisted') {
      return c.status === 'Shortlisted';
    }
    if (filterTab === 'disqualified') {
      return !c.mandatory_met && !c.unreadable;
    }
    if (filterTab === 'under_threshold') {
      return c.mandatory_met && c.matching_percentage < screeningResult.threshold_applied;
    }
    if (filterTab === 'unreadable') {
      return c.unreadable || c.ocr_needed;
    }
    return true; // 'all'
  });

  const shortlistedList = candidates.filter(c => c.status === 'Shortlisted');
  const disqualifiedList = candidates.filter(c => !c.mandatory_met && !c.unreadable);
  const underThresholdList = candidates.filter(c => c.mandatory_met && c.matching_percentage < screeningResult.threshold_applied);
  const unreadableList = candidates.filter(c => c.unreadable || c.ocr_needed);

  const handleExportExcel = async () => {
    setIsExportingExcel(true);
    try {
      await api.exportExcelReport(screeningResult, vacancy.title);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setIsExportingExcel(false);
    }
  };

  const handleDownloadZip = async () => {
    setIsDownloadingZip(true);
    try {
      const candidatesToZip = shortlistedList.length > 0 ? shortlistedList : candidates;
      await api.downloadShortlistZip(candidatesToZip, vacancy.title);
    } catch (err: any) {
      alert(`ZIP download failed: ${err.message}`);
    } finally {
      setIsDownloadingZip(false);
    }
  };

  const handleToggleApproveCandidate = (id: string) => {
    if (approvedIds.includes(id)) {
      setApprovedIds(approvedIds.filter(item => item !== id));
    } else {
      setApprovedIds([...approvedIds, id]);
    }
  };

  const handleConfirmApproval = async () => {
    setIsApproving(true);
    try {
      await api.approveShortlist(vacancy.id, approvedIds, hrNotes);
      setShowApprovalModal(false);
      await onRefreshVacancy();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Shortlist Proposal Banner */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">
                Shortlisted Candidates Review
              </h1>
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                {shortlistedList.length} of {screeningResult.top_n_cap} Target Proposed
              </span>
            </div>
            <p className="text-xs text-slate-600 mt-1">
              Minimum Threshold: <strong>{screeningResult.threshold_applied}%</strong> · Evaluated Batch: <strong>{screeningResult.total_evaluated} Candidates</strong>
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleExportExcel}
              disabled={isExportingExcel}
              className="flex items-center gap-2 px-3.5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-medium rounded-lg transition-colors shadow-xs"
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>{isExportingExcel ? 'Exporting...' : 'Export Excel Report (.xlsx)'}</span>
            </button>

            <button
              type="button"
              onClick={handleDownloadZip}
              disabled={isDownloadingZip || shortlistedList.length === 0}
              className="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-lg transition-colors shadow-xs disabled:opacity-50"
            >
              <Archive className="w-4 h-4" />
              <span>{isDownloadingZip ? 'Archiving...' : `Download CVs (ZIP · ${shortlistedList.length})`}</span>
            </button>

            <button
              type="button"
              onClick={() => setShowApprovalModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-xs"
            >
              <CheckCheck className="w-4 h-4" />
              <span>Approve Shortlist</span>
            </button>
          </div>
        </div>

        {/* Policy Explanatory Note (Addressing requirements: if fewer qualify, show actual number without lowering threshold) */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 flex items-start gap-2.5 leading-relaxed">
          <Award className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <strong>Enterprise Shortlisting Standard:</strong>{' '}
            {shortlistedList.length < screeningResult.top_n_cap ? (
              <span>
                Exactly <strong>{shortlistedList.length} candidate(s)</strong> met or exceeded the rigorous{' '}
                <strong>{screeningResult.threshold_applied}% threshold</strong> while satisfying all mandatory criteria. Per ATS policy, the threshold has <em>not</em> been lowered to artificially fill the {screeningResult.top_n_cap}-candidate cap.
              </span>
            ) : (
              <span>
                Target cap of {screeningResult.top_n_cap} candidates met with qualifying matching percentages $\ge$ {screeningResult.threshold_applied}%.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Segmented Filter Control */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-lg w-full sm:w-auto overflow-x-auto">
          <button
            type="button"
            onClick={() => setFilterTab('shortlisted')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
              filterTab === 'shortlisted'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Proposed Shortlist ({shortlistedList.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterTab('all')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
              filterTab === 'all'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All Evaluated ({candidates.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterTab('disqualified')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
              filterTab === 'disqualified'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Disqualified ({disqualifiedList.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterTab('under_threshold')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
              filterTab === 'under_threshold'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Under {screeningResult.threshold_applied}% ({underThresholdList.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterTab('unreadable')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
              filterTab === 'unreadable'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            OCR / Flagged ({unreadableList.length})
          </button>
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search candidate or skill..."
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white"
          />
        </div>
      </div>

      {/* Candidates Table / Grid */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4 w-12 text-center">Rank</th>
                <th className="py-3 px-4">Candidate & Contact</th>
                <th className="py-3 px-4 text-center">Matching %</th>
                <th className="py-3 px-4 text-center">Mandatory</th>
                <th className="py-3 px-4">Key Strengths & Evidence</th>
                <th className="py-3 px-4">Missing / Gaps</th>
                <th className="py-3 px-4 text-center">HR Select</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCandidates.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    No candidates found in this category.
                  </td>
                </tr>
              ) : (
                filteredCandidates.map((cand) => {
                  const isSelected = approvedIds.includes(cand.id);
                  const isQualifying = cand.matching_percentage >= screeningResult.threshold_applied && cand.mandatory_met;

                  return (
                    <tr
                      key={cand.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        cand.status === 'Shortlisted' ? 'bg-emerald-50/15' : ''
                      }`}
                    >
                      {/* Rank */}
                      <td className="py-3.5 px-4 text-center font-bold text-slate-900">
                        #{cand.rank}
                      </td>

                      {/* Candidate Name & Contact */}
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900 text-xs">
                          {cand.name}
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-1.5 mt-0.5">
                          <span>{cand.email}</span>
                          <span aria-hidden="true">·</span>
                          <span>{cand.phone}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-2">
                          <span className="truncate max-w-[150px]">{cand.filename}</span>
                          {cand.is_duplicate && (
                            <span className="text-[10px] text-amber-600 font-medium">Duplicate</span>
                          )}
                          {cand.ocr_needed && (
                            <span className="text-[10px] text-purple-600 font-medium">OCR Scan</span>
                          )}
                        </div>
                      </td>

                      {/* Matching Percentage */}
                      <td className="py-3.5 px-4 text-center">
                        <div
                          className={`text-sm font-bold ${
                            isQualifying ? 'text-emerald-700' : cand.mandatory_met ? 'text-amber-700' : 'text-rose-600'
                          }`}
                        >
                          {cand.matching_percentage}%
                        </div>
                        <div className="text-[10px] text-slate-600">
                          Q:{cand.category_scores?.qualifications}% · S:{cand.category_scores?.skills}% · E:{cand.category_scores?.experience}%
                        </div>
                      </td>

                      {/* Mandatory Status */}
                      <td className="py-3.5 px-4 text-center">
                        {cand.mandatory_met ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            PASS
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-800 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                            <XCircle className="w-3 h-3 text-rose-600" />
                            FAIL
                          </span>
                        )}
                      </td>

                      {/* Key Strengths & Evidence */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="space-y-1">
                          {(cand.strengths || []).slice(0, 2).map((st, i) => (
                            <div key={i} className="text-[11px] text-slate-800 flex items-start gap-1">
                              <span className="text-emerald-600 font-bold">•</span>
                              <span className="truncate">{st}</span>
                            </div>
                          ))}
                          {cand.evidence && cand.evidence.length > 0 && (
                            <div className="text-[10px] font-mono text-slate-500 italic truncate max-w-[240px]">
                              "{cand.evidence[0]}"
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Missing Requirements */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="space-y-1">
                          {cand.missing_requirements && cand.missing_requirements.length > 0 ? (
                            cand.missing_requirements.slice(0, 2).map((mr, i) => (
                              <div key={i} className="text-[11px] text-rose-700 flex items-start gap-1">
                                <span className="font-bold">•</span>
                                <span className="truncate">{mr}</span>
                              </div>
                            ))
                          ) : (
                            <span className="text-[11px] text-emerald-600 font-medium">None</span>
                          )}
                        </div>
                      </td>

                      {/* HR Selection Checkbox */}
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleApproveCandidate(cand.id)}
                          className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500 cursor-pointer"
                        />
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right space-x-1 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => onOpenCandidateDetail(cand)}
                          className="px-2.5 py-1 text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded text-[11px] font-medium transition-colors"
                        >
                          Inspect
                        </button>

                        {cand.savedPath && (
                          <a
                            href={api.getDownloadCvUrl(cand.savedPath, cand.filename)}
                            download={cand.filename}
                            className="inline-block p-1 text-slate-400 hover:text-slate-800 transition-colors"
                            title="Download original file"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* HR Shortlist Formal Approval Modal */}
      {showApprovalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-slate-200 overflow-hidden">
            <div className="p-5 bg-slate-900 text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CheckCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-sm">Formal HR Shortlist Sign-Off</h3>
              </div>
              <button
                onClick={() => setShowApprovalModal(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Cancel
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs text-slate-700">
              <p>
                You are approving <strong>{approvedIds.length} candidate(s)</strong> for progression to hiring manager review for vacancy <strong>"{vacancy.title}"</strong>.
              </p>

              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  HR Review Sign-off Notes:
                </label>
                <textarea
                  rows={3}
                  value={hrNotes}
                  onChange={(e) => setHrNotes(e.target.value)}
                  className="w-full p-2.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-900 text-[11px] space-y-0.5">
                <div className="font-semibold">Audit Record Notice:</div>
                <p>This action records your HR signature and timestamp into the vacancy audit log and locks the shortlist version.</p>
              </div>
            </div>

            <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-2">
              <button
                onClick={() => setShowApprovalModal(false)}
                className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-100 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmApproval}
                disabled={isApproving}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs"
              >
                {isApproving ? 'Recording Approval...' : 'Confirm & Save Approval'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
