export interface CategoryScores {
  qualifications: number;
  skills: number;
  experience: number;
  mandatory: number;
}

export interface CandidateEvaluation {
  id: string;
  filename: string;
  name: string;
  email: string;
  phone: string;
  years_experience?: number;
  matching_percentage: number;
  category_scores: CategoryScores;
  mandatory_met: boolean;
  strengths: string[];
  missing_requirements: string[];
  evidence: string[];
  unreadable?: boolean;
  ocr_needed?: boolean;
  flags: string[];
  status: string;
  rank?: number;
  shortlisted?: boolean;
  is_duplicate?: boolean;
  original_match?: string;
  savedPath?: string;
  hr_approved?: boolean;
  hr_notes?: string;
}

export interface DuplicateRecord {
  duplicate_file: string;
  original_file: string;
  candidate_name?: string;
}

export interface ScreeningResult {
  ranked_candidates: CandidateEvaluation[];
  qualifying_count: number;
  total_evaluated: number;
  threshold_applied: number;
  top_n_cap: number;
  duplicates?: DuplicateRecord[];
  processed_at?: string;
  hr_approval?: {
    approved_count: number;
    approved_at: string;
    notes: string;
  };
}

export interface CriteriaWeights {
  qualifications: number;
  skills: number;
  experience: number;
  mandatory: number;
}

export interface JobCriteria {
  threshold: number;
  top_n: number;
  weights: CriteriaWeights;
  qualifications: string[];
  skills: string[];
  experience: {
    required_years: number;
    domains: string[];
  };
  mandatory: string[];
}

export interface Vacancy {
  id: string;
  title: string;
  department: string;
  status: 'Active' | 'Draft' | 'Archived';
  createdAt: string;
  updatedAt?: string;
  description: string;
  criteria: JobCriteria;
  results?: ScreeningResult | null;
  lastScreenedAt?: string;
}

export interface UploadedCvFile {
  id: string;
  filename: string;
  savedPath: string;
  fileHash: string;
  fileSize: number;
  text: string;
  is_ocr_scanned: boolean;
  unreadable: boolean;
  is_duplicate?: boolean;
  duplicate_of?: string | null;
}

export interface UserSession {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  token: string;
}
