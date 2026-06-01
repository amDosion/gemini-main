// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExecutionLogPanel, type LogEntry } from './ExecutionLogPanel';
import { WorkflowAdvancedFeatures } from './WorkflowAdvancedFeatures';

const { downloadBlobInBrowserMock } = vi.hoisted(() => ({
  downloadBlobInBrowserMock: vi.fn(),
}));

vi.mock('../../services/downloadService', () => ({
  downloadBlobInBrowser: downloadBlobInBrowserMock,
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showSuccess: vi.fn(),
    showError: vi.fn(),
  }),
}));

vi.mock('./workflowSerialization', () => ({
  exportWorkflow: vi.fn(() => '{"nodes":[{"id":"node-1"}],"edges":[]}'),
  importWorkflow: vi.fn(),
}));

vi.mock('./workflowUtils', () => ({
  validateWorkflow: vi.fn(() => ({
    isValid: true,
    globalErrors: [],
    nodeErrors: {},
  })),
}));

describe('multi-agent downloads', () => {
  beforeEach(() => {
    downloadBlobInBrowserMock.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('routes execution log export through the shared browser download service', async () => {
    const logs: LogEntry[] = [
      {
        id: 'log-1',
        timestamp: Date.UTC(2026, 4, 31, 10, 0, 0),
        nodeId: 'node-1',
        nodeName: '主图生成',
        level: 'info',
        message: 'started',
      },
    ];

    render(<ExecutionLogPanel logs={logs} isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('导出日志'));

    await waitFor(() => {
      expect(downloadBlobInBrowserMock).toHaveBeenCalledTimes(1);
    });
    const options = downloadBlobInBrowserMock.mock.calls[0]?.[0];
    expect(options.fileName).toMatch(/^workflow-logs-\d+\.txt$/);
    expect(options.blob.type).toBe('text/plain');
    await expect(options.blob.text()).resolves.toContain('[INFO] [主图生成] started');
  });

  it('routes workflow JSON export through the shared browser download service', async () => {
    render(
      <WorkflowAdvancedFeatures
        nodes={[
          {
            id: 'node-1',
            type: 'custom',
            position: { x: 0, y: 0 },
            data: {
              label: '主图生成',
              type: 'agent',
              config: {},
            } as any,
          },
        ]}
        edges={[]}
        onNodesChange={vi.fn()}
        onEdgesChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('导出工作流 (Ctrl+E)'));

    await waitFor(() => {
      expect(downloadBlobInBrowserMock).toHaveBeenCalledTimes(1);
    });
    const options = downloadBlobInBrowserMock.mock.calls[0]?.[0];
    expect(options.fileName).toMatch(/^workflow-\d+\.json$/);
    expect(options.blob.type).toBe('application/json');
    await expect(options.blob.text()).resolves.toContain('"node-1"');
  });
});
