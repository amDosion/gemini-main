/**
 * Template Search & Filter panel
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L648-738
 * （< 800 行合规拆分）。
 *
 * 包含搜索框、分类切换 tab、遗留 Starter 副本切换、
 * "新增分类" 按钮以及 categoryActionFeedback 提示。
 */

import React from 'react';
import { Plus, Search } from 'lucide-react';

interface TemplateSearchFilterProps {
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  categories: string[];
  selectedCategory: string;
  setSelectedCategory: React.Dispatch<React.SetStateAction<string>>;
  isCreateCategoryDialogOpen: boolean;
  setIsCreateCategoryDialogOpen: React.Dispatch<React.SetStateAction<boolean>>;
  hiddenLegacyStarterCopyCount: number;
  showLegacyStarterCopies: boolean;
  setShowLegacyStarterCopies: React.Dispatch<React.SetStateAction<boolean>>;
  addingCategory: boolean;
  categoryActionFeedback: string | null;
  setCategoryActionFeedback: React.Dispatch<React.SetStateAction<string | null>>;
}

export const TemplateSearchFilter: React.FC<TemplateSearchFilterProps> = ({
  searchQuery,
  setSearchQuery,
  categories,
  selectedCategory,
  setSelectedCategory,
  isCreateCategoryDialogOpen,
  setIsCreateCategoryDialogOpen,
  hiddenLegacyStarterCopyCount,
  showLegacyStarterCopies,
  setShowLegacyStarterCopies,
  addingCategory,
  categoryActionFeedback,
  setCategoryActionFeedback,
}) => {
  return (
    <div className="p-4 border-b border-slate-700 space-y-3 bg-slate-900/80">
      {/* Search Bar */}
      <div className="relative">
        <Search
          size={18}
          className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索模板名称、描述或标签..."
          className="w-full pl-10 pr-4 py-2 border border-slate-700 rounded-lg bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
        />
      </div>

      {/* Category Filter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 overflow-x-auto">
            <div className="inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900 min-w-max">
              {categories.map((category, index) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
                    index > 0 ? 'border-l border-slate-700' : ''
                  } ${
                    selectedCategory === category
                      ? 'bg-teal-600 text-white'
                      : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {category === 'all' ? '全部' : category}
                </button>
              ))}
            </div>
          </div>
          {!isCreateCategoryDialogOpen && (
            <div className="flex items-center gap-2">
              {hiddenLegacyStarterCopyCount > 0 && (
                <button
                  type="button"
                  onClick={() => setShowLegacyStarterCopies((prev) => !prev)}
                  className={`px-3 py-1.5 text-xs border rounded-lg transition-colors ${
                    showLegacyStarterCopies
                      ? 'border-amber-500/40 bg-amber-500/10 text-amber-200'
                      : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {showLegacyStarterCopies
                    ? '隐藏遗留 Starter 副本'
                    : `显示遗留 Starter 副本 ${hiddenLegacyStarterCopyCount}`}
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setIsCreateCategoryDialogOpen(true);
                  setCategoryActionFeedback(null);
                }}
                disabled={addingCategory}
                className="px-3 py-1.5 text-xs border border-slate-700 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                <Plus size={13} />
                新增分类
              </button>
            </div>
          )}
        </div>

        {hiddenLegacyStarterCopyCount > 0 && !showLegacyStarterCopies && (
          <div className="text-[11px] text-amber-200 border border-amber-500/20 bg-amber-500/10 rounded-lg px-3 py-2">
            已默认隐藏 {hiddenLegacyStarterCopyCount} 个遗留 Starter 副本，这些模板仍使用旧的
            `agentName` 绑定。
          </div>
        )}

        {categoryActionFeedback && (
          <div
            className={`text-xs ${
              categoryActionFeedback.startsWith('新增失败')
                ? 'text-rose-300'
                : 'text-emerald-300'
            }`}
          >
            {categoryActionFeedback}
          </div>
        )}
      </div>
    </div>
  );
};
