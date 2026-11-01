import React, { useState } from 'react';
import { 
  Kanban as KanbanIcon, 
  Plus, 
  MapPin, 
  DollarSign, 
  Calendar, 
  Sparkles, 
  User, 
  ChevronRight, 
  ChevronLeft,
  ArrowRight,
  TrendingUp,
  Tag,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { CrmLead, PipelineStage, Priority } from '../types/index.ts';
import { updateCrmLead } from '../services/api.ts';

interface SalesPipelineKanbanProps {
  leads: CrmLead[];
  onRefresh: () => void;
  onSelectLead: (lead: CrmLead) => void;
  onOpenAiEnrich: (bizId: string) => void;
}

export const SalesPipelineKanban: React.FC<SalesPipelineKanbanProps> = ({
  leads,
  onRefresh,
  onSelectLead,
  onOpenAiEnrich
}) => {
  const stages: { id: PipelineStage; label: string; color: string; badgeBg: string }[] = [
    { id: 'new_lead', label: '1. New Lead', color: 'border-blue-500/50', badgeBg: 'bg-blue-500/10 text-blue-400' },
    { id: 'contacted', label: '2. Contacted', color: 'border-cyan-500/50', badgeBg: 'bg-cyan-500/10 text-cyan-400' },
    { id: 'qualified', label: '3. Qualified', color: 'border-indigo-500/50', badgeBg: 'bg-indigo-500/10 text-indigo-400' },
    { id: 'meeting_scheduled', label: '4. Meeting', color: 'border-purple-500/50', badgeBg: 'bg-purple-500/10 text-purple-400' },
    { id: 'proposal_sent', label: '5. Proposal', color: 'border-amber-500/50', badgeBg: 'bg-amber-500/10 text-amber-400' },
    { id: 'negotiation', label: '6. Negotiation', color: 'border-orange-500/50', badgeBg: 'bg-orange-500/10 text-orange-400' },
    { id: 'won', label: '7. Won Deal', color: 'border-emerald-500/50', badgeBg: 'bg-emerald-500/10 text-emerald-400' },
  ];

  const handleStageMove = async (leadId: string, currentStage: PipelineStage, direction: 'next' | 'prev') => {
    const stageIds: PipelineStage[] = stages.map(s => s.id);
    const currentIndex = stageIds.indexOf(currentStage);
    const newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;

    if (newIndex >= 0 && newIndex < stageIds.length) {
      await updateCrmLead(leadId, { pipelineStage: stageIds[newIndex] });
      onRefresh();
    }
  };

  const totalAed = leads.reduce((a, b) => a + b.dealValueAed, 0);

  return (
    <div className="p-6 space-y-6 max-w-full overflow-hidden text-slate-800 dark:text-slate-100 flex flex-col h-[calc(100vh-4rem)]">
      
      {/* Top Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              UAE Sales Pipeline Kanban
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
              Total: AED {totalAed.toLocaleString()}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Visualize B2B deal velocity, transition stages, and manage high-value UAE enterprise prospects
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Currency: AED (Dirhams)</span>
        </div>
      </div>

      {/* Kanban Board Horizontal Scroll Container */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4 scrollbar-thin scrollbar-thumb-slate-800">
        <div className="flex gap-4 h-full min-w-[1300px]">
          {stages.map((st, colIndex) => {
            const colLeads = leads.filter(l => l.pipelineStage === st.id);
            const colTotalAed = colLeads.reduce((acc, l) => acc + l.dealValueAed, 0);

            return (
              <div
                key={st.id}
                className="w-80 flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden shrink-0"
              >
                {/* Column Header */}
                <div className={`p-3.5 border-b border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 border-t-2 ${st.color}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900 dark:text-white">
                      {st.label}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${st.badgeBg}`}>
                      {colLeads.length}
                    </span>
                  </div>
                  <div className="text-[11px] font-mono font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                    AED {(colTotalAed / 1000).toFixed(0)}k total
                  </div>
                </div>

                {/* Column Card List */}
                <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin scrollbar-thumb-slate-800">
                  {colLeads.map((lead) => (
                    <div
                      key={lead.id}
                      className="p-3.5 rounded-xl bg-slate-50/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 shadow-xs hover:border-purple-500/50 transition group space-y-2.5"
                    >
                      {/* Priority & Deal Value */}
                      <div className="flex items-center justify-between">
                        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          lead.priority === 'urgent' ? 'bg-rose-500/10 text-rose-500 border border-rose-500/20' :
                          lead.priority === 'high' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                          'bg-blue-500/10 text-blue-500 border border-blue-500/20'
                        }`}>
                          {lead.priority}
                        </span>

                        <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          AED {lead.dealValueAed.toLocaleString()}
                        </span>
                      </div>

                      {/* Business Name */}
                      <div>
                        <h4 className="font-bold text-xs text-slate-900 dark:text-white leading-snug">
                          {lead.businessName}
                        </h4>
                        <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-slate-400" />
                          <span>{lead.area}, {lead.emirate}</span>
                        </div>
                      </div>

                      {/* AI Summary Highlight */}
                      {lead.aiSummary && (
                        <div className="p-2 rounded-lg bg-purple-50/60 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-900/30 text-[10px] text-purple-900 dark:text-purple-300 leading-tight">
                          <div className="flex items-center gap-1 font-semibold text-purple-600 dark:text-purple-400 mb-0.5">
                            <Sparkles className="w-2.5 h-2.5" />
                            <span>AI Strategic Angle</span>
                          </div>
                          <p className="line-clamp-2">{lead.aiSummary}</p>
                        </div>
                      )}

                      {/* Sales Rep & Target Date */}
                      <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-700/40 text-[10px] text-slate-500 dark:text-slate-400">
                        <div className="flex items-center gap-1">
                          <User className="w-3 h-3 text-slate-400" />
                          <span className="truncate max-w-[100px]">{lead.assignedUserName}</span>
                        </div>
                        <span>Target: {lead.expectedCloseDate}</span>
                      </div>

                      {/* Stage Move Controls */}
                      <div className="flex items-center justify-between pt-1">
                        <button
                          disabled={colIndex === 0}
                          onClick={() => handleStageMove(lead.id, lead.pipelineStage, 'prev')}
                          className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 disabled:opacity-30 cursor-pointer"
                          title="Move to Previous Stage"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>

                        <button
                          onClick={() => onOpenAiEnrich(lead.businessId)}
                          className="text-[10px] font-semibold text-purple-600 dark:text-purple-400 hover:underline flex items-center gap-1 cursor-pointer"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>Enrich Pitch</span>
                        </button>

                        <button
                          disabled={colIndex === stages.length - 1}
                          onClick={() => handleStageMove(lead.id, lead.pipelineStage, 'next')}
                          className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 disabled:opacity-30 cursor-pointer"
                          title="Advance to Next Stage"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>

                    </div>
                  ))}

                  {colLeads.length === 0 && (
                    <div className="h-28 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl flex items-center justify-center text-slate-400 text-xs text-center p-3">
                      No deals currently in this stage
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
};
