import React from 'react';
import { 
  MapPin, 
  Building2, 
  Globe, 
  ArrowRight, 
  Compass, 
  ShieldCheck, 
  Layers,
  Sparkles,
  Navigation
} from 'lucide-react';
import { Emirate } from '../types/index.ts';
import { UAE_EMIRATES } from '../data/uaeMasterData.ts';

interface LocationExplorerProps {
  onSelectEmirate: (emirate: string) => void;
  businessesByEmirate: Record<string, number>;
  onOpenGoogleMap?: () => void;
}

export const LocationExplorer: React.FC<LocationExplorerProps> = ({
  onSelectEmirate,
  businessesByEmirate,
  onOpenGoogleMap
}) => {
  const emirateProfiles = [
    {
      name: 'Dubai',
      arName: 'دبي',
      capital: 'Dubai City',
      economicFocus: 'Global Trade, Finance, Real Estate, Logistics & Tech Innovation',
      freeZones: ['DIFC', 'DMCC', 'DAFZA', 'JAFZA', 'DTEC Silicon Oasis', 'Dubai South'],
      keyDistricts: ['Business Bay', 'Downtown Dubai', 'DIFC', 'Al Quoz Industrial', 'Dubai Marina', 'JLT', 'Deira Commercial'],
      avgScore: 95,
      color: 'from-emerald-600 to-teal-700'
    },
    {
      name: 'Abu Dhabi',
      arName: 'أبوظبي',
      capital: 'Abu Dhabi (UAE Capital)',
      economicFocus: 'Energy, Sovereign Capital, Government Contracting, Heavy Industry & Advanced Tech',
      freeZones: ['ADGM (Al Maryah)', 'Masdar City', 'KIZAD / Khalifa Port', 'Hub71'],
      keyDistricts: ['Al Maryah Island', 'Corniche District', 'Musaffah Industrial', 'Al Reem Island', 'ICAD I & II'],
      avgScore: 94,
      color: 'from-blue-600 to-indigo-700'
    },
    {
      name: 'Sharjah',
      arName: 'الشارقة',
      capital: 'Sharjah City',
      economicFocus: 'Industrial Manufacturing, Publishing, Culture, Education & Logistics',
      freeZones: ['SAIF Zone', 'Hamriyah Free Zone', 'Sharjah Research Technology Park (SRTIP)'],
      keyDistricts: ['Al Majaz Waterfront', 'Sharjah Industrial Areas 1-18', 'Muwaileh Commercial', 'Al Khan'],
      avgScore: 91,
      color: 'from-amber-600 to-orange-700'
    },
    {
      name: 'Ajman',
      arName: 'عجمان',
      capital: 'Ajman City',
      economicFocus: 'Precision Metal Fabrication, Shipbuilding, FMCG & Wholesale Trading',
      freeZones: ['Ajman Free Zone (AFZ)', 'Ajman Media City Free Zone'],
      keyDistricts: ['Ajman Free Zone', 'Al Jurf Industrial 1-3', 'Al Nuaimiya', 'Al Rashidiya'],
      avgScore: 88,
      color: 'from-indigo-600 to-purple-700'
    },
    {
      name: 'Ras Al Khaimah',
      arName: 'رأس الخيمة',
      capital: 'Ras Al Khaimah',
      economicFocus: 'Ceramics, Pharmaceutical (Julphar), Quarrying, Eco-Tourism & Maritime',
      freeZones: ['RAK Economic Zone (RAKEZ)', 'RAK Maritime City Free Zone'],
      keyDistricts: ['Al Nakheel Commercial', 'RAKEZ Business Zone', 'Al Hamra Village', 'Khuzam'],
      avgScore: 89,
      color: 'from-purple-600 to-pink-700'
    },
    {
      name: 'Fujairah',
      arName: 'الفجيرة',
      capital: 'Fujairah City',
      economicFocus: 'World 2nd Largest Bunkering Hub, Marine Logistics, Mining & Oil Storage',
      freeZones: ['Fujairah Free Zone Authority', 'Fujairah Oil Industry Zone (FOIZ)'],
      keyDistricts: ['Fujairah Free Zone', 'FOIZ Marine Zone', 'Hamad Bin Abdulla Street', 'Al Faseel'],
      avgScore: 92,
      color: 'from-cyan-600 to-teal-700'
    },
    {
      name: 'Umm Al Quwain',
      arName: 'أم القيوين',
      capital: 'Umm Al Quwain',
      economicFocus: 'Automated Bottling, Construction Materials, Marine Works & Free Trade',
      freeZones: ['UAQ Free Trade Zone (UAQ FTZ)'],
      keyDistricts: ['UAQ Free Trade Zone', 'Al Salamah Commercial', 'Old Town Commercial'],
      avgScore: 86,
      color: 'from-rose-600 to-red-700'
    }
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            UAE Geographic & Free Zone Explorer
          </h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
            7 Emirates • 40+ Commercial Districts
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Explore regional commercial hubs, licensed free zones, and business density metrics across the federation
        </p>
      </div>

      {/* Google Maps Geospatial Launcher Banner */}
      {onOpenGoogleMap && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 via-cyan-950/40 to-slate-900 border border-cyan-800/40 shadow-lg text-white flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Navigation className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm">Interactive Google Maps Geospatial View</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30">
                  Live API
                </span>
              </div>
              <p className="text-xs text-slate-400">
                View all verified businesses pinned on Google Maps with real coordinates, fly-to Emirate controls, and trade license intelligence.
              </p>
            </div>
          </div>
          <button
            onClick={onOpenGoogleMap}
            className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-md shadow-cyan-600/30 shrink-0"
          >
            <span>Launch Google Map View</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Emirates Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {emirateProfiles.map((em) => {
          const count = businessesByEmirate[em.name] || 0;
          return (
            <div
              key={em.name}
              className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between hover:border-emerald-500/50 transition space-y-4"
            >
              <div>
                {/* Header Card */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${em.color} flex items-center justify-center text-white shadow-md`}>
                      <MapPin className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-base text-slate-900 dark:text-white">
                        {em.name}
                      </h3>
                      <p className="text-xs text-slate-400 font-arabic" dir="rtl">{em.arName}</p>
                    </div>
                  </div>

                  <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                    {count} In Database
                  </span>
                </div>

                {/* Capital & Focus */}
                <div className="mt-3 text-xs text-slate-600 dark:text-slate-300">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Economic Core: </span>
                  <span>{em.economicFocus}</span>
                </div>

                {/* Free Zones */}
                <div className="mt-3 space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    Major Free Zones & Ecosystems
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {em.freeZones.map((fz, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 text-[10px] font-semibold border border-blue-200 dark:border-blue-800/40">
                        {fz}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Key Commercial Districts */}
                <div className="mt-3 space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    Key Commercial Districts
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {em.keyDistricts.map((kd, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[10px]">
                        {kd}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  Avg Completeness: {em.avgScore}%
                </span>
                <button
                  onClick={() => onSelectEmirate(em.name)}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition"
                >
                  <span>Explore {em.name}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
};
