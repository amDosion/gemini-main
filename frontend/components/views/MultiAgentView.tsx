import React, { useState, useCallback, lazy, Suspense } from 'react';
import { AppMode, BaseViewProps } from '../../types/types';
import type { ExecutionStatus } from '../multiagent/types';
import { GenViewLayout } from '../common/GenViewLayout';
import { Network, Bot, RefreshCcw, Plus } from 'lucide-react';
import { useToastContext } from '../../contexts/ToastContext';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
    AGENT_MANAGER_CREATE_EVENT,
    AGENT_MANAGER_REFRESH_EVENT,
    AgentManagerPanel,
} from '../multiagent/AgentManagerPanel';
import { WorkflowHistorySidebar } from './multiagent/WorkflowHistorySidebar';
import {
    getHistoryStatusClass,
    getHistoryStatusLabel,
} from './multiagent/executionStatusUtils';
import { useWorkflowHistoryController } from './multiagent/useWorkflowHistoryController';
import { useWorkflowExecutionController } from './multiagent/useWorkflowExecutionController';

// ✅ 懒加载 MultiAgentWorkflowEditor 组件
const MultiAgentWorkflowEditor = lazy(() => 
  import('../multiagent').then(m => ({ default: m.MultiAgentWorkflowEditorReactFlow }))
);

interface MultiAgentViewProps extends BaseViewProps {
    setAppMode: (mode: AppMode) => void;
}

export const MultiAgentView: React.FC<MultiAgentViewProps> = React.memo(({
    onImageClick,
    setAppMode,
    providerId,
    activeModelConfig,
}) => {
    // ✅ Multi-Agent 工作流执行状态
    const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | undefined>(undefined);
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    const { showError } = useToastContext();

    const [showAgentManager, setShowAgentManager] = useState(false);
    const [agentManagerCount, setAgentManagerCount] = useState(0);
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

    return (
        <GenViewLayout
            sidebarHeaderIcon={<Network size={16} className="text-teal-400" />}
            sidebarTitle={showAgentManager ? (
                <span className="inline-flex items-center gap-1.5">
                    <span>Agent 管理</span>
                    <span className="text-[11px] text-slate-500">({agentManagerCount})</span>
                </span>
            ) : '工作流历史'}
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
                                    onExit={() => setAppMode('chat')}
                                />
                            </Suspense>
                        </div>
                    </div>
                </div>
            }
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
        />
    );
});

MultiAgentView.displayName = 'MultiAgentView';
