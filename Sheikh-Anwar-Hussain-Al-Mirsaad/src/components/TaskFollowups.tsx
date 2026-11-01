import React, { useState } from 'react';
import { 
  CalendarCheck2, 
  Plus, 
  CheckCircle2, 
  Clock, 
  User, 
  AlertCircle, 
  Filter,
  Check,
  Calendar
} from 'lucide-react';
import { CrmLead, CrmTask } from '../types/index.ts';
import { updateLeadTask, createLeadTask } from '../services/api.ts';

interface TaskFollowupsProps {
  leads: CrmLead[];
  onRefresh: () => void;
}

export const TaskFollowups: React.FC<TaskFollowupsProps> = ({ leads, onRefresh }) => {
  const [filterStatus, setFilterStatus] = useState<'all' | 'pending' | 'completed'>('pending');
  const [showModal, setShowModal] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState(leads[0]?.id || '');
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState(new Date(Date.now() + 86400000 * 2).toISOString().split('T')[0]);
  const [priority, setPriority] = useState('high');

  // Flatten tasks from all leads
  const allTasks: (CrmTask & { businessName: string })[] = [];
  for (const l of leads) {
    for (const t of l.tasks) {
      allTasks.push({ ...t, businessName: l.businessName });
    }
  }

  const filtered = allTasks.filter(t => {
    if (filterStatus === 'pending') return t.status === 'pending';
    if (filterStatus === 'completed') return t.status === 'completed';
    return true;
  });

  const handleToggleTask = async (task: CrmTask) => {
    const nextStatus = task.status === 'pending' ? 'completed' : 'pending';
    await updateLeadTask(task.leadId, task.id, nextStatus);
    onRefresh();
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLeadId || !title) return;
    await createLeadTask(selectedLeadId, {
      title,
      dueDate,
      priority
    });
    setTitle('');
    setShowModal(false);
    onRefresh();
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Sales Tasks & Follow-up Reminders
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/20">
              {allTasks.filter(t => t.status === 'pending').length} Pending Tasks
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Never miss an executive discovery call, proposal review, or contract SLA deadline
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center p-1 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold">
            <button
              onClick={() => setFilterStatus('pending')}
              className={`px-3 py-1 rounded-md transition ${filterStatus === 'pending' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs' : 'text-slate-500'}`}
            >
              Pending
            </button>
            <button
              onClick={() => setFilterStatus('completed')}
              className={`px-3 py-1 rounded-md transition ${filterStatus === 'completed' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs' : 'text-slate-500'}`}
            >
              Completed
            </button>
            <button
              onClick={() => setFilterStatus('all')}
              className={`px-3 py-1 rounded-md transition ${filterStatus === 'all' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs' : 'text-slate-500'}`}
            >
              All
            </button>
          </div>

          <button
            onClick={() => setShowModal(true)}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Task</span>
          </button>
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-3">
        {filtered.map((t) => (
          <div
            key={t.id}
            className={`p-4 rounded-xl border transition flex items-center justify-between gap-4 ${
              t.status === 'completed'
                ? 'bg-slate-50/50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800/60 opacity-60'
                : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm'
            }`}
          >
            <div className="flex items-start gap-3.5">
              <button
                onClick={() => handleToggleTask(t)}
                className={`mt-0.5 w-5 h-5 rounded-md border flex items-center justify-center transition cursor-pointer ${
                  t.status === 'completed'
                    ? 'bg-emerald-600 border-emerald-600 text-white'
                    : 'border-slate-300 dark:border-slate-700 hover:border-emerald-500'
                }`}
              >
                {t.status === 'completed' && <Check className="w-3.5 h-3.5" />}
              </button>

              <div>
                <h4 className={`font-semibold text-xs text-slate-900 dark:text-white ${
                  t.status === 'completed' ? 'line-through text-slate-400' : ''
                }`}>
                  {t.title}
                </h4>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{t.businessName}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1 text-slate-500">
                    <Calendar className="w-3 h-3" />
                    <span>Due {t.dueDate}</span>
                  </span>
                  <span>•</span>
                  <span>Assigned to {t.assignedUserName}</span>
                </div>
              </div>
            </div>

            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase shrink-0 ${
              t.priority === 'urgent' ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20' :
              t.priority === 'high' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20' :
              'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
            }`}>
              {t.priority}
            </span>
          </div>
        ))}

        {filtered.length === 0 && (
          <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl text-slate-400 text-xs">
            No tasks found in this view.
          </div>
        )}
      </div>

      {/* New Task Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl text-slate-100 space-y-4">
            <h3 className="text-base font-bold text-white">Create New Follow-up Task</h3>
            <form onSubmit={handleCreateTask} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Target CRM Lead</label>
                <select
                  value={selectedLeadId}
                  onChange={(e) => setSelectedLeadId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                >
                  {leads.map((l) => (
                    <option key={l.id} value={l.id}>{l.businessName} ({l.emirate})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Task Title</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Present contract proposal & pricing in AED"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Due Date</label>
                  <input
                    type="date"
                    required
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Priority</label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                  >
                    <option value="urgent">Urgent</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                >
                  Create Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
