// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const { directWorkflowImageUrl, lazyWorkflowImageUrl, fetchWorkflowPreviewImagesWithMetaMock } =
  vi.hoisted(() => ({
    directWorkflowImageUrl: 'https://cdn.example.com/workflow/direct.png',
    lazyWorkflowImageUrl: 'https://cdn.example.com/workflow/lazy.png',
    fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
  }));

vi.mock('../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source: _source, ...props }: any) => (
    <img src={src} alt={alt} {...props} />
  ),
}));

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebarExtraHeader, main, mainOverlay }: any) => (
    <div>
      <div data-testid="workflow-sidebar-header">{sidebarExtraHeader}</div>
      <div className="flex-1 flex flex-col min-w-0 bg-slate-950 relative">
        {main}
        {mainOverlay}
      </div>
    </div>
  ),
}));

vi.mock('../multiagent', () => ({
  MultiAgentWorkflowEditorReactFlow: () => <div data-testid="workflow-editor" />,
}));

vi.mock('../multiagent/AgentManagerPanel', () => ({
  AGENT_MANAGER_CREATE_EVENT: 'agent:create',
  AGENT_MANAGER_REFRESH_EVENT: 'agent:refresh',
  AgentManagerPanel: () => <div data-testid="agent-manager" />,
}));

vi.mock('./multiagent/WorkflowHistorySidebar', () => ({
  WorkflowHistorySidebar: () => <div data-testid="workflow-history-sidebar" />,
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({ showError: vi.fn() }),
}));

vi.mock('../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
}));

vi.mock('./multiagent/useWorkflowHistoryController', () => ({
  useWorkflowHistoryController: () => ({
    historySearchQuery: '',
    historyLoading: false,
    historyError: null,
    displayedWorkflowHistory: [
      {
        id: 'exec-direct',
        status: 'completed',
        title: '已有图片的工作流',
        task: '生成主图',
        resultPreview: '',
        resultImageCount: 1,
        resultImageUrls: [directWorkflowImageUrl],
        resultAudioCount: 0,
        resultAudioUrls: [],
        resultVideoCount: 0,
        resultVideoUrls: [],
        startedAt: 1779624000000,
        nodeCount: 1,
        edgeCount: 0,
      },
      {
        id: 'exec-lazy',
        status: 'completed',
        title: '需要懒加载图片的工作流',
        task: '生成细节图',
        resultPreview: '',
        resultImageCount: 1,
        resultImageUrls: [],
        resultAudioCount: 0,
        resultAudioUrls: [],
        resultVideoCount: 0,
        resultVideoUrls: [],
        startedAt: 1779624100000,
        nodeCount: 1,
        edgeCount: 0,
      },
    ],
    historyPreviewImages: {},
    historyPreviewMedia: {},
    expandedPreviewHistoryId: null,
    selectedHistoryId: null,
    loadingHistoryId: null,
    deletingHistoryId: null,
    downloadingHistoryId: null,
    downloadingAnalysisId: null,
    downloadMediaProgress: {},
    downloadAnalysisProgress: {},
    previewingHistoryId: null,
    workflowLoadRequest: null,
    isMountedRef: { current: true },
    activeExecutionControllerRef: { current: null },
    activeExecutionCleanupRef: { current: null },
    setHistorySearchQuery: vi.fn(),
    createRequestController: () => new AbortController(),
    releaseRequestController: vi.fn(),
    fetchWorkflowHistory: vi.fn(),
    handleLoadWorkflowFromHistory: vi.fn(),
    handleDeleteWorkflowHistory: vi.fn(),
    handleDownloadWorkflowMedia: vi.fn(),
    handleDownloadWorkflowAnalysis: vi.fn(),
    handleToggleWorkflowMediaPreview: vi.fn(),
  }),
}));

vi.mock('./multiagent/useWorkflowExecutionController', () => ({
  useWorkflowExecutionController: () => ({ handleWorkflowExecute: vi.fn() }),
}));

import { MultiAgentView } from './MultiAgentView';

describe('MultiAgentView workflow media images', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('opens all media images from the displayed workflow history and lazy-loads missing previews', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [lazyWorkflowImageUrl],
      skippedCount: 0,
      count: 1,
    });

    render(
      <MultiAgentView
        {...({
          setAppMode: vi.fn(),
          onImageClick: vi.fn(),
          providerId: 'gemini',
          activeModelConfig: { id: 'model-1', name: 'Model 1' },
        } as any)}
      />
    );

    const header = screen.getByTestId('workflow-sidebar-header');
    const mediaButton = screen.getByRole('button', { name: '查看全部媒体图片' });
    expect(header).toContainElement(mediaButton);
    expect(mediaButton).toHaveAttribute('title', '查看全部媒体图片（2）');

    fireEvent.click(mediaButton);

    expect(screen.getByText('全部媒体图片')).toBeInTheDocument();
    expect(screen.getByText('2 张')).toBeInTheDocument();
    expect(screen.getByAltText('媒体图片 1')).toHaveAttribute('src', directWorkflowImageUrl);

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-lazy',
        40
      );
    });
    expect(await screen.findByAltText('媒体图片 2')).toHaveAttribute('src', lazyWorkflowImageUrl);
  });
});
