import React, { useState } from 'react';
import { 
  ShieldCheck, 
  UserPlus, 
  Mail, 
  Building2, 
  TrendingUp, 
  CheckCircle2, 
  Award,
  DollarSign
} from 'lucide-react';
import { TeamMember } from '../types/index.ts';

interface TeamManagementProps {
  teamMembers: TeamMember[];
}

export const TeamManagement: React.FC<TeamManagementProps> = ({ teamMembers }) => {
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Sales Team & Role-Based Access Control
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold border border-purple-500/20">
              {teamMembers.length} Active Members
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Manage sales reps, territories, pipeline ownership, and revenue quotas across the UAE
          </p>
        </div>
      </div>

      {/* Team Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {teamMembers.map((member) => (
          <div
            key={member.id}
            className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between hover:border-purple-500/40 transition space-y-4"
          >
            <div>
              <div className="flex items-start justify-between">
                <div className="w-12 h-12 rounded-xl bg-purple-600 text-white font-bold flex items-center justify-center text-sm shadow-md">
                  {member.name.split(' ').map(n => n[0]).join('')}
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-300 border border-purple-500/20">
                  {member.role.replace('_', ' ')}
                </span>
              </div>

              <div className="mt-3">
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  {member.name}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">{member.email}</p>
              </div>

              {/* Performance Stats */}
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Assigned Leads</span>
                  <span className="font-bold text-slate-900 dark:text-white font-mono">
                    {member.leadsAssigned}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Pipeline Value</span>
                  <span className="font-bold text-slate-900 dark:text-white font-mono">
                    AED {(member.pipelineValueAed / 1000).toFixed(0)}k
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Deals Won</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                    AED {(member.dealsWonAed / 1000).toFixed(0)}k
                  </span>
                </div>
              </div>
            </div>

            {/* Quota Progress */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-medium">Monthly Quota</span>
                <span className="font-bold text-purple-600 dark:text-purple-400 font-mono">
                  {member.quotaProgress}%
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full ${member.quotaProgress >= 100 ? 'bg-emerald-500' : 'bg-purple-600'}`}
                  style={{ width: `${Math.min(member.quotaProgress, 100)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
};
