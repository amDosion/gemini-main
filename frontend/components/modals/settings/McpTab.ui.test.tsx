// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

const mocks = vi.hoisted(() => {
  const mcpService = {
    getConfig: vi.fn(),
    saveConfig: vi.fn(),
    getServerTools: vi.fn(),
    stopSessions: vi.fn(),
    invokeServerTool: vi.fn(),
  };

  return {
    mcpService,
    callSkybridgeTool: vi.fn(),
    getSkybridgeHostType: vi.fn(),
    isSkybridgeHostAvailable: vi.fn(),
  };
});

vi.mock('../../../services/mcpConfigService', () => ({
  default: mocks.mcpService,
  mcpConfigService: mocks.mcpService,
}));

vi.mock('../../../services/skybridgeToolService', () => ({
  callSkybridgeTool: mocks.callSkybridgeTool,
  getSkybridgeHostType: mocks.getSkybridgeHostType,
  isSkybridgeHostAvailable: mocks.isSkybridgeHostAvailable,
}));

import { McpTab } from './McpTab';

const baseConfigPayload = {
  configJson: JSON.stringify(
    {
      mcpServers: {
        'demo-server': {
          serverType: 'stdio',
          command: 'node',
          args: ['server.js'],
        },
      },
    },
    null,
    2
  ),
  updatedAt: '2026-03-05T10:00:00Z',
};

const baseToolsPayload = {
  serverKey: 'demo-server',
  toolCount: 1,
  tools: [{ name: 'analyze_excel', description: 'Analyze spreadsheet data' }],
};

const baseInvokePayload = {
  serverKey: 'demo-server',
  toolName: 'analyze_excel',
  sessionId: 'session-1',
  latencyMs: 18,
  timestamp: Date.now(),
  success: true,
  isError: false,
  result: { summary: 'ok' },
};

const renderAndWaitLoaded = async () => {
  render(<McpTab />);
  await screen.findByText('demo-server');
};

describe('McpTab UI-equivalent workflow tests', () => {
  beforeEach(() => {
    mocks.mcpService.getConfig.mockResolvedValue(baseConfigPayload);
    mocks.mcpService.getServerTools.mockResolvedValue(baseToolsPayload);
    mocks.mcpService.invokeServerTool.mockResolvedValue(baseInvokePayload);

    mocks.getSkybridgeHostType.mockReturnValue(null);
    mocks.isSkybridgeHostAvailable.mockReturnValue(false);
    mocks.callSkybridgeTool.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('loads MCP cards and lazily loads tools only after click', async () => {
    await renderAndWaitLoaded();

    expect(mocks.mcpService.getServerTools).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Load' }));

    await waitFor(() => {
      expect(mocks.mcpService.getServerTools).toHaveBeenCalledWith('demo-server');
    });
    expect(await screen.findByText('analyze_excel')).toBeInTheDocument();
  });

  it('runs tool via backend bridge when skybridge host is unavailable', async () => {
    await renderAndWaitLoaded();

    fireEvent.click(screen.getByRole('button', { name: 'Load' }));
    await screen.findByText('analyze_excel');

    fireEvent.click(screen.getByRole('button', { name: 'Run' }));
    await screen.findByText('Tool Invocation');

    fireEvent.click(screen.getByRole('button', { name: 'Run tool' }));

    await waitFor(() => {
      expect(mocks.mcpService.invokeServerTool).toHaveBeenCalledWith(
        'demo-server',
        'analyze_excel',
        {}
      );
    });

    expect(screen.getByText(/Executed via backend MCP bridge/i)).toBeInTheDocument();
    expect(screen.getByText(/Mode:\s*Backend Bridge/i)).toBeInTheDocument();
  });

  it('falls back to backend bridge when skybridge call fails', async () => {
    mocks.getSkybridgeHostType.mockReturnValue('mcp-app');
    mocks.isSkybridgeHostAvailable.mockReturnValue(true);
    mocks.callSkybridgeTool.mockRejectedValue(new Error('skybridge down'));

    await renderAndWaitLoaded();

    fireEvent.click(screen.getByRole('button', { name: 'Load' }));
    await screen.findByText('analyze_excel');
    fireEvent.click(screen.getByRole('button', { name: 'Run' }));
    await screen.findByText('Tool Invocation');
    fireEvent.click(screen.getByRole('button', { name: 'Run tool' }));

    await waitFor(() => {
      expect(mocks.callSkybridgeTool).toHaveBeenCalledWith('analyze_excel', {});
      expect(mocks.mcpService.invokeServerTool).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText(/fell back to backend bridge/i)).toBeInTheDocument();
    expect(screen.getByText(/Mode:\s*Backend Bridge/i)).toBeInTheDocument();
  });

  it('uses skybridge mode directly when host call succeeds', async () => {
    mocks.getSkybridgeHostType.mockReturnValue('apps-sdk');
    mocks.isSkybridgeHostAvailable.mockReturnValue(true);
    mocks.callSkybridgeTool.mockResolvedValue({
      structuredContent: { output: 'from-skybridge' },
      isError: false,
      result: 'ok',
    });

    await renderAndWaitLoaded();

    fireEvent.click(screen.getByRole('button', { name: 'Load' }));
    await screen.findByText('analyze_excel');
    fireEvent.click(screen.getByRole('button', { name: 'Run' }));
    await screen.findByText('Tool Invocation');
    fireEvent.click(screen.getByRole('button', { name: 'Run tool' }));

    await waitFor(() => {
      expect(mocks.callSkybridgeTool).toHaveBeenCalledWith('analyze_excel', {});
    });

    expect(mocks.mcpService.invokeServerTool).not.toHaveBeenCalled();
    expect(screen.getByText(/Mode:\s*Skybridge Host/i)).toBeInTheDocument();
    expect(screen.getByText(/from-skybridge/i)).toBeInTheDocument();
  });
});
