import React, { useState } from 'react';
import { 
  Users, 
  Search, 
  Filter, 
  Phone, 
  MessageCircle, 
  Mail, 
  Sparkles, 
  Plus, 
  Edit3, 
  CheckCircle2, 
  Calendar, 
  Clock, 
  ChevronRight,
  TrendingUp,
  Tag,
  ArrowUpDown,
  MoreVertical
} from 'lucide-react';
import { CrmLead, Priority, PipelineStage, TeamMember } from '../types/index.ts';
import { updateCrmLead, createLeadTask, createLeadActivity } from '../services/api.ts';

interface LeadManagementProps {
  leads: CrmLead[];
  teamMembers: TeamMember[];
  onRefresh: () => void;
  onOpenPipeline: () => void;
  onSelectLead?: (lead: CrmLead) => void;
}

export const LeadManagement: React.FC<LeadManagementProps> = ({
  leads,
  teamMembers,
  onRefresh,
  onOpenPipeline,
  onSelectLead
}) => {
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('all');
  const [assignedFilter, setAssignedFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [selectedLead, setSelectedLead] = useState<CrmLead | null>(null);
  const [isEditingDeal, setIsEditingDeal] = useState(false);
  const [newDealValue, setNewDealValue] = useState<number>(0);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [showTaskModal, setShowTaskModal] = useState(false);

  const filtered = leads.filter(l => {
    if (stageFilter !== 'all' && l.pipelineStage !== stageFilter) return false;
    if (assignedFilter !== 'all' && l.assignedUserId !== assignedFilter) return false;
    if (priorityFilter !== 'all' && l.priority !== priorityFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        l.businessName.toLowerCase().includes(q) ||
        l.area.toLowerCase().includes(q) ||
        l.emirate.toLowerCase().includes(q) ||
        l.assignedUserName.toLowerCase().includes(q) ||
        l.tags.some(t => t.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const handleStageChange = async (leadId: string, stage: PipelineStage) => {
    await updateCrmLead(leadId, { pipelineStage: stage });
    onRefresh();
  };

  const handleAssigneeChange = async (leadId: string, userId: string) => {
    await updateCrmLead(leadId, { assignedUserId: userId });
    onRefresh();
  };

  const handleUpdateDealValue = async (lead: CrmLead) => {
    await updateCrmLead(lead.id, { dealValueAed: newDealValue });
    setIsEditingDeal(false);
    onRefresh();
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLead || !newTaskTitle) return;
    await createLeadTask(selectedLead.id, {
      title: newTaskTitle,
      dueDate: new Date(Date.now() + 86400000 * 3).toISOString().split('T')[0],
      priority: 'high'
    });
    setNewTaskTitle('');
    setShowTaskModal(false);
    onRefresh();
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Qualified Sales Leads
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold border border-purple-500/20">
              {filtered.length} Active Leads
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Manage sales lead ownership, stage progression, deal values in AED, and client follow-ups
          </p>
        </div>

        <button
          onClick={onOpenPipeline}
          className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs flex items-center gap-2 shadow-sm transition"
        >
          <TrendingUp className="w-4 h-4" />
          <span>Switch to Kanban Pipeline</span>
        </button>
      </div>

      {/* Filter Row */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company, rep, area, tag..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
          />
        </div>

        {/* Stage Filter */}
        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className="px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
        >
          <option value="all">All Funnel Stages</option>
          <option value="new_lead">New Lead</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="meeting_scheduled">Meeting Scheduled</option>
          <option value="proposal_sent">Proposal Sent</option>
          <option value="negotiation">Negotiation</option>
          <option value="won">Won Deal</option>
          <option value="lost">Lost</option>
        </select>

        {/* Assigned Rep Filter */}
        <select
          value={assignedFilter}
          onChange={(e) => setAssignedFilter(e.target.value)}
          className="px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
        >
          <option value="all">All Sales Reps</option>
          {teamMembers.map((m) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>

        {/* Priority Filter */}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
        >
          <option value="all">All Priorities</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Leads Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Company / Prospect</th>
                <th className="p-3.5">Pipeline Stage</th>
                <th className="p-3.5">Deal Value (AED)</th>
                <th className="p-3.5">Assigned Rep</th>
                <th className="p-3.5">Priority</th>
                <th className="p-3.5">Close Target</th>
                <th className="p-3.5">Tags</th>
                <th className="p-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filtered.map((lead) => (
                <tr key={lead.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition group">
                  
                  {/* Company */}
                  <td className="p-3.5 max-w-xs">
                    <div className="font-semibold text-slate-900 dark:text-white truncate">
                      {lead.businessName}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      {lead.area}, {lead.emirate} • {lead.category}
                    </div>
                  </td>

                  {/* Stage Selector */}
                  <td className="p-3.5 whitespace-nowrap">
                    <select
                      value={lead.pipelineStage}
                      onChange={(e) => handleStageChange(lead.id, e.target.value as PipelineStage)}
                      className="px-2 py-1 rounded-md text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-none"
                    >
                      <option value="new_lead">New Lead</option>
                      <option value="contacted">Contacted</option>
                      <option value="qualified">Qualified</option>
                      <option value="meeting_scheduled">Meeting Scheduled</option>
                      <option value="proposal_sent">Proposal Sent</option>
                      <option value="negotiation">Negotiation</option>
                      <option value="won">Won Deal</option>
                      <option value="lost">Lost</option>
                    </select>
                  </td>

                  {/* Deal Value */}
                  <td className="p-3.5 whitespace-nowrap font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    AED {lead.dealValueAed.toLocaleString()}
                  </td>

                  {/* Assigned Rep */}
                  <td className="p-3.5 whitespace-nowrap">
                    <select
                      value={lead.assignedUserId}
                      onChange={(e) => handleAssigneeChange(lead.id, e.target.value)}
                      className="px-2 py-1 rounded-md text-[11px] bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 focus:outline-none"
                    >
                      {teamMembers.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </td>

                  {/* Priority */}
                  <td className="p-3.5 whitespace-nowrap">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                      lead.priority === 'urgent' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20' :
                      lead.priority === 'high' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20' :
                      'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
                    }`}>
                      {lead.priority}
                    </span>
                  </td>

                  {/* Close Date */}
                  <td className="p-3.5 whitespace-nowrap text-slate-500 text-[11px]">
                    {lead.expectedCloseDate}
                  </td>

                  {/* Tags */}
                  <td className="p-3.5">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {lead.tags.map((tg, idx) => (
                        <span key={idx} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[10px]">
                          {tg}
                        </span>
                      ))}
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="p-3.5 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => {
                          setSelectedLead(lead);
                          setShowTaskModal(true);
                        }}
                        className="p-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-emerald-500"
                        title="Add Task / Follow-up"
                      >
                        <Calendar className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Task Creation Modal */}
      {showTaskModal && selectedLead && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl text-slate-100 space-y-4">
            <h3 className="text-base font-bold text-white">
              Schedule Follow-up for {selectedLead.businessName}
            </h3>
            <form onSubmit={handleAddTask} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Task / Milestone Title</label>
                <input
                  type="text"
                  required
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="e.g. Executive Discovery Call with VP Procurement"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold"
                >
                  Schedule Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
