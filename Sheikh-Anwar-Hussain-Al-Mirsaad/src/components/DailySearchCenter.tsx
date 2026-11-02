import React, { useState } from 'react';
import { 
  Sparkles, 
  Globe, 
  Calendar, 
  Clock, 
  CheckCircle2, 
  RefreshCw, 
  Phone, 
  Mail, 
  MessageCircle, 
  User, 
  ShieldCheck, 
  Terminal, 
  Sliders, 
  Play, 
  Building2, 
  AlertCircle,
  Bell,
  ArrowRight
} from 'lucide-react';
import { DailySearchConfig, DailySearchRun, Emirate } from '../types/index.ts';
import { runDailySearchNow, updateDailySearchConfig } from '../services/api.ts';

interface DailySearchCenterProps {
  config: DailySearchConfig;
  runs: DailySearchRun[];
  onRefresh: () => void;
  categories: { nameEn: string }[];
}

export const DailySearchCenter: React.FC<DailySearchCenterProps> = ({
  config,
  runs,
  onRefresh,
  categories
}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [selectedEmirate, setSelectedEmirate] = useState('all');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [latestRunResult, setLatestRunResult] = useState<DailySearchRun | null>(null);
  const [showConfigDrawer, setShowConfigDrawer] = useState(false);
  const [schedConfig, setSchedConfig] = useState<DailySearchConfig>(config);
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  const handleRunNow = async () => {
    setIsRunning(true);
    setLiveLogs([
      `[${new Date().toLocaleTimeString()} GST] Initiating daily automated web crawler across UAE domains...`,
      `[${new Date().toLocaleTimeString()} GST] Querying Google Maps Platform UAE commercial delta updates...`,
      `[${new Date().toLocaleTimeString()} GST] Inspecting newly registered UAE trade licenses (DED/DET feeds)...`,
      `[${new Date().toLocaleTimeString()} GST] Crawling active .ae corporate web headers for contact Schema.org metadata...`
    ]);

    try {
      const res = await runDailySearchNow({
        targetEmirate: selectedEmirate,
        targetCategory: selectedCategory
      });

      if (res.success && res.run) {
        setLatestRunResult(res.run);
        setLiveLogs(res.run.logs);
        onRefresh();
      }
    } catch (err: any) {
      setLiveLogs(prev => [...prev, `[ERROR] Daily search failed: ${err.message}`]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingConfig(true);
    try {
      await updateDailySearchConfig(schedConfig);
      setShowConfigDrawer(false);
      onRefresh();
    } catch (err) {
      console.error('Failed to update scheduler config:', err);
    } finally {
      setIsSavingConfig(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Top Banner: Daily Discovery Mission Control */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950 via-slate-900 to-slate-950 text-white shadow-xl border border-indigo-900/50 relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold text-xs border border-emerald-500/30 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Automated Daily Web Search: {config.enabled ? 'ACTIVE' : 'PAUSED'}</span>
              </span>
              <span className="text-xs text-slate-400 font-mono">
                {config.frequency === 'daily' ? 'Every 24h at 03:00 GST' : config.frequency}
              </span>
            </div>

            <h3 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
              <span>Daily Automated Web & Contact Discovery</span>
              <Sparkles className="w-5 h-5 text-amber-300" />
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              Every day at 03:00 GST, the engine autonomously crawls commercial online sources, scanning for newly registered UAE companies, authorized Google Maps updates, 2GIS additions, and public corporate domains. It extracts full contact details (landlines, WhatsApp, emails, decision makers) while honoring UAE PDPL opt-out suppression.
            </p>

            {/* Daily Schedule Metadata */}
            <div className="pt-2 flex flex-wrap items-center gap-4 text-xs text-slate-300">
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-blue-400" />
                <span>Last Run: {new Date(config.lastRunTimestamp || Date.now()).toLocaleDateString()}</span>
              </div>
              <span>•</span>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-purple-400" />
                <span>Next Run: {new Date(config.nextRunTimestamp || Date.now()).toLocaleDateString()}</span>
              </div>
              <span>•</span>
              <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Auto-Deduplication & E.164 Cleaned</span>
              </div>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            <button
              onClick={() => setShowConfigDrawer(!showConfigDrawer)}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs flex items-center justify-center gap-2 transition cursor-pointer"
            >
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Configure Schedule</span>
            </button>

            <button
              onClick={handleRunNow}
              disabled={isRunning}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/30 transition disabled:opacity-50 cursor-pointer"
            >
              {isRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Searching Webs...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Daily Search Now</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Target Parameters for Manual or Next Run */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-xs uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Globe className="w-4 h-4 text-blue-500" />
            <span>Target Web Search Scope for Today's Ingestion</span>
          </h4>
          <span className="text-[11px] text-slate-500">
            Custom filter for instant or daily sweep
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 block mb-1">
              Filter Target Emirate
            </label>
            <select
              value={selectedEmirate}
              onChange={(e) => setSelectedEmirate(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All 7 Emirates (Dubai, Abu Dhabi, Sharjah, etc.)</option>
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
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 block mb-1">
              Filter Industry Sector
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All Business Categories</option>
              {categories.map((c) => (
                <option key={c.nameEn} value={c.nameEn}>{c.nameEn}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 block mb-1">
              Target Web Sources
            </label>
            <div className="px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-300 font-medium truncate">
              Google Maps, 2GIS, DED & .ae Web Crawl
            </div>
          </div>
        </div>
      </div>

      {/* Contact Points Extracted Summary Card */}
      {latestRunResult && (
        <div className="p-5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs shadow-sm space-y-3 animate-in fade-in duration-300">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <span>Daily Web Search Completed: +{latestRunResult.newBusinessesAdded} New UAE Businesses Discovered</span>
            </div>
            <span className="text-[11px] text-slate-500 font-mono">
              Scanned {latestRunResult.recordsScanned} records
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-800/40 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center gap-1">
                <Mail className="w-3.5 h-3.5 text-blue-500" />
                <span>Emails Extracted</span>
              </span>
              <div className="text-xl font-bold text-slate-900 dark:text-white font-mono">
                +{latestRunResult.contactsExtracted.emails}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-800/40 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center gap-1">
                <Phone className="w-3.5 h-3.5 text-emerald-500" />
                <span>Landlines Verified</span>
              </span>
              <div className="text-xl font-bold text-slate-900 dark:text-white font-mono">
                +{latestRunResult.contactsExtracted.phones}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-800/40 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center gap-1">
                <MessageCircle className="w-3.5 h-3.5 text-emerald-500" />
                <span>WhatsApp Numbers</span>
              </span>
              <div className="text-xl font-bold text-slate-900 dark:text-white font-mono">
                +{latestRunResult.contactsExtracted.whatsapps}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-800/40 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center gap-1">
                <User className="w-3.5 h-3.5 text-purple-500" />
                <span>Decision Makers</span>
              </span>
              <div className="text-xl font-bold text-slate-900 dark:text-white font-mono">
                +{latestRunResult.contactsExtracted.decisionMakers}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Live Log Stream Console */}
      <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800 text-slate-300 font-mono text-xs shadow-inner space-y-2">
        <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="font-bold text-slate-200">Daily Web Discovery Crawler Terminal</span>
          </div>
          <span className="text-[10px] text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>24h Scheduled Worker Running</span>
          </span>
        </div>

        <div className="max-h-52 overflow-y-auto space-y-1.5 text-[11px] text-emerald-400/90 scrollbar-thin scrollbar-thumb-slate-800">
          {liveLogs.length > 0 ? (
            liveLogs.map((log, idx) => <div key={idx}>{log}</div>)
          ) : (
            <div className="text-slate-500">
              Daily automated scheduler initialized. Next scheduled web search runs tomorrow at 03:00 GST.
              Click "Run Daily Search Now" to perform today's web search immediately.
            </div>
          )}
        </div>
      </div>

      {/* Historical Daily Runs */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h4 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
          <Clock className="w-4 h-4 text-purple-500" />
          <span>Past Daily Web Search Runs</span>
        </h4>

        <div className="space-y-3">
          {runs.map((r) => (
            <div
              key={r.id}
              className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-900 dark:text-white">
                    {new Date(r.timestamp).toLocaleDateString()} {new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold">
                    Completed
                  </span>
                </div>
                <span className="text-slate-500 font-mono text-[11px]">
                  Scanned {r.recordsScanned} web records
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-600 dark:text-slate-300">
                <span className="font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                  +{r.newBusinessesAdded} Businesses Added
                </span>
                <span>•</span>
                <span>+{r.contactsExtracted.emails} Emails</span>
                <span>•</span>
                <span>+{r.contactsExtracted.phones} Landlines</span>
                <span>•</span>
                <span>+{r.contactsExtracted.whatsapps} WhatsApp</span>
                <span>•</span>
                <span>+{r.contactsExtracted.decisionMakers} Executives</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Schedule Configuration Drawer / Modal */}
      {showConfigDrawer && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl text-slate-100 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <span>Configure Daily Web Search Scheduler</span>
              </h3>
              <button onClick={() => setShowConfigDrawer(false)} className="text-slate-400 hover:text-white text-xs">
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveConfig} className="space-y-4 text-xs">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={schedConfig.enabled}
                  onChange={(e) => setSchedConfig({ ...schedConfig, enabled: e.target.checked })}
                  className="rounded text-emerald-600 focus:ring-emerald-500"
                />
                <span className="font-semibold text-slate-200">
                  Enable Autonomous Daily Discovery Web Search
                </span>
              </label>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Frequency</label>
                  <select
                    value={schedConfig.frequency}
                    onChange={(e) => setSchedConfig({ ...schedConfig, frequency: e.target.value as any })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                  >
                    <option value="daily">Once Daily (Every 24 hours)</option>
                    <option value="twice_daily">Twice Daily (Every 12 hours)</option>
                    <option value="hourly">Hourly Sync (High frequency)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Scheduled Time (GST)</label>
                  <input
                    type="text"
                    value={schedConfig.scheduledTime}
                    onChange={(e) => setSchedConfig({ ...schedConfig, scheduledTime: e.target.value })}
                    placeholder="03:00 GST (Daily)"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Alert Email for Daily New Contacts Report
                </label>
                <input
                  type="email"
                  value={schedConfig.notificationEmail}
                  onChange={(e) => setSchedConfig({ ...schedConfig, notificationEmail: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                />
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={schedConfig.autoExtractContacts}
                    onChange={(e) => setSchedConfig({ ...schedConfig, autoExtractContacts: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Automatically extract phones, WhatsApp, emails, and decision makers</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={schedConfig.autoDeduplicate}
                    onChange={(e) => setSchedConfig({ ...schedConfig, autoDeduplicate: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Run fuzzy deduplication against existing database</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={schedConfig.emailNotifications}
                    onChange={(e) => setSchedConfig({ ...schedConfig, emailNotifications: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Send daily email summary when new businesses are added</span>
                </label>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowConfigDrawer(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingConfig}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                >
                  Save Schedule Configuration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
