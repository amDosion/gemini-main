// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({
    src,
    alt,
    source,
    preferMemoryCache,
    replaceCachedObjectUrl,
    rawFallbackDelayMs: _rawFallbackDelayMs,
    ...props
  }: any) => (
    <img
      data-source-url={source?.url || ''}
      data-prefer-memory-cache={String(preferMemoryCache)}
      data-replace-cached-object-url={String(replaceCachedObjectUrl)}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import { WorkflowHistorySidebar } from './WorkflowHistorySidebar';

describe('WorkflowHistorySidebar video metadata', () => {
  afterEach(() => {
    cleanup();
  });

  const baseSidebarProps = {
    historySearchQuery: '',
    historyLoading: false,
    historyError: null,
    selectedHistoryId: null,
    loadingHistoryId: null,
    deletingHistoryId: null,
    downloadingHistoryId: null,
    downloadingAnalysisId: null,
    downloadMediaProgress: {},
    downloadAnalysisProgress: {},
    previewingHistoryId: null,
    onHistorySearchQueryChange: vi.fn(),
    onRefreshHistory: vi.fn(),
    onLoadWorkflowFromHistory: vi.fn(),
    onDeleteWorkflowHistory: vi.fn(),
    onDownloadWorkflowMedia: vi.fn(),
    onDownloadWorkflowAnalysis: vi.fn(),
    onToggleWorkflowMediaPreview: vi.fn(),
    onOpenAgentManager: vi.fn(),
    onImageClick: vi.fn(),
    formatHistoryTime: () => '刚刚',
    formatHistoryDuration: () => '1s',
    getHistoryStatusLabel: () => '已完成',
    getHistoryStatusClass: () => 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  };

  const imageWorkflowHistoryItem = {
    id: 'exec-image-preview',
    status: 'completed' as const,
    title: 'Image Workflow',
    source: 'template' as const,
    task: 'Generate images',
    resultPreview: 'image result',
    resultImageCount: 1,
    resultImageUrls: ['/api/storage/local-files/workflow/history-preview.png'],
    resultAudioCount: 0,
    resultAudioUrls: [],
    resultVideoCount: 0,
    resultVideoUrls: [],
    startedAt: Date.now(),
    nodeCount: 2,
    edgeCount: 1,
  };

  it('renders workflow video metadata badges from result summary', () => {
    render(
      <WorkflowHistorySidebar
        historySearchQuery=""
        historyLoading={false}
        historyError={null}
        displayedWorkflowHistory={[
          {
            id: 'exec-video-meta',
            status: 'completed',
            title: 'Video Workflow',
            source: 'template',
            task: 'Generate promo',
            resultPreview: 'extended video result',
            resultImageCount: 0,
            resultImageUrls: [],
            resultAudioCount: 0,
            resultAudioUrls: [],
            resultVideoCount: 1,
            resultVideoUrls: ['/api/temp-images/video-1'],
            continuationStrategy: 'video_extension_chain',
            videoExtensionApplied: 3,
            totalDurationSeconds: 29,
            subtitleMode: 'vtt',
            subtitleFileCount: 1,
            primaryRuntime: 'google',
            runtimeHints: ['google'],
            startedAt: Date.now(),
            nodeCount: 4,
            edgeCount: 3,
          },
        ]}
        historyPreviewImages={{}}
        historyPreviewMedia={{}}
        expandedPreviewHistoryId={null}
        selectedHistoryId={null}
        loadingHistoryId={null}
        deletingHistoryId={null}
        downloadingHistoryId={null}
        downloadingAnalysisId={null}
        downloadMediaProgress={{}}
        downloadAnalysisProgress={{}}
        previewingHistoryId={null}
        onHistorySearchQueryChange={vi.fn()}
        onRefreshHistory={vi.fn()}
        onLoadWorkflowFromHistory={vi.fn()}
        onDeleteWorkflowHistory={vi.fn()}
        onDownloadWorkflowMedia={vi.fn()}
        onDownloadWorkflowAnalysis={vi.fn()}
        onToggleWorkflowMediaPreview={vi.fn()}
        onOpenAgentManager={vi.fn()}
        onImageClick={vi.fn()}
        formatHistoryTime={() => '刚刚'}
        formatHistoryDuration={() => '29s'}
        getHistoryStatusLabel={() => '已完成'}
        getHistoryStatusClass={() => 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'}
      />
    );

    expect(screen.getByText('延长 3 次')).toBeInTheDocument();
    expect(screen.getByText('总时长 29s')).toBeInTheDocument();
    expect(screen.getByText('字幕 · 1')).toBeInTheDocument();
    expect(screen.getByText('官方续接')).toBeInTheDocument();
  });

  it('renders expanded history image previews through the shared cached image component', () => {
    render(
      <WorkflowHistorySidebar
        {...baseSidebarProps}
        displayedWorkflowHistory={[imageWorkflowHistoryItem]}
        historyPreviewImages={{
          'exec-image-preview': ['/api/storage/local-files/workflow/history-preview.png'],
        }}
        historyPreviewMedia={{}}
        expandedPreviewHistoryId="exec-image-preview"
      />
    );

    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/history-preview.png'
    );
    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/history-preview.png'
    );
    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'data-prefer-memory-cache',
      'true'
    );
    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'data-replace-cached-object-url',
      'false'
    );
    expect(screen.getByAltText('workflow-preview-1')).not.toHaveAttribute('loading');
  });

  it('updates expanded preview images from stale blob urls to durable workflow storage urls', () => {
    const { rerender } = render(
      <WorkflowHistorySidebar
        {...baseSidebarProps}
        displayedWorkflowHistory={[imageWorkflowHistoryItem]}
        historyPreviewImages={{
          'exec-image-preview': ['blob:https://gemini.dicry.cn:18443/stale-workflow-preview'],
        }}
        historyPreviewMedia={{}}
        expandedPreviewHistoryId="exec-image-preview"
      />
    );

    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'data-source-url',
      'blob:https://gemini.dicry.cn:18443/stale-workflow-preview'
    );

    rerender(
      <WorkflowHistorySidebar
        {...baseSidebarProps}
        displayedWorkflowHistory={[imageWorkflowHistoryItem]}
        historyPreviewImages={{
          'exec-image-preview': ['/api/storage/local-files/workflow/history-preview-new.png'],
        }}
        historyPreviewMedia={{}}
        expandedPreviewHistoryId="exec-image-preview"
      />
    );

    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/history-preview-new.png'
    );
    expect(screen.getByAltText('workflow-preview-1')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/history-preview-new.png'
    );
  });
});
