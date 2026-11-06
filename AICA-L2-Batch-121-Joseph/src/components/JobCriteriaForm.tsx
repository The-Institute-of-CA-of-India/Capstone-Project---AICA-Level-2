import React, { useState } from 'react';
import { 
  FileText, 
  Sliders, 
  Plus, 
  Trash2, 
  AlertCircle, 
  CheckCircle2, 
  Save, 
  Upload, 
  Sparkles,
  Info,
  Scale
} from 'lucide-react';
import { JobCriteria, Vacancy } from '../types';

interface JobCriteriaFormProps {
  vacancy: Vacancy;
  onSaveVacancy: (updated: Partial<Vacancy>) => Promise<void>;
  onProceedToUpload: () => void;
}

export const JobCriteriaForm: React.FC<JobCriteriaFormProps> = ({
  vacancy,
  onSaveVacancy,
  onProceedToUpload
}) => {
  const [title, setTitle] = useState(vacancy.title);
  const [department, setDepartment] = useState(vacancy.department);
  const [description, setDescription] = useState(vacancy.description);
  const [criteria, setCriteria] = useState<JobCriteria>(vacancy.criteria);
  const [newQual, setNewQual] = useState('');
  const [newSkill, setNewSkill] = useState('');
  const [newMandatory, setNewMandatory] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Calculate total weight
  const totalWeight =
    criteria.weights.qualifications +
    criteria.weights.skills +
    criteria.weights.experience +
    criteria.weights.mandatory;

  const isWeightValid = totalWeight === 100;

  const handleWeightChange = (category: keyof JobCriteria['weights'], value: number) => {
    setCriteria({
      ...criteria,
      weights: {
        ...criteria.weights,
        [category]: Number(value)
      }
    });
  };

  const autoBalanceWeights = () => {
    // Balances cleanly to 100
    setCriteria({
      ...criteria,
      weights: {
        qualifications: 25,
        skills: 35,
        experience: 25,
        mandatory: 15
      }
    });
  };

  const handleAddQualification = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQual.trim()) return;
    setCriteria({
      ...criteria,
      qualifications: [...criteria.qualifications, newQual.trim()]
    });
    setNewQual('');
  };

  const handleRemoveQualification = (index: number) => {
    setCriteria({
      ...criteria,
      qualifications: criteria.qualifications.filter((_, i) => i !== index)
    });
  };

  const handleAddSkill = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSkill.trim()) return;
    setCriteria({
      ...criteria,
      skills: [...criteria.skills, newSkill.trim()]
    });
    setNewSkill('');
  };

  const handleRemoveSkill = (index: number) => {
    setCriteria({
      ...criteria,
      skills: criteria.skills.filter((_, i) => i !== index)
    });
  };

  const handleAddMandatory = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMandatory.trim()) return;
    setCriteria({
      ...criteria,
      mandatory: [...criteria.mandatory, newMandatory.trim()]
    });
    setNewMandatory('');
  };

  const handleRemoveMandatory = (index: number) => {
    setCriteria({
      ...criteria,
      mandatory: criteria.mandatory.filter((_, i) => i !== index)
    });
  };

  const handleAddDomain = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDomain.trim()) return;
    setCriteria({
      ...criteria,
      experience: {
        ...criteria.experience,
        domains: [...criteria.experience.domains, newDomain.trim()]
      }
    });
    setNewDomain('');
  };

  const handleRemoveDomain = (index: number) => {
    setCriteria({
      ...criteria,
      experience: {
        ...criteria.experience,
        domains: criteria.experience.domains.filter((_, i) => i !== index)
      }
    });
  };

  const handleJobDescFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setDescription(content);
    };
    reader.readAsText(file);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSaveVacancy({
        title,
        department,
        description,
        criteria
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner / Heading */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Job Description & Selection Criteria</h1>
          <p className="text-xs text-slate-500 mt-1">
            Define role parameters, assign 100% weighted evaluation criteria, and configure shortlisting thresholds.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-medium rounded-lg transition-colors border border-slate-300"
          >
            <Save className="w-3.5 h-3.5 text-slate-600" />
            <span>{isSaving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save Vacancy'}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              handleSave();
              onProceedToUpload();
            }}
            disabled={!isWeightValid}
            className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-xs disabled:opacity-50"
          >
            <span>Proceed to Upload CVs</span>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Job Description Details (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs space-y-4">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-600" />
              <span>Job Specification</span>
            </h2>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Job Position Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="e.g. Senior Full-Stack Engineer"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Department / Team
              </label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="e.g. Engineering & Platform Architecture"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-medium text-slate-700">
                  Job Description Content
                </label>
                <label className="text-[11px] text-emerald-600 hover:text-emerald-700 cursor-pointer flex items-center gap-1 font-medium">
                  <Upload className="w-3 h-3" />
                  <span>Upload Document</span>
                  <input
                    type="file"
                    accept=".txt,.md"
                    onChange={handleJobDescFileUpload}
                    className="hidden"
                  />
                </label>
              </div>
              <textarea
                rows={12}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-3 text-xs border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none leading-relaxed"
                placeholder="Paste or upload the full job description here..."
              />
            </div>
          </div>

          {/* Shortlisting Thresholds Card */}
          <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs space-y-5">
            <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-emerald-600" />
              <span>Shortlisting Target Parameters</span>
            </h2>

            {/* Minimum Matching Score (Default 90%) */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium text-slate-700">Minimum Matching Score Threshold</span>
                <span className="font-bold text-slate-900 text-sm">{criteria.threshold}%</span>
              </div>
              <input
                type="range"
                min={60}
                max={98}
                step={1}
                value={criteria.threshold}
                onChange={(e) =>
                  setCriteria({ ...criteria, threshold: Number(e.target.value) })
                }
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
              <div className="flex justify-between text-[11px] text-slate-600 mt-1">
                <span>Flexible (60%)</span>
                <span className="text-emerald-700 font-semibold">Standard Default (90%)</span>
                <span>Elite (98%)</span>
              </div>
              <p className="text-[11px] text-slate-600 mt-1.5">
                Only candidates meeting or exceeding this weighted score AND satisfying all mandatory requirements will be proposed.
              </p>
            </div>

            {/* Target Shortlist Cap (Default 10) */}
            <div className="pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium text-slate-700">Number of Candidates to Shortlist</span>
                <span className="font-bold text-slate-900 text-sm">{criteria.top_n} candidates</span>
              </div>
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={criteria.top_n}
                onChange={(e) =>
                  setCriteria({ ...criteria, top_n: Number(e.target.value) })
                }
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
              <div className="flex justify-between text-[11px] text-slate-600 mt-1">
                <span>Top 1</span>
                <span className="text-emerald-700 font-semibold">Default (Top 10)</span>
                <span>Top 30</span>
              </div>
              <p className="text-[11px] text-slate-600 mt-1.5">
                If fewer candidates qualify, the ATS will propose the actual qualified number without lowering the threshold.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: 4 Criteria Categories & 100% Weight Balance (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Weight Allocation Bar & Validation */}
          <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Scale className="w-4 h-4 text-emerald-600" />
                <h2 className="text-sm font-semibold text-slate-900">Criteria Weight Allocation</h2>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-md ${
                    isWeightValid
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  Total: {totalWeight}% / 100%
                </span>
                {!isWeightValid && (
                  <button
                    type="button"
                    onClick={autoBalanceWeights}
                    className="text-xs text-emerald-700 hover:text-emerald-800 underline font-medium"
                  >
                    Auto-Balance to 100%
                  </button>
                )}
              </div>
            </div>

            {/* Visual Weight Distribution Bar */}
            <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden flex">
              <div
                style={{ width: `${criteria.weights.qualifications}%` }}
                className="bg-blue-500 h-full transition-all"
                title={`Qualifications: ${criteria.weights.qualifications}%`}
              />
              <div
                style={{ width: `${criteria.weights.skills}%` }}
                className="bg-emerald-500 h-full transition-all"
                title={`Skills: ${criteria.weights.skills}%`}
              />
              <div
                style={{ width: `${criteria.weights.experience}%` }}
                className="bg-amber-500 h-full transition-all"
                title={`Experience: ${criteria.weights.experience}%`}
              />
              <div
                style={{ width: `${criteria.weights.mandatory}%` }}
                className="bg-purple-500 h-full transition-all"
                title={`Mandatory: ${criteria.weights.mandatory}%`}
              />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1">
              <div className="p-2 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="text-blue-900 font-medium">Qualifications</div>
                <div className="flex items-center justify-between mt-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={criteria.weights.qualifications}
                    onChange={(e) => handleWeightChange('qualifications', Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 text-xs border border-blue-300 rounded font-bold text-blue-950"
                  />
                  <span className="text-blue-700">%</span>
                </div>
              </div>

              <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                <div className="text-emerald-900 font-medium">Skills</div>
                <div className="flex items-center justify-between mt-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={criteria.weights.skills}
                    onChange={(e) => handleWeightChange('skills', Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 text-xs border border-emerald-300 rounded font-bold text-emerald-950"
                  />
                  <span className="text-emerald-700">%</span>
                </div>
              </div>

              <div className="p-2 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="text-amber-900 font-medium">Experience</div>
                <div className="flex items-center justify-between mt-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={criteria.weights.experience}
                    onChange={(e) => handleWeightChange('experience', Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 text-xs border border-amber-300 rounded font-bold text-amber-950"
                  />
                  <span className="text-amber-700">%</span>
                </div>
              </div>

              <div className="p-2 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="text-purple-900 font-medium">Mandatory</div>
                <div className="flex items-center justify-between mt-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={criteria.weights.mandatory}
                    onChange={(e) => handleWeightChange('mandatory', Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 text-xs border border-purple-300 rounded font-bold text-purple-950"
                  />
                  <span className="text-purple-700">%</span>
                </div>
              </div>
            </div>

            {!isWeightValid && (
              <div className="flex items-center gap-2 p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Total weight is {totalWeight}%. Please adjust weights to sum exactly 100%.</span>
              </div>
            )}
          </div>

          {/* 1. Mandatory Requirements (Dealbreakers) */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-purple-950 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-purple-600 inline-block"></span>
                  Mandatory Requirements (Dealbreakers)
                </h3>
                <p className="text-[11px] text-slate-500">
                  Strict prerequisite filters. Any candidate missing even one mandatory criterion is disqualified from the shortlist.
                </p>
              </div>
            </div>

            <div className="space-y-1.5">
              {criteria.mandatory.map((req, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 text-xs bg-purple-50/50 border border-purple-200 rounded-md"
                >
                  <span className="text-slate-800 font-medium">{req}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveMandatory(idx)}
                    className="text-slate-400 hover:text-rose-600 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            <form onSubmit={handleAddMandatory} className="flex gap-2 pt-1">
              <input
                type="text"
                value={newMandatory}
                onChange={(e) => setNewMandatory(e.target.value)}
                placeholder="e.g. 6+ years hands-on production engineering"
                className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-purple-700 hover:bg-purple-800 text-white text-xs font-medium rounded-lg flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </form>
          </div>

          {/* 2. Skills Criteria */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-3">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-950 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-600 inline-block"></span>
                Key Skills & Technical Stack
              </h3>
              <p className="text-[11px] text-slate-500">
                Core technologies, frameworks, methodologies, and technical proficiencies.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {criteria.skills.map((skill, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs bg-slate-100 text-slate-800 border border-slate-300 rounded-md"
                >
                  <span className="font-medium">{skill}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveSkill(idx)}
                    className="text-slate-400 hover:text-rose-600"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>

            <form onSubmit={handleAddSkill} className="flex gap-2 pt-1">
              <input
                type="text"
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                placeholder="e.g. TypeScript, React, Python, PostgreSQL..."
                className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Skill
              </button>
            </form>
          </div>

          {/* 3. Qualifications Criteria */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-3">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-blue-950 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-600 inline-block"></span>
                Qualifications & Certifications
              </h3>
              <p className="text-[11px] text-slate-500">
                Degrees, formal educational credentials, and industry-recognized certifications.
              </p>
            </div>

            <div className="space-y-1.5">
              {criteria.qualifications.map((qual, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 text-xs bg-blue-50/40 border border-blue-200 rounded-md"
                >
                  <span className="text-slate-800">{qual}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveQualification(idx)}
                    className="text-slate-400 hover:text-rose-600 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            <form onSubmit={handleAddQualification} className="flex gap-2 pt-1">
              <input
                type="text"
                value={newQual}
                onChange={(e) => setNewQual(e.target.value)}
                placeholder="e.g. AWS Certified Solutions Architect Professional"
                className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </form>
          </div>

          {/* 4. Experience Criteria */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-4">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-amber-950 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-600 inline-block"></span>
                Relevant Experience & Domain Depth
              </h3>
              <p className="text-[11px] text-slate-500">
                Minimum professional years in role and specialized domain expertise.
              </p>
            </div>

            <div className="flex items-center justify-between p-3 bg-amber-50/50 border border-amber-200 rounded-lg">
              <div>
                <span className="text-xs font-medium text-slate-800">Target Experience Duration</span>
                <p className="text-[11px] text-slate-500">Calculated from verified CV timelines</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={25}
                  value={criteria.experience.required_years}
                  onChange={(e) =>
                    setCriteria({
                      ...criteria,
                      experience: {
                        ...criteria.experience,
                        required_years: Number(e.target.value)
                      }
                    })
                  }
                  className="w-16 px-2 py-1 text-sm font-bold border border-amber-300 rounded-md text-center bg-white"
                />
                <span className="text-xs font-semibold text-slate-700">Years</span>
              </div>
            </div>

            {/* Domains */}
            <div className="space-y-2">
              <span className="text-xs font-medium text-slate-700">Specialized Domain Experience:</span>
              <div className="flex flex-wrap gap-2">
                {criteria.experience.domains.map((dom, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs bg-amber-50 text-amber-900 border border-amber-200 rounded-md"
                  >
                    <span>{dom}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveDomain(idx)}
                      className="text-amber-500 hover:text-rose-600"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>

              <form onSubmit={handleAddDomain} className="flex gap-2 pt-1">
                <input
                  type="text"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  placeholder="e.g. Distributed Systems Architecture"
                  className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:outline-none"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Domain
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
