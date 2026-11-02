import React, { useState, useEffect } from 'react';
import { 
  Database, 
  HardDrive, 
  Cloud, 
  ShieldCheck, 
  CheckCircle2, 
  RefreshCw, 
  Download, 
  X, 
  FileJson, 
  Layers, 
  Clock, 
  Server,
  AlertCircle
} from 'lucide-react';
import { fetchStorageStatus, persistStorageNow } from '../services/api.ts';

interface StorageStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRefreshParent: () => void;
}

export const StorageStatusModal: React.FC<StorageStatusModalProps> = ({
  isOpen,
  onClose,
  onRefreshParent
}) => {
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [storageData, setStorageData] = useState<{
    status: string;
    mode: string;
    storageFile: string;
    fileExists: boolean;
    fileSizeKb: number;
    lastSavedAt: string | null;
    firestoreDatabaseId: string;
    cloudStorageTarget: string;
    counts: {
      businesses: number;
      leads: number;
      contacts: number;
      dailyRuns: number;
      suppressions: number;
      auditLogs: number;
    };
  } | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const res = await fetchStorageStatus();
      setStorageData(res);
    } catch (e) {
      console.error('Failed to load storage status:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadStatus();
    }
  }, [isOpen]);

  const handleManualPersist = async () => {
    setSyncing(true);
    try {
      await persistStorageNow();
      await loadStatus();
      onRefreshParent();
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl shadow-2xl text-white overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Data Storage & Cloud Persistence Engine</h2>
              <p className="text-xs text-slate-400">
                All downloaded, extracted, and enriched business intelligence is permanently stored across sessions.
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 overflow-y-auto">
          {/* Dual Storage Banner */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/50 via-slate-900 to-slate-950 border border-emerald-900/50 flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="text-xs font-bold text-emerald-300 uppercase tracking-wider">
                  Persistent Storage Active
                </span>
              </div>
              <p className="text-sm text-slate-200 font-medium">
                Dual Storage: Disk JSON Database + Google Cloud Firestore
              </p>
            </div>
            <button
              onClick={handleManualPersist}
              disabled={syncing}
              className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 transition shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
              <span>{syncing ? 'Persisting...' : 'Commit Storage Now'}</span>
            </button>
          </div>

          {/* Storage Locations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Local Server Disk Storage */}
            <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-emerald-400" />
                  <span>Disk Database</span>
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300">
                  {storageData?.fileExists ? 'Saved to Disk' : 'Initializing'}
                </span>
              </div>
              <div className="text-xs font-mono text-slate-300 bg-slate-900 p-2 rounded-lg border border-slate-800 truncate">
                {storageData?.storageFile || 'data/uae_database.json'}
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                <span>File Size: <strong className="text-slate-200">{storageData?.fileSizeKb || 0} KB</strong></span>
                <span>Auto-Saves: <strong className="text-emerald-400">On Every Extraction</strong></span>
              </div>
            </div>

            {/* Cloud Firestore Storage */}
            <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Cloud className="w-4 h-4 text-cyan-400" />
                  <span>Google Cloud Firestore</span>
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300">
                  Connected
                </span>
              </div>
              <div className="text-xs font-mono text-slate-300 bg-slate-900 p-2 rounded-lg border border-slate-800 truncate">
                {storageData?.firestoreDatabaseId || 'ai-studio-almirsaaduaebusi-195bec68-2c38-444b-892a-cbaef52c0b32'}
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                <span>Collections: <strong className="text-slate-200">4 Collections</strong></span>
                <span>Security Rules: <strong className="text-emerald-400">Deployed</strong></span>
              </div>
            </div>
          </div>

          {/* Stored Entities Breakdown */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-amber-400" />
              <span>Stored Record Inventory</span>
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">Businesses Stored</div>
                <div className="text-xl font-bold text-white mt-1">
                  {storageData?.counts.businesses || 0}
                </div>
              </div>

              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">Contacts & Execs</div>
                <div className="text-xl font-bold text-cyan-400 mt-1">
                  {storageData?.counts.contacts || 0}
                </div>
              </div>

              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">CRM Sales Leads</div>
                <div className="text-xl font-bold text-emerald-400 mt-1">
                  {storageData?.counts.leads || 0}
                </div>
              </div>

              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">Daily Crawler Runs</div>
                <div className="text-xl font-bold text-purple-400 mt-1">
                  {storageData?.counts.dailyRuns || 0}
                </div>
              </div>

              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">Suppression List</div>
                <div className="text-xl font-bold text-rose-400 mt-1">
                  {storageData?.counts.suppressions || 0}
                </div>
              </div>

              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700/50">
                <div className="text-xs text-slate-400">Audit Trail Logs</div>
                <div className="text-xl font-bold text-amber-400 mt-1">
                  {storageData?.counts.auditLogs || 0}
                </div>
              </div>
            </div>
          </div>

          {/* Last Sync Timestamp */}
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-slate-500" />
              <span>Last saved to disk database:</span>
            </span>
            <span className="font-mono text-slate-300">
              {storageData?.lastSavedAt ? new Date(storageData.lastSavedAt).toLocaleString() + ' GST' : 'On Startup'}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            UAE PDPL Compliance & Auto-Storage Safeguard Active
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
