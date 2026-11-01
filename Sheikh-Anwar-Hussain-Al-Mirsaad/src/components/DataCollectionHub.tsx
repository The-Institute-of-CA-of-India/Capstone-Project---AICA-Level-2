import React, { useState } from 'react';
import { 
  DownloadCloud, 
  Database, 
  MapPin, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Play, 
  Clock, 
  Calendar, 
  ShieldCheck, 
  Terminal, 
  FileText,
  Sliders,
  Sparkles,
  Flame,
  Navigation,
  ExternalLink,
  Phone,
  MessageCircle,
  Mail,
  UserCheck,
  Building
} from 'lucide-react';
import { CollectionJob, Emirate, DailySearchConfig, DailySearchRun, HardSearchResult } from '../types/index.ts';
import { runCollectionJob, runHardSearch } from '../services/api.ts';
import { DailySearchCenter } from './DailySearchCenter.tsx';

interface DataCollectionHubProps {
  jobs: CollectionJob[];
  onJobCompleted: () => void;
  categories: { nameEn: string }[];
  dailyConfig: DailySearchConfig;
  dailyRuns: DailySearchRun[];
  initialTab?: 'daily' | 'targeted' | 'hard_search';
}

export const DataCollectionHub: React.FC<DataCollectionHubProps> = ({
  jobs,
  onJobCompleted,
  categories,
  dailyConfig,
  dailyRuns,
  initialTab = 'hard_search'
}) => {
  const [activeTab, setActiveTab] = useState<'daily' | 'targeted' | 'hard_search'>(initialTab);
  const [source, setSource] = useState('google_places');
  const [emirate, setEmirate] = useState<Emirate>('Dubai');
  const [area, setArea] = useState('Business Bay');
  const [category, setCategory] = useState('Real estate');
  const [searchQuery, setSearchQuery] = useState('');
  const [maxResults, setMaxResults] = useState(25);
  const [isRunning, setIsRunning] = useState(false);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [selectedJob, setSelectedJob] = useState<CollectionJob | null>(null);

  // Hard Search State (Google Maps + 2GIS)
  const [hardEmirate, setHardEmirate] = useState<string>('all');
  const [hardCategory, setHardCategory] = useState<string>('all');
  const [hardLimit, setHardLimit] = useState<number>(10);
  const [isHardSearching, setIsHardSearching] = useState<boolean>(false);
  const [hardLogs, setHardLogs] = useState<string[]>([]);
  const [hardResult, setHardResult] = useState<HardSearchResult | null>(null);

  const sources = [
    { id: 'google_places', name: 'Google Places API', desc: 'Verified commercial locations, operating hours & coordinates', badge: 'High Precision' },
    { id: '2gis', name: '2GIS UAE Catalog', desc: 'Building entrances, industrial zones (Musaffah, Al Quoz)', badge: 'Industrial Depth' },
    { id: 'ded_registry', name: 'UAE DED / DET Directory', desc: 'Official commercial trade licenses & legal forms', badge: 'Official Open Data' },
    { id: 'uae_yellowpages', name: 'UAE Commercial Directory', desc: 'Local landline phone contacts & corporate emails', badge: 'Public Directory' },
    { id: 'web_crawl', name: 'Permitted Web Crawler', desc: 'Executive profiles, services, and social handles', badge: 'robots.txt safe' }
  ];

  const emirateAreas: Record<string, string[]> = {
    'Dubai': ['Business Bay', 'Downtown Dubai', 'DIFC', 'Al Quoz Industrial', 'Dubai Marina', 'JLT', 'Deira', 'Dubai Silicon Oasis'],
    'Abu Dhabi': ['Al Maryah Island', 'Corniche Area', 'Musaffah Industrial', 'Al Reem Island', 'Khalifa City', 'ICAD'],
    'Sharjah': ['Al Majaz', 'Sharjah Industrial Area', 'Muwaileh', 'SAIF Zone', 'Al Khan'],
    'Ajman': ['Ajman Free Zone', 'Al Nuaimiya', 'Al Jurf Industrial'],
    'Ras Al Khaimah': ['Al Nakheel', 'RAKEZ Economic Zone', 'Al Hamra'],
    'Fujairah': ['Fujairah Free Zone', 'FOIZ Oil Zone', 'Hamad Bin Abdulla St'],
    'Umm Al Quwain': ['UAQ Free Trade Zone', 'Old Town', 'Al Salamah']
  };

  const handleStartJob = async () => {
    setIsRunning(true);
    setLiveLogs([
      `[${new Date().toLocaleTimeString()}] Authenticating with ${source}...`,
      `[${new Date().toLocaleTimeString()}] Target bounds: ${area}, ${emirate}, UAE`,
      `[${new Date().toLocaleTimeString()}] Applying UAE PDPL compliance filters & robots.txt rules...`
    ]);

    try {
      const res = await runCollectionJob({
        sourcePlatform: source,
        emirate,
        area,
        category,
        searchQuery: searchQuery || `${category} in ${area}, ${emirate}`,
        maxResults
      });

      if (res.success && res.job) {
        setLiveLogs(prev => [
          ...prev,
          ...res.job.logs.map((l: string) => `[${new Date().toLocaleTimeString()}] ${l}`),
          `[${new Date().toLocaleTimeString()}] Successfully added ${res.job.newRecordsAdded} businesses, queued ${res.job.duplicatesDetected} duplicates.`
        ]);
        onJobCompleted();
      }
    } catch (err: any) {
      setLiveLogs(prev => [...prev, `[ERROR] Failed to execute job: ${err.message}`]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleExecuteHardSearch = async (override?: { emirate?: string; category?: string; limit?: number }) => {
    setIsHardSearching(true);
    const em = override?.emirate || hardEmirate;
    const cat = override?.category || hardCategory;
    const lim = override?.limit || hardLimit;

    setHardLogs([
      `[${new Date().toLocaleTimeString()} GST] Authenticating with Google Maps Places Platform API...`,
      `[${new Date().toLocaleTimeString()} GST] Connecting to 2GIS UAE Enterprise Catalog for building entrances & Makani IDs...`,
      `[${new Date().toLocaleTimeString()} GST] Query bounds: ${em === 'all' ? 'All 7 UAE Emirates' : em} | Sector: ${cat === 'all' ? 'All Commercial/Industrial' : cat} | Depth: Deep Hard Scan`,
      `[${new Date().toLocaleTimeString()} GST] Querying Google Places delta feeds & 2GIS commercial buildings...`
    ]);

    try {
      const res = await runHardSearch({
        sources: ['google_places', '2gis'],
        emirate: em,
        category: cat,
        depth: 'deep_hard_scan',
        maxResults: lim,
        autoPersist: true
      });

      if (res.success) {
        setHardResult(res);
        setHardLogs(res.logs || []);
        onJobCompleted();
      }
    } catch (err: any) {
      setHardLogs(prev => [...prev, `[ERROR] Hard search failed: ${err.message}`]);
    } finally {
      setIsHardSearching(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Title & Mode Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Data Discovery & Web Search Engine
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
              UAE Real-Time Ingestion
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Autonomously scan the web daily for fresh UAE company databases, contacts, and trade registrations
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold shrink-0 gap-1 flex-wrap">
          <button
            onClick={() => setActiveTab('hard_search')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              activeTab === 'hard_search'
                ? 'bg-amber-600 text-white shadow-xs font-bold'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-amber-300 fill-amber-300" />
            <span>Hard Search (Google Maps + 2GIS)</span>
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-400/20 text-amber-200 font-mono font-bold">DUAL</span>
          </button>

          <button
            onClick={() => setActiveTab('daily')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition ${
              activeTab === 'daily'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            <span>Daily Web Search</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          </button>

          <button
            onClick={() => setActiveTab('targeted')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              activeTab === 'targeted'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <DownloadCloud className="w-3.5 h-3.5" />
            <span>On-Demand Ingestion</span>
          </button>
        </div>
      </div>

      {/* RENDER ACTIVE TAB */}
      {activeTab === 'hard_search' ? (
        <div className="space-y-6">
          {/* Hero Banner */}
          <div className="p-6 rounded-2xl bg-gradient-to-r from-amber-950/60 via-slate-900 to-slate-900 border border-amber-800/40 shadow-lg">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-1 rounded-md bg-amber-500/20 text-amber-300 font-mono text-xs font-bold flex items-center gap-1.5 border border-amber-500/30">
                    <Flame className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    <span>DUAL-SOURCE HARD SEARCH</span>
                  </span>
                  <span className="px-2.5 py-1 rounded-md bg-blue-500/20 text-blue-300 font-mono text-xs font-bold border border-blue-500/30">
                    Google Maps Platform API
                  </span>
                  <span className="px-2.5 py-1 rounded-md bg-teal-500/20 text-teal-300 font-mono text-xs font-bold border border-teal-500/30">
                    2GIS UAE Catalog
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white tracking-tight">
                  Simultaneous Google Maps & 2GIS Deep Entity Extractor
                </h3>
                <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                  Deeply crawls Google Maps Places API and authorized 2GIS UAE Enterprise directories simultaneously. Extracts verified building entrances, industrial plot numbers, Makani coordinates, direct landlines, WhatsApp desks, and C-Suite decision makers.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
                <button
                  onClick={() => handleExecuteHardSearch({ emirate: 'all', category: 'all', limit: 12 })}
                  disabled={isHardSearching}
                  className="px-5 py-3 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-amber-900/30 transition disabled:opacity-50 cursor-pointer"
                >
                  {isHardSearching ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Hard Crawling Maps + 2GIS...</span>
                    </>
                  ) : (
                    <>
                      <Flame className="w-4 h-4 fill-white" />
                      <span>Execute Full UAE Hard Search</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Quick Benchmark presets */}
            <div className="mt-5 pt-4 border-t border-amber-900/30 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold text-amber-300/80 mr-1">Quick Scans:</span>
              <button
                onClick={() => handleExecuteHardSearch({ emirate: 'Dubai', category: 'Construction and contracting', limit: 6 })}
                disabled={isHardSearching}
                className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-[11px] text-slate-200 transition cursor-pointer"
              >
                Dubai Industrial & Contracting (Al Quoz)
              </button>
              <button
                onClick={() => handleExecuteHardSearch({ emirate: 'Abu Dhabi', category: 'Logistics and transport', limit: 6 })}
                disabled={isHardSearching}
                className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-[11px] text-slate-200 transition cursor-pointer"
              >
                Abu Dhabi Logistics Hubs (Musaffah & ICAD)
              </button>
              <button
                onClick={() => handleExecuteHardSearch({ emirate: 'Sharjah', category: 'Manufacturing and factories', limit: 6 })}
                disabled={isHardSearching}
                className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-[11px] text-slate-200 transition cursor-pointer"
              >
                Sharjah Manufacturing & SAIF Zone
              </button>
            </div>
          </div>

          {/* Interactive Parameters Form */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Target Emirate
              </label>
              <select
                value={hardEmirate}
                onChange={(e) => setHardEmirate(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              >
                <option value="all">All 7 UAE Emirates</option>
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
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Industry Sector
              </label>
              <select
                value={hardCategory}
                onChange={(e) => setHardCategory(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              >
                <option value="all">All Sectors</option>
                {categories.map(c => (
                  <option key={c.nameEn} value={c.nameEn}>{c.nameEn}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Extraction Depth
              </label>
              <select
                disabled
                className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 opacity-90"
              >
                <option>Deep Hard Scan (2GIS Entrances + Makani)</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={() => handleExecuteHardSearch()}
                disabled={isHardSearching}
                className="w-full py-2 px-4 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition disabled:opacity-50 cursor-pointer"
              >
                {isHardSearching ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-white" />}
                <span>Launch Search</span>
              </button>
            </div>
          </div>

          {/* Live Progress Terminal */}
          {(isHardSearching || hardLogs.length > 0) && (
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 font-mono text-xs shadow-inner">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800 text-slate-400">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-amber-400" />
                  <span className="font-semibold text-slate-200">Google Maps + 2GIS Hard Search Console</span>
                </div>
                {isHardSearching && (
                  <span className="flex items-center gap-1.5 text-amber-400 text-[11px] animate-pulse">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>Ingesting records...</span>
                  </span>
                )}
              </div>
              <div className="max-h-52 overflow-y-auto space-y-1.5 text-[11px]">
                {hardLogs.map((log, idx) => (
                  <div key={idx} className={log.includes('ERROR') ? 'text-rose-400' : log.includes('Extracted') || log.includes('COMPLETED') ? 'text-emerald-400 font-semibold' : 'text-slate-300'}>
                    {log}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Hard Search Results */}
          {hardResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[10px] text-slate-400 block uppercase">Scanned</span>
                  <span className="text-xl font-bold font-mono text-white">{hardResult.totalRecordsScanned}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900 border border-emerald-900/40 text-center">
                  <span className="text-[10px] text-emerald-400 block uppercase">Added to DB</span>
                  <span className="text-xl font-bold font-mono text-emerald-400">+{hardResult.newBusinessesAdded}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[10px] text-slate-400 block uppercase">Direct Emails</span>
                  <span className="text-xl font-bold font-mono text-blue-400">+{hardResult.contactsExtracted.directEmails}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[10px] text-slate-400 block uppercase">Landlines</span>
                  <span className="text-xl font-bold font-mono text-slate-200">+{hardResult.contactsExtracted.landlines}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[10px] text-slate-400 block uppercase">WhatsApps</span>
                  <span className="text-xl font-bold font-mono text-emerald-400">+{hardResult.contactsExtracted.whatsapps}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-900 border border-amber-900/40 text-center">
                  <span className="text-[10px] text-amber-400 block uppercase">Decision Makers</span>
                  <span className="text-xl font-bold font-mono text-amber-400">+{hardResult.contactsExtracted.decisionMakers}</span>
                </div>
              </div>

              {/* Business Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {hardResult.businesses.map((biz) => (
                  <div key={biz.id} className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                            MAPS
                          </span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                            2GIS
                          </span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-emerald-500/10 text-emerald-600 font-mono">
                            {biz.qualityScore}%
                          </span>
                        </div>
                        <h4 className="font-bold text-sm text-slate-900 dark:text-white mt-1.5">{biz.nameEn}</h4>
                        {biz.nameAr && <p className="text-[10px] text-slate-400 font-arabic" dir="rtl">{biz.nameAr}</p>}
                      </div>
                    </div>

                    <div className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                        <span className="truncate">{biz.area}, {biz.emirate}</span>
                      </div>
                      {biz.buildingEntrance && (
                        <div className="p-1.5 rounded bg-teal-950/20 border border-teal-800/30 text-[10px] text-teal-300 flex items-center gap-1">
                          <span className="font-semibold text-teal-400">2GIS Entrance:</span>
                          <span className="truncate">{biz.buildingEntrance}</span>
                        </div>
                      )}
                      {biz.plotNumber && (
                        <div className="p-1.5 rounded bg-blue-950/20 border border-blue-800/30 text-[10px] text-blue-300 flex items-center gap-1">
                          <span className="font-semibold text-blue-400">Plot/Makani:</span>
                          <span className="truncate">{biz.plotNumber}</span>
                        </div>
                      )}
                    </div>

                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        {biz.primaryPhone && (
                          <a href={`tel:${biz.primaryPhone}`} className="text-slate-500 hover:text-emerald-500" title={biz.primaryPhone}>
                            <Phone className="w-3.5 h-3.5" />
                          </a>
                        )}
                        {biz.whatsappNumber && (
                          <a href={`https://wa.me/${biz.whatsappNumber.replace(/[^\d]/g, '')}`} target="_blank" rel="noreferrer" className="text-emerald-500 hover:text-emerald-400" title={biz.whatsappNumber}>
                            <MessageCircle className="w-3.5 h-3.5" />
                          </a>
                        )}
                        {biz.twoGisListingUrl && (
                          <a href={biz.twoGisListingUrl} target="_blank" rel="noreferrer" className="text-teal-400 hover:text-teal-300 font-semibold text-[10px] flex items-center gap-0.5">
                            <span>2GIS</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                        {biz.googleMapsListingUrl && (
                          <a href={biz.googleMapsListingUrl} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 font-semibold text-[10px] flex items-center gap-0.5">
                            <span>Maps</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </div>
                      <span className="text-[10px] text-emerald-500 font-semibold">✓ Stored</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : activeTab === 'daily' ? (
        <DailySearchCenter
          config={dailyConfig}
          runs={dailyRuns}
          onRefresh={onJobCompleted}
          categories={categories}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: Ingestion Job Launcher */}
        <div className="lg:col-span-2 space-y-5">
          
          {/* Source Selection Cards */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              1. Select Authorized Data Source
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {sources.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setSource(s.id)}
                  className={`p-3.5 rounded-xl border text-xs cursor-pointer transition flex flex-col justify-between ${
                    source === s.id
                      ? 'bg-blue-50/60 dark:bg-blue-950/30 border-blue-500 text-blue-950 dark:text-blue-100 shadow-xs'
                      : 'bg-slate-50/50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-slate-400'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-900 dark:text-white">{s.name}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold">
                        {s.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
                      {s.desc}
                    </p>
                  </div>
                  <div className="mt-2 text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                    ✓ Permitted & Licensed
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Location & Category Parameters */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              2. Target Geographical & Sector Parameters
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Emirate */}
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Target Emirate
                </label>
                <select
                  value={emirate}
                  onChange={(e) => {
                    const em = e.target.value as Emirate;
                    setEmirate(em);
                    setArea(emirateAreas[em]?.[0] || 'Central Area');
                  }}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  <option value="Dubai">Dubai (دبي)</option>
                  <option value="Abu Dhabi">Abu Dhabi (أبوظبي)</option>
                  <option value="Sharjah">Sharjah (الشارقة)</option>
                  <option value="Ajman">Ajman (عجمان)</option>
                  <option value="Ras Al Khaimah">Ras Al Khaimah (رأس الخيمة)</option>
                  <option value="Fujairah">Fujairah (الفجيرة)</option>
                  <option value="Umm Al Quwain">Umm Al Quwain (أم القيوين)</option>
                </select>
              </div>

              {/* Commercial Area */}
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Commercial Zone / District
                </label>
                <select
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  {(emirateAreas[emirate] || []).map((ar) => (
                    <option key={ar} value={ar}>{ar}</option>
                  ))}
                </select>
              </div>

              {/* Category */}
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Business Industry Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none"
                >
                  {categories.map((c) => (
                    <option key={c.nameEn} value={c.nameEn}>{c.nameEn}</option>
                  ))}
                </select>
              </div>

              {/* Max Results */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Max Permitted Limit
                  </label>
                  <span className="text-xs font-mono font-bold text-slate-900 dark:text-white">
                    {maxResults} records
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="5"
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-full accent-blue-600 mt-2"
                />
              </div>
            </div>

            {/* Keyword Search */}
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Custom Keyword Filter (Optional)
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g. Fitout Contractors, ISO Certified Garages, Freight Forwarders..."
                className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
              />
            </div>

            {/* Launch Trigger */}
            <div className="pt-2 flex items-center justify-between border-t border-slate-100 dark:border-slate-800">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                <span>Respects robots.txt, 30-day Google caching policy & UAE PDPL</span>
              </div>

              <button
                onClick={handleStartJob}
                disabled={isRunning}
                className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center gap-2 shadow-md transition disabled:opacity-50 cursor-pointer"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Collecting Data...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    <span>Run Data Discovery</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Live Ingestion Log Console */}
          <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800 text-slate-300 font-mono text-xs shadow-inner space-y-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-[11px] text-slate-400">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span className="font-bold text-slate-200">Execution Log Console</span>
              </div>
              <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Active</span>
              </span>
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1.5 text-[11px] text-emerald-400/90 scrollbar-thin scrollbar-thumb-slate-800">
              {liveLogs.length > 0 ? (
                liveLogs.map((log, idx) => <div key={idx}>{log}</div>)
              ) : (
                <div className="text-slate-600">
                  Ready. Click "Run Data Discovery" to execute live collection.
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Right Col: Historical Jobs & Scheduled Sync */}
        <div className="space-y-5">
          
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-500" />
                <span>Job History</span>
              </h3>
              <span className="text-[10px] text-slate-400 font-mono">{jobs.length} jobs</span>
            </div>

            <div className="space-y-3">
              {jobs.map((j) => (
                <div
                  key={j.id}
                  onClick={() => setSelectedJob(j)}
                  className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 hover:border-blue-500/40 transition cursor-pointer text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 dark:text-white truncate">
                      {j.category}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold">
                      Completed
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                    <MapPin className="w-3 h-3 text-slate-400" />
                    <span>{j.area || j.emirate}</span>
                    <span>•</span>
                    <span className="uppercase font-mono text-[9px]">{j.sourcePlatform.replace('_', ' ')}</span>
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-700/40 text-[10px] text-slate-500">
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">+{j.newRecordsAdded} Added</span>
                    <span>{j.duplicatesDetected} Duplicates</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Automated Schedule Card */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-950/40 to-slate-900 border border-indigo-900/40 shadow-sm space-y-3 text-xs">
            <div className="flex items-center gap-2 text-indigo-400 font-bold uppercase tracking-wider text-[10px]">
              <Calendar className="w-3.5 h-3.5" />
              <span>Recurring Cron Schedule</span>
            </div>
            <h4 className="font-bold text-white text-sm">Automated 30-Day Cache Sync</h4>
            <p className="text-slate-300 text-[11px] leading-relaxed">
              Google Places API records are scheduled for automated re-verification every 30 days to adhere strictly to Google terms and maintain fresh telephone and operating hours data.
            </p>
            <div className="pt-1 flex items-center justify-between text-[11px]">
              <span className="text-emerald-400 font-semibold">Cron: Every Sunday 02:00 UTC</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">Active</span>
            </div>
          </div>

        </div>

      </div>
      )}

    </div>
  );
};
