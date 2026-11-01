import React from 'react';
import { 
  Search, 
  MapPin, 
  Bell, 
  ShieldCheck, 
  BookOpen, 
  Sparkles, 
  Globe, 
  CheckCircle2,
  RefreshCw,
  Database,
  Navigation
} from 'lucide-react';
import { Emirate } from '../types/index.ts';

interface NavbarProps {
  currentViewTitle: string;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  selectedEmirate: string;
  onEmirateChange: (emirate: string) => void;
  onOpenSpecsModal: () => void;
  onOpenDailySearch?: () => void;
  onOpenStorageModal?: () => void;
  onOpenGoogleMap?: () => void;
  onOpenTracer?: () => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentViewTitle,
  searchQuery,
  onSearchChange,
  selectedEmirate,
  onEmirateChange,
  onOpenSpecsModal,
  onOpenDailySearch,
  onOpenStorageModal,
  onOpenGoogleMap,
  onOpenTracer,
  onRefresh,
  isRefreshing
}) => {
  const emirates: { label: string; value: string }[] = [
    { label: 'All 7 Emirates', value: 'all' },
    { label: 'Dubai (دبي)', value: 'Dubai' },
    { label: 'Abu Dhabi (أبوظبي)', value: 'Abu Dhabi' },
    { label: 'Sharjah (الشارقة)', value: 'Sharjah' },
    { label: 'Ajman (عجمان)', value: 'Ajman' },
    { label: 'Ras Al Khaimah (رأس الخيمة)', value: 'Ras Al Khaimah' },
    { label: 'Fujairah (الفجيرة)', value: 'Fujairah' },
    { label: 'Umm Al Quwain (أم القيوين)', value: 'Umm Al Quwain' }
  ];

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 flex items-center justify-between z-10 shrink-0">
      {/* View Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
          {currentViewTitle}
        </h1>
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
          <Globe className="w-3.5 h-3.5 text-emerald-500" />
          <span>UAE Commercial Registry</span>
        </div>
      </div>

      {/* Center Controls: Global Search & Emirate Quick Switcher */}
      <div className="flex items-center gap-3 max-w-xl w-full mx-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search UAE trade name, phone, trade license, or area..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
          />
        </div>

        {/* Emirate Quick Dropdown */}
        <div className="relative shrink-0">
          <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200">
            <MapPin className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
            <select
              value={selectedEmirate}
              onChange={(e) => onEmirateChange(e.target.value)}
              className="bg-transparent text-xs font-medium text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
            >
              {emirates.map((em) => (
                <option key={em.value} value={em.value} className="bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                  {em.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* AI Tracer Shortcut */}
        {onOpenTracer && (
          <button
            onClick={onOpenTracer}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition shadow-xs cursor-pointer"
            title="Trace Business via Maps + Search Grounding"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span>AI Tracer</span>
          </button>
        )}

        {/* Google Maps Shortcut */}
        {onOpenGoogleMap && (
          <button
            onClick={onOpenGoogleMap}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800 text-xs font-semibold hover:bg-cyan-100 dark:hover:bg-cyan-900/50 transition shadow-xs cursor-pointer"
            title="Open Interactive Google Map"
          >
            <Navigation className="w-3.5 h-3.5 text-cyan-500" />
            <span>Google Map</span>
          </button>
        )}

        {/* Cloud & Disk Storage Button */}
        {onOpenStorageModal && (
          <button
            onClick={onOpenStorageModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-semibold hover:bg-emerald-100 dark:hover:bg-emerald-900/50 transition shadow-xs cursor-pointer"
            title="Database & Storage Status"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <Database className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span className="hidden md:inline">Storage: Active</span>
          </button>
        )}

        {/* Daily Web Search Quick Button */}
        {onOpenDailySearch && (
          <button
            onClick={onOpenDailySearch}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition shadow-xs cursor-pointer"
            title="Daily Automated Web Discovery"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden sm:inline">Daily Search</span>
          </button>
        )}

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh Data"
          className="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-emerald-500' : ''}`} />
        </button>

        {/* Master Architecture & PRD Specs Button */}
        <button
          onClick={onOpenSpecsModal}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 text-xs font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/50 transition shadow-sm"
        >
          <BookOpen className="w-3.5 h-3.5 text-blue-500" />
          <span className="hidden sm:inline">System Specs</span>
        </button>

        {/* User Profile Pill */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-800">
          <div className="w-8 h-8 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-xs shadow-sm">
            TA
          </div>
          <div className="hidden md:block text-left">
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">Tariq Al Hashemi</div>
            <div className="text-[10px] text-slate-500 dark:text-slate-400">Sales Director • Admin</div>
          </div>
        </div>
      </div>
    </header>
  );
};

