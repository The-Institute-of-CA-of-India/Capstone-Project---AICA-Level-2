import React, { useState } from 'react';
import { 
  X, 
  Building2, 
  MapPin, 
  Phone, 
  Mail, 
  Globe, 
  ExternalLink, 
  ShieldCheck, 
  Sparkles, 
  UserPlus, 
  Clock, 
  Layers, 
  CheckCircle2, 
  AlertCircle,
  MessageCircle,
  FileText
} from 'lucide-react';
import { Business } from '../types/index.ts';

interface BusinessDetailDrawerProps {
  business: Business | null;
  isOpen: boolean;
  onClose: () => void;
  onConvertToLead: (biz: Business) => void;
  onEnrichWithAi: (biz: Business) => void;
}

export const BusinessDetailDrawer: React.FC<BusinessDetailDrawerProps> = ({
  business,
  isOpen,
  onClose,
  onConvertToLead,
  onEnrichWithAi
}) => {
  if (!isOpen || !business) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end">
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 text-slate-100 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-250">
        
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-800 flex items-start justify-between bg-slate-900/90 shrink-0">
          <div className="flex items-start gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-600 to-teal-700 flex items-center justify-center text-white shrink-0 shadow-lg shadow-emerald-900/30">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {business.emirate}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  Score: {business.qualityScore}%
                </span>
              </div>
              <h2 className="text-lg font-bold text-white mt-1 leading-tight">{business.nameEn}</h2>
              {business.nameAr && (
                <p className="text-xs text-slate-400 font-arabic mt-0.5" dir="rtl">{business.nameAr}</p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs text-slate-300 scrollbar-thin scrollbar-thumb-slate-800">
          
          {/* Quick Action Bar */}
          <div className="flex items-center gap-2">
            {business.crmLeadStatus === 'unassigned' ? (
              <button
                onClick={() => onConvertToLead(business)}
                className="flex-1 py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center justify-center gap-2 shadow-sm transition"
              >
                <UserPlus className="w-4 h-4" />
                <span>Convert to CRM Lead</span>
              </button>
            ) : (
              <div className="flex-1 py-2 px-3 rounded-lg bg-slate-800 text-emerald-400 font-semibold flex items-center justify-center gap-2 border border-emerald-500/30">
                <CheckCircle2 className="w-4 h-4" />
                <span>In Active CRM Pipeline</span>
              </div>
            )}

            <button
              onClick={() => onEnrichWithAi(business)}
              className="py-2 px-3 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 border border-purple-500/40 font-semibold flex items-center gap-2 transition"
            >
              <Sparkles className="w-4 h-4 text-amber-300" />
              <span>AI Lead Intel</span>
            </button>
          </div>

          {/* Description */}
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-1.5">
            <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Business Profile</h4>
            <p className="text-slate-200 leading-relaxed">{business.description}</p>
            <div className="flex items-center gap-2 pt-2 text-[11px] text-slate-400">
              <span className="font-semibold text-slate-300">{business.category}</span>
              <span>•</span>
              <span>{business.subcategory}</span>
            </div>
          </div>

          {/* Contact Points & Location */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Phone */}
            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-emerald-400" />
                <span>Primary Phone</span>
              </span>
              <p className="font-mono text-slate-100">{business.primaryPhone || 'Not published'}</p>
              {business.normalizedPhone && (
                <p className="text-[10px] text-slate-400 font-mono">E.164: {business.normalizedPhone}</p>
              )}
            </div>

            {/* Email */}
            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-blue-400" />
                <span>Business Email</span>
              </span>
              <p className="text-slate-100 truncate">{business.primaryEmail || 'Not published'}</p>
            </div>

            {/* WhatsApp */}
            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span>WhatsApp Business</span>
              </span>
              {business.whatsappNumber ? (
                <a
                  href={`https://wa.me/${business.whatsappNumber.replace(/[^\d]/g, '')}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-400 hover:underline flex items-center gap-1"
                >
                  <span>{business.whatsappNumber}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-slate-500">Not verified</span>
              )}
            </div>

            {/* Website */}
            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-cyan-400" />
                <span>Website</span>
              </span>
              {business.websiteUrl ? (
                <a
                  href={business.websiteUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-cyan-400 hover:underline flex items-center gap-1 truncate"
                >
                  <span className="truncate">{business.websiteUrl.replace(/https?:\/\//, '')}</span>
                  <ExternalLink className="w-3 h-3 shrink-0" />
                </a>
              ) : (
                <span className="text-slate-500">No website registered</span>
              )}
            </div>
          </div>

          {/* Physical Address & Map Coordinates */}
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-rose-400" />
              <span>Physical Address & Coordinates</span>
            </span>
            <p className="text-slate-200">
              {business.streetAddress}, {business.area}, {business.city}, {business.emirate}, UAE
            </p>
            {business.buildingName && (
              <p className="text-slate-400 text-[11px]">Building: {business.buildingName}</p>
            )}
            {business.buildingEntrance && (
              <div className="p-2 rounded-md bg-emerald-950/30 border border-emerald-800/40 text-emerald-300 text-[11px] flex items-center gap-2">
                <span className="font-semibold text-emerald-400">2GIS Verified Entrance:</span>
                <span>{business.buildingEntrance}</span>
              </div>
            )}
            {business.plotNumber && (
              <div className="p-2 rounded-md bg-blue-950/30 border border-blue-800/40 text-blue-300 text-[11px] flex items-center gap-2">
                <span className="font-semibold text-blue-400">Plot & Makani:</span>
                <span>{business.plotNumber}</span>
              </div>
            )}
            <div className="pt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-700/40">
              <span className="font-mono text-slate-400 text-[11px]">
                Lat: {business.latitude.toFixed(4)}, Lng: {business.longitude.toFixed(4)}
              </span>
              <div className="flex items-center gap-2">
                {business.twoGisListingUrl && (
                  <a
                    href={business.twoGisListingUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="px-2 py-1 rounded bg-teal-600/20 hover:bg-teal-600/30 text-teal-300 border border-teal-500/30 text-xs font-semibold flex items-center gap-1 transition"
                  >
                    <span>2GIS Catalog</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                <a
                  href={business.googleMapsListingUrl || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(business.nameEn + ' ' + business.emirate)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2 py-1 rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-semibold flex items-center gap-1 transition"
                >
                  <span>Google Maps</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>

          {/* Field-Level Provenance & Multi-Source Attribution */}
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>Multi-Source Provenance & Caching</span>
              </span>
              <span className="text-[10px] text-emerald-400 font-medium">
                Verified: {new Date(business.dateLastVerified).toLocaleDateString()}
              </span>
            </div>
            
            <div className="space-y-2">
              {business.sources.map((src, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <div>
                      <span className="font-semibold text-slate-200 uppercase tracking-tight text-[11px]">
                        {src.platform.replace('_', ' ')}
                      </span>
                      {src.isPrimary && (
                        <span className="ml-1.5 text-[9px] bg-blue-500/20 text-blue-300 px-1.5 py-0.2 rounded font-semibold">
                          PRIMARY
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Discovered {src.discoveredAt}
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-1 text-[10px] text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>Google Places 30-day cache refresh policy actively enforced.</span>
            </div>
          </div>

          {/* Regulatory & Trade License */}
          <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                Commercial Trade License
              </span>
              <span className="font-mono font-bold text-white text-xs">
                {business.tradeLicenseNumber || 'UAE-DED-COMMERCIAL'}
              </span>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                Operating Hours
              </span>
              <span className="text-slate-300 text-xs">
                {business.operatingHours || 'Standard Business Hours'}
              </span>
            </div>
          </div>

        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-400 font-mono">
            ID: {business.id}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
