import { JobCriteria, ScreeningResult, Vacancy, UploadedCvFile, UserSession } from '../types';

export const api = {
  // Authentication
  async login(email: string, password: string): Promise<UserSession> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) throw new Error('Authentication failed');
    const data = await res.json();
    return data.user;
  },

  // Vacancies
  async getVacancies(): Promise<Vacancy[]> {
    const res = await fetch('/api/vacancies');
    if (!res.ok) throw new Error('Failed to fetch vacancies');
    return res.json();
  },

  async createVacancy(vacancy: Partial<Vacancy>): Promise<Vacancy> {
    const res = await fetch('/api/vacancies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(vacancy)
    });
    if (!res.ok) throw new Error('Failed to create vacancy');
    return res.json();
  },

  async updateVacancy(id: string, updates: Partial<Vacancy>): Promise<Vacancy> {
    const res = await fetch(`/api/vacancies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    if (!res.ok) throw new Error('Failed to update vacancy');
    return res.json();
  },

  async deleteVacancy(id: string): Promise<void> {
    const res = await fetch(`/api/vacancies/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete vacancy');
  },

  // Upload Files / Folders
  async uploadCvs(files: File[]): Promise<UploadedCvFile[]> {
    const formData = new FormData();
    for (const f of files) {
      formData.append('files', f);
    }
    const res = await fetch('/api/screening/upload', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Failed to upload CV files');
    const data = await res.json();
    return data.files;
  },

  // Load realistic sample data
  async loadSampleData(): Promise<UploadedCvFile[]> {
    const res = await fetch('/api/screening/sample-data');
    if (!res.ok) throw new Error('Failed to load sample dataset');
    const data = await res.json();
    return data.files;
  },

  // Process screening with Python backend
  async processScreening(
    vacancyId: string,
    criteria: JobCriteria,
    cvs: UploadedCvFile[],
    hrAiConsent: boolean
  ): Promise<ScreeningResult> {
    const res = await fetch('/api/screening/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vacancyId,
        criteria,
        cvs,
        hrAiConsent
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Screening computation failed in Python engine');
    }
    return res.json();
  },

  // Approve Shortlist
  async approveShortlist(vacancyId: string, approvedCandidateIds: string[], hrNotes: string): Promise<void> {
    const res = await fetch('/api/screening/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vacancyId, approvedCandidateIds, hrNotes })
    });
    if (!res.ok) throw new Error('Failed to record HR approval');
  },

  // Export Excel
  async exportExcelReport(results: ScreeningResult, vacancyTitle: string): Promise<void> {
    const res = await fetch('/api/screening/export-excel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ results, vacancyTitle })
    });
    if (!res.ok) throw new Error('Failed to export Excel report');
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ATS_Shortlist_${vacancyTitle.replace(/\s+/g, '_')}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  },

  // Download ZIP of shortlisted CVs
  async downloadShortlistZip(candidates: any[], vacancyTitle: string): Promise<void> {
    const res = await fetch('/api/screening/download-zip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidates, vacancyTitle })
    });
    if (!res.ok) throw new Error('Failed to download ZIP archive');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Shortlisted_CVs_${vacancyTitle.replace(/\s+/g, '_')}.zip`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  },

  // Download individual CV
  getDownloadCvUrl(savedPath: string, filename: string): string {
    return `/api/screening/download-cv?path=${encodeURIComponent(savedPath)}&filename=${encodeURIComponent(filename)}`;
  }
};
