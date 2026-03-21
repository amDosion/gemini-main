// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { WorkflowTemplateSaveDialog } from './WorkflowTemplateSaveDialog';

vi.mock('../../services/apiClient', () => ({
  getAuthHeaders: () => ({}),
}));

vi.mock('../../services/workflowTemplateCategoryService', () => ({
  listWorkflowTemplateCategories: vi.fn(async () => [{ name: 'media' }]),
  createWorkflowTemplateCategory: vi.fn(async () => ({ name: 'media' })),
}));

const fetchMock = vi.fn();

describe('WorkflowTemplateSaveDialog', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('defaults to update mode for editable active template and saves via PUT', async () => {
    const onSaveSuccess = vi.fn();
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (typeof input === 'string' && input === '/api/workflows/templates/template-1') {
        return {
          ok: true,
          json: async () => ({
            id: 'template-1',
            name: 'Editable Flow',
            description: 'updated description',
            category: 'media',
            tags: ['editable'],
            config: { nodes: [], edges: [] },
            isEditable: true,
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input} ${init?.method || 'GET'}`);
    });

    render(
      <WorkflowTemplateSaveDialog
        isOpen
        onClose={vi.fn()}
        nodes={[]}
        edges={[]}
        activeTemplate={{
          id: 'template-1',
          name: 'Editable Flow',
          description: 'editable description',
          category: 'media',
          tags: ['editable'],
          isEditable: true,
          isLocked: false,
        }}
        onSaveSuccess={onSaveSuccess}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('更新模板')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Editable Flow')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText('描述这个工作流模板的用途和功能...');
    fireEvent.change(textarea, { target: { value: 'updated description' } });
    fireEvent.click(screen.getByRole('button', { name: /保存覆盖/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows/templates/template-1',
        expect.objectContaining({
          method: 'PUT',
          credentials: 'include',
        }),
      );
    });
    expect(onSaveSuccess).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'template-1',
        name: 'Editable Flow',
      }),
      { mode: 'update' },
    );
  });

  it('falls back to create mode for read-only template source', async () => {
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (typeof input === 'string' && input === '/api/workflows/templates') {
        return {
          ok: true,
          json: async () => ({
            id: 'template-new',
            name: 'Copied Flow',
            description: 'copied template',
            category: 'media',
            tags: [],
            config: { nodes: [], edges: [] },
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${input} ${init?.method || 'GET'}`);
    });

    render(
      <WorkflowTemplateSaveDialog
        isOpen
        onClose={vi.fn()}
        nodes={[]}
        edges={[]}
        activeTemplate={{
          id: 'starter-1',
          name: 'Starter Flow',
          description: 'starter description',
          category: 'media',
          tags: ['starter'],
          isEditable: false,
          isLocked: true,
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('保存为模板')).toBeInTheDocument();
      expect(screen.getByText(/当前画布来自只读模板/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('例如：客户服务工作流'), { target: { value: 'Copied Flow' } });
    fireEvent.change(screen.getByPlaceholderText('描述这个工作流模板的用途和功能...'), {
      target: { value: 'copied template' },
    });
    fireEvent.click(screen.getByRole('button', { name: /保存模板/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows/templates',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        }),
      );
    });
  });
});
