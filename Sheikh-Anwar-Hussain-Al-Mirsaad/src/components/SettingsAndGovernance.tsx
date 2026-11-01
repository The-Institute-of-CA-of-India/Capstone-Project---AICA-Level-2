import React, { useState } from 'react';
import { 
  Sliders, 
  ShieldAlert, 
  GitMerge, 
  Database, 
  CheckCircle2, 
  X, 
  Trash2, 
  Plus, 
  FileText, 
  Clock,
  AlertTriangle,
  History,
  Lock
} from 'lucide-react';
import { DuplicateCandidate, SuppressionRecord, AuditLog } from '../types/index.ts';
import { mergeDuplicate, dismissDuplicate, addSuppression, deleteSuppression } from '../services/api.ts';

interface SettingsAndGovernanceProps {
  duplicates: DuplicateCandidate[];
  suppressions: SuppressionRecord[];
  auditLogs: AuditLog[];
  onRefresh: () => void;
}

export const SettingsAndGovernance: React.FC<SettingsAndGovernanceProps> = ({
  duplicates,
  suppressions,
  auditLogs,
  onRefresh
}) => {
  const [activeTab, setActiveTab] = useState<'duplicates' | 'suppression' | 'retention' | 'audit'>('duplicates');

  // Add suppression form state
  const [suppType, setSuppType] = useState<'phone' | 'email' | 'domain'>('phone');
  const [suppValue, setSuppValue] = useState('');
  const [suppReason, setSuppReason] = useState('');
  const [isAddingSupp, setIsAddingSupp] = useState(false);

  const pendingDuplicates = duplicates.filter(d => d.status === 'pending');

  const handleMerge = async (dup: DuplicateCandidate) => {
    await mergeDuplicate(dup.id, dup.primaryBusinessId, dup.secondaryBusinessId);
    onRefresh();
  };

  const handleDismiss = async (dup: DuplicateCandidate) => {
    await dismissDuplicate(dup.id);
    onRefresh();
  };

  const handleAddSuppression = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!suppValue.trim()) return;
    setIsAddingSupp(true);
    try {
      await addSuppression({
        type: suppType,
        value: suppValue.trim(),
        reason: suppReason || 'Requested opt-out under UAE PDPL'
      });
      setSuppValue('');
      setSuppReason('');
      onRefresh();
    } catch (err) {
      console.error('Failed to add suppression:', err);
    } finally {
      setIsAddingSupp(false);
    }
  };

  const handleDeleteSuppression = async (id: string) => {
    await deleteSuppression(id);
    onRefresh();
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Title */}
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            System Governance, Deduplication & Compliance
          </h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
            UAE PDPL Article 12
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Fuzzy entity resolution, opt-out suppression lists, 30-day cache retention, and immutable audit logs
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('duplicates')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'duplicates'
              ? 'bg-amber-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <GitMerge className="w-3.5 h-3.5" />
          <span>Fuzzy Deduplication Queue ({pendingDuplicates.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('suppression')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'suppression'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>PDPL Suppression List ({suppressions.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('retention')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'retention'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>Data Retention & Cache Rules</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === 'audit'
              ? 'bg-purple-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Audit Log Viewer</span>
        </button>
      </div>

      {/* TAB 1: DUPLICATES */}
      {activeTab === 'duplicates' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-900 dark:text-amber-200">
            <h4 className="font-bold flex items-center gap-1.5 text-amber-800 dark:text-amber-300 mb-1">
              <AlertTriangle className="w-4 h-4" />
              <span>Intelligent Deduplication Engine</span>
            </h4>
            <p className="leading-relaxed">
              Potential duplicates detected using Levenshtein distance, token sort ratio, normalized E.164 phone hash, and geographic proximity. Merging retains all field provenance and never overwrites user notes.
            </p>
          </div>

          <div className="space-y-3">
            {pendingDuplicates.map((dup) => (
              <div
                key={dup.id}
                className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-300">
                      {dup.confidenceScore}% Match Confidence
                    </span>
                    <span className="text-xs text-slate-500">
                      Levenshtein: {dup.matchCriteria.nameSimilarity}% • Phone Match: {dup.matchCriteria.phoneMatch ? 'Yes' : 'No'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleDismiss(dup)}
                      className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 text-xs font-semibold transition"
                    >
                      Keep Separate
                    </button>
                    <button
                      onClick={() => handleMerge(dup)}
                      className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition"
                    >
                      <GitMerge className="w-3.5 h-3.5" />
                      <span>Merge Into Golden Record</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Primary Master Record
                    </span>
                    <div className="font-bold text-slate-900 dark:text-white">{dup.primaryName}</div>
                    <span className="text-[10px] text-slate-500 font-mono">ID: {dup.primaryBusinessId}</span>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Discovered Candidate Match
                    </span>
                    <div className="font-bold text-slate-900 dark:text-white">{dup.secondaryName}</div>
                    <span className="text-[10px] text-slate-500 font-mono">ID: {dup.secondaryBusinessId}</span>
                  </div>
                </div>
              </div>
            ))}

            {pendingDuplicates.length === 0 && (
              <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl text-slate-400 text-xs">
                Zero duplicate candidates pending review. Database normalized!
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: SUPPRESSION LIST */}
      {activeTab === 'suppression' && (
        <div className="space-y-6">
          {/* Add Suppression Form */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-blue-500" />
              <span>Add Opt-out / Do-Not-Contact Record</span>
            </h3>

            <form onSubmit={handleAddSuppression} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <label className="block text-slate-600 dark:text-slate-300 font-semibold mb-1">Type</label>
                <select
                  value={suppType}
                  onChange={(e) => setSuppType(e.target.value as any)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  <option value="phone">Phone / WhatsApp</option>
                  <option value="email">Email Address</option>
                  <option value="domain">Corporate Domain</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-300 font-semibold mb-1">Value</label>
                <input
                  type="text"
                  required
                  value={suppValue}
                  onChange={(e) => setSuppValue(e.target.value)}
                  placeholder="+97143999999 or user@domain.ae"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-300 font-semibold mb-1">Reason / Legal Ground</label>
                <input
                  type="text"
                  value={suppReason}
                  onChange={(e) => setSuppReason(e.target.value)}
                  placeholder="UAE PDPL Article 12 Right to Opt-out"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={isAddingSupp}
                  className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition"
                >
                  Add to Suppression
                </button>
              </div>
            </form>
          </div>

          {/* List Table */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="p-3.5">Type</th>
                    <th className="p-3.5">Identifier Value</th>
                    <th className="p-3.5">Reason</th>
                    <th className="p-3.5">Date Added</th>
                    <th className="p-3.5 text-right">Remove</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {suppressions.map((sup) => (
                    <tr key={sup.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                      <td className="p-3.5 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded-full text-[10px] uppercase font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {sup.type}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono font-bold text-slate-900 dark:text-white">
                        {sup.value}
                      </td>
                      <td className="p-3.5 text-slate-500">{sup.reason}</td>
                      <td className="p-3.5 text-slate-500 text-[11px]">{sup.dateAdded}</td>
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => handleDeleteSuppression(sup.id)}
                          className="p-1 rounded text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: RETENTION RULES */}
      {activeTab === 'retention' && (
        <div className="space-y-4">
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3 text-xs leading-relaxed">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-500" />
              <span>Third-Party Data Retention & Caching Policy</span>
            </h3>

            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60">
                <span className="font-semibold text-slate-900 dark:text-white block mb-0.5">
                  Google Maps Platform Terms (Section 3.2.3)
                </span>
                <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                  Place Details cannot be cached permanently. The platform strictly adheres to the 30-day maximum caching limit for Place IDs and latitude/longitude, automatically flagging records for re-fetch after 30 days.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60">
                <span className="font-semibold text-slate-900 dark:text-white block mb-0.5">
                  2GIS Commercial Data License
                </span>
                <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                  B2B CRM storage permitted under authorized enterprise contract. Records marked with 2GIS identifier for audit provenance.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60">
                <span className="font-semibold text-slate-900 dark:text-white block mb-0.5">
                  User CRM Ownership Guarantee
                </span>
                <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                  User notes, pipeline deals, tasks, and confirmed customer relationships are never overwritten by external automated scraping or sync jobs.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: AUDIT LOGS */}
      {activeTab === 'audit' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <History className="w-4 h-4 text-purple-500" />
              <span>Immutable System Audit Log</span>
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">{auditLogs.length} events recorded</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="p-3.5">Timestamp</th>
                  <th className="p-3.5">Action</th>
                  <th className="p-3.5">User</th>
                  <th className="p-3.5">Resource</th>
                  <th className="p-3.5">Event Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                    <td className="p-3.5 text-slate-400 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="p-3.5 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {log.action}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                      {log.userName}
                    </td>
                    <td className="p-3.5 text-slate-400 whitespace-nowrap">
                      {log.resourceType}
                    </td>
                    <td className="p-3.5 text-slate-700 dark:text-slate-200 font-sans">
                      {log.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
};
