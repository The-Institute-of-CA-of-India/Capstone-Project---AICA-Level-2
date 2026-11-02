export type Emirate = 
  | 'Dubai' 
  | 'Abu Dhabi' 
  | 'Sharjah' 
  | 'Ajman' 
  | 'Ras Al Khaimah' 
  | 'Fujairah' 
  | 'Umm Al Quwain';

export type LeadStatus = 
  | 'unassigned' 
  | 'lead_created' 
  | 'in_pipeline' 
  | 'customer' 
  | 'disqualified' 
  | 'suppressed';

export type PipelineStage = 
  | 'new_lead' 
  | 'contacted' 
  | 'qualified' 
  | 'meeting_scheduled' 
  | 'proposal_sent' 
  | 'negotiation' 
  | 'won' 
  | 'lost';

export type Priority = 'low' | 'medium' | 'high' | 'urgent';

export type SourcePlatform = 
  | 'google_places' 
  | '2gis' 
  | 'uae_yellowpages' 
  | 'ded_registry' 
  | 'web_crawl' 
  | 'csv_import';

export interface BusinessCategory {
  id: string;
  nameEn: string;
  nameAr?: string;
  slug: string;
  icon: string;
  businessCount?: number;
  subcategories: string[];
}

export interface BusinessSourceRecord {
  platform: SourcePlatform;
  externalId?: string;
  sourceUrl?: string;
  discoveredAt: string;
  lastVerifiedAt: string;
  isPrimary?: boolean;
}

export interface SocialLinks {
  linkedin?: string;
  instagram?: string;
  facebook?: string;
  twitter?: string;
}

export interface Business {
  id: string;
  nameEn: string;
  nameAr?: string;
  normalizedName: string;
  category: string;
  subcategory: string;
  description: string;
  emirate: Emirate;
  city: string;
  area: string;
  streetAddress: string;
  buildingName?: string;
  latitude: number;
  longitude: number;
  websiteUrl?: string;
  primaryPhone?: string;
  normalizedPhone?: string;
  primaryEmail?: string;
  whatsappNumber?: string;
  socialLinks?: SocialLinks;
  operatingHours?: string;
  tradeLicenseNumber?: string;
  twoGisListingUrl?: string;
  googleMapsListingUrl?: string;
  buildingEntrance?: string;
  plotNumber?: string;
  sourcePlatform: SourcePlatform;
  sources: BusinessSourceRecord[];
  dateDiscovered: string;
  dateLastVerified: string;
  qualityScore: number; // 0 - 100
  crmLeadStatus: LeadStatus;
  crmLeadId?: string;
}

export interface HardSearchOptions {
  sources?: ('google_places' | '2gis')[];
  emirate?: string;
  area?: string;
  category?: string;
  searchQuery?: string;
  depth?: 'standard' | 'deep_hard_scan';
  maxResults?: number;
  autoPersist?: boolean;
}

export interface HardSearchResult {
  success: boolean;
  jobId: string;
  sourcesScanned: ('google_places' | '2gis')[];
  emiratesCovered: string[];
  totalRecordsScanned: number;
  newBusinessesAdded: number;
  duplicatesMatchedAndMerged: number;
  contactsExtracted: {
    directEmails: number;
    landlines: number;
    whatsapps: number;
    decisionMakers: number;
  };
  businesses: Business[];
  logs: string[];
  persistedToStorage: boolean;
  totalBusinessesInDatabase: number;
}

export interface DuplicateCandidate {
  id: string;
  primaryBusinessId: string;
  secondaryBusinessId: string;
  primaryName: string;
  secondaryName: string;
  confidenceScore: number; // 0 - 100
  matchCriteria: {
    nameSimilarity: number;
    phoneMatch: boolean;
    domainMatch: boolean;
    geoDistanceMeters?: number;
  };
  status: 'pending' | 'merged' | 'dismissed';
}

export interface CrmTask {
  id: string;
  leadId: string;
  title: string;
  description?: string;
  dueDate: string;
  status: 'pending' | 'completed';
  priority: Priority;
  assignedUserName: string;
}

export interface CrmActivity {
  id: string;
  leadId: string;
  type: 'call' | 'whatsapp' | 'email' | 'meeting' | 'note' | 'stage_change';
  summary: string;
  details?: string;
  timestamp: string;
  authorName: string;
}

export interface CrmContact {
  id: string;
  leadId?: string;
  businessId: string;
  businessName: string;
  fullName: string;
  jobTitle: string;
  email: string;
  phone: string;
  whatsapp?: string;
  isPrimary: boolean;
}

export interface CrmLead {
  id: string;
  businessId: string;
  businessName: string;
  category: string;
  emirate: Emirate;
  area: string;
  assignedUserId: string;
  assignedUserName: string;
  pipelineStage: PipelineStage;
  dealValueAed: number;
  expectedCloseDate: string;
  priority: Priority;
  tags: string[];
  tasks: CrmTask[];
  activities: CrmActivity[];
  contacts: CrmContact[];
  aiSummary?: string;
  aiPitchEn?: string;
  aiPitchAr?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CollectionJob {
  id: string;
  sourcePlatform: SourcePlatform;
  emirate: Emirate;
  area: string;
  category: string;
  searchQuery: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  recordsDiscovered: number;
  duplicatesDetected: number;
  newRecordsAdded: number;
  startedAt?: string;
  completedAt?: string;
  logs: string[];
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'sales_manager' | 'account_executive' | 'sdr';
  avatar: string;
  leadsAssigned: number;
  pipelineValueAed: number;
  dealsWonAed: number;
  quotaProgress: number; // percentage
}

export interface SuppressionRecord {
  id: string;
  type: 'phone' | 'email' | 'domain';
  value: string;
  reason: string;
  dateAdded: string;
}

export interface AuditLog {
  id: string;
  action: string;
  userId: string;
  userName: string;
  resourceType: string;
  details: string;
  timestamp: string;
}

export interface DailySearchConfig {
  enabled: boolean;
  frequency: 'daily' | 'twice_daily' | 'hourly';
  scheduledTime: string;
  targetEmirates: Emirate[];
  targetCategories: string[];
  sources: SourcePlatform[];
  autoExtractContacts: boolean;
  autoDeduplicate: boolean;
  autoAiEnrich: boolean;
  emailNotifications: boolean;
  notificationEmail: string;
  lastRunTimestamp?: string;
  nextRunTimestamp?: string;
}

export interface DailySearchRun {
  id: string;
  timestamp: string;
  status: 'running' | 'completed' | 'failed';
  sourceQueries: string[];
  recordsScanned: number;
  newBusinessesAdded: number;
  contactsExtracted: {
    emails: number;
    phones: number;
    whatsapps: number;
    decisionMakers: number;
  };
  duplicatesDetected: number;
  logs: string[];
}

export interface GroundingSourceChunk {
  type: 'maps' | 'web';
  title: string;
  uri: string;
  snippets?: string[];
}

export interface BusinessTraceResult {
  success: boolean;
  business: Business;
  isExisting: boolean;
  persistedToStorage: boolean;
  totalBusinessesCount: number;
  grounding: {
    model: string;
    mapsChunks: GroundingSourceChunk[];
    searchChunks: GroundingSourceChunk[];
    webSearchQueries: string[];
    mapsSummaryText: string;
    searchSummaryText: string;
    tracingMode: 'dual' | 'maps_only' | 'search_only';
    timestamp: string;
  };
  contactExtracted?: {
    name: string;
    title: string;
    phone?: string;
    email?: string;
  };
}

