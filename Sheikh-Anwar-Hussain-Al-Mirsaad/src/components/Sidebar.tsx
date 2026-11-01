import React from 'react';
import {
  LayoutDashboard,
  Search,
  DownloadCloud,
  FolderTree,
  MapPin,
  Users,
  Kanban,
  Contact,
  CalendarCheck2,
  BarChart3,
  ArrowUpDown,
  ShieldCheck,
  Sliders,
  BookOpen,
  ChevronRight,
  Sparkles,
  Building2,
  CheckCircle2,
  Navigation,
  Database
} from 'lucide-react';

export type NavView = 
  | 'overview'
  | 'tracer'
  | 'explorer'
  | 'google_map'
  | 'daily_search'
  | 'collection'
  | 'categories'
  | 'locations'
  | 'leads'
  | 'pipeline'
  | 'contacts'
  | 'tasks'
  | 'analytics'
  | 'import_export'
  | 'team'
  | 'settings';

interface SidebarProps {
  currentView: NavView;
  onSelectView: (view: NavView) => void;
  onOpenSpecsModal: () => void;
  onOpenStorageModal?: () => void;
  activeDuplicatesCount: number;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeColor?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  onOpenSpecsModal,
  onOpenStorageModal,
  activeDuplicatesCount
}) => {
  const navSections: NavSection[] = [
    {
      title: 'INTELLIGENCE & DATA',
      items: [
        { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
        { id: 'tracer', label: 'AI Business Tracer', icon: Sparkles, badge: 'Maps + Search', badgeColor: 'bg-indigo-500/20 text-indigo-300 font-semibold' },
        { id: 'explorer', label: 'Business Explorer', icon: Search, badge: '50k+ Live' },
        { id: 'google_map', label: 'Google Maps Geospatial', icon: Navigation, badge: 'Live API', badgeColor: 'bg-cyan-500/20 text-cyan-300 font-semibold' },
        { id: 'daily_search', label: 'Daily Web Search & Sync', icon: CheckCircle2, badge: 'Every 24h', badgeColor: 'bg-emerald-500/20 text-emerald-300 font-semibold' },
        { id: 'collection', label: 'Data Collection Hub', icon: DownloadCloud },
        { id: 'categories', label: 'Business Categories', icon: FolderTree },
        { id: 'locations', label: 'UAE Location Explorer', icon: MapPin, badge: '7 Emirates' },
      ]
    },
    {
      title: 'SALES & CRM PIPELINE',
      items: [
        { id: 'leads', label: 'Lead Management', icon: Users },
        { id: 'pipeline', label: 'Sales Pipeline (Kanban)', icon: Kanban, badge: 'AED Funnel' },
        { id: 'contacts', label: 'Contacts & Customers', icon: Contact },
        { id: 'tasks', label: 'Tasks & Follow-ups', icon: CalendarCheck2 },
      ]
    },
    {
      title: 'REPORTING & GOVERNANCE',
      items: [
        { id: 'analytics', label: 'Analytics & Reports', icon: BarChart3 },
        { id: 'import_export', label: 'Import / Export Hub', icon: ArrowUpDown },
        { id: 'team', label: 'Team Management', icon: ShieldCheck },
        { id: 'settings', label: 'Settings & Governance', icon: Sliders, badge: activeDuplicatesCount > 0 ? `${activeDuplicatesCount} Alerts` : undefined, badgeColor: 'bg-amber-500/20 text-amber-300' },
      ]
    }
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-screen border-r border-slate-800 select-none shrink-0">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 via-teal-600 to-cyan-700 flex items-center justify-center text-white shadow-lg shadow-emerald-900/30">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-white text-base tracking-tight">Al-Mirsaad</span>
              <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold px-1.5 py-0.5 rounded border border-emerald-500/30">UAE</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">B2B Intelligence & CRM</p>
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6 scrollbar-thin scrollbar-thumb-slate-800">
        {navSections.map((section, idx) => (
          <div key={idx}>
            <div className="px-3 mb-2 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
              {section.title}
            </div>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = currentView === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelectView(item.id as NavView)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all group ${
                      isActive
                        ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 shadow-sm'
                        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <Icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ml-1.5 ${
                        item.badgeColor || (isActive ? 'bg-emerald-500/30 text-emerald-300' : 'bg-slate-800 text-slate-400')
                      }`}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Storage & Architecture Trigger Cards */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/60 space-y-2">
        {onOpenStorageModal && (
          <button
            onClick={onOpenStorageModal}
            className="w-full flex items-center justify-between p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/40 hover:border-emerald-600/60 text-left transition group shadow-sm"
          >
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                <Database className="w-3.5 h-3.5" />
              </div>
              <div>
                <div className="text-[11px] font-semibold text-emerald-200 flex items-center gap-1">
                  <span>Cloud & Disk Storage</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                </div>
                <p className="text-[9px] text-slate-400">All Extractions Stored</p>
              </div>
            </div>
            <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-emerald-400 transition" />
          </button>
        )}

        <button
          onClick={onOpenSpecsModal}
          className="w-full flex items-center justify-between p-2 rounded-lg bg-gradient-to-r from-blue-950/60 to-indigo-950/60 border border-blue-800/40 hover:border-blue-700/60 text-left transition group shadow-sm"
        >
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <BookOpen className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[11px] font-semibold text-slate-100 flex items-center gap-1">
                <span>Architecture & PRD</span>
                <Sparkles className="w-2.5 h-2.5 text-cyan-400" />
              </div>
              <p className="text-[9px] text-slate-400">Full 10-point Master Specs</p>
            </div>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-blue-400 transition" />
        </button>

        {/* UAE Compliance Footnote */}
        <div className="mt-2.5 flex items-center justify-between px-1 text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>UAE PDPL Compliant</span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">v2.4.0</span>
        </div>
      </div>
    </aside>
  );
};
