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

const buildNode = (id: string, type: string) =>
  ({
    id,
    type,
    position: { x: 0, y: 0 },
    data: {
      type,
      label: id,
      description: '',
      icon: '',
      iconColor: '',
    },
  }) as any;

const validNodes = [
  buildNode('start', 'start'),
  buildNode('input', 'input_text'),
  buildNode('end', 'end'),
];

const validEdges = [
  { id: 'e-start-input', source: 'start', target: 'input' },
  { id: 'e-input-end', source: 'input', target: 'end' },
] as any;

const invalidNodes = [
  buildNode('start', 'start'),
  buildNode('end', 'end'),
  buildNode('orphan', 'input_text'),
];

const invalidEdges = [{ id: 'e-start-end', source: 'start', target: 'end' }] as any;

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
        nodes={validNodes}
        edges={validEdges}
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
        nodes={validNodes}
        edges={validEdges}
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
        }),
      );
    });
  });

  it('blocks template save locally when workflow graph is invalid', async () => {
    render(
      <WorkflowTemplateSaveDialog
        isOpen
        onClose={vi.fn()}
        nodes={invalidNodes}
        edges={invalidEdges}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('保存为模板')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('例如：客户服务工作流'), {
      target: { value: 'Invalid Flow' },
    });
    fireEvent.change(screen.getByPlaceholderText('描述这个工作流模板的用途和功能...'), {
      target: { value: 'invalid disconnected graph' },
    });
    fireEvent.click(screen.getByRole('button', { name: /保存模板/i }));

    await waitFor(() => {
      expect(screen.getByText(/工作流结构校验失败/)).toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('redacts sensitive credentials from failed save responses', async () => {
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (typeof input === 'string' && input === '/api/workflows/templates') {
        return new Response(
          'save failed for https://files.example.com/template.json?token=secret-save-token&safe=1 with Bearer secret-save-bearer and api_key=secret-save-key',
          {
            status: 500,
            headers: { 'content-type': 'text/plain' },
          },
        );
      }
      throw new Error(`Unexpected fetch: ${input} ${init?.method || 'GET'}`);
    });

    render(
      <WorkflowTemplateSaveDialog
        isOpen
        onClose={vi.fn()}
        nodes={validNodes}
        edges={validEdges}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('保存为模板')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('例如：客户服务工作流'), {
      target: { value: 'Sensitive Failure Flow' },
    });
    fireEvent.change(screen.getByPlaceholderText('描述这个工作流模板的用途和功能...'), {
      target: { value: 'save failure should be redacted' },
    });
    fireEvent.click(screen.getByRole('button', { name: /保存模板/i }));

    await waitFor(() => {
      expect(screen.getByText(/token=REDACTED/)).toBeInTheDocument();
    });

    expect(document.body.textContent).not.toContain('secret-save-token');
    expect(document.body.textContent).not.toContain('secret-save-bearer');
    expect(document.body.textContent).not.toContain('secret-save-key');
    expect(document.body.textContent).toContain('safe=1');
    expect(document.body.textContent).toContain('Bearer REDACTED');
    expect(document.body.textContent).toContain('api_key=REDACTED');
  });
});
