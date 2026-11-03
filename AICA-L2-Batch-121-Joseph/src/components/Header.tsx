import React from 'react';
import { Briefcase, Terminal, ShieldCheck, LogOut, ChevronDown, Plus, Sparkles, Sliders } from 'lucide-react';
import { Vacancy, UserSession } from '../types';

interface HeaderProps {
  vacancies: Vacancy[];
  activeVacancy: Vacancy | null;
  onSelectVacancy: (vacancy: Vacancy) => void;
  onCreateNewVacancy: () => void;
  user: UserSession;
  onLogout: () => void;
  onOpenSetupGuide: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  vacancies,
  activeVacancy,
  onSelectVacancy,
  onCreateNewVacancy,
  user,
  onLogout,
  onOpenSetupGuide
}) => {
  const [dropdownOpen, setDropdownOpen] = React.useState(false);

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand & System Identity */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-semibold shadow-sm">
                <Briefcase className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold tracking-tight text-white text-base">ATS CV Shortlisting</span>
                  <span className="text-slate-400 text-xs hidden sm:inline">v2.4 Enterprise</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span>Python Screening Engine</span>
                  <span aria-hidden="true">·</span>
                  <span className="text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
                    Backend Active
                  </span>
                </div>
              </div>
            </div>

            {/* Vacancy Selector */}
            <div className="relative hidden md:block">
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 px-3 py-1.5 text-xs text-slate-200 bg-slate-800 hover:bg-slate-750 border border-slate-700 rounded-md transition-colors"
              >
                <span className="text-slate-400">Role:</span>
                <span className="font-medium text-white max-w-[200px] truncate">
                  {activeVacancy?.title || 'Select Vacancy'}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-1" />
              </button>

              {dropdownOpen && (
                <div className="absolute left-0 mt-2 w-72 bg-slate-900 border border-slate-700 rounded-lg shadow-xl py-1 z-50">
                  <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800 flex items-center justify-between">
                    <span>Saved Vacancies</span>
                    <button
                      onClick={() => {
                        setDropdownOpen(false);
                        onCreateNewVacancy();
                      }}
                      className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 text-xs"
                    >
                      <Plus className="w-3 h-3" />
                      New
                    </button>
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {vacancies.map((v) => (
                      <button
                        key={v.id}
                        onClick={() => {
                          onSelectVacancy(v);
                          setDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs hover:bg-slate-800 transition-colors ${
                          v.id === activeVacancy?.id ? 'bg-slate-800/80 text-emerald-400' : 'text-slate-200'
                        }`}
                      >
                        <div className="font-medium truncate">{v.title}</div>
                        <div className="text-slate-400 text-[11px] flex items-center gap-2 mt-0.5">
                          <span>{v.department}</span>
                          <span aria-hidden="true">·</span>
                          <span>{v.results ? `${v.results.qualifying_count} Shortlisted` : 'Not screened yet'}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Tools & User Info */}
          <div className="flex items-center gap-3">
            {/* Setup & Architecture Guide Button */}
            <button
              onClick={onOpenSetupGuide}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors"
              title="Architecture and setup instructions for JS Frontend and Python Backend"
            >
              <Terminal className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">JS & Python Setup</span>
            </button>

            {/* Unbiased Guarantee Notice */}
            <div className="hidden lg:flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800/60 px-2.5 py-1 rounded border border-slate-750">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Unbiased ATS (Zero Demographic Processing)</span>
            </div>

            {/* User Profile */}
            <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
              <div className="text-right hidden sm:block">
                <div className="text-xs font-medium text-white">{user.name}</div>
                <div className="text-[11px] text-slate-400">{user.role}</div>
              </div>
              <button
                onClick={onLogout}
                className="p-1.5 text-slate-400 hover:text-rose-400 transition-colors"
                title="Log out of ATS session"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
