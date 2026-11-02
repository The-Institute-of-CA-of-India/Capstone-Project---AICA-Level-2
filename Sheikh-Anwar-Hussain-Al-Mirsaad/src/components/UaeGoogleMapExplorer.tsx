import React, { useState, useMemo } from 'react';
import { 
  APIProvider, 
  Map, 
  AdvancedMarker, 
  Pin, 
  InfoWindow, 
  MapControl, 
  ControlPosition 
} from '@vis.gl/react-google-maps';
import { 
  MapPin, 
  Layers, 
  Building2, 
  Phone, 
  Mail, 
  MessageCircle, 
  ExternalLink, 
  Search, 
  Filter, 
  Database, 
  ShieldCheck, 
  Navigation, 
  Crosshair, 
  Compass,
  CheckCircle,
  Eye,
  Briefcase,
  Sparkles
} from 'lucide-react';
import { Business, Emirate } from '../types/index.ts';

interface UaeGoogleMapExplorerProps {
  businesses: Business[];
  onSelectBusiness: (business: Business) => void;
  onConvertToLead: (business: Business) => void;
  selectedEmirate?: string;
  onEmirateChange?: (emirate: string) => void;
  onOpenTracer?: () => void;
}

const EMIRATE_COORDINATES: Record<string, { lat: number; lng: number; zoom: number }> = {
  all: { lat: 24.85, lng: 55.05, zoom: 8 },
  Dubai: { lat: 25.1972, lng: 55.2744, zoom: 12 },
  'Abu Dhabi': { lat: 24.4539, lng: 54.3773, zoom: 11 },
  Sharjah: { lat: 25.3573, lng: 55.4033, zoom: 12 },
  Ajman: { lat: 25.4052, lng: 55.5136, zoom: 13 },
  'Ras Al Khaimah': { lat: 25.7895, lng: 55.9432, zoom: 12 },
  Fujairah: { lat: 25.1288, lng: 56.3265, zoom: 12 },
  'Umm Al Quwain': { lat: 25.5647, lng: 55.5552, zoom: 13 }
};

const CATEGORY_COLORS: Record<string, { bg: string; border: string }> = {
  'Construction and contracting': { bg: '#f97316', border: '#c2410c' },
  'Real estate': { bg: '#3b82f6', border: '#1d4ed8' },
  'IT and software companies': { bg: '#6366f1', border: '#4338ca' },
  'Healthcare and clinics': { bg: '#10b981', border: '#047857' },
  'Logistics and transport': { bg: '#8b5cf6', border: '#6d28d9' },
  'Financial and professional services': { bg: '#06b6d4', border: '#0e7490' },
  'Manufacturing and factories': { bg: '#ec4899', border: '#be185d' },
  'Restaurants and cafes': { bg: '#eab308', border: '#a16207' },
  'Automobile services': { bg: '#ef4444', border: '#b91c1c' },
  'Retail and supermarkets': { bg: '#14b8a6', border: '#0f766e' }
};

export const UaeGoogleMapExplorer: React.FC<UaeGoogleMapExplorerProps> = ({
  businesses,
  onSelectBusiness,
  onConvertToLead,
  selectedEmirate = 'all',
  onEmirateChange,
  onOpenTracer
}) => {
  const [activeEmirate, setActiveEmirate] = useState<string>(selectedEmirate);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const [mapType, setMapType] = useState<string>('roadmap');

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || 'AIzaSyCFsBqxPro_YQOYjuBh_ZauOOnVIYDeepw';

  const emiratesList = ['all', 'Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Ras Al Khaimah', 'Fujairah', 'Umm Al Quwain'];

  const filteredBusinesses = useMemo(() => {
    return businesses.filter(b => {
      const matchEmirate = activeEmirate === 'all' || b.emirate === activeEmirate;
      const matchCategory = selectedCategory === 'all' || b.category === selectedCategory;
      const matchSearch = !searchQuery || 
        b.nameEn.toLowerCase().includes(searchQuery.toLowerCase()) ||
        b.area.toLowerCase().includes(searchQuery.toLowerCase()) ||
        b.category.toLowerCase().includes(searchQuery.toLowerCase());
      return matchEmirate && matchCategory && matchSearch && b.latitude && b.longitude;
    });
  }, [businesses, activeEmirate, selectedCategory, searchQuery]);

  const mapCenter = EMIRATE_COORDINATES[activeEmirate] || EMIRATE_COORDINATES.all;

  const handleEmirateClick = (em: string) => {
    setActiveEmirate(em);
    if (onEmirateChange) onEmirateChange(em);
    setSelectedBusiness(null);
  };

  const getPinColor = (category: string) => {
    return CATEGORY_COLORS[category] || { bg: '#0284c7', border: '#0369a1' };
  };

  return (
    <div className="space-y-4">
      {/* Header & Mission Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg text-white">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                <Navigation className="w-5 h-5" />
              </span>
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <span>UAE Interactive Google Maps Geospatial Intelligence</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-semibold border border-emerald-500/30 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" />
                    <span>Live Google Maps Platform API</span>
                  </span>
                </h2>
                <p className="text-sm text-slate-400">
                  Visual geospatial intelligence across all 7 Emirates. Discover commercial clusters, navigate to sites, and convert local entities to CRM leads.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl px-3.5 py-2 text-right">
              <div className="text-xs text-slate-400">Verified Entities Mapped</div>
              <div className="text-lg font-bold text-cyan-400 flex items-center justify-end gap-1.5">
                <Database className="w-4 h-4 text-emerald-400" />
                <span>{filteredBusinesses.length} Stored in Database</span>
              </div>
            </div>
            <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl px-3.5 py-2 text-right">
              <div className="text-xs text-slate-400">Cloud Sync</div>
              <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Firestore Connected</span>
              </div>
            </div>
            {onOpenTracer && (
              <button
                onClick={onOpenTracer}
                className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center gap-1.5 shadow-md shadow-indigo-600/30 transition-all cursor-pointer"
                title="Trace New Business with Maps + Search Grounding"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                <span>Trace on Map</span>
              </button>
            )}
          </div>
        </div>

        {/* Filters & Fly-To Controls */}
        <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
          {/* Emirate Quick Fly-To Buttons */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1 mr-1">
              <Compass className="w-3.5 h-3.5" />
              <span>Emirate:</span>
            </span>
            {emiratesList.map(em => (
              <button
                key={em}
                onClick={() => handleEmirateClick(em)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                  activeEmirate === em
                    ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30 font-semibold'
                    : 'bg-slate-800/70 text-slate-300 hover:bg-slate-700/70 border border-slate-700/50'
                }`}
              >
                {em === 'all' ? 'All Emirates (UAE)' : em}
              </button>
            ))}
          </div>

          {/* Search & Map Type Toggle */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search mapped businesses or areas..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex rounded-lg border border-slate-700 bg-slate-800 p-0.5 text-xs">
              <button
                onClick={() => setMapType('roadmap')}
                className={`px-2.5 py-1 rounded-md transition ${mapType === 'roadmap' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
              >
                Roadmap
              </button>
              <button
                onClick={() => setMapType('satellite')}
                className={`px-2.5 py-1 rounded-md transition ${mapType === 'satellite' ? 'bg-cyan-600 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
              >
                Satellite
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Interactive Map Container */}
      <div className="h-[620px] w-full rounded-2xl overflow-hidden border border-slate-700/70 shadow-2xl relative bg-slate-950">
        <APIProvider apiKey={apiKey} solutionChannel="gmp_git_agentskills_v1">
          <Map
            mapId="DEMO_MAP_ID"
            defaultCenter={{ lat: mapCenter.lat, lng: mapCenter.lng }}
            defaultZoom={mapCenter.zoom}
            center={{ lat: mapCenter.lat, lng: mapCenter.lng }}
            zoom={mapCenter.zoom}
            gestureHandling="greedy"
            disableDefaultUI={false}
            mapTypeId={mapType}
            className="w-full h-full"
          >
            {/* Custom Top Control Bar inside Map */}
            <MapControl position={ControlPosition.TOP_LEFT}>
              <div className="m-3 bg-slate-900/90 backdrop-blur-md border border-slate-700/80 rounded-xl p-2.5 shadow-xl text-white max-w-sm">
                <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 mb-1.5">
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Showing {filteredBusinesses.length} verified locations in {activeEmirate === 'all' ? 'UAE' : activeEmirate}</span>
                </div>
                <p className="text-[11px] text-slate-300">
                  Click any marker to view contact intelligence, trade license verification, and convert directly to a CRM lead.
                </p>
              </div>
            </MapControl>

            {/* Render Advanced Markers for each business */}
            {filteredBusinesses.map(b => {
              const colors = getPinColor(b.category);
              return (
                <AdvancedMarker
                  key={b.id}
                  position={{ lat: b.latitude, lng: b.longitude }}
                  title={`${b.nameEn} (${b.category})`}
                  onClick={() => setSelectedBusiness(b)}
                >
                  <Pin
                    background={colors.bg}
                    borderColor={colors.border}
                    glyphColor="#ffffff"
                    scale={selectedBusiness?.id === b.id ? 1.3 : 1.0}
                  />
                </AdvancedMarker>
              );
            })}

            {/* InfoWindow for Clicked Business */}
            {selectedBusiness && (
              <InfoWindow
                position={{ lat: selectedBusiness.latitude, lng: selectedBusiness.longitude }}
                onCloseClick={() => setSelectedBusiness(null)}
                maxWidth={340}
              >
                <div className="p-2 text-slate-900 space-y-2.5">
                  <div className="border-b border-slate-200 pb-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800">
                        {selectedBusiness.emirate} • {selectedBusiness.area}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        {selectedBusiness.qualityScore}% Quality
                      </span>
                    </div>
                    <h3 className="font-bold text-sm text-slate-900 mt-1 leading-tight">
                      {selectedBusiness.nameEn}
                    </h3>
                    {selectedBusiness.nameAr && (
                      <p className="text-xs text-slate-500 font-arabic text-right mt-0.5" dir="rtl">
                        {selectedBusiness.nameAr}
                      </p>
                    )}
                    <p className="text-[11px] text-slate-600 mt-0.5">
                      {selectedBusiness.category} ({selectedBusiness.subcategory})
                    </p>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-700">
                    {selectedBusiness.primaryPhone && (
                      <div className="flex items-center gap-2">
                        <Phone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <a href={`tel:${selectedBusiness.primaryPhone}`} className="hover:underline font-medium">
                          {selectedBusiness.primaryPhone}
                        </a>
                      </div>
                    )}
                    {selectedBusiness.whatsappNumber && (
                      <div className="flex items-center gap-2">
                        <MessageCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <a 
                          href={`https://wa.me/${selectedBusiness.whatsappNumber.replace(/[^0-9]/g, '')}`} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="text-emerald-700 font-semibold hover:underline flex items-center gap-1"
                        >
                          <span>WhatsApp Direct</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      </div>
                    )}
                    {selectedBusiness.primaryEmail && (
                      <div className="flex items-center gap-2">
                        <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{selectedBusiness.primaryEmail}</span>
                      </div>
                    )}
                    {selectedBusiness.streetAddress && (
                      <div className="flex items-start gap-2 text-[11px] text-slate-500">
                        <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                        <span>{selectedBusiness.streetAddress}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions inside InfoWindow */}
                  <div className="pt-2 border-t border-slate-200 flex items-center gap-2">
                    <button
                      onClick={() => onSelectBusiness(selectedBusiness)}
                      className="flex-1 py-1.5 px-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-1 transition"
                    >
                      <Eye className="w-3 h-3" />
                      <span>Details</span>
                    </button>
                    {selectedBusiness.crmLeadStatus !== 'lead_created' && (
                      <button
                        onClick={() => onConvertToLead(selectedBusiness)}
                        className="flex-1 py-1.5 px-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-1 transition shadow-sm"
                      >
                        <Briefcase className="w-3 h-3" />
                        <span>Add to Lead</span>
                      </button>
                    )}
                  </div>
                </div>
              </InfoWindow>
            )}
          </Map>
        </APIProvider>
      </div>

      {/* Geospatial Category Legend */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5" />
          <span>Industry Categories Map Legend</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(CATEGORY_COLORS).map(([cat, colors]) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(selectedCategory === cat ? 'all' : cat)}
              className={`px-2.5 py-1 rounded-lg text-xs flex items-center gap-1.5 transition border ${
                selectedCategory === cat 
                  ? 'bg-slate-800 text-white border-white/40 ring-1 ring-white/30 font-semibold' 
                  : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800'
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors.bg }} />
              <span>{cat}</span>
              <span className="text-[10px] text-slate-500 ml-0.5">
                ({businesses.filter(b => b.category === cat).length})
              </span>
            </button>
          ))}
          {selectedCategory !== 'all' && (
            <button
              onClick={() => setSelectedCategory('all')}
              className="px-2 py-1 text-xs text-rose-400 hover:underline"
            >
              Clear Filter
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
