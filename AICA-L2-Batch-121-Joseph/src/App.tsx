/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { 
  Briefcase, 
  UploadCloud, 
  Users, 
  SlidersHorizontal, 
  FileText, 
  ShieldCheck, 
  Play, 
  CheckCircle2, 
  AlertCircle,
  HelpCircle,
  Sparkles,
  RefreshCw,
  Plus
} from 'lucide-react';
import { Vacancy, CandidateEvaluation, UploadedCvFile, UserSession, ScreeningResult } from './types';
import { api } from './services/api';
import { Header } from './components/Header';
import { JobCriteriaForm } from './components/JobCriteriaForm';
import { CvUploadCenter } from './components/CvUploadCenter';
import { ScreeningProgress } from './components/ScreeningProgress';
import { ShortlistReview } from './components/ShortlistReview';
import { CandidateDetailModal } from './components/CandidateDetailModal';
import { SetupInstructionsModal } from './components/SetupInstructionsModal';
import { LoginModal } from './components/LoginModal';

const DEFAULT_USER: UserSession = {
  id: 'hr-lead-01',
  name: 'Sarah Jenkins',
  email: 'sarah.jenkins@enterprise-talent.com',
  role: 'Senior Talent Acquisition Lead',
  department: 'Global Human Resources',
  token: 'jwt-default-session'
};

export default function App() {
  const [user, setUser] = useState<UserSession | null>(() => {
    const saved = localStorage.getItem('ats_hr_session');
    return saved ? JSON.parse(saved) : DEFAULT_USER;
  });

  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [activeVacancy, setActiveVacancy] = useState<Vacancy | null>(null);
  const [activeTab, setActiveTab] = useState<'criteria' | 'upload' | 'review'>('criteria');
  const [uploadedCvs, setUploadedCvs] = useState<UploadedCvFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [screeningResult, setScreeningResult] = useState<ScreeningResult | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateEvaluation | null>(null);
  const [showSetupGuide, setShowSetupGuide] = useState(false);
  const [hrAiConsent, setHrAiConsent] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Load vacancies on start
  const fetchVacancies = async () => {
    try {
      const list = await api.getVacancies();
      setVacancies(list);
      if (list.length > 0) {
        if (!activeVacancy) {
          setActiveVacancy(list[0]);
          if (list[0].results) {
            setScreeningResult(list[0].results);
          }
        } else {
          const updatedActive = list.find(v => v.id === activeVacancy.id);
          if (updatedActive) {
            setActiveVacancy(updatedActive);
            if (updatedActive.results) {
              setScreeningResult(updatedActive.results);
            }
          }
        }
      }
    } catch (e) {
      console.error('Failed to load vacancies:', e);
    } finally {
      setLoadingInitial(false);
    }
  };

  useEffect(() => {
    fetchVacancies();
  }, []);

  const handleSelectVacancy = (v: Vacancy) => {
    setActiveVacancy(v);
    setScreeningResult(v.results || null);
    if (v.results) {
      setActiveTab('review');
    } else {
      setActiveTab('criteria');
    }
  };

  const handleCreateNewVacancy = async () => {
    try {
      const newVac = await api.createVacancy({
        title: 'New Position',
        department: 'Talent Acquisition',
        description: 'Enter job specification and responsibilities...',
        criteria: {
          threshold: 90.0,
          top_n: 10,
          weights: { qualifications: 25, skills: 35, experience: 25, mandatory: 15 },
          qualifications: ["Bachelor's Degree in STEM or relevant discipline"],
          skills: ['JavaScript', 'Python', 'Problem Solving'],
          experience: { required_years: 5, domains: ['Enterprise Software'] },
          mandatory: ['Bachelor Degree', '5+ years experience']
        }
      });
      await fetchVacancies();
      setActiveVacancy(newVac);
      setScreeningResult(null);
      setActiveTab('criteria');
      showToast('Created new vacancy draft');
    } catch (err: any) {
      alert(`Error creating vacancy: ${err.message}`);
    }
  };

  const handleSaveActiveVacancy = async (updated: Partial<Vacancy>) => {
    if (!activeVacancy) return;
    try {
      const saved = await api.updateVacancy(activeVacancy.id, updated);
      setActiveVacancy(saved);
      await fetchVacancies();
      showToast('Vacancy and criteria saved successfully');
    } catch (err: any) {
      alert(`Failed to save vacancy: ${err.message}`);
    }
  };

  const handleStartScreening = async () => {
    if (!activeVacancy || uploadedCvs.length === 0) return;
    setIsProcessing(true);
    try {
      const result = await api.processScreening(
        activeVacancy.id,
        activeVacancy.criteria,
        uploadedCvs,
        hrAiConsent
      );
      setScreeningResult(result);
      await fetchVacancies();
      // Transition to Shortlist Review Tab
      setActiveTab('review');
      showToast(`Screening complete! ${result.qualifying_count} candidate(s) met the 90% threshold.`);
    } catch (err: any) {
      alert(`Screening processing error in Python backend: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const showToast = (msg: string) => {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 4000);
  };

  const handleUpdateCandidateDecision = (id: string, approved: boolean, notes: string) => {
    if (!screeningResult) return;
    const updatedCandidates = screeningResult.ranked_candidates.map(c => {
      if (c.id === id) {
        return { ...c, hr_approved: approved, hr_notes: notes };
      }
      return c;
    });
    setScreeningResult({
      ...screeningResult,
      ranked_candidates: updatedCandidates
    });
    showToast(`Updated decision for candidate.`);
  };

  if (!user) {
    return (
      <LoginModal
        onLoginSuccess={(u) => {
          setUser(u);
          localStorage.setItem('ats_hr_session', JSON.stringify(u));
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-slate-800 antialiased selection:bg-emerald-500 selection:text-white">
      {/* Top Navigation & Brand Header */}
      <Header
        vacancies={vacancies}
        activeVacancy={activeVacancy}
        onSelectVacancy={handleSelectVacancy}
        onCreateNewVacancy={handleCreateNewVacancy}
        user={user}
        onLogout={() => {
          setUser(null);
          localStorage.removeItem('ats_hr_session');
        }}
        onOpenSetupGuide={() => setShowSetupGuide(true)}
      />

      {/* Main Workflow Tabs Bar */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <nav className="flex space-x-1 sm:space-x-8" aria-label="ATS Pipeline Steps">
              {/* Step 1: Job Description & Criteria */}
              <button
                type="button"
                onClick={() => setActiveTab('criteria')}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 text-xs font-semibold transition-colors ${
                  activeTab === 'criteria'
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  activeTab === 'criteria' ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'
                }`}>
                  1
                </div>
                <span>Job Description & 100% Criteria</span>
              </button>

              {/* Step 2: Upload CVs & Document Center */}
              <button
                type="button"
                onClick={() => setActiveTab('upload')}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 text-xs font-semibold transition-colors ${
                  activeTab === 'upload'
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  activeTab === 'upload' ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'
                }`}>
                  2
                </div>
                <span>CV Batch Ingestion ({uploadedCvs.length})</span>
              </button>

              {/* Step 3: Shortlist Review & Export */}
              <button
                type="button"
                onClick={() => setActiveTab('review')}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 text-xs font-semibold transition-colors ${
                  activeTab === 'review'
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  activeTab === 'review' ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'
                }`}>
                  3
                </div>
                <span>
                  Shortlist & Assessment Results
                  {screeningResult && ` (${screeningResult.qualifying_count})`}
                </span>
              </button>
            </nav>

            {/* Quick Status Kicker */}
            <div className="hidden lg:flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Deterministic Python Evaluator</span>
              </span>
              <span aria-hidden="true">·</span>
              <span>Default Threshold: 90%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Action Notification Toast */}
      {actionMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-xl border border-slate-700 flex items-center gap-3 text-xs animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loadingInitial ? (
          <div className="text-center py-20 text-slate-500 text-sm">
            Initializing Enterprise ATS Screening System...
          </div>
        ) : isProcessing ? (
          <ScreeningProgress totalCount={uploadedCvs.length} />
        ) : !activeVacancy ? (
          <div className="text-center py-16 bg-white rounded-xl border border-slate-200 p-8">
            <Briefcase className="w-12 h-12 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-800">No Active Vacancy Selected</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Please choose a saved role or create a new vacancy specification to begin CV screening.
            </p>
            <button
              onClick={handleCreateNewVacancy}
              className="mt-4 px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 transition-colors"
            >
              Create First Vacancy
            </button>
          </div>
        ) : (
          <>
            {activeTab === 'criteria' && (
              <JobCriteriaForm
                vacancy={activeVacancy}
                onSaveVacancy={handleSaveActiveVacancy}
                onProceedToUpload={() => setActiveTab('upload')}
              />
            )}

            {activeTab === 'upload' && (
              <CvUploadCenter
                uploadedFiles={uploadedCvs}
                onFilesUpdated={setUploadedCvs}
                hrAiConsent={hrAiConsent}
                onAiConsentChange={setHrAiConsent}
                onStartScreening={handleStartScreening}
                isProcessing={isProcessing}
              />
            )}

            {activeTab === 'review' && (
              screeningResult ? (
                <ShortlistReview
                  vacancy={activeVacancy}
                  screeningResult={screeningResult}
                  onOpenCandidateDetail={(cand) => setSelectedCandidate(cand)}
                  onRefreshVacancy={fetchVacancies}
                />
              ) : (
                <div className="text-center py-16 bg-white rounded-xl border border-slate-200 p-8 space-y-4">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto text-slate-500">
                    <Users className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">No Screening Results for this Vacancy Yet</h3>
                    <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
                      To generate a ranked shortlist against the 90% threshold, upload candidate CVs and start the Python screening engine.
                    </p>
                  </div>
                  <button
                    onClick={() => setActiveTab('upload')}
                    className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors inline-flex items-center gap-2 shadow-xs"
                  >
                    <UploadCloud className="w-4 h-4" />
                    <span>Upload CVs to Screen</span>
                  </button>
                </div>
              )
            )}
          </>
        )}
      </main>

      {/* Candidate Deep Inspection Modal */}
      {selectedCandidate && (
        <CandidateDetailModal
          candidate={selectedCandidate}
          onClose={() => setSelectedCandidate(null)}
          onUpdateCandidateDecision={handleUpdateCandidateDecision}
        />
      )}

      {/* Architecture & Setup Guide Modal */}
      <SetupInstructionsModal
        isOpen={showSetupGuide}
        onClose={() => setShowSetupGuide(false)}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span>ATS CV Shortlisting</span>
            <span aria-hidden="true">·</span>
            <span>Enterprise Talent Acquisition Engine</span>
          </div>
          <div className="flex items-center gap-3 text-slate-400 text-[11px]">
            <span>Full work authorization & GDPR compliant</span>
            <span aria-hidden="true">·</span>
            <span>Final hiring decisions remain with HR</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
