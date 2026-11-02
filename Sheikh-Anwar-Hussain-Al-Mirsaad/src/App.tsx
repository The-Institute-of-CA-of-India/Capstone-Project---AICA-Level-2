/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { Sidebar, NavView } from './components/Sidebar.tsx';
import { Navbar } from './components/Navbar.tsx';
import { OverviewDashboard } from './components/OverviewDashboard.tsx';
import { BusinessExplorer } from './components/BusinessExplorer.tsx';
import { DataCollectionHub } from './components/DataCollectionHub.tsx';
import { CategoryManager } from './components/CategoryManager.tsx';
import { LocationExplorer } from './components/LocationExplorer.tsx';
import { LeadManagement } from './components/LeadManagement.tsx';
import { SalesPipelineKanban } from './components/SalesPipelineKanban.tsx';
import { ContactsDirectory } from './components/ContactsDirectory.tsx';
import { TaskFollowups } from './components/TaskFollowups.tsx';
import { AnalyticsReports } from './components/AnalyticsReports.tsx';
import { ImportExportHub } from './components/ImportExportHub.tsx';
import { TeamManagement } from './components/TeamManagement.tsx';
import { SettingsAndGovernance } from './components/SettingsAndGovernance.tsx';
import { ArchitectureDocsModal } from './components/ArchitectureDocsModal.tsx';
import { AiEnrichmentModal } from './components/AiEnrichmentModal.tsx';
import { BusinessDetailDrawer } from './components/BusinessDetailDrawer.tsx';
import { UaeGoogleMapExplorer } from './components/UaeGoogleMapExplorer.tsx';
import { StorageStatusModal } from './components/StorageStatusModal.tsx';
import { GroundedBusinessTracer } from './components/GroundedBusinessTracer.tsx';
import { batchSyncBusinessesToFirestore } from './services/firebase.ts';

import { 
  fetchBusinesses, 
  fetchCategories, 
  fetchCrmLeads, 
  fetchDuplicates, 
  fetchCollectionJobs, 
  fetchContacts, 
  fetchTeam, 
  fetchSuppressions, 
  fetchAuditLogs,
  convertToLead,
  fetchDailySearch
} from './services/api.ts';

import { 
  Business, 
  BusinessCategory, 
  CollectionJob, 
  CrmContact, 
  CrmLead, 
  DuplicateCandidate, 
  SuppressionRecord, 
  TeamMember, 
  AuditLog,
  DailySearchConfig,
  DailySearchRun
} from './types/index.ts';

export default function App() {
  const [currentView, setCurrentView] = useState<NavView>('overview');
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [categories, setCategories] = useState<BusinessCategory[]>([]);
  const [leads, setLeads] = useState<CrmLead[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[]>([]);
  const [collectionJobs, setCollectionJobs] = useState<CollectionJob[]>([]);
  const [contacts, setContacts] = useState<CrmContact[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [suppressions, setSuppressions] = useState<SuppressionRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [dailyConfig, setDailyConfig] = useState<DailySearchConfig>({
    enabled: true,
    frequency: 'daily',
    scheduledTime: '03:00 GST (Daily)',
    targetEmirates: ['Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Ras Al Khaimah', 'Fujairah', 'Umm Al Quwain'],
    targetCategories: ['Construction and contracting', 'Real estate', 'IT and software companies'],
    sources: ['google_places', '2gis', 'web_crawl', 'ded_registry'],
    autoExtractContacts: true,
    autoDeduplicate: true,
    autoAiEnrich: true,
    emailNotifications: true,
    notificationEmail: 'admin@sa-auditors.com'
  });
  const [dailyRuns, setDailyRuns] = useState<DailySearchRun[]>([]);

  // Modals and Drawers
  const [isSpecsOpen, setIsSpecsOpen] = useState(false);
  const [isStorageModalOpen, setIsStorageModalOpen] = useState(false);
  const [drawerBusiness, setDrawerBusiness] = useState<Business | null>(null);
  const [aiModalBusiness, setAiModalBusiness] = useState<Business | null>(null);

  // Global Filter / Search
  const [globalSearch, setGlobalSearch] = useState('');
  const [selectedEmirate, setSelectedEmirate] = useState('all');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const loadAllData = async () => {
    setIsRefreshing(true);
    try {
      const [
        bizRes,
        catRes,
        leadsRes,
        dupRes,
        jobsRes,
        contactsRes,
        teamRes,
        suppRes,
        auditRes,
        dailyRes
      ] = await Promise.all([
        fetchBusinesses(),
        fetchCategories(),
        fetchCrmLeads(),
        fetchDuplicates(),
        fetchCollectionJobs(),
        fetchContacts(),
        fetchTeam(),
        fetchSuppressions(),
        fetchAuditLogs(),
        fetchDailySearch()
      ]);

      if (bizRes?.businesses) {
        setBusinesses(bizRes.businesses);
        // Seamless background sync of downloaded/extracted businesses to Firestore
        batchSyncBusinessesToFirestore(bizRes.businesses).catch(() => {});
      }
      if (Array.isArray(catRes)) setCategories(catRes);
      if (leadsRes?.leads) setLeads(leadsRes.leads);
      if (dupRes?.candidates) setDuplicates(dupRes.candidates);
      if (jobsRes?.jobs) setCollectionJobs(jobsRes.jobs);
      if (contactsRes?.contacts) setContacts(contactsRes.contacts);
      if (Array.isArray(teamRes)) setTeamMembers(teamRes);
      if (suppRes?.suppressions) setSuppressions(suppRes.suppressions);
      if (auditRes?.logs) setAuditLogs(auditRes.logs);
      if (dailyRes?.config) setDailyConfig(dailyRes.config);
      if (dailyRes?.runs) setDailyRuns(dailyRes.runs);
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const handleConvertToLead = async (biz: Business) => {
    try {
      const res = await convertToLead(biz.id, {
        dealValueAed: 65000,
        assignedUserId: 'usr-1',
        priority: 'high',
        tags: [biz.emirate, biz.category.split(' ')[0]]
      });

      if (res.success) {
        showToast(`Converted "${biz.nameEn}" into active CRM Lead (AED 65,000)`);
        loadAllData();
      }
    } catch (err) {
      console.error('Failed to convert to lead:', err);
    }
  };

  const handleOpenAiEnrich = (biz: Business) => {
    setAiModalBusiness(biz);
  };

  const handleOpenAiEnrichById = (bizId: string) => {
    const biz = businesses.find(b => b.id === bizId);
    if (biz) setAiModalBusiness(biz);
  };

  const viewTitles: Record<NavView, string> = {
    overview: 'UAE Business Intelligence Overview',
    tracer: 'AI Business Tracer (Google Maps & Search Grounding)',
    explorer: 'Business Explorer & Prospecting',
    google_map: 'UAE Interactive Google Maps Geospatial Intelligence',
    daily_search: 'Daily Automated Web Discovery & Contact Search',
    collection: 'Data Collection & Discovery Engine',
    categories: 'UAE Business Categories Hierarchy',
    locations: 'UAE 7 Emirates & Free Zone Explorer',
    leads: 'CRM Lead Management',
    pipeline: 'Sales Pipeline (Kanban Board)',
    contacts: 'Verified Decision Makers & Contacts',
    tasks: 'Tasks, Follow-ups & Reminders',
    analytics: 'Analytics & Revenue Reports',
    import_export: 'Import / Export Hub (PDPL Compliant)',
    team: 'Sales Team & Territories',
    settings: 'System Governance & Compliance',
  };

  // Compute businesses grouped by Emirate for locations explorer
  const businessesByEmirate: Record<string, number> = {};
  for (const b of businesses) {
    businessesByEmirate[b.emirate] = (businessesByEmirate[b.emirate] || 0) + 1;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 dark:bg-slate-950 font-sans">
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 bg-slate-900 border border-emerald-500/40 text-emerald-300 px-4 py-2.5 rounded-xl text-xs font-semibold shadow-2xl flex items-center gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Left Sidebar */}
      <Sidebar
        currentView={currentView}
        onSelectView={setCurrentView}
        onOpenSpecsModal={() => setIsSpecsOpen(true)}
        onOpenStorageModal={() => setIsStorageModalOpen(true)}
        activeDuplicatesCount={duplicates.filter(d => d.status === 'pending').length}
      />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        
        {/* Top Header Navbar */}
        <Navbar
          currentViewTitle={viewTitles[currentView]}
          searchQuery={globalSearch}
          onSearchChange={(q) => {
            setGlobalSearch(q);
            if (currentView !== 'explorer' && currentView !== 'google_map' && q.trim()) {
              setCurrentView('explorer');
            }
          }}
          selectedEmirate={selectedEmirate}
          onEmirateChange={(em) => {
            setSelectedEmirate(em);
            if (currentView !== 'explorer' && currentView !== 'google_map') {
              setCurrentView('explorer');
            }
          }}
          onOpenSpecsModal={() => setIsSpecsOpen(true)}
          onOpenDailySearch={() => setCurrentView('daily_search')}
          onOpenStorageModal={() => setIsStorageModalOpen(true)}
          onOpenGoogleMap={() => setCurrentView('google_map')}
          onOpenTracer={() => setCurrentView('tracer')}
          onRefresh={loadAllData}
          isRefreshing={isRefreshing}
        />

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50 scrollbar-thin scrollbar-thumb-slate-800">
          
          {currentView === 'overview' && (
            <OverviewDashboard
              businesses={businesses}
              leads={leads}
              collectionJobs={collectionJobs}
              duplicatesCount={duplicates.filter(d => d.status === 'pending').length}
              onNavigate={setCurrentView}
              onOpenSpecsModal={() => setIsSpecsOpen(true)}
            />
          )}

          {currentView === 'tracer' && (
            <div className="p-6">
              <GroundedBusinessTracer
                onBusinessCreated={loadAllData}
                onSelectBusiness={(biz) => setDrawerBusiness(biz)}
                onOpenGoogleMap={() => setCurrentView('google_map')}
              />
            </div>
          )}

          {currentView === 'google_map' && (
            <div className="p-6">
              <UaeGoogleMapExplorer
                businesses={businesses}
                onSelectBusiness={(biz) => setDrawerBusiness(biz)}
                onConvertToLead={handleConvertToLead}
                selectedEmirate={selectedEmirate}
                onEmirateChange={setSelectedEmirate}
                onOpenTracer={() => setCurrentView('tracer')}
              />
            </div>
          )}

          {currentView === 'explorer' && (
            <BusinessExplorer
              businesses={businesses}
              onSelectBusiness={(biz) => setDrawerBusiness(biz)}
              onConvertToLead={handleConvertToLead}
              onEnrichWithAi={handleOpenAiEnrich}
              categories={categories}
              selectedEmirate={selectedEmirate}
              onEmirateChange={setSelectedEmirate}
              onOpenTracer={() => setCurrentView('tracer')}
            />
          )}

          {currentView === 'daily_search' && (
            <DataCollectionHub
              jobs={collectionJobs}
              onJobCompleted={loadAllData}
              categories={categories}
              dailyConfig={dailyConfig}
              dailyRuns={dailyRuns}
              initialTab="daily"
            />
          )}

          {currentView === 'collection' && (
            <DataCollectionHub
              jobs={collectionJobs}
              onJobCompleted={loadAllData}
              categories={categories}
              dailyConfig={dailyConfig}
              dailyRuns={dailyRuns}
              initialTab="targeted"
            />
          )}

          {currentView === 'categories' && (
            <CategoryManager
              categories={categories}
              onRefresh={loadAllData}
              onFilterByCategory={(catName) => {
                setCurrentView('explorer');
              }}
            />
          )}

          {currentView === 'locations' && (
            <LocationExplorer
              onSelectEmirate={(em) => {
                setSelectedEmirate(em);
                setCurrentView('explorer');
              }}
              businessesByEmirate={businessesByEmirate}
              onOpenGoogleMap={() => setCurrentView('google_map')}
            />
          )}

          {currentView === 'leads' && (
            <LeadManagement
              leads={leads}
              teamMembers={teamMembers}
              onRefresh={loadAllData}
              onOpenPipeline={() => setCurrentView('pipeline')}
            />
          )}

          {currentView === 'pipeline' && (
            <SalesPipelineKanban
              leads={leads}
              onRefresh={loadAllData}
              onSelectLead={(lead) => {
                const b = businesses.find(item => item.id === lead.businessId);
                if (b) setDrawerBusiness(b);
              }}
              onOpenAiEnrich={handleOpenAiEnrichById}
            />
          )}

          {currentView === 'contacts' && (
            <ContactsDirectory contacts={contacts} />
          )}

          {currentView === 'tasks' && (
            <TaskFollowups leads={leads} onRefresh={loadAllData} />
          )}

          {currentView === 'analytics' && (
            <AnalyticsReports
              businesses={businesses}
              leads={leads}
              teamMembers={teamMembers}
            />
          )}

          {currentView === 'import_export' && (
            <ImportExportHub onImportComplete={loadAllData} />
          )}

          {currentView === 'team' && (
            <TeamManagement teamMembers={teamMembers} />
          )}

          {currentView === 'settings' && (
            <SettingsAndGovernance
              duplicates={duplicates}
              suppressions={suppressions}
              auditLogs={auditLogs}
              onRefresh={loadAllData}
            />
          )}

        </main>
      </div>

      {/* Slide-out Business Detail Drawer */}
      <BusinessDetailDrawer
        business={drawerBusiness}
        isOpen={!!drawerBusiness}
        onClose={() => setDrawerBusiness(null)}
        onConvertToLead={(b) => {
          handleConvertToLead(b);
          setDrawerBusiness(null);
        }}
        onEnrichWithAi={(b) => {
          setDrawerBusiness(null);
          setAiModalBusiness(b);
        }}
      />

      {/* Gemini 3.8 Flash AI Lead Intel Modal */}
      <AiEnrichmentModal
        business={aiModalBusiness}
        isOpen={!!aiModalBusiness}
        onClose={() => setAiModalBusiness(null)}
        onLeadUpdated={loadAllData}
      />

      {/* Master 10-Point Technical Architecture & PRD Modal */}
      <ArchitectureDocsModal
        isOpen={isSpecsOpen}
        onClose={() => setIsSpecsOpen(false)}
      />

      {/* Cloud & Disk Storage Persistence Modal */}
      <StorageStatusModal
        isOpen={isStorageModalOpen}
        onClose={() => setIsStorageModalOpen(false)}
        onRefreshParent={loadAllData}
      />

    </div>
  );
}
