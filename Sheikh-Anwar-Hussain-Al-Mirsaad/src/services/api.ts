import { 
  Business, 
  BusinessCategory, 
  CollectionJob, 
  CrmLead, 
  DuplicateCandidate, 
  Emirate, 
  SuppressionRecord, 
  TeamMember, 
  AuditLog,
  CrmContact,
  DailySearchConfig,
  DailySearchRun,
  BusinessTraceResult,
  HardSearchOptions,
  HardSearchResult
} from '../types/index.ts';

export async function fetchHealth() {
  const res = await fetch('/api/health');
  return res.json();
}

export async function fetchBusinesses(filters?: {
  emirate?: string;
  area?: string;
  category?: string;
  search?: string;
  minScore?: number;
  source?: string;
  hasPhone?: boolean;
  hasWebsite?: boolean;
  crmStatus?: string;
}): Promise<{ total: number; businesses: Business[] }> {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.emirate) params.set('emirate', filters.emirate);
    if (filters.area) params.set('area', filters.area);
    if (filters.category) params.set('category', filters.category);
    if (filters.search) params.set('search', filters.search);
    if (filters.minScore) params.set('minScore', filters.minScore.toString());
    if (filters.source) params.set('source', filters.source);
    if (filters.hasPhone) params.set('hasPhone', 'true');
    if (filters.hasWebsite) params.set('hasWebsite', 'true');
    if (filters.crmStatus) params.set('crmStatus', filters.crmStatus);
  }
  const res = await fetch(`/api/businesses?${params.toString()}`);
  return res.json();
}

export async function fetchBusinessDetails(id: string) {
  const res = await fetch(`/api/businesses/${id}`);
  return res.json();
}

export async function convertToLead(businessId: string, data: {
  dealValueAed: number;
  assignedUserId: string;
  priority: string;
  tags?: string[];
}) {
  const res = await fetch(`/api/businesses/${businessId}/convert-to-lead`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function fetchDuplicates(): Promise<{ total: number; candidates: DuplicateCandidate[] }> {
  const res = await fetch('/api/duplicates');
  return res.json();
}

export async function mergeDuplicate(duplicateId: string, primaryId: string, secondaryId: string) {
  const res = await fetch('/api/duplicates/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ duplicateId, primaryId, secondaryId })
  });
  return res.json();
}

export async function dismissDuplicate(duplicateId: string) {
  const res = await fetch('/api/duplicates/dismiss', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ duplicateId })
  });
  return res.json();
}

export async function fetchCategories(): Promise<BusinessCategory[]> {
  const res = await fetch('/api/categories');
  return res.json();
}

export async function createCategory(data: Partial<BusinessCategory>) {
  const res = await fetch('/api/categories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function fetchEmirates() {
  const res = await fetch('/api/emirates');
  return res.json();
}

export async function fetchCollectionJobs(): Promise<{ jobs: CollectionJob[] }> {
  const res = await fetch('/api/collection-jobs');
  return res.json();
}

export async function runCollectionJob(data: {
  sourcePlatform: string;
  emirate: string;
  area: string;
  category: string;
  searchQuery?: string;
  maxResults?: number;
}) {
  const res = await fetch('/api/collection-jobs/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function fetchCrmLeads(filters?: {
  stage?: string;
  assignedUserId?: string;
  priority?: string;
}): Promise<{ total: number; leads: CrmLead[] }> {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.stage) params.set('stage', filters.stage);
    if (filters.assignedUserId) params.set('assignedUserId', filters.assignedUserId);
    if (filters.priority) params.set('priority', filters.priority);
  }
  const res = await fetch(`/api/crm/leads?${params.toString()}`);
  return res.json();
}

export async function updateCrmLead(leadId: string, data: Partial<CrmLead>) {
  const res = await fetch(`/api/crm/leads/${leadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function createLeadTask(leadId: string, task: {
  title: string;
  dueDate: string;
  priority: string;
  description?: string;
}) {
  const res = await fetch(`/api/crm/leads/${leadId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task)
  });
  return res.json();
}

export async function updateLeadTask(leadId: string, taskId: string, status: 'pending' | 'completed') {
  const res = await fetch(`/api/crm/leads/${leadId}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  return res.json();
}

export async function createLeadActivity(leadId: string, activity: {
  type: string;
  summary: string;
  details?: string;
}) {
  const res = await fetch(`/api/crm/leads/${leadId}/activities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(activity)
  });
  return res.json();
}

export async function fetchContacts(): Promise<{ total: number; contacts: CrmContact[] }> {
  const res = await fetch('/api/contacts');
  return res.json();
}

export async function fetchTeam(): Promise<TeamMember[]> {
  const res = await fetch('/api/team');
  return res.json();
}

export async function fetchAnalytics() {
  const res = await fetch('/api/analytics');
  return res.json();
}

export async function enrichWithAi(businessId: string, customAngle?: string) {
  const res = await fetch('/api/ai/enrich-lead', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ businessId, customAngle })
  });
  return res.json();
}

export async function importCsvBusinesses(rows: any[], defaults?: { emirate?: string; category?: string }) {
  const res = await fetch('/api/import/csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rows,
      defaultEmirate: defaults?.emirate || 'Dubai',
      defaultCategory: defaults?.category || 'General Trading'
    })
  });
  return res.json();
}

export async function fetchSuppressions(): Promise<{ total: number; suppressions: SuppressionRecord[] }> {
  const res = await fetch('/api/compliance/suppression');
  return res.json();
}

export async function addSuppression(data: { type: string; value: string; reason?: string }) {
  const res = await fetch('/api/compliance/suppression', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function deleteSuppression(id: string) {
  const res = await fetch(`/api/compliance/suppression/${id}`, {
    method: 'DELETE'
  });
  return res.json();
}

export async function fetchAuditLogs(): Promise<{ total: number; logs: AuditLog[] }> {
  const res = await fetch('/api/audit-logs');
  return res.json();
}

export async function fetchMasterSpecs(): Promise<{ markdown: string }> {
  const res = await fetch('/api/specs');
  return res.json();
}

export async function fetchDailySearch(): Promise<{
  config: DailySearchConfig;
  runs: DailySearchRun[];
  totalDiscoveredSoFar: number;
  totalVerifiedContacts: number;
}> {
  const res = await fetch('/api/daily-search');
  return res.json();
}

export async function updateDailySearchConfig(config: Partial<DailySearchConfig>) {
  const res = await fetch('/api/daily-search/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return res.json();
}

export async function runDailySearchNow(params?: {
  targetEmirate?: string;
  targetCategory?: string;
}) {
  const res = await fetch('/api/daily-search/run-now', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params || {})
  });
  return res.json();
}

export async function fetchStorageStatus(): Promise<{
  status: string;
  mode: string;
  storageFile: string;
  fileExists: boolean;
  fileSizeKb: number;
  lastSavedAt: string | null;
  firestoreDatabaseId: string;
  cloudStorageTarget: string;
  counts: {
    businesses: number;
    leads: number;
    contacts: number;
    dailyRuns: number;
    suppressions: number;
    auditLogs: number;
  };
}> {
  const res = await fetch('/api/storage/status');
  return res.json();
}

export async function persistStorageNow() {
  const res = await fetch('/api/storage/persist-now', {
    method: 'POST'
  });
  return res.json();
}

export async function traceBusinessWithGrounding(params: {
  query: string;
  emirate?: string;
  category?: string;
  tracingMode?: 'dual' | 'maps_only' | 'search_only';
  saveToDatabase?: boolean;
}): Promise<BusinessTraceResult> {
  const res = await fetch('/api/trace/business', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ error: 'Failed to trace business' }));
    throw new Error(errorData.error || `Error ${res.status}: Failed to trace business`);
  }
  return res.json();
}

export async function fetchTracePresets(): Promise<{
  presets: {
    name: string;
    query: string;
    emirate: string;
    category: string;
    area: string;
  }[];
}> {
  const res = await fetch('/api/trace/presets');
  return res.json();
}

export async function traceBatchBusinesses(queries: string[], emirate?: string) {
  const res = await fetch('/api/trace/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ queries, emirate })
  });
  return res.json();
}

export async function runHardSearch(options: HardSearchOptions = {}): Promise<HardSearchResult> {
  const res = await fetch('/api/hard-search/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ error: 'Hard search failed' }));
    throw new Error(errorData.error || `Error ${res.status}: Failed to execute hard search on Google Maps & 2GIS`);
  }
  return res.json();
}

