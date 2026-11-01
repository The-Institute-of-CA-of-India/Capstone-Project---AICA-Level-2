import React, { useState } from 'react';
import { 
  Contact as ContactIcon, 
  Search, 
  Phone, 
  Mail, 
  MessageCircle, 
  Building2, 
  ExternalLink, 
  CheckCircle2, 
  MapPin,
  ShieldCheck,
  UserCheck
} from 'lucide-react';
import { CrmContact } from '../types/index.ts';

interface ContactsDirectoryProps {
  contacts: CrmContact[];
}

export const ContactsDirectory: React.FC<ContactsDirectoryProps> = ({ contacts }) => {
  const [search, setSearch] = useState('');

  const filtered = contacts.filter(c => 
    c.fullName.toLowerCase().includes(search.toLowerCase()) ||
    c.jobTitle.toLowerCase().includes(search.toLowerCase()) ||
    c.businessName.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase()) ||
    c.phone.includes(search)
  );

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Commercial Contacts & Decision Makers
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
              {contacts.length} Verified Contacts
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Key corporate executives, procurement leads, and commercial desks across UAE enterprises
          </p>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search contact, title, company..."
            className="w-64 pl-8 pr-3 py-1.5 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Grid of Contacts */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((con) => (
          <div
            key={con.id}
            className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between hover:border-emerald-500/40 transition group space-y-4"
          >
            <div>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600 to-teal-700 text-white font-bold flex items-center justify-center text-sm shadow-md">
                    {con.fullName.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-900 dark:text-white group-hover:text-emerald-500 transition">
                      {con.fullName}
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                      {con.jobTitle}
                    </p>
                  </div>
                </div>

                {con.isPrimary && (
                  <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                    Primary
                  </span>
                )}
              </div>

              {/* Linked Company */}
              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
                <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300 font-semibold truncate">
                  <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{con.businessName}</span>
                </div>
              </div>

              {/* Contact Details */}
              <div className="mt-3 space-y-2 text-xs text-slate-600 dark:text-slate-300">
                <div className="flex items-center gap-2">
                  <Phone className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  <span className="font-mono">{con.phone}</span>
                </div>

                <div className="flex items-center gap-2 truncate">
                  <Mail className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                  <span className="truncate">{con.email}</span>
                </div>
              </div>
            </div>

            {/* Communication Action Row */}
            <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                <span>Opt-in Verified</span>
              </span>

              <div className="flex items-center gap-2">
                <a
                  href={`tel:${con.phone}`}
                  className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 text-xs font-semibold flex items-center gap-1"
                >
                  <Phone className="w-3 h-3" />
                  <span>Call</span>
                </a>

                {con.whatsapp ? (
                  <a
                    href={`https://wa.me/${con.whatsapp.replace(/[^\d]/g, '')}`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1 shadow-xs"
                  >
                    <MessageCircle className="w-3 h-3" />
                    <span>WhatsApp</span>
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
};
