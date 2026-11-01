import React, { useState } from 'react';
import { 
  FolderTree, 
  Plus, 
  Edit3, 
  Tag, 
  Building2, 
  CheckCircle2, 
  Search, 
  ArrowRight,
  GitMerge,
  Layers
} from 'lucide-react';
import { BusinessCategory } from '../types/index.ts';
import { createCategory } from '../services/api.ts';

interface CategoryManagerProps {
  categories: BusinessCategory[];
  onRefresh: () => void;
  onFilterByCategory: (categoryName: string) => void;
}

export const CategoryManager: React.FC<CategoryManagerProps> = ({
  categories,
  onRefresh,
  onFilterByCategory
}) => {
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newNameEn, setNewNameEn] = useState('');
  const [newNameAr, setNewNameAr] = useState('');
  const [newSubcats, setNewSubcats] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filtered = categories.filter(c => 
    c.nameEn.toLowerCase().includes(search.toLowerCase()) ||
    (c.nameAr && c.nameAr.toLowerCase().includes(search.toLowerCase())) ||
    c.subcategories.some(s => s.toLowerCase().includes(search.toLowerCase()))
  );

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNameEn) return;
    setIsSubmitting(true);
    try {
      await createCategory({
        nameEn: newNameEn,
        nameAr: newNameAr,
        subcategories: newSubcats.split(',').map(s => s.trim()).filter(Boolean)
      });
      setNewNameEn('');
      setNewNameAr('');
      setNewSubcats('');
      setShowAddModal(false);
      onRefresh();
    } catch (err) {
      console.error('Failed to create category:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-slate-800 dark:text-slate-100">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              UAE Business Categories & Sectors
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
              {categories.length} Industry Sectors
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Configurable industry hierarchy aligned with UAE DED and Chamber of Commerce activity codes
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search category or subcategory..."
              className="pl-8 pr-3 py-1.5 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Category</span>
          </button>
        </div>
      </div>

      {/* Categories Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((cat) => (
          <div
            key={cat.id}
            className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between hover:border-emerald-500/40 transition group"
          >
            <div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-bold text-sm text-slate-900 dark:text-white group-hover:text-emerald-500 transition">
                    {cat.nameEn}
                  </h3>
                  {cat.nameAr && (
                    <p className="text-xs text-slate-400 font-arabic mt-0.5" dir="rtl">{cat.nameAr}</p>
                  )}
                </div>

                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {cat.businessCount ? `${cat.businessCount.toLocaleString()} in UAE` : 'Active'}
                </span>
              </div>

              {/* Subcategories Pills */}
              <div className="mt-3 space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                  Subcategories & Activities
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {cat.subcategories.map((sub, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 text-[11px] font-medium"
                    >
                      {sub}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-mono">
                Slug: {cat.slug}
              </span>
              <button
                onClick={() => onFilterByCategory(cat.nameEn)}
                className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 hover:underline"
              >
                <span>View Businesses</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Category Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl text-slate-100 space-y-4">
            <h3 className="text-base font-bold text-white">Add New Business Category</h3>
            <form onSubmit={handleAddCategory} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Category Name (English)</label>
                <input
                  type="text"
                  required
                  value={newNameEn}
                  onChange={(e) => setNewNameEn(e.target.value)}
                  placeholder="e.g. Renewable Energy & Solar"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Category Name (Arabic)</label>
                <input
                  type="text"
                  value={newNameAr}
                  onChange={(e) => setNewNameAr(e.target.value)}
                  placeholder="e.g. الطاقة المتجددة وحلول الطاقة الشمسية"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                  dir="rtl"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Subcategories (Comma-separated)</label>
                <input
                  type="text"
                  value={newSubcats}
                  onChange={(e) => setNewSubcats(e.target.value)}
                  placeholder="Solar Installation, EV Charging Stations, Battery Storage"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                >
                  Save Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
