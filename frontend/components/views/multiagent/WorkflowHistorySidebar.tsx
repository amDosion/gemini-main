import React from 'react';
import { Bot, Download, Eye, FileText, Loader2, RefreshCcw, Search, Trash2 } from 'lucide-react';
import type { WorkflowHistoryMediaPreviewItem } from '../../../services/workflowHistoryService';
import type { WorkflowHistoryItem } from './types';

interface WorkflowHistorySidebarProps {
  historySearchQuery: string;
  historyLoading: boolean;
  historyError: string | null;
  displayedWorkflowHistory: WorkflowHistoryItem[];
  historyPreviewImages: Record<string, string[]>;
  historyPreviewMedia: Record<string, {
    audioItems: WorkflowHistoryMediaPreviewItem[];
    videoItems: WorkflowHistoryMediaPreviewItem[];
  }>;
  expandedPreviewHistoryId: string | null;
  selectedHistoryId: string | null;
  loadingHistoryId: string | null;
  deletingHistoryId: string | null;
  downloadingHistoryId: string | null;
  downloadingAnalysisId: string | null;
  downloadMediaProgress: Record<string, number>;
  downloadAnalysisProgress: Record<string, number>;
  previewingHistoryId: string | null;
  onHistorySearchQueryChange: (value: string) => void;
  onRefreshHistory: () => void;
  onLoadWorkflowFromHistory: (executionId: string) => void;
  onDeleteWorkflowHistory: (executionId: string) => void;
  onDownloadWorkflowMedia: (item: WorkflowHistoryItem) => void;
  onDownloadWorkflowAnalysis: (item: WorkflowHistoryItem) => void;
  onToggleWorkflowMediaPreview: (item: WorkflowHistoryItem) => void;
  onOpenAgentManager: () => void;
  onImageClick: (url: string) => void;
  formatHistoryTime: (timestamp: number) => string;
  formatHistoryDuration: (durationMs?: number) => string;
  getHistoryStatusLabel: (status: string) => string;
  getHistoryStatusClass: (status: string) => string;
}

export const WorkflowHistorySidebar: React.FC<WorkflowHistorySidebarProps> = ({
  historySearchQuery,
  historyLoading,
  historyError,
  displayedWorkflowHistory,
  historyPreviewImages,
  historyPreviewMedia,
  expandedPreviewHistoryId,
  selectedHistoryId,
  loadingHistoryId,
  deletingHistoryId,
  downloadingHistoryId,
  downloadingAnalysisId,
  downloadMediaProgress,
  downloadAnalysisProgress,
  previewingHistoryId,
  onHistorySearchQueryChange,
  onRefreshHistory,
  onLoadWorkflowFromHistory,
  onDeleteWorkflowHistory,
  onDownloadWorkflowMedia,
  onDownloadWorkflowAnalysis,
  onToggleWorkflowMediaPreview,
  onOpenAgentManager,
  onImageClick,
  formatHistoryTime,
  formatHistoryDuration,
  getHistoryStatusLabel,
  getHistoryStatusClass,
}) => (
  <div className="p-4 space-y-4">
    <div>
      <button
        onClick={onOpenAgentManager}
        className="w-full p-3 bg-teal-600/20 border border-teal-500/30 rounded-lg text-left hover:bg-teal-600/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-teal-400" />
          <span className="text-xs font-semibold text-teal-300">管理 Agent</span>
        </div>
        <p className="text-[10px] text-slate-400 mt-1">创建和配置 Agent（LLM + Prompt）</p>
      </button>
    </div>

    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider whitespace-nowrap">工作流历史</h3>
          <div className="relative flex-1 min-w-0">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={historySearchQuery}
              onChange={(event) => onHistorySearchQueryChange(event.target.value)}
              placeholder="搜索历史..."
              className="w-full h-6 pl-6 pr-2 rounded-md bg-slate-800 border border-slate-700 text-[11px] text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500/50"
            />
          </div>
        </div>
        <button
          onClick={onRefreshHistory}
          disabled={historyLoading}
          className="p-1 rounded-md border border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition-colors"
          title="刷新历史"
        >
          {historyLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCcw size={12} />}
        </button>
      </div>

      {historyError && (
        <div className="mb-2 text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded px-2 py-1.5">
          {historyError}
        </div>
      )}

      <div className="space-y-2 overflow-y-auto pr-1 custom-scrollbar">
        {historyLoading && displayedWorkflowHistory.length === 0 && (
          <div className="px-2 py-4 text-center text-xs text-slate-500">加载中...</div>
        )}

        {!historyLoading && displayedWorkflowHistory.length === 0 && (
          <div className="px-2 py-4 text-center text-xs text-slate-500 border border-dashed border-slate-700 rounded">
            {historySearchQuery.trim() ? '未匹配到历史记录' : '暂无历史执行记录'}
          </div>
        )}

        {displayedWorkflowHistory.map((item) => {
          const previewImages = historyPreviewImages[item.id] || [];
          const previewMedia = historyPreviewMedia[item.id] || { audioItems: [], videoItems: [] };
          const isPreviewExpanded = expandedPreviewHistoryId === item.id;
          const mediaDownloadPercent = downloadMediaProgress[item.id];
          const analysisDownloadPercent = downloadAnalysisProgress[item.id];
          const hasResultMedia = item.resultImageCount > 0 || item.resultAudioCount > 0 || item.resultVideoCount > 0;
          return (
            <div
              key={item.id}
              className={`p-2 rounded border transition-colors ${
                selectedHistoryId === item.id
                  ? 'border-teal-500/40 bg-teal-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <button
                  onClick={() => onLoadWorkflowFromHistory(item.id)}
                  disabled={loadingHistoryId === item.id}
                  className="flex-1 text-left min-w-0"
                >
                  <div className="text-xs font-medium text-slate-200 truncate">{item.title}</div>
                  <div className="text-[10px] text-slate-500 mt-1 truncate">{item.task || '无任务描述'}</div>
                  {item.source && (
                    <div className="mt-1 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-teal-500/30 bg-teal-500/10 text-teal-200">
                      {item.source}
                    </div>
                  )}
                  {item.resultPreview && (
                    <div className="text-[10px] text-slate-400 mt-1 line-clamp-2 break-words">
                      结果: {item.resultPreview}
                    </div>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {item.resultImageCount > 0 && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-200">
                        图片 {item.resultImageCount} 张
                      </div>
                    )}
                    {item.resultVideoCount > 0 && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-200">
                        视频 {item.resultVideoCount} 条
                      </div>
                    )}
                    {item.resultAudioCount > 0 && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-sky-500/30 bg-sky-500/10 text-sky-200">
                        音频 {item.resultAudioCount} 条
                      </div>
                    )}
                    {(item.videoExtensionApplied || item.videoExtensionCount) && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-orange-500/30 bg-orange-500/10 text-orange-200">
                        延长 {item.videoExtensionApplied || item.videoExtensionCount} 次
                      </div>
                    )}
                    {item.totalDurationSeconds && item.totalDurationSeconds > 0 && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                        总时长 {item.totalDurationSeconds}s
                      </div>
                    )}
                    {((item.subtitleMode && item.subtitleMode !== 'none') || (item.subtitleFileCount || 0) > 0) && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                        字幕{item.subtitleFileCount ? ` · ${item.subtitleFileCount}` : ''}
                      </div>
                    )}
                    {(item.continuedFromVideo || item.continuationStrategy) && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-violet-500/30 bg-violet-500/10 text-violet-200">
                        {item.continuationStrategy === 'video_extension_chain' ? '官方续接' : '视频续接'}
                      </div>
                    )}
                    {item.primaryRuntime && (
                      <div className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
                        runtime: {item.primaryRuntime}
                      </div>
                    )}
                  </div>
                </button>

                <div className="flex items-center gap-1 flex-shrink-0">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border ${getHistoryStatusClass(item.status)}`}>
                    {getHistoryStatusLabel(item.status)}
                  </span>
                  <button
                    onClick={() => onToggleWorkflowMediaPreview(item)}
                    disabled={previewingHistoryId === item.id || item.status !== 'completed' || !hasResultMedia}
                    className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-cyan-300 disabled:opacity-40 transition-colors"
                    title={hasResultMedia ? (isPreviewExpanded ? '收起媒体预览' : '查看媒体预览') : '无可预览媒体'}
                  >
                    {previewingHistoryId === item.id ? <Loader2 size={11} className="animate-spin" /> : <Eye size={11} />}
                  </button>
                  <button
                    onClick={() => onDownloadWorkflowAnalysis(item)}
                    disabled={downloadingAnalysisId === item.id || item.status !== 'completed'}
                    className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-teal-300 disabled:opacity-40 transition-colors"
                    title={item.status === 'completed' ? '下载分析结果 Excel' : '仅完成记录可下载分析结果'}
                  >
                    {downloadingAnalysisId === item.id ? <Loader2 size={11} className="animate-spin" /> : <FileText size={11} />}
                  </button>
                  <button
                    onClick={() => onDownloadWorkflowMedia(item)}
                    disabled={downloadingHistoryId === item.id || item.status !== 'completed' || !hasResultMedia}
                    className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-indigo-300 disabled:opacity-40 transition-colors"
                    title={hasResultMedia ? '批量下载结果媒体' : '无可下载媒体'}
                  >
                    {downloadingHistoryId === item.id ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
                  </button>
                  <button
                    onClick={() => onDeleteWorkflowHistory(item.id)}
                    disabled={deletingHistoryId === item.id || item.status === 'running'}
                    className="p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-rose-300 disabled:opacity-40 transition-colors"
                    title={item.status === 'running' ? '运行中的记录不能删除' : '删除历史'}
                  >
                    {deletingHistoryId === item.id ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                  </button>
                </div>
              </div>

              <button
                onClick={() => onLoadWorkflowFromHistory(item.id)}
                disabled={loadingHistoryId === item.id}
                className="mt-2 w-full text-left text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
              >
                {loadingHistoryId === item.id ? '加载中...' : '加载到画布'}
                {' · '}
                {item.nodeCount} 节点 / {item.edgeCount} 连线
                {' · '}
                {formatHistoryTime(item.startedAt)}
                {item.durationMs ? ` · ${formatHistoryDuration(item.durationMs)}` : ''}
              </button>

              {(downloadingHistoryId === item.id && Number.isFinite(mediaDownloadPercent)) && (
                <div className="mt-1 text-[10px] text-indigo-300">
                  媒体下载进度: {Math.max(0, Math.min(100, Math.round(mediaDownloadPercent || 0)))}%
                </div>
              )}
              {(downloadingAnalysisId === item.id && Number.isFinite(analysisDownloadPercent)) && (
                <div className="mt-1 text-[10px] text-teal-300">
                  分析下载进度: {Math.max(0, Math.min(100, Math.round(analysisDownloadPercent || 0)))}%
                </div>
              )}

              {previewingHistoryId === item.id && (
                <div className="mt-2 text-[10px] text-slate-500">正在加载媒体预览...</div>
              )}

              {isPreviewExpanded && (
                <div className="mt-2 space-y-2">
                  {previewImages.length <= 0 &&
                    previewMedia.audioItems.length <= 0 &&
                    previewMedia.videoItems.length <= 0 && (
                      <div className="rounded border border-dashed border-slate-700 bg-slate-900/40 px-2 py-3 text-[10px] text-slate-500">
                        当前记录暂时没有可内联预览的媒体结果
                      </div>
                    )}
                  {previewImages.length > 0 && (
                    <div className="grid grid-cols-2 gap-1.5">
                      {previewImages.map((previewUrl, previewIndex) => (
                        <button
                          key={`${item.id}-preview-${previewIndex}`}
                          type="button"
                          onClick={() => onImageClick(previewUrl)}
                          className="group relative rounded border border-slate-700 overflow-hidden bg-slate-900/60"
                          title="点击查看大图"
                        >
                          <img
                            src={previewUrl}
                            alt={`workflow-preview-${previewIndex + 1}`}
                            className="h-20 w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                            loading="lazy"
                          />
                        </button>
                      ))}
                    </div>
                  )}

                  {previewMedia.videoItems.length > 0 && (
                    <div className="space-y-2">
                      {previewMedia.videoItems.map((previewItem) => (
                        <div
                          key={`${item.id}-video-${previewItem.index}`}
                          className="rounded border border-slate-700 bg-slate-900/60 p-2"
                        >
                          <div className="mb-1 text-[10px] text-slate-400">{previewItem.fileName || `video-${previewItem.index}`}</div>
                          <video
                            controls
                            preload="metadata"
                            className="w-full rounded bg-black"
                            src={previewItem.previewUrl}
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {previewMedia.audioItems.length > 0 && (
                    <div className="space-y-2">
                      {previewMedia.audioItems.map((previewItem) => (
                        <div
                          key={`${item.id}-audio-${previewItem.index}`}
                          className="rounded border border-slate-700 bg-slate-900/60 p-2"
                        >
                          <div className="mb-1 text-[10px] text-slate-400">{previewItem.fileName || `audio-${previewItem.index}`}</div>
                          <audio
                            controls
                            preload="metadata"
                            className="w-full"
                            src={previewItem.previewUrl}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  </div>
);
