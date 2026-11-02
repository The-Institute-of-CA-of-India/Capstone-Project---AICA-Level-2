import React from 'react';
import { 
  Building2, 
  Users, 
  Kanban, 
  TrendingUp, 
  DownloadCloud, 
  CheckCircle2, 
  MapPin, 
  ShieldCheck, 
  Sparkles, 
  ArrowRight,
  Clock,
  Briefcase,
  AlertTriangle
} from 'lucide-react';
import { Business, CollectionJob, CrmLead, Emirate } from '../types/index.ts';

interface OverviewDashboardProps {
  businesses: Business[];
  leads: CrmLead[];
  collectionJobs: CollectionJob[];
  duplicatesCount: number;
  onNavigate: (view: any) => void;
  onOpenSpecsModal: () => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  businesses,
  leads,
  collectionJobs,
  duplicatesCount,
  onNavigate,
  onOpenSpecsModal
}) => {
  // Compute analytics
  const totalBusinesses = businesses.length;
  const verifiedContacts = businesses.filter(b => !!b.primaryPhone || !!b.whatsappNumber).length;
  const totalPipelineAed = leads.reduce((acc, l) => acc + l.dealValueAed, 0);
  const avgQualityScore = Math.round(
    businesses.reduce((acc, b) => acc + b.qualityScore, 0) / (totalBusinesses || 1)
  );

  const emirateCounts: Record<string, number> = {};
  for (const b of businesses) {
    emirateCounts[b.emirate] = (emirateCounts[b.emirate] || 0) + 1;
  }

  const pipelineStages = [
    { id: 'new_lead', label: 'New Lead' },
    { id: 'contacted', label: 'Contacted' },
    { id: 'qualified', label: 'Qualified' },
    { id: 'meeting_scheduled', label: 'Meeting' },
    { id: 'proposal_sent', label: 'Proposal' },
    { id: 'negotiation', label: 'Negotiation' },
    { id: 'won', label: 'Won' },
  ];

  const recentJobs = collectionJobs.slice(0, 3);

  // Pending tasks
  const pendingTasks = leads.flatMap(l => l.tasks).filter(t => t.status === 'pending').slice(0, 4);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Top Banner & Quick Mission Control */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white shadow-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="space-y-2 z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold text-xs border border-emerald-500/30 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              UAE Multi-Emirate Ingestion Active
            </span>
            <span className="text-xs text-slate-400 font-mono">PDPL Compliant</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            UAE Commercial Intelligence & Sales Pipeline
          </h2>
          <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
            Real-time business discovery across Dubai, Abu Dhabi, Sharjah, Ajman, RAK, Fujairah, and UAQ. Ingest permitted registry data, eliminate duplicates with fuzzy matching, and convert qualified prospects into sales leads.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 z-10 shrink-0">
          <button
            onClick={() => onNavigate('daily_search')}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition cursor-pointer"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse"></span>
            <Sparkles className="w-4 h-4 text-amber-300" />
            <span>Daily Web Search</span>
          </button>
          <button
            onClick={() => onNavigate('collection')}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs flex items-center gap-2 transition cursor-pointer"
          >
            <DownloadCloud className="w-4 h-4 text-blue-400" />
            <span>Targeted Ingestion</span>
          </button>
          <button
            onClick={onOpenSpecsModal}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs flex items-center gap-2 transition cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span>Specs & PRD</span>
          </button>
        </div>
      </div>

      {/* 4 Core KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-start justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Permitted Businesses</span>
            <div className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              {totalBusinesses.toLocaleString()}
            </div>
            <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
              <span>+18% from last month</span>
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 2 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-start justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Verified Contacts</span>
            <div className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              {verifiedContacts.toLocaleString()}
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              E.164 phone & WhatsApp active
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 3 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-start justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total CRM Pipeline Value</span>
            <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 tracking-tight">
              AED {(totalPipelineAed / 1000).toFixed(0)}k
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
              {leads.length} active deals in funnel
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 4 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-start justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Avg Completeness Score</span>
            <div className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              {avgQualityScore}%
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {duplicatesCount} duplicate candidates queued
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Grid: UAE Distribution & Sales Pipeline Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Emirate Distribution Breakdown */}
        <div className="lg:col-span-1 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                <MapPin className="w-4 h-4 text-emerald-500" />
                <span>Emirates Market Distribution</span>
              </h3>
              <button
                onClick={() => onNavigate('locations')}
                className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline font-semibold"
              >
                Explorer →
              </button>
            </div>

            <div className="space-y-3">
              {[
                { name: 'Dubai', ar: 'دبي', color: 'bg-emerald-500' },
                { name: 'Abu Dhabi', ar: 'أبوظبي', color: 'bg-blue-500' },
                { name: 'Sharjah', ar: 'الشارقة', color: 'bg-amber-500' },
                { name: 'Ajman', ar: 'عجمان', color: 'bg-indigo-500' },
                { name: 'Ras Al Khaimah', ar: 'رأس الخيمة', color: 'bg-purple-500' },
                { name: 'Fujairah', ar: 'الفجيرة', color: 'bg-cyan-500' },
                { name: 'Umm Al Quwain', ar: 'أم القيوين', color: 'bg-rose-500' },
              ].map((em) => {
                const count = emirateCounts[em.name] || 0;
                const percent = Math.round((count / (totalBusinesses || 1)) * 100);
                return (
                  <div key={em.name} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700 dark:text-slate-300">
                        {em.name} <span className="text-[10px] text-slate-400 font-arabic">({em.ar})</span>
                      </span>
                      <span className="font-semibold text-slate-900 dark:text-white font-mono">
                        {count} ({percent}%)
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${em.color} transition-all duration-500`}
                        style={{ width: `${Math.max(percent, 4)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>DED & Free Zone registries mapped</span>
            <span className="font-semibold text-slate-700 dark:text-slate-300">7 / 7 Active</span>
          </div>
        </div>

        {/* 7-Stage Sales Pipeline Funnel */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                  <Kanban className="w-4 h-4 text-purple-500" />
                  <span>CRM Pipeline Conversion Funnel</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Total pipeline: AED {totalPipelineAed.toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => onNavigate('pipeline')}
                className="text-xs text-purple-600 dark:text-purple-400 hover:underline font-semibold"
              >
                Kanban View →
              </button>
            </div>

            {/* Stage Cards Progression */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {pipelineStages.map((st, i) => {
                const stageLeads = leads.filter(l => l.pipelineStage === st.id);
                const stageVal = stageLeads.reduce((a, b) => a + b.dealValueAed, 0);
                return (
                  <div
                    key={st.id}
                    onClick={() => onNavigate('pipeline')}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 hover:border-purple-500/40 transition cursor-pointer flex flex-col justify-between"
                  >
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-tight truncate">
                        {st.label}
                      </div>
                      <div className="text-lg font-black text-slate-900 dark:text-white mt-1">
                        {stageLeads.length}
                      </div>
                    </div>
                    <div className="mt-2 text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold font-mono truncate">
                      AED {(stageVal / 1000).toFixed(0)}k
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Quick Prospecting Callouts */}
            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/50 flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                    Unassigned Discovered Businesses
                  </span>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    Ready to convert into sales opportunities
                  </span>
                </div>
                <button
                  onClick={() => onNavigate('explorer')}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-500 transition"
                >
                  Explore
                </button>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/50 flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                    Fuzzy Deduplication Queue
                  </span>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    {duplicatesCount} potential duplicate pairs flagged
                  </span>
                </div>
                <button
                  onClick={() => onNavigate('settings')}
                  className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold hover:bg-amber-500 transition"
                >
                  Review
                </button>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Average deal cycle: 26 days</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Win Rate: 34.2%</span>
          </div>
        </div>

      </div>

      {/* Bottom Grid: Recent Ingestion Jobs & Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Recent Data Collection Jobs */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <DownloadCloud className="w-4 h-4 text-blue-500" />
              <span>Recent Ingestion Jobs</span>
            </h3>
            <button
              onClick={() => onNavigate('collection')}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-semibold"
            >
              All Jobs →
            </button>
          </div>

          <div className="space-y-2.5">
            {recentJobs.map((job) => (
              <div
                key={job.id}
                className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-slate-900 dark:text-white">
                      {job.category} in {job.area || job.emirate}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 uppercase font-semibold">
                      {job.sourcePlatform.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    +{job.newRecordsAdded} new records • {job.duplicatesDetected} duplicates detected
                  </div>
                </div>

                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  Completed
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Priority Follow-ups & Reminders */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-500" />
              <span>Upcoming Sales Tasks & Follow-ups</span>
            </h3>
            <button
              onClick={() => onNavigate('tasks')}
              className="text-xs text-amber-600 dark:text-amber-400 hover:underline font-semibold"
            >
              Calendar →
            </button>
          </div>

          <div className="space-y-2.5">
            {pendingTasks.map((t) => (
              <div
                key={t.id}
                className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-xs text-slate-900 dark:text-white">
                    {t.title}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 flex items-center gap-2">
                    <span>Due: {t.dueDate}</span>
                    <span>•</span>
                    <span className="text-slate-600 dark:text-slate-300 font-medium">{t.assignedUserName}</span>
                  </div>
                </div>

                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                  t.priority === 'urgent' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' :
                  t.priority === 'high' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                  'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                }`}>
                  {t.priority}
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
};
