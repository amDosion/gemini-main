// @vitest-environment jsdom
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { WorkflowHistorySidebar } from './WorkflowHistorySidebar';

describe('WorkflowHistorySidebar video metadata', () => {
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
});
