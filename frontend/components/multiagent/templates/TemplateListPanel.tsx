/**
 * Template List panel (left half of content area)
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L743-859
 * （< 800 行合规拆分）。
 *
 * 负责渲染：loading 状态、error 状态、空列表占位以及
 * 过滤后的模板卡片列表（含 origin/runtime/legacy/sampleResult 摘要徽标）。
 */

import React from 'react';
import { ChevronRight, FileText, Loader2 } from 'lucide-react';
import {
  type WorkflowTemplate,
  resolveTemplateOriginLabel,
  resolveTemplateRuntimeLabel,
} from '../workflowTemplateTypes';

interface TemplateListPanelProps {
  loading: boolean;
  error: string | null;
  filteredTemplates: WorkflowTemplate[];
  selectedTemplate: WorkflowTemplate | null;
  setSelectedTemplate: React.Dispatch<React.SetStateAction<WorkflowTemplate | null>>;
  fetchTemplates: () => void;
}

export const TemplateListPanel: React.FC<TemplateListPanelProps> = ({
  loading,
  error,
  filteredTemplates,
  selectedTemplate,
  setSelectedTemplate,
  fetchTemplates,
}) => {
  return (
    <div className="w-1/2 border-r border-slate-700 overflow-y-auto bg-slate-950/40">
      {loading ? (
        <div className="flex items-center justify-center h-full">
          <Loader2 size={32} className="animate-spin text-teal-400" />
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-full text-rose-300">
          <div className="text-center">
            <p className="font-medium">加载失败</p>
            <p className="text-sm mt-1">{error}</p>
            <button
              onClick={fetchTemplates}
              className="mt-3 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500"
            >
              重试
            </button>
          </div>
        </div>
      ) : filteredTemplates.length === 0 ? (
        <div className="flex items-center justify-center h-full text-slate-500">
          <div className="text-center">
            <FileText size={48} className="mx-auto mb-2" />
            <p>没有找到匹配的模板</p>
          </div>
        </div>
      ) : (
        <div className="p-4 space-y-4">
          {filteredTemplates.map((template) => (
            <button
              key={template.id}
              onClick={() => setSelectedTemplate(template)}
              className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                selectedTemplate?.id === template.id
                  ? 'border-teal-500 bg-teal-500/10'
                  : 'border-slate-700 hover:border-slate-600 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-semibold text-slate-100 mb-1">{template.name}</h3>
                  <p className="text-sm text-slate-400 mb-2 line-clamp-2">
                    {template.description}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded border border-slate-700">
                      {template.category}
                    </span>
                    <span className="text-xs px-2 py-0.5 bg-slate-950/80 text-slate-300 rounded border border-slate-700">
                      {resolveTemplateOriginLabel(template)}
                    </span>
                    {resolveTemplateRuntimeLabel(template) && (
                      <span className="text-xs px-2 py-0.5 bg-amber-500/10 text-amber-200 rounded border border-amber-500/20">
                        {resolveTemplateRuntimeLabel(template)}
                      </span>
                    )}
                    {template.isLegacyStarterCopy && (
                      <span className="text-xs px-2 py-0.5 bg-amber-600/15 text-amber-100 rounded border border-amber-500/30">
                        遗留 Starter 副本
                      </span>
                    )}
                    <span className="text-xs text-slate-500">
                      {template.config.nodes.length || template.estimatedNodeCount || 0}{' '}
                      个节点
                    </span>
                    {template.sampleResultSummary?.hasResult && (
                      <span className="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-200 rounded border border-emerald-500/30">
                        有结果样例
                      </span>
                    )}
                    {(template.sampleResultSummary?.videoCount || 0) > 0 && (
                      <span className="text-xs px-2 py-0.5 bg-sky-500/15 text-sky-200 rounded border border-sky-500/30">
                        视频 {template.sampleResultSummary?.videoCount || 0}
                      </span>
                    )}
                    {((template.sampleResultSummary?.videoExtensionApplied || 0) > 0 ||
                      (template.sampleResultSummary?.videoExtensionCount || 0) > 0) && (
                      <span className="text-xs px-2 py-0.5 bg-orange-500/15 text-orange-200 rounded border border-orange-500/30">
                        延长{' '}
                        {template.sampleResultSummary?.videoExtensionApplied ||
                          template.sampleResultSummary?.videoExtensionCount ||
                          0}
                      </span>
                    )}
                    {(template.sampleResultSummary?.totalDurationSeconds || 0) > 0 && (
                      <span className="text-xs px-2 py-0.5 bg-cyan-500/15 text-cyan-200 rounded border border-cyan-500/30">
                        {template.sampleResultSummary?.totalDurationSeconds || 0}s
                      </span>
                    )}
                    {(((template.sampleResultSummary?.subtitleMode || '') !== '' &&
                      template.sampleResultSummary?.subtitleMode !== 'none') ||
                      (template.sampleResultSummary?.subtitleFileCount || 0) > 0) && (
                      <span className="text-xs px-2 py-0.5 bg-emerald-500/15 text-emerald-200 rounded border border-emerald-500/30">
                        字幕
                        {(template.sampleResultSummary?.subtitleFileCount || 0) > 0
                          ? ` · ${template.sampleResultSummary?.subtitleFileCount}`
                          : ''}
                      </span>
                    )}
                    {(template.sampleResultSummary?.audioCount || 0) > 0 && (
                      <span className="text-xs px-2 py-0.5 bg-cyan-500/15 text-cyan-200 rounded border border-cyan-500/30">
                        音频 {template.sampleResultSummary?.audioCount || 0}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronRight
                  size={20}
                  className={`flex-shrink-0 ml-2 ${
                    selectedTemplate?.id === template.id ? 'text-teal-400' : 'text-slate-500'
                  }`}
                />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
