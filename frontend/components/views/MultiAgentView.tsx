import React, { useState, useCallback, useMemo, lazy, Suspense } from 'react';
import { AppMode, BaseViewProps } from '../../types/types';
import type { ExecutionStatus } from '../multiagent/types';
import { GenViewLayout } from '../common/GenViewLayout';
import { Network, Bot, RefreshCcw, Plus, Images } from 'lucide-react';
import { useToastContext } from '../../contexts/ToastContext';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
  AGENT_MANAGER_CREATE_EVENT,
  AGENT_MANAGER_REFRESH_EVENT,
  AgentManagerPanel,
} from '../multiagent/AgentManagerPanel';
import { WorkflowHistorySidebar } from './multiagent/WorkflowHistorySidebar';
import { getHistoryStatusClass, getHistoryStatusLabel } from './multiagent/executionStatusUtils';
import { useWorkflowHistoryController } from './multiagent/useWorkflowHistoryController';
import { useWorkflowExecutionController } from './multiagent/useWorkflowExecutionController';
import { WorkflowResultImageCanvas } from '../multiagent/WorkflowResultImageCanvas';
import { extractImageUrls, isDirectlyRenderableImageUrl } from '../multiagent/workflowResultUtils';
import { useWorkflowHistoryImageBrowser } from './multiagent/useWorkflowHistoryImageBrowser';

// ✅ 懒加载 MultiAgentWorkflowEditor 组件
const MultiAgentWorkflowEditor = lazy(() =>
  import('../multiagent').then((m) => ({ default: m.MultiAgentWorkflowEditorReactFlow }))
);

interface MultiAgentViewProps extends BaseViewProps {
  setAppMode: (mode: AppMode) => void;
}

const collectExecutionImageUrls = (status?: ExecutionStatus | null): string[] => {
  if (!status) {
    return [];
  }
  const seen = new Set<string>();
  const imageUrls: string[] = [];
  const push = (value: unknown) => {
    if (typeof value !== 'string') {
      return;
    }
    const normalized = value.trim();
    if (!normalized || seen.has(normalized) || !isDirectlyRenderableImageUrl(normalized)) {
      return;
    }
    seen.add(normalized);
    imageUrls.push(normalized);
  };
  const collectFromPayload = (payload: unknown) => {
    extractImageUrls(payload).forEach(push);
  };

  collectFromPayload(status.finalResult);
  Object.values(status.nodeResults || {}).forEach(collectFromPayload);
  (status.resultPreviewImageUrls || []).forEach(push);

  return imageUrls;
};

export const MultiAgentView: React.FC<MultiAgentViewProps> = React.memo(
  ({ onImageClick, setAppMode, providerId, activeModelConfig }) => {
    // ✅ Multi-Agent 工作流执行状态
    const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | undefined>(undefined);
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    const { showError } = useToastContext();

    const [showAgentManager, setShowAgentManager] = useState(false);
    const [agentManagerCount, setAgentManagerCount] = useState(0);
    const [imageViewerState, setImageViewerState] = useState<{
      source: 'current' | 'history';
      title: string;
      imageUrls: string[];
      initialIndex: number;
    } | null>(null);
    const {
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
      workflowLoadRequest,
      isMountedRef,
      activeExecutionControllerRef,
      activeExecutionCleanupRef,
      setHistorySearchQuery,
      createRequestController,
      releaseRequestController,
      fetchWorkflowHistory,
      handleLoadWorkflowFromHistory,
      handleDeleteWorkflowHistory,
      handleDownloadWorkflowMedia,
      handleDownloadWorkflowAnalysis,
      handleToggleWorkflowMediaPreview,
    } = useWorkflowHistoryController({
      setExecutionStatus,
      showError,
    });

    const { handleWorkflowExecute } = useWorkflowExecutionController({
      providerId,
      modelId: activeModelConfig?.id,
      setExecutionStatus,
      showError,
      isMountedRef,
      activeExecutionControllerRef,
      activeExecutionCleanupRef,
      createRequestController,
      releaseRequestController,
      fetchWorkflowHistory,
    });
    const historyImageBrowser = useWorkflowHistoryImageBrowser({
      items: displayedWorkflowHistory,
      seedPreviewImages: historyPreviewImages,
      enabled: imageViewerState?.source === 'history',
      showError,
    });

    const formatHistoryTime = useCallback((timestamp: number) => {
      if (!timestamp) return '--';
      return new Date(timestamp).toLocaleString();
    }, []);

    const formatHistoryDuration = useCallback((durationMs?: number) => {
      if (!durationMs || durationMs <= 0) return '';
      if (durationMs < 1000) return `${durationMs}ms`;
      if (durationMs < 60_000) return `${(durationMs / 1000).toFixed(1)}s`;
      return `${(durationMs / 60_000).toFixed(1)}m`;
    }, []);

    const emitAgentManagerHeaderAction = useCallback((eventName: string) => {
      if (typeof window === 'undefined') {
        return;
      }
      window.dispatchEvent(new CustomEvent(eventName));
    }, []);

    const allWorkflowMediaImageUrls = useMemo(() => {
      const seen = new Set<string>();
      const imageUrls: string[] = [];
      const push = (value: string) => {
        const normalized = value.trim();
        if (!normalized || seen.has(normalized)) {
          return;
        }
        seen.add(normalized);
        imageUrls.push(normalized);
      };
      collectExecutionImageUrls(workflowLoadRequest?.executionStatus).forEach(push);
      collectExecutionImageUrls(executionStatus).forEach(push);
      (workflowLoadRequest?.nodes || []).forEach((node) => {
        extractImageUrls(node.data?.result).forEach((imageUrl) => {
          if (isDirectlyRenderableImageUrl(imageUrl)) {
            push(imageUrl);
          }
        });
      });
      return imageUrls;
    }, [executionStatus, workflowLoadRequest]);

    const openWorkflowImageViewer = useCallback(
      (request?: { title?: string; imageUrls?: string[]; initialIndex?: number }) => {
        const imageUrls =
          request?.imageUrls && request.imageUrls.length > 0
            ? request.imageUrls
            : allWorkflowMediaImageUrls;
        if (imageUrls.length === 0) {
          showError('当前工作流没有可查看的媒体图片');
          return;
        }
        const rawIndex = Number(request?.initialIndex || 0);
        const initialIndex = Number.isFinite(rawIndex)
          ? Math.max(0, Math.min(imageUrls.length - 1, Math.floor(rawIndex)))
          : 0;
        setImageViewerState({
          source: 'current',
          title: request?.title || '全部媒体图片',
          imageUrls,
          initialIndex,
        });
      },
      [allWorkflowMediaImageUrls, showError]
    );
    const openWorkflowHistoryImageViewer = useCallback(() => {
      if (!historyImageBrowser.hasImages) {
        showError('当前工作流历史没有可查看的媒体图片');
        return;
      }
      historyImageBrowser.resetPage();
      setImageViewerState({
        source: 'history',
        title: '全部媒体图片',
        imageUrls: [],
        initialIndex: 0,
      });
    }, [historyImageBrowser, showError]);

    return (
      <GenViewLayout
        sidebarHeaderIcon={<Network size={16} className="text-teal-400" />}
        sidebarTitle={
          showAgentManager ? (
            <span className="inline-flex items-center gap-1.5">
              <span>Agent 管理</span>
              <span className="text-[11px] text-slate-500">({agentManagerCount})</span>
            </span>
          ) : (
            '工作流历史'
          )
        }
        sidebar={
          showAgentManager ? (
            <AgentManagerPanel
              onAgentCountChange={setAgentManagerCount}
              preferredProviderId={providerId}
              preferredModelId={activeModelConfig?.id}
            />
          ) : (
            <WorkflowHistorySidebar
              historySearchQuery={historySearchQuery}
              historyLoading={historyLoading}
              historyError={historyError}
              displayedWorkflowHistory={displayedWorkflowHistory}
              historyPreviewImages={historyPreviewImages}
              historyPreviewMedia={historyPreviewMedia}
              expandedPreviewHistoryId={expandedPreviewHistoryId}
              selectedHistoryId={selectedHistoryId}
              loadingHistoryId={loadingHistoryId}
              deletingHistoryId={deletingHistoryId}
              downloadingHistoryId={downloadingHistoryId}
              downloadingAnalysisId={downloadingAnalysisId}
              downloadMediaProgress={downloadMediaProgress}
              downloadAnalysisProgress={downloadAnalysisProgress}
              previewingHistoryId={previewingHistoryId}
              onHistorySearchQueryChange={setHistorySearchQuery}
              onRefreshHistory={fetchWorkflowHistory}
              onLoadWorkflowFromHistory={handleLoadWorkflowFromHistory}
              onDeleteWorkflowHistory={handleDeleteWorkflowHistory}
              onDownloadWorkflowMedia={handleDownloadWorkflowMedia}
              onDownloadWorkflowAnalysis={handleDownloadWorkflowAnalysis}
              onToggleWorkflowMediaPreview={handleToggleWorkflowMediaPreview}
              onOpenAgentManager={() => setShowAgentManager(true)}
              onImageClick={onImageClick}
              formatHistoryTime={formatHistoryTime}
              formatHistoryDuration={formatHistoryDuration}
              getHistoryStatusLabel={getHistoryStatusLabel}
              getHistoryStatusClass={getHistoryStatusClass}
            />
          )
        }
        sidebarExtraHeader={
          <div className="flex items-center gap-2">
            {!showAgentManager && (
              <button
                type="button"
                onClick={openWorkflowHistoryImageViewer}
                disabled={!historyImageBrowser.hasImages}
                className="p-1.5 rounded-lg border border-slate-700/80 bg-slate-800/70 text-slate-400 transition-colors hover:border-indigo-500/50 hover:bg-slate-800 hover:text-indigo-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-700/80 disabled:hover:bg-slate-800/70 disabled:hover:text-slate-400"
                title={
                  historyImageBrowser.hasImages
                    ? `查看全部媒体图片（${historyImageBrowser.totalCount}）`
                    : '暂无可查看的媒体图片'
                }
                aria-label="查看全部媒体图片"
              >
                <Images size={16} />
              </button>
            )}
            {showAgentManager && (
              <>
                <button
                  onClick={() => emitAgentManagerHeaderAction(AGENT_MANAGER_REFRESH_EVENT)}
                  className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                  title="刷新 Agent 列表"
                >
                  <RefreshCcw size={16} />
                </button>
                <button
                  onClick={() => emitAgentManagerHeaderAction(AGENT_MANAGER_CREATE_EVENT)}
                  className="p-1.5 hover:bg-slate-800 rounded-lg text-teal-400 transition-colors"
                  title="创建 Agent"
                >
                  <Plus size={16} />
                </button>
              </>
            )}
            <button
              onClick={() => setShowAgentManager(!showAgentManager)}
              className={`p-1.5 hover:bg-slate-800 rounded-lg transition-colors ${showAgentManager ? 'text-teal-400 bg-slate-800' : 'text-slate-400 hover:text-white'}`}
              title={showAgentManager ? '切换到工作流历史' : '切换到 Agent 管理'}
            >
              <Bot size={16} />
            </button>
          </div>
        }
        main={
          <div className="flex-1 flex flex-row h-full relative">
            {/* ========== 左侧：主内容区 ========== */}
            <div className="flex-1 flex flex-col h-full">
              {/* 主内容区 */}
              <div className="flex-1 overflow-hidden">
                <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
                  <MultiAgentWorkflowEditor
                    onExecute={handleWorkflowExecute}
                    onSave={async (workflow) => {
                      // 工作流保存功能（可以保存为模板）
                    }}
                    executionStatus={executionStatus}
                    loadedWorkflow={workflowLoadRequest}
                    onOpenResultImages={openWorkflowImageViewer}
                    onExit={() => setAppMode('chat')}
                  />
                </Suspense>
              </div>
            </div>
          </div>
        }
        mainOverlay={
          <WorkflowResultImageCanvas
            open={Boolean(imageViewerState)}
            title={imageViewerState?.title}
            imageUrls={
              imageViewerState?.source === 'history' ? [] : imageViewerState?.imageUrls || []
            }
            imageCards={
              imageViewerState?.source === 'history'
                ? historyImageBrowser.currentPageCards
                : undefined
            }
            totalCount={
              imageViewerState?.source === 'history' ? historyImageBrowser.totalCount : undefined
            }
            page={imageViewerState?.source === 'history' ? historyImageBrowser.page : undefined}
            totalPages={
              imageViewerState?.source === 'history' ? historyImageBrowser.totalPages : undefined
            }
            onPageChange={
              imageViewerState?.source === 'history' ? historyImageBrowser.setPage : undefined
            }
            initialIndex={imageViewerState?.initialIndex || 0}
            onClose={() => setImageViewerState(null)}
            onImageClick={onImageClick}
          />
        }
        isMobileHistoryOpen={isMobileHistoryOpen}
        setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      />
    );
  }
);

MultiAgentView.displayName = 'MultiAgentView';
