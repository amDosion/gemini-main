// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('../../services/apiClient', () => ({
  getAuthHeaders: () => ({}),
}));

vi.mock('../../services/workflowTemplateCategoryService', () => ({
  listWorkflowTemplateCategories: vi.fn(async () => [{ name: 'media' }]),
  createWorkflowTemplateCategory: vi.fn(async () => ({ name: 'media' })),
}));

import { WorkflowTemplateSelector } from './WorkflowTemplateSelector';

const fetchMock = vi.fn();

describe('WorkflowTemplateSelector media result preview', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === '/api/auth/me') {
        return {
          ok: true,
          json: async () => ({ id: 'user-1' }),
        };
      }
      if (input === '/api/workflows/templates') {
        return {
          ok: true,
          json: async () => ({
            templates: [
              {
                id: 'template-media-preview',
                name: 'Media Template',
                description: 'template with sample media result',
                category: 'media',
                tags: [],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                config: { nodes: [], edges: [] },
                sampleResultSummary: {
                  hasResult: true,
                  textPreview: '样例媒体结果',
                  imageCount: 0,
                  imageUrls: [],
                  audioCount: 1,
                  audioUrls: ['https://cdn.example.com/sample.mp3'],
                  videoCount: 1,
                  videoUrls: ['https://cdn.example.com/sample.mp4'],
                  continuationStrategy: 'video_extension_chain',
                  videoExtensionApplied: 3,
                  totalDurationSeconds: 29,
                  subtitleMode: 'vtt',
                  subtitleFileCount: 1,
                },
              },
            ],
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input}`);
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders audio and video sample result previews for selected template', async () => {
    render(
      <WorkflowTemplateSelector
        isOpen
        onClose={vi.fn()}
        onLoadTemplate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Media Template')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Media Template/ }));

    await waitFor(() => {
      expect(screen.getByText('模板最近结果')).toBeInTheDocument();
      expect(screen.getByText('视频结果（1）')).toBeInTheDocument();
      expect(screen.getByText('音频结果（1）')).toBeInTheDocument();
      expect(screen.getAllByText('延长 3 次').length).toBeGreaterThan(0);
      expect(screen.getAllByText('总时长 29s').length).toBeGreaterThan(0);
      expect(screen.getAllByText('字幕 · 1').length).toBeGreaterThan(0);
      expect(screen.getByText('官方续接')).toBeInTheDocument();
    });

    expect(document.querySelector('video')).toBeTruthy();
    expect(document.querySelector('audio')).toBeTruthy();
  });

  it('surfaces origin/runtime labels without extra top filter rows', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === '/api/auth/me') {
        return {
          ok: true,
          json: async () => ({ id: 'user-1' }),
        };
      }
      if (input === '/api/workflows/templates') {
        return {
          ok: true,
          json: async () => ({
            templates: [
              {
                id: 'template-user-copy',
                userId: 'user-1',
                name: 'My Workflow Copy',
                description: 'user-owned template',
                category: 'media',
                tags: ['video'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                copiedFromStarterKey: 'adk_sample_camel_v1',
                origin: {
                  kind: 'user',
                  label: '我的模板',
                  isLocked: false,
                  runtimeScope: 'google-runtime',
                  runtimeLabel: 'Google runtime',
                },
                config: { nodes: [], edges: [] },
              },
              {
                id: 'template-starter',
                userId: 'user-1',
                name: 'Official Starter',
                description: 'starter template',
                category: 'media',
                tags: ['adk'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                isStarter: true,
                starterKey: 'adk_sample_camel_v1',
                origin: {
                  kind: 'starter',
                  label: '官方 Starter',
                  isLocked: true,
                  runtimeScope: 'google-runtime',
                  runtimeLabel: 'Google runtime',
                },
                config: { nodes: [], edges: [] },
              },
            ],
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input}`);
    });

    render(
      <WorkflowTemplateSelector
        isOpen
        onClose={vi.fn()}
        onLoadTemplate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('My Workflow Copy')).toBeInTheDocument();
      expect(screen.getByText('Official Starter')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Official Starter/i }));

    await waitFor(() => {
      expect(screen.getAllByText('官方 Starter').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Google runtime').length).toBeGreaterThan(0);
      expect(screen.getByText(/这是官方 Starter 模板/)).toBeInTheDocument();
    });

    const editButton = screen.getByRole('button', { name: /编辑标题/i });
    expect(editButton).toBeDisabled();
  });

  it('loads editable template into canvas when edit button is clicked', async () => {
    const onLoadTemplate = vi.fn();
    const onClose = vi.fn();

    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === '/api/auth/me') {
        return {
          ok: true,
          json: async () => ({ id: 'user-1' }),
        };
      }
      if (input === '/api/workflows/templates') {
        return {
          ok: true,
          json: async () => ({
            templates: [
              {
                id: 'template-editable',
                userId: 'user-1',
                name: 'Editable Flow',
                description: 'editable user template',
                category: 'media',
                tags: ['editable'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                origin: {
                  kind: 'user',
                  label: '我的模板',
                  isLocked: false,
                },
                isEditable: true,
                config: { nodes: [], edges: [] },
              },
            ],
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input}`);
    });

    render(
      <WorkflowTemplateSelector
        isOpen
        onClose={onClose}
        onLoadTemplate={onLoadTemplate}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Editable Flow')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Editable Flow/i }));
    fireEvent.click(screen.getByRole('button', { name: /编辑模板/i }));

    expect(onLoadTemplate).toHaveBeenCalledTimes(1);
    expect(onLoadTemplate.mock.calls[0][0]).toMatchObject({
      id: 'template-editable',
      name: 'Editable Flow',
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('hides legacy starter copies by default', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === '/api/auth/me') {
        return {
          ok: true,
          json: async () => ({ id: 'user-1' }),
        };
      }
      if (input === '/api/workflows/templates') {
        return {
          ok: true,
          json: async () => ({
            templates: [
              {
                id: 'legacy-copy',
                userId: 'user-1',
                name: 'Legacy Data Copy',
                description: 'legacy starter copy',
                category: '数据分析',
                tags: ['data-analysis'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                copiedFromStarterKey: 'table_analysis_v1',
                taskTypes: ['data-analysis'],
                primaryTaskType: 'data-analysis',
                bindingStrategy: 'registry-name',
                isLegacyStarterCopy: true,
                runtimeScope: 'provider-neutral',
                runtimeLabel: 'Provider-neutral',
                origin: {
                  kind: 'user',
                  label: '我的模板',
                  isLocked: false,
                  runtimeScope: 'provider-neutral',
                  runtimeLabel: 'Provider-neutral',
                },
                config: { nodes: [], edges: [] },
              },
              {
                id: 'provider-video',
                userId: 'user-1',
                name: 'Provider Video Flow',
                description: 'provider neutral video',
                category: '多模态工作流',
                tags: ['video-gen'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                taskTypes: ['video-gen'],
                primaryTaskType: 'video-gen',
                runtimeScope: 'provider-neutral',
                runtimeLabel: 'Provider-neutral',
                origin: {
                  kind: 'starter',
                  label: '官方 Starter',
                  isLocked: true,
                  runtimeScope: 'provider-neutral',
                  runtimeLabel: 'Provider-neutral',
                },
                config: { nodes: [], edges: [] },
              },
              {
                id: 'google-data',
                userId: 'user-1',
                name: 'Google Data Flow',
                description: 'google runtime data analysis',
                category: '数据分析',
                tags: ['data-analysis', 'google-adk'],
                createdAt: Date.now(),
                updatedAt: Date.now(),
                taskTypes: ['data-analysis'],
                primaryTaskType: 'data-analysis',
                runtimeScope: 'google-runtime',
                runtimeLabel: 'Google runtime',
                origin: {
                  kind: 'starter',
                  label: '官方 Starter',
                  isLocked: true,
                  runtimeScope: 'google-runtime',
                  runtimeLabel: 'Google runtime',
                },
                config: { nodes: [], edges: [] },
              },
            ],
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input}`);
    });

    render(
      <WorkflowTemplateSelector
        isOpen
        onClose={vi.fn()}
        onLoadTemplate={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Provider Video Flow')).toBeInTheDocument();
      expect(screen.getByText('Google Data Flow')).toBeInTheDocument();
    });

    expect(screen.queryByText('Legacy Data Copy')).not.toBeInTheDocument();
    expect(screen.getByText(/已默认隐藏 1 个遗留 Starter 副本/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /显示遗留 Starter 副本 1/i }));

    await waitFor(() => {
      expect(screen.getByText('Legacy Data Copy')).toBeInTheDocument();
    });
  });
});
