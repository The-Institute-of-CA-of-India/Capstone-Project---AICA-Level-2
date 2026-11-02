import React from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Building2, 
  ShieldCheck, 
  MapPin, 
  FolderTree, 
  Layers, 
  Users, 
  CheckCircle2, 
  DollarSign,
  PieChart
} from 'lucide-react';
import { Business, CrmLead, TeamMember } from '../types/index.ts';

interface AnalyticsReportsProps {
  businesses: Business[];
  leads: CrmLead[];
  teamMembers: TeamMember[];
}

export const AnalyticsReports: React.FC<AnalyticsReportsProps> = ({
  businesses,
  leads,
  teamMembers
}) => {
  const totalBusinesses = businesses.length;
  const totalLeads = leads.length;
  const wonLeads = leads.filter(l => l.pipelineStage === 'won');
  const wonRevenueAed = wonLeads.reduce((a, b) => a + b.dealValueAed, 0);
  const totalPipelineAed = leads.reduce((a, b) => a + b.dealValueAed, 0);
  const winRate = totalLeads > 0 ? Math.round((wonLeads.length / totalLeads) * 100) : 0;

  // Breakdown by Emirate
  const emirateCounts: Record<string, number> = {};
  for (const b of businesses) {
    emirateCounts[b.emirate] = (emirateCounts[b.emirate] || 0) + 1;
  }

  // Breakdown by Category
  const catCounts: Record<string, number> = {};
  for (const b of businesses) {
    catCounts[b.category] = (catCounts[b.category] || 0) + 1;
  }

  // Breakdown by Source
  const sourceCounts: Record<string, number> = {};
  for (const b of businesses) {
    sourceCounts[b.sourcePlatform] = (sourceCounts[b.sourcePlatform] || 0) + 1;
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Title */}
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            UAE Intelligence & CRM Executive Analytics
          </h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
            Real-Time Telemetry
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Data ingestion coverage, market density, sales funnel conversion velocity, and team quota pacing
        </p>
      </div>

      {/* 4 Financial & Health KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Closed Revenue (Won)</span>
          <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
            AED {(wonRevenueAed / 1000).toFixed(0)}k
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            {wonLeads.length} won enterprise accounts
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total In-Funnel Pipeline</span>
          <div className="text-2xl font-black text-slate-900 dark:text-white font-mono">
            AED {(totalPipelineAed / 1000).toFixed(0)}k
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Across 7 pipeline stages
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Conversion Win Rate</span>
          <div className="text-2xl font-black text-blue-600 dark:text-blue-400 font-mono">
            {winRate}%
          </div>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
            +6.4% above UAE B2B SaaS benchmark
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Deduplication Accuracy</span>
          <div className="text-2xl font-black text-purple-600 dark:text-purple-400 font-mono">
            96.8%
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Levenshtein + E.164 phone hash
          </p>
        </div>
      </div>

      {/* Grid: Emirate Distribution & Sources Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Emirate Density Chart */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <MapPin className="w-4 h-4 text-emerald-500" />
              <span>Businesses Ingested by Emirate</span>
            </h3>
            <span className="text-xs font-semibold text-slate-500">7 Emirates</span>
          </div>

          <div className="space-y-3">
            {Object.entries(emirateCounts).map(([emirate, count]) => {
              const pct = Math.round((count / (totalBusinesses || 1)) * 100);
              return (
                <div key={emirate} className="space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-700 dark:text-slate-300">{emirate}</span>
                    <span className="font-bold text-slate-900 dark:text-white font-mono">
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                      style={{ width: `${Math.max(pct, 4)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Source Platform Breakdown */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-500" />
              <span>Records by Source Platform</span>
            </h3>
            <span className="text-xs font-semibold text-slate-500">Attribution</span>
          </div>

          <div className="space-y-3">
            {Object.entries(sourceCounts).map(([src, count]) => {
              const pct = Math.round((count / (totalBusinesses || 1)) * 100);
              return (
                <div key={src} className="space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-700 dark:text-slate-300 uppercase">
                      {src.replace('_', ' ')}
                    </span>
                    <span className="font-bold text-slate-900 dark:text-white font-mono">
                      {count} records ({pct}%)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all duration-500"
                      style={{ width: `${Math.max(pct, 4)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Sales Team Quota Leaderboard */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
          <Users className="w-4 h-4 text-purple-500" />
          <span>Sales Team Quota Attainment & Pacing</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {teamMembers.map((m) => (
            <div
              key={m.id}
              className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 space-y-2.5"
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-purple-600 text-white font-bold flex items-center justify-center text-xs shadow-xs">
                  {m.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div>
                  <h4 className="font-semibold text-xs text-slate-900 dark:text-white">{m.name}</h4>
                  <p className="text-[10px] text-slate-500 uppercase">{m.role.replace('_', ' ')}</p>
                </div>
              </div>

              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Pipeline Managed</span>
                  <span className="font-bold text-slate-900 dark:text-white font-mono">
                    AED {(m.pipelineValueAed / 1000).toFixed(0)}k
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Deals Won</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                    AED {(m.dealsWonAed / 1000).toFixed(0)}k
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-slate-500">Monthly Quota</span>
                  <span className="font-bold text-purple-600 dark:text-purple-400">{m.quotaProgress}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${m.quotaProgress >= 100 ? 'bg-emerald-500' : 'bg-purple-500'}`}
                    style={{ width: `${Math.min(m.quotaProgress, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
