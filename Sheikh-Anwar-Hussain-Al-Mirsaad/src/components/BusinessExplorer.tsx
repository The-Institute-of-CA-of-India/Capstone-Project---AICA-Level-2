import React, { useState } from 'react';
import { 
  Search, 
  Filter, 
  MapPin, 
  Phone, 
  Globe, 
  Sparkles, 
  UserPlus, 
  CheckCircle2, 
  ExternalLink, 
  MessageCircle, 
  SlidersHorizontal, 
  Download, 
  Layers, 
  ArrowUpDown,
  CheckSquare,
  Square,
  ShieldCheck,
  Building2,
  List,
  LayoutGrid
} from 'lucide-react';
import { Business, Emirate } from '../types/index.ts';

interface BusinessExplorerProps {
  businesses: Business[];
  onSelectBusiness: (biz: Business) => void;
  onConvertToLead: (biz: Business) => void;
  onEnrichWithAi: (biz: Business) => void;
  categories: { nameEn: string }[];
  selectedEmirate: string;
  onEmirateChange: (em: string) => void;
  onOpenTracer?: () => void;
}

export const BusinessExplorer: React.FC<BusinessExplorerProps> = ({
  businesses,
  onSelectBusiness,
  onConvertToLead,
  onEnrichWithAi,
  categories,
  selectedEmirate,
  onEmirateChange,
  onOpenTracer
}) => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSource, setSelectedSource] = useState('all');
  const [minQualityScore, setMinQualityScore] = useState(0);
  const [hasPhoneOnly, setHasPhoneOnly] = useState(false);
  const [hasWebsiteOnly, setHasWebsiteOnly] = useState(false);
  const [crmStatusFilter, setCrmStatusFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showFiltersDrawer, setShowFiltersDrawer] = useState(false);

  // Filter businesses
  const filtered = businesses.filter(b => {
    if (selectedEmirate !== 'all' && b.emirate !== selectedEmirate) return false;
    if (selectedCategory !== 'all' && b.category !== selectedCategory) return false;
    if (selectedSource !== 'all' && b.sourcePlatform !== selectedSource) return false;
    if (b.qualityScore < minQualityScore) return false;
    if (hasPhoneOnly && !b.primaryPhone && !b.whatsappNumber) return false;
    if (hasWebsiteOnly && !b.websiteUrl) return false;
    if (crmStatusFilter !== 'all' && b.crmLeadStatus !== crmStatusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      const match = 
        b.nameEn.toLowerCase().includes(q) ||
        (b.nameAr && b.nameAr.toLowerCase().includes(q)) ||
        b.area.toLowerCase().includes(q) ||
        b.city.toLowerCase().includes(q) ||
        b.category.toLowerCase().includes(q) ||
        b.description.toLowerCase().includes(q) ||
        (b.primaryPhone && b.primaryPhone.includes(q));
      if (!match) return false;
    }
    return true;
  });

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === filtered.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filtered.map(b => b.id));
    }
  };

  const handleBulkConvert = () => {
    const unassigned = filtered.filter(b => selectedIds.includes(b.id) && b.crmLeadStatus === 'unassigned');
    for (const b of unassigned) {
      onConvertToLead(b);
    }
    setSelectedIds([]);
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              UAE Business Explorer
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
              {filtered.length} businesses
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Discover verified commercial entities across all 7 Emirates with field-level provenance
          </p>
        </div>

        {/* View Switcher & Action buttons */}
        <div className="flex items-center gap-2">
          {selectedIds.length > 0 && (
            <div className="flex items-center gap-2 mr-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                {selectedIds.length} selected
              </span>
              <button
                onClick={handleBulkConvert}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Bulk Add to CRM</span>
              </button>
            </div>
          )}

          <div className="flex items-center p-1 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md text-xs font-medium transition ${
                viewMode === 'table' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs' : 'text-slate-500'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md text-xs font-medium transition ${
                viewMode === 'grid' ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs' : 'text-slate-500'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={() => setShowFiltersDrawer(!showFiltersDrawer)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition ${
              showFiltersDrawer 
                ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-700' 
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200'
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Filters</span>
          </button>

          {onOpenTracer && (
            <button
              onClick={onOpenTracer}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              <span>Trace Business</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Drawer / Bar */}
      <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          
          {/* Quick Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search company or area..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          {/* Emirate */}
          <div>
            <select
              value={selectedEmirate}
              onChange={(e) => onEmirateChange(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All Emirates (جميع الإمارات)</option>
              <option value="Dubai">Dubai (دبي)</option>
              <option value="Abu Dhabi">Abu Dhabi (أبوظبي)</option>
              <option value="Sharjah">Sharjah (الشارقة)</option>
              <option value="Ajman">Ajman (عجمان)</option>
              <option value="Ras Al Khaimah">Ras Al Khaimah (رأس الخيمة)</option>
              <option value="Fujairah">Fujairah (الفجيرة)</option>
              <option value="Umm Al Quwain">Umm Al Quwain (أم القيوين)</option>
            </select>
          </div>

          {/* Category */}
          <div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All Categories</option>
              {categories.map((c) => (
                <option key={c.nameEn} value={c.nameEn}>
                  {c.nameEn}
                </option>
              ))}
            </select>
          </div>

          {/* Source Platform */}
          <div>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All Source Platforms</option>
              <option value="google_places">Google Places API</option>
              <option value="2gis">2GIS UAE</option>
              <option value="ded_registry">DED / DET Registry</option>
              <option value="uae_yellowpages">UAE YellowPages</option>
              <option value="web_crawl">Website Crawler</option>
            </select>
          </div>

          {/* CRM Status */}
          <div>
            <select
              value={crmStatusFilter}
              onChange={(e) => setCrmStatusFilter(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              <option value="all">All CRM Statuses</option>
              <option value="unassigned">Unassigned (New Leads)</option>
              <option value="lead_created">Lead Created</option>
              <option value="in_pipeline">In Sales Pipeline</option>
              <option value="customer">Confirmed Customer</option>
            </select>
          </div>
        </div>

        {/* Second Row Filters: Checkboxes & Slider */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-1.5 cursor-pointer text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={hasPhoneOnly}
                onChange={(e) => setHasPhoneOnly(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500"
              />
              <span>Has Verified Phone / WhatsApp</span>
            </label>

            <label className="flex items-center gap-1.5 cursor-pointer text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={hasWebsiteOnly}
                onChange={(e) => setHasWebsiteOnly(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500"
              />
              <span>Has Website</span>
            </label>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-slate-500 text-xs">Min Quality Score: {minQualityScore}%</span>
            <input
              type="range"
              min="0"
              max="95"
              step="5"
              value={minQualityScore}
              onChange={(e) => setMinQualityScore(Number(e.target.value))}
              className="w-28 accent-emerald-600"
            />
          </div>
        </div>
      </div>

      {/* Main Content: Table or Grid */}
      {viewMode === 'table' ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800 select-none">
                <tr>
                  <th className="p-3.5 w-10">
                    <button onClick={toggleSelectAll} className="cursor-pointer text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                      {selectedIds.length === filtered.length && filtered.length > 0 ? (
                        <CheckSquare className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="p-3.5">Business / Trade Name</th>
                  <th className="p-3.5">Emirate & Area</th>
                  <th className="p-3.5">Category</th>
                  <th className="p-3.5">Contact Points</th>
                  <th className="p-3.5">Score</th>
                  <th className="p-3.5">Source</th>
                  <th className="p-3.5">CRM Status</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map((biz) => {
                  const isSelected = selectedIds.includes(biz.id);
                  return (
                    <tr
                      key={biz.id}
                      className={`hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition group ${
                        isSelected ? 'bg-emerald-50/40 dark:bg-emerald-950/20' : ''
                      }`}
                    >
                      <td className="p-3.5">
                        <button onClick={() => toggleSelect(biz.id)} className="cursor-pointer text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-emerald-600" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>

                      {/* Business Name */}
                      <td className="p-3.5 max-w-xs cursor-pointer" onClick={() => onSelectBusiness(biz)}>
                        <div className="font-semibold text-slate-900 dark:text-white group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition truncate">
                          {biz.nameEn}
                        </div>
                        {biz.nameAr && (
                          <div className="text-[10px] text-slate-400 font-arabic truncate" dir="rtl">
                            {biz.nameAr}
                          </div>
                        )}
                        <div className="text-[10px] text-slate-400 mt-0.5 truncate">
                          {biz.buildingName || biz.streetAddress}
                        </div>
                      </td>

                      {/* Emirate & Area */}
                      <td className="p-3.5 whitespace-nowrap">
                        <span className="font-medium text-slate-800 dark:text-slate-200 block">
                          {biz.emirate}
                        </span>
                        <span className="text-[10px] text-slate-400">{biz.area}</span>
                      </td>

                      {/* Category */}
                      <td className="p-3.5">
                        <span className="text-slate-700 dark:text-slate-300 font-medium block truncate max-w-[140px]">
                          {biz.category}
                        </span>
                        <span className="text-[10px] text-slate-400 truncate block max-w-[140px]">
                          {biz.subcategory}
                        </span>
                      </td>

                      {/* Contacts */}
                      <td className="p-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {biz.primaryPhone ? (
                            <a
                              href={`tel:${biz.primaryPhone}`}
                              className="p-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:text-emerald-600"
                              title={biz.primaryPhone}
                            >
                              <Phone className="w-3.5 h-3.5" />
                            </a>
                          ) : null}

                          {biz.whatsappNumber ? (
                            <a
                              href={`https://wa.me/${biz.whatsappNumber.replace(/[^\d]/g, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100"
                              title={`WhatsApp: ${biz.whatsappNumber}`}
                            >
                              <MessageCircle className="w-3.5 h-3.5" />
                            </a>
                          ) : null}

                          {biz.websiteUrl ? (
                            <a
                              href={biz.websiteUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:text-blue-600"
                              title={biz.websiteUrl}
                            >
                              <Globe className="w-3.5 h-3.5" />
                            </a>
                          ) : null}
                        </div>
                      </td>

                      {/* Score */}
                      <td className="p-3.5 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] font-mono ${
                          biz.qualityScore >= 90 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' :
                          biz.qualityScore >= 80 ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20' :
                          'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                        }`}>
                          {biz.qualityScore}%
                        </span>
                      </td>

                      {/* Source */}
                      <td className="p-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {biz.sources && biz.sources.some(s => s.platform === 'google_places') && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                              MAPS
                            </span>
                          )}
                          {((biz.sources && biz.sources.some(s => s.platform === '2gis')) || biz.twoGisListingUrl) && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                              2GIS
                            </span>
                          )}
                          {(!biz.sources || !biz.sources.some(s => s.platform === '2gis' || s.platform === 'google_places')) && (
                            <span className="text-[10px] font-medium text-slate-500 uppercase tracking-tight">
                              {biz.sourcePlatform.replace('_', ' ')}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* CRM Status */}
                      <td className="p-3.5 whitespace-nowrap">
                        {biz.crmLeadStatus === 'unassigned' ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 font-medium">
                            Unassigned
                          </span>
                        ) : biz.crmLeadStatus === 'customer' ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-semibold border border-emerald-500/20">
                            Customer
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 font-semibold border border-purple-500/20">
                            In Pipeline
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="p-3.5 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => onEnrichWithAi(biz)}
                            title="AI Lead Intelligence"
                            className="p-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition"
                          >
                            <Sparkles className="w-4 h-4 text-purple-500" />
                          </button>

                          {biz.crmLeadStatus === 'unassigned' && (
                            <button
                              onClick={() => onConvertToLead(biz)}
                              title="Add to Sales Pipeline"
                              className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold flex items-center gap-1 shadow-xs transition"
                            >
                              <UserPlus className="w-3.5 h-3.5" />
                              <span>Convert</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Grid Cards View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((biz) => (
            <div
              key={biz.id}
              className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between hover:border-emerald-500/40 transition space-y-4"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                      {biz.emirate}
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase font-mono">
                      {biz.sourcePlatform.replace('_', ' ')}
                    </span>
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300">
                    {biz.qualityScore}% Score
                  </span>
                </div>

                <h3
                  onClick={() => onSelectBusiness(biz)}
                  className="font-bold text-sm text-slate-900 dark:text-white mt-2 hover:text-emerald-500 cursor-pointer transition"
                >
                  {biz.nameEn}
                </h3>
                {biz.nameAr && (
                  <p className="text-[11px] text-slate-400 font-arabic" dir="rtl">{biz.nameAr}</p>
                )}

                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 line-clamp-2">
                  {biz.description}
                </p>

                <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-300 font-medium">
                  <MapPin className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                  <span className="truncate">{biz.area}, {biz.city}</span>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {biz.primaryPhone && (
                    <a href={`tel:${biz.primaryPhone}`} className="text-slate-500 hover:text-emerald-600">
                      <Phone className="w-4 h-4" />
                    </a>
                  )}
                  {biz.whatsappNumber && (
                    <a href={`https://wa.me/${biz.whatsappNumber.replace(/[^\d]/g, '')}`} target="_blank" rel="noreferrer" className="text-emerald-500 hover:text-emerald-400">
                      <MessageCircle className="w-4 h-4" />
                    </a>
                  )}
                  {biz.websiteUrl && (
                    <a href={biz.websiteUrl} target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400">
                      <Globe className="w-4 h-4" />
                    </a>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => onEnrichWithAi(biz)}
                    className="p-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40"
                  >
                    <Sparkles className="w-4 h-4" />
                  </button>
                  {biz.crmLeadStatus === 'unassigned' && (
                    <button
                      onClick={() => onConvertToLead(biz)}
                      className="px-3 py-1 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-500 transition"
                    >
                      Convert
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};
