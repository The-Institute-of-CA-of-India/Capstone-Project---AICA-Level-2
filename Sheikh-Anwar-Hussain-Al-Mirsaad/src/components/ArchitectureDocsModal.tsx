import React, { useState } from 'react';
import { 
  X, 
  BookOpen, 
  Database, 
  Layers, 
  FileCode2, 
  Calendar, 
  DollarSign, 
  Shield, 
  CheckCircle2, 
  Copy, 
  Download,
  Terminal,
  ExternalLink,
  Table
} from 'lucide-react';

interface ArchitectureDocsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ArchitectureDocsModal: React.FC<ArchitectureDocsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'prd' | 'diagram' | 'sources' | 'schema' | 'api' | 'ui' | 'roadmap' | 'mvp' | 'costs' | 'security'>('prd');
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const tabs = [
    { id: 'prd', label: '1. PRD & Overview', icon: BookOpen },
    { id: 'diagram', label: '2. System Diagram', icon: Layers },
    { id: 'sources', label: '3. Data Sources & Licensing', icon: Database },
    { id: 'schema', label: '4. PostgreSQL Schema', icon: Table },
    { id: 'api', label: '5. API Specs', icon: FileCode2 },
    { id: 'ui', label: '6. UI/UX Plan', icon: Layers },
    { id: 'roadmap', label: '7. Roadmap', icon: Calendar },
    { id: 'mvp', label: '8. MVP Scope', icon: CheckCircle2 },
    { id: 'costs', label: '9. Cost Estimates', icon: DollarSign },
    { id: 'security', label: '10. Security & PDPL', icon: Shield },
  ];

  const copyCurrentContent = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-hidden">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-5xl h-[88vh] flex flex-col shadow-2xl text-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white shadow-md">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">Master Technical Architecture & PRD</h2>
                <span className="text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded-full">
                  10 Deliverables
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Al-Mirsaad UAE Business Intelligence, Lead Generation & Sales CRM SaaS
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Horizontal Navigation Tabs */}
        <div className="px-6 py-2 border-b border-slate-800 bg-slate-950/50 flex gap-1.5 overflow-x-auto scrollbar-none shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-6 text-sm text-slate-300 scrollbar-thin scrollbar-thumb-slate-800 space-y-6">
          
          {/* TAB 1: PRD */}
          {activeTab === 'prd' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-800/40 text-blue-200">
                <h3 className="font-bold text-base text-white mb-1">1. Product Requirements Document (PRD)</h3>
                <p className="text-xs leading-relaxed text-blue-200/90">
                  Comprehensive functional and compliance blueprint for multi-tenant UAE business discovery, deduplication, and CRM prospecting across Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, Fujairah, and Umm Al Quwain.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">Core Objectives</h4>
                  <ul className="text-xs space-y-1.5 list-disc list-inside text-slate-300">
                    <li>Discover licensed enterprises across all 7 UAE Emirates and free zones (DIFC, ADGM, DMCC, SAIF, RAKEZ).</li>
                    <li>Field-level data ingestion with Google Places, 2GIS, DED Registries, and Web Crawl attribution.</li>
                    <li>Intelligent deduplication using Levenshtein distance, token sort ratio, and E.164 phone matching.</li>
                    <li>7-stage sales CRM pipeline with deal valuations in UAE Dirhams (AED) and team assignment.</li>
                    <li>Built-in compliance with UAE Personal Data Protection Law (Federal Decree-Law No. 45/2021).</li>
                  </ul>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400">Target User Personas</h4>
                  <ul className="text-xs space-y-1.5 text-slate-300">
                    <li><strong className="text-white">B2B Sales Development Reps (SDRs):</strong> Prospect high-completeness records, verify WhatsApp/landlines, and execute direct outreach.</li>
                    <li><strong className="text-white">Account Executives (AEs):</strong> Manage pipeline stages, log client calls, schedule demos, and close deals.</li>
                    <li><strong className="text-white">Sales Directors & Managers:</strong> Territory assignment across Emirates, revenue forecasting, and team quota tracking.</li>
                    <li><strong className="text-white">Compliance Officers:</strong> Monitor opt-outs, TDRA spam directives, and audit log inspection.</li>
                  </ul>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/40">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200 mb-2">Standard UAE Data Fields Captured</h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 text-xs">
                  {['Trade Name (EN/AR)', 'Normalized Name', 'Emirate & City', 'Commercial Area', 'Street Address', 'Latitude / Longitude', 'Primary Landline', 'Normalized E.164 Phone', 'Verified Email', 'WhatsApp Business Link', 'Official Website', 'Trade License Number', 'Operating Hours', 'Social Media Links', 'Quality Score (0-100)', 'Source Provenance', 'CRM Pipeline Stage', 'Last Verified Date'].map((field, i) => (
                    <div key={i} className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                      <span>{field}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: DIAGRAM */}
          {activeTab === 'diagram' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-base text-white">2. Full-Stack System Architecture Diagram</h3>
                <button
                  onClick={() => copyCurrentContent(`[System Architecture Diagram]`)}
                  className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 px-2.5 py-1 rounded bg-slate-800"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>{copied ? 'Copied!' : 'Copy Diagram'}</span>
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-slate-950 font-mono text-xs text-emerald-400 border border-slate-800 overflow-x-auto leading-relaxed">
{`+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|  React 19 SPA + Tailwind CSS v4 + Motion + Lucide Icons (Browser / Tablet / Mobile)|
+----------------------------------------+------------------------------------------+
                                         | HTTPS (REST API + SSE)
                                         v
+-----------------------------------------------------------------------------------+
|                            API GATEWAY & BACKEND LAYER                            |
|                          Node.js / Express (TypeScript)                           |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Auth & RBAC Guards |  | Rate Limiter & Audit |  | UAE PDPL Suppression Gate |  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Business Explorer  |  | CRM Pipeline Engine  |  | Data Ingestion Workers    |  |
|  | API / Saved Search |  | Kanban / Deals / Task|  | (Google, 2GIS, Web, CSV)  |  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  +-----------------------------------------------------------------------------+  |
|  | Deduplication Engine: Fuzzy Name Matcher + Geo Proximity + Phone Normalizer |  |
|  +-----------------------------------------------------------------------------+  |
|  | Gemini 3.8 Flash AI Service: Business Summaries & Bilingual B2B Outreach    |  |
|  +-----------------------------------------------------------------------------+  |
+----------------------------------------+------------------------------------------+
                                         |
     +-----------------------------------+-----------------------------------+
     v                                   v                                   v
+-------------------------+  +-------------------------+  +-------------------------+
|     POSTGRESQL +        |  |      REDIS QUEUE        |  |   EXTERNAL PROVIDERS    |
|       POSTGIS           |  |       & CACHING         |  | - Google Places API     |
| - Normalized Businesses |  | - Background Ingestion  |  | - 2GIS UAE API          |
| - CRM Leads & Deals     |  | - Deduplication Tasks   |  | - UAE Public Registries |
| - Audit & Provenance    |  | - Cache Layer (30-day)  |  | - Google GenAI SDK      |
| - Spatial Index (GIST)  |  | - Rate-limit state      |  |   (Gemini 3.8 Flash)    |
+-------------------------+  +-------------------------+  +-------------------------+`}
              </pre>
            </div>
          )}

          {/* TAB 3: DATA SOURCES & LICENSING */}
          {activeTab === 'sources' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">3. Comparison of Data-Source Options and Restrictions</h3>
              <p className="text-xs text-slate-400">
                Commercial and compliance trade-offs across authorized UAE business discovery pipelines:
              </p>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-800 text-slate-200">
                    <tr>
                      <th className="p-3">Source Provider</th>
                      <th className="p-3">Strengths for UAE</th>
                      <th className="p-3">Licensing Limitations</th>
                      <th className="p-3">Data Retention Policy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-900/60 text-slate-300">
                    <tr>
                      <td className="p-3 font-semibold text-white">Google Places API</td>
                      <td className="p-3">High accuracy for retail, dining, corporate offices across Dubai & Abu Dhabi.</td>
                      <td className="p-3">Google Terms strictly prohibit caching Place Details permanently. Place IDs and lat/lng can be cached up to 30 days.</td>
                      <td className="p-3"><span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300">30-Day Auto-Refresh</span></td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">2GIS UAE Data API</td>
                      <td className="p-3">Unmatched accuracy for industrial zones (Musaffah, Al Quoz, Sharjah Industrial); building entrance coordinates.</td>
                      <td className="p-3">Requires commercial B2B licensing for CRM storage; monthly volume quotas.</td>
                      <td className="p-3"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">Permanent CRM Use (Licensed)</span></td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">UAE DED / DET Open Portals</td>
                      <td className="p-3">Official trade license numbers, legal entity forms (LLC, Free Zone), verified commercial trade activities.</td>
                      <td className="p-3">Batch updates; personal direct emails rarely included to protect privacy.</td>
                      <td className="p-3"><span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">Open Data License</span></td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">Permitted Web Crawling</td>
                      <td className="p-3">Executive names, corporate email addresses (sales@, info@), service portfolios, social links.</td>
                      <td className="p-3">Must strictly honor robots.txt, user-agent disclosures, and avoid any anti-bot or CAPTCHA bypass.</td>
                      <td className="p-3"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">First-Party Public Provenance</span></td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">CSV / Excel Uploads</td>
                      <td className="p-3">Customer-owned trade fair attendee lists, chamber directories, and existing ERP records.</td>
                      <td className="p-3">Subject to customer compliance representations; automatic validation against suppression lists.</td>
                      <td className="p-3"><span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300">Tenant-Isolated Storage</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: SCHEMA */}
          {activeTab === 'schema' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-base text-white">4. Normalized PostgreSQL + PostGIS Database Schema</h3>
                  <p className="text-xs text-slate-400">Production-ready DDL covering 12 core tables, indexes, and relations.</p>
                </div>
                <button
                  onClick={() => copyCurrentContent(`-- Normalized PostgreSQL Schema\nCREATE TABLE businesses...`)}
                  className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 px-2.5 py-1 rounded bg-slate-800"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>{copied ? 'Copied!' : 'Copy SQL DDL'}</span>
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-slate-950 font-mono text-xs text-slate-300 border border-slate-800 overflow-x-auto leading-relaxed">
{`-- Core Businesses Master Record
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name_en VARCHAR(300) NOT NULL,
    name_ar VARCHAR(300),
    normalized_name VARCHAR(300) NOT NULL,
    emirate VARCHAR(50) NOT NULL CHECK (emirate IN ('Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Ras Al Khaimah', 'Fujairah', 'Umm Al Quwain')),
    city VARCHAR(100) NOT NULL,
    area VARCHAR(150),
    street_address TEXT,
    building_name VARCHAR(150),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    website_url VARCHAR(500),
    primary_phone VARCHAR(50),
    normalized_phone VARCHAR(50),
    primary_email VARCHAR(255),
    whatsapp_number VARCHAR(50),
    trade_license_number VARCHAR(100),
    quality_score INTEGER DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100),
    crm_lead_status VARCHAR(50) DEFAULT 'unassigned',
    date_discovered TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_last_verified TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Field-Level Provenance & Multi-Source Tracking
CREATE TABLE business_source_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    source_url TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cache_expires_at TIMESTAMP WITH TIME ZONE
);

-- CRM Leads & Pipeline
CREATE TABLE crm_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    pipeline_stage VARCHAR(50) DEFAULT 'new_lead' 
      CHECK (pipeline_stage IN ('new_lead', 'contacted', 'qualified', 'meeting_scheduled', 'proposal_sent', 'negotiation', 'won', 'lost')),
    deal_value_aed NUMERIC(15,2) DEFAULT 0,
    expected_close_date DATE,
    priority VARCHAR(20) DEFAULT 'medium',
    tags TEXT[],
    ai_summary TEXT,
    ai_pitch_draft TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Search & Spatial Queries
CREATE INDEX idx_businesses_emirate ON businesses(emirate);
CREATE INDEX idx_businesses_normalized_name ON businesses(normalized_name);
CREATE INDEX idx_businesses_normalized_phone ON businesses(normalized_phone);
CREATE INDEX idx_crm_leads_stage ON crm_leads(pipeline_stage);`}
              </pre>
            </div>
          )}

          {/* TAB 5: API */}
          {activeTab === 'api' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">5. REST API Endpoint Specifications</h3>
              <div className="space-y-2 text-xs">
                {[
                  { method: 'GET', path: '/api/businesses', desc: 'Query UAE businesses with filters (emirate, area, category, minScore, source, hasPhone, crmStatus)' },
                  { method: 'GET', path: '/api/businesses/:id', desc: 'Retrieve full business golden record, source provenance history, and linked CRM lead' },
                  { method: 'POST', path: '/api/businesses/:id/convert-to-lead', desc: 'Transition discovered business to active CRM lead with deal value in AED' },
                  { method: 'GET', path: '/api/duplicates', desc: 'Retrieve fuzzy duplicate candidates with similarity scores and match criteria' },
                  { method: 'POST', path: '/api/duplicates/merge', desc: 'Merge secondary duplicate into master record while maintaining source provenance' },
                  { method: 'GET', path: '/api/collection-jobs', desc: 'List active and historical collection jobs with live logs' },
                  { method: 'POST', path: '/api/collection-jobs/run', desc: 'Execute live discovery job for specified Emirate, category, and source' },
                  { method: 'GET', path: '/api/crm/leads', desc: 'List CRM leads filtered by stage, sales rep, or priority' },
                  { method: 'PATCH', path: '/api/crm/leads/:id', desc: 'Update lead stage (Kanban transition), deal value, or assigned user' },
                  { method: 'POST', path: '/api/ai/enrich-lead', desc: 'Call server-side Gemini 3.8 Flash for commercial summary and bilingual pitch' },
                  { method: 'POST', path: '/api/import/csv', desc: 'Ingest external CSV records with automated phone normalization' },
                  { method: 'GET', path: '/api/export', desc: 'Compliant CSV export filtered against UAE PDPL suppression list' },
                ].map((ep, i) => (
                  <div key={i} className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                        ep.method === 'GET' ? 'bg-blue-500/20 text-blue-300' :
                        ep.method === 'POST' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                      }`}>
                        {ep.method}
                      </span>
                      <code className="text-white font-mono text-xs">{ep.path}</code>
                    </div>
                    <span className="text-slate-400 text-xs">{ep.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 6: UI/UX PLAN */}
          {activeTab === 'ui' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">6. Page-by-Page UI/UX Architecture</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                {[
                  { title: '1. Overview Dashboard', desc: 'Real-time KPI metrics, Emirates market share, 7-stage sales funnel, and live collection status.' },
                  { title: '2. Business Explorer', desc: 'High-density directory with multi-filter drawer, quality score meters, WhatsApp direct triggers, and AI enrich action.' },
                  { title: '3. Data Collection Hub', desc: 'Discovery launcher for Google Places, 2GIS, UAE YellowPages with real-time logs and job scheduler.' },
                  { title: '4. Business Categories', desc: 'Hierarchical tree of 17 core UAE industries with subcategories and live record count badges.' },
                  { title: '5. UAE Location Explorer', desc: 'Interactive atlas of all 7 Emirates with neighborhood commercial densities (Business Bay, DIFC, Musaffah, etc.).' },
                  { title: '6. Lead Management', desc: 'Comprehensive sales lead table with lead owners, priority badges, follow-up timers, and bulk actions.' },
                  { title: '7. Sales Pipeline (Kanban)', desc: '7-column visual board with stage totals in AED, drag-and-drop transitions, and deal editing.' },
                  { title: '8. Contacts & Customers', desc: 'Directory of verified UAE corporate decision makers with direct phone, email, and WhatsApp links.' },
                  { title: '9. Tasks & Follow-ups', desc: 'Sales task manager with priority tags, client meeting reminders, and completion checkoffs.' },
                  { title: '10. Analytics & Reports', desc: 'Deep analytical charts for Emirate distribution, SDR leaderboard, win/loss rates, and deal revenue forecasting.' },
                  { title: '11. Import / Export Hub', desc: 'CSV/Excel file uploader with column auto-mapping and compliant CSV exporter with PDPL opt-out filters.' },
                  { title: '12. Team Management', desc: 'Sales reps roster, roles (Admin, AE, SDR), assigned leads, and monthly quota progress.' },
                  { title: '13. Settings & Governance', desc: 'UAE PDPL suppression list, data retention policies, source API credentials, and audit log inspection.' },
                ].map((page, i) => (
                  <div key={i} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/60">
                    <h4 className="font-semibold text-white mb-1">{page.title}</h4>
                    <p className="text-slate-400 text-xs">{page.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 7: ROADMAP */}
          {activeTab === 'roadmap' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">7. Development Roadmap & Milestones</h3>
              <div className="space-y-3">
                {[
                  { phase: 'Phase 1: Architecture & Compliance (Days 1-7)', status: 'Complete', items: ['PRD & Master Technical Specs', 'UAE PDPL & TDRA Compliance Framework', 'PostgreSQL Schema & PostGIS DDL', 'UI Component System Setup'] },
                  { phase: 'Phase 2: MVP Core Platform (Days 8-21)', status: 'Delivered in MVP', items: ['7 Emirates & 17 Categories modeling', 'Multi-Source Data Ingestion Engine (Google, 2GIS, Web, CSV)', 'Fuzzy Deduplication & Normalization Engine', 'Business Explorer & Lead Conversion', '7-Stage Sales Pipeline with AED Deal Values'] },
                  { phase: 'Phase 3: Advanced CRM & Intelligence (Days 22-35)', status: 'Active in Build', items: ['Kanban Drag-and-Drop Board', 'Server-Side Gemini 3.8 Flash Bilingual Lead Enrichment', 'Tasks, Reminders & Activity Logging', 'Suppression List & Compliance Gate'] },
                  { phase: 'Phase 4: Enterprise Scale & Integrations (Days 36-50)', status: 'Planned Expansion', items: ['Automated Redis background workers', 'WhatsApp Cloud Business API integration', 'Multi-tenant subscription billing (Stripe)', 'Custom Webhooks & REST API keys'] },
                ].map((road, i) => (
                  <div key={i} className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-bold text-xs text-white uppercase tracking-wider">{road.phase}</h4>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold">
                        {road.status}
                      </span>
                    </div>
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-slate-300">
                      {road.items.map((it, idx) => (
                        <li key={idx} className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>{it}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 8: MVP SCOPE */}
          {activeTab === 'mvp' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">8. Realistic MVP Scope Definition</h3>
              <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3 text-xs leading-relaxed">
                <p>
                  To maximize business value while ensuring compliance, the MVP focuses on high-impact prospecting features for UAE sales teams:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <h5 className="font-semibold text-emerald-400 mb-1">INCLUDED IN MVP</h5>
                    <ul className="space-y-1 text-slate-300 list-disc list-inside">
                      <li>Complete 7 Emirates coverage & 40+ top business districts.</li>
                      <li>17 Standard UAE categories with subcategories.</li>
                      <li>Multi-source ingestion simulation & live collector.</li>
                      <li>Fuzzy deduplication with similarity scoring & manual merge.</li>
                      <li>7-stage CRM pipeline with deal values in AED.</li>
                      <li>Server-side Gemini 3.8 Flash AI enrichment (English/Arabic).</li>
                      <li>CSV Import with auto phone normalizer to E.164.</li>
                      <li>Export builder with UAE PDPL suppression check.</li>
                    </ul>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <h5 className="font-semibold text-amber-400 mb-1">FUTURE (COMMERCIAL API KEYS REQUIRED)</h5>
                    <ul className="space-y-1 text-slate-300 list-disc list-inside">
                      <li>Live Google Places API key (uses user cloud credentials).</li>
                      <li>Live 2GIS Commercial Catalog API license.</li>
                      <li>Official WhatsApp Business Platform sender account.</li>
                      <li>Automated daily cron sync workers via Redis/BullMQ.</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 9: COSTS */}
          {activeTab === 'costs' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">9. Estimated Infrastructure & API Cost Categories</h3>
              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-800 text-slate-200">
                    <tr>
                      <th className="p-3">Cost Category</th>
                      <th className="p-3">Provider</th>
                      <th className="p-3">Monthly Estimate</th>
                      <th className="p-3">Scaling Factor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-900/60 text-slate-300">
                    <tr>
                      <td className="p-3 font-semibold text-white">App Server (Node.js/Express)</td>
                      <td className="p-3">Google Cloud Run</td>
                      <td className="p-3 text-emerald-400 font-mono">$45 - $120</td>
                      <td className="p-3">Autoscaling based on concurrent sales users.</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">Database (PostgreSQL + PostGIS)</td>
                      <td className="p-3">Cloud SQL</td>
                      <td className="p-3 text-emerald-400 font-mono">$80 - $220</td>
                      <td className="p-3">2 vCPU, 8 GB RAM, 50 GB SSD storage.</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">Queue & Cache (Redis)</td>
                      <td className="p-3">Cloud Memorystore</td>
                      <td className="p-3 text-emerald-400 font-mono">$35 - $70</td>
                      <td className="p-3">Background scraping jobs and duplicate cache.</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">Google Places API</td>
                      <td className="p-3">Google Maps Platform</td>
                      <td className="p-3 text-emerald-400 font-mono">$200 - $600</td>
                      <td className="p-3">50,000 to 150,000 place discovery queries.</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">2GIS Data API</td>
                      <td className="p-3">2GIS UAE Service</td>
                      <td className="p-3 text-emerald-400 font-mono">$300 - $800</td>
                      <td className="p-3">Commercial building-level catalog licensing.</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-white">Generative AI (Enrichment)</td>
                      <td className="p-3">Gemini 3.8 Flash</td>
                      <td className="p-3 text-emerald-400 font-mono">$15 - $45</td>
                      <td className="p-3">Tokens for business summaries & bilingual emails.</td>
                    </tr>
                    <tr className="bg-slate-800/80 font-bold text-white">
                      <td className="p-3" colSpan={2}>Total Monthly Estimate</td>
                      <td className="p-3 text-emerald-400 font-mono" colSpan={2}>~$675 - $1,855 / month</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 10: SECURITY */}
          {activeTab === 'security' && (
            <div className="space-y-4">
              <h3 className="font-bold text-base text-white">10. Testing, Security & UAE PDPL Compliance Strategy</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <h4 className="font-bold text-emerald-400 uppercase tracking-wider">UAE Legal Framework</h4>
                  <ul className="space-y-2 text-slate-300">
                    <li><strong className="text-white">Federal Decree-Law No. 45/2021 (PDPL):</strong> Right to opt-out, suppression lists for marketing, and protection of sole proprietor personal data.</li>
                    <li><strong className="text-white">TDRA Spam & Cold Contact Guidelines:</strong> Opt-in enforcement, caller ID transparency, and business hours restrictions for sales calling.</li>
                    <li><strong className="text-white">Source Attribution:</strong> Maintaining source URLs, discovery timestamps, and license badges.</li>
                  </ul>
                </div>

                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-2">
                  <h4 className="font-bold text-cyan-400 uppercase tracking-wider">Security Architecture</h4>
                  <ul className="space-y-2 text-slate-300">
                    <li><strong className="text-white">Server-Side Secrets:</strong> Gemini, Google Maps, and 2GIS API keys never exposed to client browsers.</li>
                    <li><strong className="text-white">Pre-Export Compliance Gate:</strong> Automated verification against suppression list before any CSV download.</li>
                    <li><strong className="text-white">Immutable Audit Trail:</strong> Every export, lead assignment, and deduplication logged with user attribution.</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-400">
            Document Version: <span className="text-slate-200 font-mono">v2.4-UAE-PROD</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
          >
            Close Documentation
          </button>
        </div>

      </div>
    </div>
  );
};
