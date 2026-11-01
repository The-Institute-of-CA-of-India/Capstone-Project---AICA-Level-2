# UAE Business Intelligence, Lead Generation & CRM SaaS Platform
## Master Technical Architecture & Product Requirements Document (PRD)

---

### 1. Product Requirements Document (PRD)

#### 1.1 Executive Summary
**Al-Mirsaad (المرصاد)** is an enterprise-grade UAE Business Data Intelligence, Lead Generation, and Sales CRM SaaS platform. It enables sales, business development, and marketing teams to discover, verify, and prospect licensed commercial enterprises across all seven Emirates of the United Arab Emirates (Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, Fujairah, and Umm Al Quwain). 

The platform continuously collects authorized business information from legitimate public directories, Google Places API, 2GIS API, authorized registry feeds, and customer-uploaded files, executing automated entity normalization and deduplication. Qualified business records seamlessly transition into a full-featured sales CRM with custom Kanban pipelines, task management, WhatsApp/Email outreach assistance, and Gemini AI-powered business summarization and Arabic/English outreach generation.

#### 1.2 Target User Personas
1. **B2B Sales Development Representatives (SDRs):** Target new commercial clients in specific UAE zones (e.g., Business Bay, DIFC, Musaffah, Al Quoz) filtered by industry, verified phone, and digital presence.
2. **Sales Managers & Directors:** Monitor sales rep productivity, assign leads by territory or industry vertical, inspect deal pipeline velocity in AED, and audit compliance.
3. **Marketing Operations & Growth Teams:** Build segmented prospect lists for multi-channel outreach, check suppression lists against the UAE Telecommunications and Digital Government Regulatory Authority (TDRA) opt-out directives, and ensure PDPL compliance.
4. **Data Engineers / Admins:** Configure data collection pipelines from Google Places, 2GIS, and DED (Department of Economy and Tourism) directories, tune fuzzy deduplication thresholds, and manage role-based access control.

#### 1.3 Key Functional Requirements
- **UAE Geographic Coverage:** Native modeling of 7 Emirates, 50+ major commercial zones, free zones (DIFC, DMCC, ADGM, DAFZA, JAFZA, SAIF Zone), and geographic coordinates.
- **Multi-Source Ingestion & Provenance:** Ingest business attributes from Google Places, 2GIS, Public UAE Registries, Company Web Crawl, and CSV/Excel uploads while maintaining field-level source provenance and discovery timestamps.
- **Intelligent Deduplication:** Multi-pass fuzzy matching (Levenshtein + token sort ratio) over normalized Arabic/English company names, standardized E.164 phone numbers (+971), domain URLs, and geographic proximity (<150m radius).
- **Data Quality Scoring:** Automated 0-100% completeness metric assessing presence of trade name, contact email, mobile/landline, website, social handles, physical location, and trade license status.
- **Sales CRM Pipeline:** 7-stage sales funnel (New Lead → Contacted → Qualified → Meeting Scheduled → Proposal Sent → Negotiation → Won / Lost), deal valuations in AED, activity logging, and task reminders.
- **UAE PDPL & Compliance Engine:** Built-in suppression list (Do-Not-Call/Do-Not-Email), consent tracking, source caching policy enforcement (30-day Google Places caching rule), and audit trail.
- **AI-Powered Lead Enrichment:** Server-side Gemini 3.8 Flash engine to generate instant business summaries, ICP fit scores, and bilingual (English/Arabic) cold outreach emails.

---

### 2. System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
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
| - CRM Leads & Deals     |  | - Deduplication Tasks   |  | - UAE Public Directories|
| - Audit & Provenance    |  | - Cache Layer (30-day)  |  | - Google GenAI SDK      |
| - Spatial Index (GIST)  |  | - Rate-limit state      |  |   (Gemini 3.8 Flash)    |
+-------------------------+  +-------------------------+  +-------------------------+
```

---

### 3. Comparison of Data-Source Options and Restrictions

| Data Source | Type | Strengths for UAE | Limitations & Licensing Restrictions | Compliance & Retention Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Google Places API (Place Details / Nearby Search)** | Official REST API | High accuracy for retail, hospitality, consumer businesses; verified coordinates and operating hours across Dubai & Abu Dhabi. | Google Maps Platform Terms prohibit permanently caching Place Details (except Place ID and latitude/longitude up to 30 days for refresh). Attribution required. | Store Place ID for re-fetching. Auto-refresh cache after 30 days. Display "Powered by Google" where applicable. |
| **2GIS UAE Data API** | Authorized Commercial API | Industry-leading UAE accuracy for industrial zones (Al Quoz, Musaffah, Sharjah Industrial Area); building-level entrance coordinates. | Commercial license required; strict monthly call quotas and redistribution restrictions. | Maintain 2GIS license identifier; verify permitted resale/CRM use; refresh every 60 days. |
| **UAE Federal & Local Economic Departments (DED/DET)** | Public Open Data / Official Portals | Official commercial license numbers, legal entity type (LLC, Sole Establishment, Free Zone), verified trade activity codes. | Typically updated in periodic batches; rarely includes direct personal email of decision makers. | Permitted under UAE Open Government Data frameworks for business verification and commercial reference. |
| **Direct Company Website Crawling** | Web Scraper (Permitted) | Primary source for official info@ and sales@ emails, executive names, service offerings, and social media links. | Strict obedience to `robots.txt`, crawl rate limits, and UAE copyright laws. Must bypass no anti-bot or CAPTCHA mechanisms. | Store crawl timestamp, target URL, and respect `meta name="robots" content="noindex"`. |
| **User CSV / Excel Uploads** | First-Party Ingestion | Allows customer to bring existing trade show lists, chamber of commerce directories, or internal CRM files. | Data quality varies; risk of dirty data, inconsistent phone formats, and duplicates. | Run automated field mapping, phone normalization to E.164 (+971), and duplicate pre-screening before commit. |

---

### 4. Normalized PostgreSQL Database Schema

```sql
-- Core Organizations (Multi-tenant Workspace)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    trade_license_number VARCHAR(100),
    country_code VARCHAR(2) DEFAULT 'AE',
    plan_tier VARCHAR(50) DEFAULT 'pro',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Users & Organization Members (RBAC)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'sdr' CHECK (role IN ('admin', 'manager', 'account_executive', 'sdr', 'auditor')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE organization_members (
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    member_role VARCHAR(50) DEFAULT 'member',
    PRIMARY KEY (organization_id, user_id)
);

-- Categories & Subcategories Hierarchy
CREATE TABLE business_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID REFERENCES business_categories(id) ON DELETE SET NULL,
    name_en VARCHAR(150) NOT NULL,
    name_ar VARCHAR(150),
    slug VARCHAR(150) UNIQUE NOT NULL,
    icon VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Normalized Businesses (Master Golden Record)
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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
    operating_hours JSONB,
    social_links JSONB,
    quality_score INTEGER DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100),
    crm_lead_status VARCHAR(50) DEFAULT 'unassigned' CHECK (crm_lead_status IN ('unassigned', 'lead_created', 'in_pipeline', 'customer', 'disqualified', 'suppressed')),
    date_discovered TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_last_verified TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Business Category Links (Many-to-Many)
CREATE TABLE business_category_links (
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    category_id UUID REFERENCES business_categories(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (business_id, category_id)
);

-- Business Source Records (Field-level Provenance)
CREATE TABLE business_source_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    source_platform VARCHAR(50) NOT NULL CHECK (source_platform IN ('google_places', '2gis', 'uae_yellowpages', 'ded_registry', 'web_crawl', 'csv_import')),
    external_id VARCHAR(255),
    source_url TEXT,
    raw_payload JSONB,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cache_expires_at TIMESTAMP WITH TIME ZONE
);

-- Duplicate Detection Candidates & Merge History
CREATE TABLE duplicate_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    secondary_business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    confidence_score NUMERIC(5,2) NOT NULL,
    match_criteria JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'auto_merged', 'manually_merged', 'rejected')),
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- CRM Leads & Pipeline
CREATE TABLE crm_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    pipeline_stage VARCHAR(50) DEFAULT 'new_lead' CHECK (pipeline_stage IN ('new_lead', 'contacted', 'qualified', 'meeting_scheduled', 'proposal_sent', 'negotiation', 'won', 'lost')),
    deal_value_aed NUMERIC(15,2) DEFAULT 0,
    expected_close_date DATE,
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    tags TEXT[],
    ai_summary TEXT,
    ai_pitch_draft TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- CRM Tasks & Follow-ups
CREATE TABLE crm_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES crm_leads(id) ON DELETE CASCADE,
    assigned_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(30) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'overdue')),
    priority VARCHAR(20) DEFAULT 'medium',
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- CRM Activities & Call Logs
CREATE TABLE crm_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES crm_leads(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) CHECK (activity_type IN ('call', 'whatsapp', 'email', 'meeting', 'note', 'stage_change')),
    summary VARCHAR(255) NOT NULL,
    details TEXT,
    activity_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Data Collection Jobs
CREATE TABLE collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_platform VARCHAR(50) NOT NULL,
    emirate VARCHAR(50) NOT NULL,
    area VARCHAR(150),
    category_id UUID REFERENCES business_categories(id),
    search_query VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    records_discovered INTEGER DEFAULT 0,
    duplicates_detected INTEGER DEFAULT 0,
    new_records_added INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- UAE PDPL Compliance Suppression List
CREATE TABLE suppression_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier_type VARCHAR(50) CHECK (identifier_type IN ('phone', 'email', 'domain')),
    identifier_value VARCHAR(255) NOT NULL UNIQUE,
    reason VARCHAR(255) DEFAULT 'User requested opt-out under UAE PDPL',
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- System Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    ip_address VARCHAR(45),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Speed & Spatial Queries
CREATE INDEX idx_businesses_emirate ON businesses(emirate);
CREATE INDEX idx_businesses_normalized_name ON businesses(normalized_name);
CREATE INDEX idx_businesses_normalized_phone ON businesses(normalized_phone);
CREATE INDEX idx_businesses_quality_score ON businesses(quality_score);
CREATE INDEX idx_crm_leads_stage ON crm_leads(pipeline_stage);
CREATE INDEX idx_crm_leads_assigned ON crm_leads(assigned_user_id);
```

---

### 5. API Endpoint Specifications

| Method | Endpoint | Description | Request Body / Query Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/businesses` | Query discovered UAE businesses with multi-faceted filtering. | `?emirate=Dubai&area=Business+Bay&category=Real+Estate&search=tower&minScore=50&hasPhone=true` |
| `GET` | `/api/businesses/:id` | Fetch full details, source records, duplicate history, and CRM link. | None |
| `POST` | `/api/businesses/:id/convert-to-lead` | Convert a discovered business record into a CRM lead. | `{ "dealValue": 45000, "priority": "high", "assignedUserId": "u1" }` |
| `GET` | `/api/duplicates` | Retrieve candidate duplicate pairs for manual or auto merge. | `?status=pending&minConfidence=75` |
| `POST` | `/api/duplicates/merge` | Merge duplicate candidate into master record. | `{ "primaryId": "b1", "secondaryId": "b2", "fieldPicks": { "website": "b2" } }` |
| `GET` | `/api/collection-jobs` | List background/scheduled scraping and API jobs. | `?limit=20` |
| `POST` | `/api/collection-jobs/run` | Trigger a new live collection job. | `{ "source": "google_places", "emirate": "Dubai", "area": "Al Quoz", "category": "Automobile" }` |
| `GET` | `/api/crm/leads` | Retrieve leads grouped by pipeline stage or tabular list. | `?stage=all&assignedTo=me` |
| `PATCH` | `/api/crm/leads/:id` | Update lead pipeline stage, priority, deal value, or notes. | `{ "pipelineStage": "meeting_scheduled", "dealValue": 60000 }` |
| `POST` | `/api/crm/leads/:id/tasks` | Create a task or follow-up reminder. | `{ "title": "Follow up with CEO", "dueDate": "2026-11-05", "priority": "high" }` |
| `POST` | `/api/crm/leads/:id/activities` | Log a phone call, WhatsApp conversation, or meeting note. | `{ "type": "call", "summary": "Discussed contract tier", "details": "Will send proposal" }` |
| `POST` | `/api/ai/enrich-lead` | Server-side Gemini 3.8 Flash lead enrichment and pitch generation. | `{ "businessId": "b1", "targetLanguage": "both" }` |
| `POST` | `/api/import/csv` | Ingest CSV data with header mapping and duplicate pre-screen. | Multipart / JSON array with mapping definition |
| `GET` | `/api/export` | Download filtered leads/businesses (CSV format) after PDPL suppression check. | `?format=csv&emirate=Dubai&suppressOptOuts=true` |
| `GET` | `/api/analytics` | High-level metrics, Emirate breakdown, stage velocity, deal pipeline value. | None |
| `GET` | `/api/compliance/suppression` | List and manage suppressed phone numbers and emails. | `?type=phone` |

---

### 6. Page-by-Page UI/UX Plan

1. **Overview Dashboard:** Executive mission control. Real-time KPI counters (Total Permitted Records, Verified Contacts, Active CRM Leads, Total Pipeline Value in AED). UAE Emirate distribution bar visualizer, 7-stage conversion funnel, recent collection jobs ticker, and upcoming tasks widget.
2. **Business Explorer:** High-density data grid & card layout. Granular sidebar filters (Emirate, Neighborhood, Category, Verification Status, Phone/Email availability, Data Completeness slider). Direct "WhatsApp", "Call", "Inspect Sources", "Enrich with AI", and "Convert to Lead" actions.
3. **Data Collection Hub:** Multi-source discovery launcher. Source selection (Google Places API, 2GIS, UAE YellowPages, Web Crawl, CSV), parameter selector (Emirate, Area, Radius, Category, Max limit). Live simulated/actual progress tracker with real-time logs, discovered count, deduplication rate, and error handling.
4. **Business Categories:** Hierarchical management tree of UAE industry sectors and specialized subcategories (e.g., Construction → MEP, Civil Works, Interior Fitout). Category edit modal and business count badges.
5. **UAE Location Explorer:** Interactive Emirate atlas. Visual breakdown of all 7 Emirates with neighborhood counts (Business Bay, Downtown, DIFC, Musaffah, Deira, Al Majaz, etc.), business density, and average completeness score.
6. **Lead Management:** Tabular CRM list of qualified sales prospects. Status badges, lead owner assignment, priority indicators, last activity date, tags, and bulk operations.
7. **Sales Pipeline (Kanban):** Drag-and-drop or column transition board across 7 stages: *New Lead → Contacted → Qualified → Meeting Scheduled → Proposal Sent → Negotiation → Won / Lost*. Shows individual deal values and stage total values in AED.
8. **Contacts & Customers:** Dedicated directory of key executive decision makers, phone extensions, direct emails, LinkedIn links, and WhatsApp direct links.
9. **Tasks & Follow-ups:** Calendar and list view of upcoming sales deadlines, discovery calls, contract reviews, and scheduled follow-ups with priority indicators.
10. **Analytics & Reports:** Deep analytical insights: Emirate market penetration, category distribution, SDR conversion leaderboard, win/loss reasons, and monthly deal forecasts.
11. **Import / Export Hub:** CSV/Excel file dropzone with column auto-mapping, duplicate preview modal, and compliant CSV export generator with automatic exclusion of suppressed records.
12. **Team Management:** Team member directory, role assignment (Admin, Manager, SDR, AE), active deals count, and monthly quota progress.
13. **Settings & Governance:** UAE Personal Data Protection Law compliance dashboard, suppression list manager, Google/2GIS API key configuration, data retention policies, and complete immutable audit log.
14. **System Architecture & Specs Viewer:** Embedded modal and documentation hub rendering the complete technical specification, PostgreSQL schema DDL, system diagram, and API guide.

---

### 7. Development Roadmap with Milestones

```
[Phase 1: Architecture & Feasibility] (Days 1 - 7)
├── Finalize PRD, Compliance Governance (UAE PDPL & TDRA)
├── Database Schema Architecture & PostGIS Spatial Indexes
└── UI Design System & Component Library Setup

[Phase 2: MVP Core Platform] (Days 8 - 21)
├── Data Models & In-Memory / PostgreSQL Stores
├── Ingestion Engine (Google Places, 2GIS, UAE YellowPages, CSV)
├── Deduplication Engine (Fuzzy Matching + E.164 Phone Normalization)
├── Business Explorer with 7 Emirates & 17 Categories
└── Basic 7-Stage Sales CRM Pipeline with Deal Values

[Phase 3: Advanced CRM & Intelligence] (Days 22 - 35)
├── Kanban Drag-and-Drop Pipeline & Stage Transitions
├── Tasks, Reminders, Activity Logging & Contact Management
├── Gemini 3.8 Flash AI Integration (Lead Scoring & Bilingual Outreach)
└── Advanced Filter Builder, Saved Searches & Export Engine

[Phase 4: Enterprise Automation & Governance] (Days 36 - 50)
├── Scheduled Background Ingestion Workers & Redis Queues
├── UAE PDPL Suppression List Enforcement & Compliance Auditing
├── Team Roles, Quota Tracking & Executive Analytics
└── Cloud Deployment (Cloud Run, Cloud SQL, Redis) & Monitoring
```

---

### 8. Realistic MVP Scope

The MVP encompasses:
- Complete coverage of all 7 Emirates (Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, Fujairah, Umm Al Quwain) and 40+ commercial zones.
- Comprehensive seed and dynamic ingestion covering 17 industry verticals.
- Multi-source ingestion simulation and live collector with provenance tracking.
- Automated fuzzy deduplication engine displaying match confidence scores and field-level merge controls.
- Full-featured 7-stage Sales CRM with Kanban board, deal values in AED, activity logs, and follow-up tasks.
- Gemini 3.8 Flash AI enrichment generating company summaries and bilingual (EN/AR) pitch emails.
- CSV/Excel upload with field mapping and compliant CSV export.
- UAE PDPL suppression list and data governance settings.

---

### 9. Estimated Infrastructure & Third-Party API Cost Categories

| Cost Category | Service Provider | Monthly Estimate (USD) | Notes |
| :--- | :--- | :--- | :--- |
| **Compute / API Hosting** | Google Cloud Run (Autoscaling) | $45 - $120 | Scale-to-zero in off-peak hours; 2-4 vCPU, 4-8 GB RAM. |
| **Managed Database** | Cloud SQL (PostgreSQL 16 + PostGIS) | $80 - $220 | db-custom-2-7680, 50 GB SSD, automated backups. |
| **Caching & Queues** | Google Cloud Memorystore (Redis) | $35 - $70 | Background job broker and deduplication cache. |
| **Google Places API** | Google Maps Platform | $200 - $600 | Based on 50,000 - 150,000 Place Searches & Details / month. |
| **2GIS UAE API** | 2GIS Commercial Service | $300 - $800 | B2B commercial catalog licensing for UAE cities. |
| **Generative AI** | Google Gemini 3.8 Flash API | $15 - $45 | High throughput, cost-efficient for lead summarization & drafts. |
| **Object Storage & CDN** | Google Cloud Storage | $10 - $25 | CSV backups, exported lists, static assets. |
| **Total Estimated Run Rate**| | **~$685 - $1,880 / mo** | Scales linearly with ingestion volume and sales seat count. |

---

### 10. Testing, Security & Deployment Strategy

- **Security & Privacy:**
  - TLS 1.3 enforced for all client-server communication.
  - API keys (Google Places, 2GIS, Gemini) kept strictly server-side in environment variables.
  - Role-Based Access Control (RBAC) preventing unauthorized lead export or suppression modifications.
  - UAE PDPL data protection compliance checks on every export.
- **Testing Strategy:**
  - Unit tests for phone normalization (standardizing +971 local 04, 02, 06, 050, 054, 058 formats to E.164).
  - Fuzzy string matching regression tests (verifying "Al Futtaim Group LLC" merges with "Al-Futtaim Group").
  - API integration tests validating pagination, filter correctness, and pipeline stage transitions.
- **Deployment Strategy:**
  - Containerized with Docker.
  - Hosted on Google Cloud Run with continuous deployment.
  - Healthcheck endpoint at `/api/health`.
