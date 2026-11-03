import React, { useState } from 'react';
import { Lock, UserCheck, ShieldCheck, ArrowRight } from 'lucide-react';
import { UserSession } from '../types';
import { api } from '../services/api';

interface LoginModalProps {
  onLoginSuccess: (user: UserSession) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('sarah.jenkins@enterprise-talent.com');
  const [password, setPassword] = useState('atsAdmin2026!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await api.login(email, password);
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-slate-200 overflow-hidden">
        {/* Top Header */}
        <div className="bg-slate-900 p-6 text-white text-center">
          <div className="w-12 h-12 rounded-xl bg-emerald-600 flex items-center justify-center mx-auto mb-3 shadow-md">
            <Lock className="w-6 h-6 text-white" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">Enterprise ATS Portal</h2>
          <p className="text-xs text-slate-400 mt-1">
            Authorized Talent Acquisition & Candidate Screening Access
          </p>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              HR Manager Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm border border-slate-350 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              placeholder="hr@enterprise.com"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm border border-slate-350 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              placeholder="••••••••••••"
            />
          </div>

          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-1">
            <div className="flex items-center gap-1.5 font-medium text-slate-900">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Security & Audit Notice</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Session is encrypted. All screening calculations, shortlist approvals, and document downloads are logged in compliance with enterprise audit policies.
            </p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
          >
            {loading ? (
              <span>Authenticating HR Credentials...</span>
            ) : (
              <>
                <span>Access Screening Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
