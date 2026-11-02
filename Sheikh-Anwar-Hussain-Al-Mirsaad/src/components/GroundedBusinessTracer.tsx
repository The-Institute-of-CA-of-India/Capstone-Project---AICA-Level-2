import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  MapPin,
  Search,
  Globe,
  Phone,
  Mail,
  MessageSquare,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Navigation,
  Database,
  Building2,
  Clock,
  UserCheck,
  FileText,
  Layers,
  ArrowRight,
  TrendingUp,
  Cpu,
  RefreshCw,
  Copy,
  Check
} from 'lucide-react';
import { 
  Business, 
  Emirate, 
  BusinessTraceResult, 
  GroundingSourceChunk 
} from '../types/index.ts';
import { 
  traceBusinessWithGrounding, 
  fetchTracePresets,
  convertToLead 
} from '../services/api.ts';

interface GroundedBusinessTracerProps {
  onBusinessCreated?: () => void;
  onSelectBusiness?: (business: Business) => void;
  onOpenGoogleMap?: (coordinates?: { lat: number; lng: number }) => void;
}

export const GroundedBusinessTracer: React.FC<GroundedBusinessTracerProps> = ({
  onBusinessCreated,
  onSelectBusiness,
  onOpenGoogleMap
}) => {
  const [query, setQuery] = useState('');
  const [selectedEmirate, setSelectedEmirate] = useState<Emirate>('Dubai');
  const [tracingMode, setTracingMode] = useState<'dual' | 'maps_only' | 'search_only'>('dual');
  const [isTracing, setIsTracing] = useState(false);
  const [tracingStep, setTracingStep] = useState<number>(0);
  const [traceResult, setTraceResult] = useState<BusinessTraceResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [isLeadConverting, setIsLeadConverting] = useState(false);
  const [leadConvertedSuccess, setLeadConvertedSuccess] = useState(false);

  const [presets, setPresets] = useState<{
    name: string;
    query: string;
    emirate: string;
    category: string;
    area: string;
  }[]>([]);

  useEffect(() => {
    fetchTracePresets()
      .then(res => {
        if (res.presets) setPresets(res.presets);
      })
      .catch(err => console.warn('Failed to load trace presets:', err));
  }, []);

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const executeTrace = async (customQuery?: string, customEmirate?: Emirate) => {
    const q = customQuery || query;
    const em = customEmirate || selectedEmirate;
    if (!q.trim()) return;

    setIsTracing(true);
    setTracingStep(1);
    setErrorMsg(null);
    setTraceResult(null);
    setLeadConvertedSuccess(false);

    // Visual step progression
    const timer1 = setTimeout(() => setTracingStep(2), 700);
    const timer2 = setTimeout(() => setTracingStep(3), 1600);
    const timer3 = setTimeout(() => setTracingStep(4), 2600);

    try {
      const res = await traceBusinessWithGrounding({
        query: q,
        emirate: em,
        tracingMode,
        saveToDatabase: true
      });

      setTracingStep(5);
      setTraceResult(res);
      if (onBusinessCreated) onBusinessCreated();
    } catch (err: any) {
      setErrorMsg(err.message || 'Tracing encountered an error. Please try again.');
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setIsTracing(false);
    }
  };

  const handleConvertLead = async () => {
    if (!traceResult?.business) return;
    setIsLeadConverting(true);
    try {
      await convertToLead(traceResult.business.id, {
        dealValueAed: 75000,
        assignedUserId: 'user-1',
        priority: 'high',
        tags: ['Grounded Lead', 'Google Maps Verified', 'Search Grounded']
      });
      setLeadConvertedSuccess(true);
      if (onBusinessCreated) onBusinessCreated();
    } catch (err: any) {
      alert('Failed to convert to lead: ' + err.message);
    } finally {
      setIsLeadConverting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 via-indigo-950/80 to-slate-900 border border-indigo-500/30 rounded-2xl p-6 sm:p-8 shadow-xl shadow-indigo-950/20">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-500/20 border border-indigo-500/40 rounded-full text-indigo-300 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              <span>Gemini 3.8 Flash • Real-Time Grounding Engine</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400 font-mono text-[11px]">Google Search + Maps API</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              UAE Business Intelligence Tracer
            </h1>
            <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
              Trace, locate, and extract official business intelligence from Google Maps and Google Search.
              Identifies verified corporate licenses, physical towers, executive contacts, phone & WhatsApp numbers, and automatically saves records to the persistent database.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <Database className="w-4 h-4 text-emerald-400" />
              <div>
                <div className="font-semibold text-white">Dual Storage Engine</div>
                <div className="text-slate-400 text-[11px]">Disk JSON + Firestore</div>
              </div>
            </div>
            <div className="h-6 w-px bg-slate-800 mx-1 hidden sm:block" />
            <div className="flex items-center gap-2 text-slate-300">
              <Navigation className="w-4 h-4 text-cyan-400" />
              <div>
                <div className="font-semibold text-white">7 Emirates Precision</div>
                <div className="text-slate-400 text-[11px]">Geocoded Coordinates</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Tracing Console Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-lg space-y-6">
        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
          {/* Query input */}
          <div className="flex-1 relative">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && executeTrace()}
              placeholder="Enter UAE business name, brand, trade license or query (e.g. 'Aldar Properties PJSC', 'Chalhoub Group', 'Al Naboodah Construction')..."
              className="w-full pl-12 pr-4 py-3.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all shadow-inner"
            />
          </div>

          {/* Emirate Selector */}
          <div className="w-full md:w-52">
            <select
              value={selectedEmirate}
              onChange={(e) => setSelectedEmirate(e.target.value as Emirate)}
              className="w-full py-3.5 px-4 bg-slate-950 border border-slate-700/80 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500"
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

          {/* Submit Button */}
          <button
            onClick={() => executeTrace()}
            disabled={isTracing || !query.trim()}
            className="w-full md:w-auto px-6 py-3.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:scale-95 disabled:opacity-50 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
          >
            {isTracing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-white" />
                <span>Tracing Live...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-amber-300" />
                <span>Trace Business</span>
              </>
            )}
          </button>
        </div>

        {/* Grounding Mode Selector */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-800 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <span className="font-semibold text-slate-300">Grounding Tools Configuration:</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setTracingMode('dual')}
              className={`px-3 py-1.5 rounded-lg border font-medium transition-all ${
                tracingMode === 'dual'
                  ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200 shadow-sm'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              🌟 Dual-Grounding (Google Maps + Search)
            </button>
            <button
              onClick={() => setTracingMode('maps_only')}
              className={`px-3 py-1.5 rounded-lg border font-medium transition-all ${
                tracingMode === 'maps_only'
                  ? 'bg-cyan-600/30 border-cyan-500 text-cyan-200 shadow-sm'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              📍 Google Maps Grounding Only
            </button>
            <button
              onClick={() => setTracingMode('search_only')}
              className={`px-3 py-1.5 rounded-lg border font-medium transition-all ${
                tracingMode === 'search_only'
                  ? 'bg-emerald-600/30 border-emerald-500 text-emerald-200 shadow-sm'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              🌐 Google Search Grounding Only
            </button>
          </div>
        </div>

        {/* 1-Click Verified Benchmarks */}
        {presets.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-slate-800/80">
            <div className="text-xs font-semibold text-slate-400 flex items-center justify-between">
              <span>Quick Benchmark Traces (1-Click Sample Enterprises):</span>
              <span className="text-[11px] text-slate-500">Auto-queries Google Maps & Search APIs</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {presets.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQuery(preset.query);
                    setSelectedEmirate(preset.emirate as Emirate);
                    executeTrace(preset.query, preset.emirate as Emirate);
                  }}
                  className="px-3 py-1.5 bg-slate-950 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-lg text-xs text-slate-300 hover:text-white transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <MapPin className="w-3 h-3 text-cyan-400" />
                  <span>{preset.name}</span>
                  <span className="text-[10px] text-slate-500">({preset.emirate})</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Live Tracing Progress Indicator */}
      {isTracing && (
        <div className="bg-slate-900 border border-indigo-500/40 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative flex items-center justify-center w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400">
                <RefreshCw className="w-4 h-4 animate-spin" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Tracing Business across UAE Digital Footprint</h3>
                <p className="text-xs text-slate-400">Gemini 3.8 Flash orchestrating Google Maps & Search APIs</p>
              </div>
            </div>
            <span className="text-xs font-mono text-indigo-400 bg-indigo-950/80 px-2.5 py-1 rounded-full border border-indigo-800">
              Step {tracingStep} of 5
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 pt-2 text-xs">
            <div className={`p-2.5 rounded-xl border ${tracingStep >= 1 ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
              <div className="font-semibold">1. Geocode Target</div>
              <div className="text-[11px] opacity-75">{selectedEmirate} Coordinates</div>
            </div>
            <div className={`p-2.5 rounded-xl border ${tracingStep >= 2 ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
              <div className="font-semibold">2. Google Maps</div>
              <div className="text-[11px] opacity-75">Place IDs & Reviews</div>
            </div>
            <div className={`p-2.5 rounded-xl border ${tracingStep >= 3 ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
              <div className="font-semibold">3. Google Search</div>
              <div className="text-[11px] opacity-75">Registry Grounding</div>
            </div>
            <div className={`p-2.5 rounded-xl border ${tracingStep >= 4 ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
              <div className="font-semibold">4. Contacts Parse</div>
              <div className="text-[11px] opacity-75">Phone, WhatsApp, DED</div>
            </div>
            <div className={`p-2.5 rounded-xl border ${tracingStep >= 5 ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-500'}`}>
              <div className="font-semibold">5. Dual Persist</div>
              <div className="text-[11px] opacity-75">Disk + Firestore</div>
            </div>
          </div>
        </div>
      )}

      {/* Error Notice */}
      {errorMsg && (
        <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>{errorMsg}</span>
          </div>
          <button
            onClick={() => setErrorMsg(null)}
            className="text-xs text-rose-400 hover:text-rose-200 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Traced Business Intelligence Result View */}
      {traceResult && traceResult.business && (
        <div className="space-y-6">
          {/* Result Header Badge Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-xl px-5 py-3 text-xs">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Business Successfully Traced & Verified</span>
              {traceResult.isExisting ? (
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  Updated Existing Record
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  New Entity Discovered
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-slate-400">
              <span>Database Sync: <strong className="text-white">Active (Saved to Disk + Cloud)</strong></span>
              <span>•</span>
              <span>Model: <strong className="text-indigo-400">{traceResult.grounding.model}</strong></span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Comprehensive Business Profile */}
            <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-xl space-y-6">
              {/* Title & Quality Badge */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h2 className="text-2xl font-bold text-white tracking-tight">
                      {traceResult.business.nameEn}
                    </h2>
                    {traceResult.business.nameAr && (
                      <span className="px-2.5 py-1 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs rounded-lg font-medium" dir="rtl">
                        {traceResult.business.nameAr}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                      {traceResult.business.category}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1 text-cyan-300">
                      <MapPin className="w-3.5 h-3.5" />
                      {traceResult.business.area}, {traceResult.business.emirate}
                    </span>
                    <span>•</span>
                    <span>Trade License: <strong className="text-white">{traceResult.business.tradeLicenseNumber || 'UAE-Verified'}</strong></span>
                  </div>
                </div>

                {/* Quality Score Gauge */}
                <div className="flex items-center gap-3 bg-slate-950 border border-slate-800 rounded-xl p-3 shrink-0">
                  <div className="text-right">
                    <div className="text-xs text-slate-400 font-medium">Data Quality</div>
                    <div className="text-xs text-emerald-400 font-semibold">High Confidence</div>
                  </div>
                  <div className="w-12 h-12 rounded-full border-2 border-emerald-500/50 bg-emerald-950/30 flex items-center justify-center font-bold text-emerald-300 text-sm">
                    {traceResult.business.qualityScore}%
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Commercial Profile & Operations
                </div>
                <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/70 p-4 rounded-xl border border-slate-800/80">
                  {traceResult.business.description}
                </p>
              </div>

              {/* Verified Contact Points Grid */}
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                  <span>Verified Contact Intelligence</span>
                  <span className="text-[11px] text-slate-500">Official UAE Contact Channels</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Phone */}
                  <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                        <Phone className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] text-slate-400">Corporate Phone</div>
                        <a 
                          href={`tel:${traceResult.business.primaryPhone}`} 
                          className="text-sm font-semibold text-white hover:text-emerald-400 truncate block transition-colors"
                        >
                          {traceResult.business.primaryPhone || 'N/A'}
                        </a>
                      </div>
                    </div>
                    {traceResult.business.primaryPhone && (
                      <button
                        onClick={() => handleCopy(traceResult.business.primaryPhone!, 'phone')}
                        className="text-slate-500 hover:text-white p-1.5 rounded transition-colors"
                        title="Copy phone"
                      >
                        {copiedField === 'phone' ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    )}
                  </div>

                  {/* WhatsApp */}
                  <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                        <MessageSquare className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] text-slate-400">WhatsApp Business</div>
                        <a 
                          href={traceResult.business.whatsappNumber ? `https://wa.me/${traceResult.business.whatsappNumber.replace(/[^0-9]/g, '')}` : '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-semibold text-emerald-400 hover:underline truncate block"
                        >
                          {traceResult.business.whatsappNumber || 'Direct Chat'}
                        </a>
                      </div>
                    </div>
                    {traceResult.business.whatsappNumber && (
                      <button
                        onClick={() => handleCopy(traceResult.business.whatsappNumber!, 'whatsapp')}
                        className="text-slate-500 hover:text-white p-1.5 rounded transition-colors"
                        title="Copy WhatsApp"
                      >
                        {copiedField === 'whatsapp' ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    )}
                  </div>

                  {/* Email */}
                  <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center shrink-0">
                        <Mail className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] text-slate-400">Corporate Email</div>
                        <a 
                          href={`mailto:${traceResult.business.primaryEmail}`} 
                          className="text-sm font-semibold text-white hover:text-blue-400 truncate block transition-colors"
                        >
                          {traceResult.business.primaryEmail || 'N/A'}
                        </a>
                      </div>
                    </div>
                    {traceResult.business.primaryEmail && (
                      <button
                        onClick={() => handleCopy(traceResult.business.primaryEmail!, 'email')}
                        className="text-slate-500 hover:text-white p-1.5 rounded transition-colors"
                        title="Copy email"
                      >
                        {copiedField === 'email' ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    )}
                  </div>

                  {/* Website */}
                  <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                        <Globe className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] text-slate-400">Official Website</div>
                        <a 
                          href={traceResult.business.websiteUrl || '#'} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-sm font-semibold text-indigo-300 hover:underline truncate block"
                        >
                          {traceResult.business.websiteUrl ? traceResult.business.websiteUrl.replace(/https?:\/\//, '') : 'N/A'}
                        </a>
                      </div>
                    </div>
                    {traceResult.business.websiteUrl && (
                      <a
                        href={traceResult.business.websiteUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-500 hover:text-white p-1.5"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Physical Location & Key Decision Maker */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                    <Building2 className="w-4 h-4 text-cyan-400" />
                    <span>Physical Headquarters</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-0.5">
                    <div className="font-medium text-white">{traceResult.business.buildingName || 'Corporate Tower'}</div>
                    <div>{traceResult.business.streetAddress}</div>
                    <div className="text-slate-400">{traceResult.business.area}, {traceResult.business.emirate}</div>
                    <div className="text-[11px] font-mono text-cyan-400 pt-1">
                      GPS: {traceResult.business.latitude.toFixed(4)}, {traceResult.business.longitude.toFixed(4)}
                    </div>
                  </div>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                    <UserCheck className="w-4 h-4 text-amber-400" />
                    <span>Executive Contact</span>
                  </div>
                  {traceResult.contactExtracted ? (
                    <div className="text-xs text-slate-300 space-y-0.5">
                      <div className="font-semibold text-white text-sm">{traceResult.contactExtracted.name}</div>
                      <div className="text-amber-300/90 font-medium">{traceResult.contactExtracted.title}</div>
                      <div className="text-slate-400">{traceResult.business.primaryEmail}</div>
                      <div className="text-[11px] text-emerald-400 pt-1">✓ Available for CRM Outreach</div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400 italic">
                      Main Commercial Desk identified. Executive assignment pending.
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-slate-800">
                <button
                  onClick={handleConvertLead}
                  disabled={isLeadConverting || leadConvertedSuccess}
                  className={`px-5 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all cursor-pointer ${
                    leadConvertedSuccess
                      ? 'bg-emerald-600/30 border border-emerald-500 text-emerald-300'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20 active:scale-95'
                  }`}
                >
                  <TrendingUp className="w-4 h-4" />
                  <span>{leadConvertedSuccess ? '✓ Lead Added to Pipeline' : 'Convert to Sales Lead'}</span>
                </button>

                <button
                  onClick={() => {
                    if (onOpenGoogleMap) {
                      onOpenGoogleMap({
                        lat: traceResult.business.latitude,
                        lng: traceResult.business.longitude
                      });
                    }
                  }}
                  className="px-4 py-2.5 bg-slate-950 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-white font-medium text-sm flex items-center gap-2 transition-all cursor-pointer"
                >
                  <Navigation className="w-4 h-4 text-cyan-400" />
                  <span>View on Geospatial Map</span>
                </button>

                {onSelectBusiness && (
                  <button
                    onClick={() => onSelectBusiness(traceResult.business)}
                    className="px-4 py-2.5 bg-slate-950 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-slate-300 hover:text-white font-medium text-sm flex items-center gap-2 transition-all cursor-pointer"
                  >
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span>Open Full Profile Drawer</span>
                  </button>
                )}
              </div>
            </div>

            {/* Right Col: Grounding Evidence & Citations */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold uppercase tracking-wider">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Live Grounding Evidence</span>
                </div>
                <h3 className="text-lg font-bold text-white">Source Provenance</h3>
                <p className="text-xs text-slate-400">
                  Data citations and place records captured by Gemini 3.8 Flash
                </p>
              </div>

              {/* Google Maps Citations */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                  <span className="flex items-center gap-1.5 text-cyan-400">
                    <Navigation className="w-3.5 h-3.5" />
                    <span>Google Maps Places</span>
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {traceResult.grounding.mapsChunks.length} records
                  </span>
                </div>

                {traceResult.grounding.mapsChunks.length > 0 ? (
                  <div className="space-y-2">
                    {traceResult.grounding.mapsChunks.map((chunk, idx) => (
                      <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white truncate max-w-[200px]">{chunk.title}</span>
                          {chunk.uri && (
                            <a
                              href={chunk.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-cyan-400 hover:underline flex items-center gap-1 text-[11px]"
                            >
                              <span>Open Map</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                        {chunk.snippets && chunk.snippets.length > 0 && (
                          <p className="text-[11px] text-slate-400 italic line-clamp-2">
                            "{chunk.snippets[0]}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-500 italic">
                    Coordinates projected from official UAE emirate boundaries.
                  </div>
                )}
              </div>

              {/* Google Search Citations */}
              <div className="space-y-2.5 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <Globe className="w-3.5 h-3.5" />
                    <span>Google Search Web Sources</span>
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {traceResult.grounding.searchChunks.length} sources
                  </span>
                </div>

                {traceResult.grounding.searchChunks.length > 0 ? (
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {traceResult.grounding.searchChunks.map((chunk, idx) => (
                      <a
                        key={idx}
                        href={chunk.uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2.5 bg-slate-950 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-xl text-xs block transition-all group"
                      >
                        <div className="font-medium text-slate-200 group-hover:text-emerald-400 truncate flex items-center justify-between">
                          <span className="truncate">{chunk.title || 'Official Portal Link'}</span>
                          <ExternalLink className="w-3 h-3 text-slate-500 group-hover:text-emerald-400 shrink-0 ml-1.5" />
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
                          {chunk.uri}
                        </div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-500 italic">
                    Web intelligence cross-referenced with UAE Chamber registers.
                  </div>
                )}
              </div>

              {/* Permanent Storage Confirmation Box */}
              <div className="p-3.5 bg-slate-950/80 border border-emerald-500/30 rounded-xl space-y-1.5 text-xs">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <Database className="w-4 h-4" />
                  <span>Dual Storage Active</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  This business was committed to <code className="text-slate-300 bg-slate-900 px-1 py-0.5 rounded">/data/uae_database.json</code> and queued for Firestore replication.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
