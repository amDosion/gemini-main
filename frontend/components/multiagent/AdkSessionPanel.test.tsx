// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('./adkSessionService', async () => {
  const actual = await vi.importActual<typeof import('./adkSessionService')>('./adkSessionService');
  return {
    ...actual,
    listAdkAgentSessions: vi.fn(),
    getAdkAgentSession: vi.fn(),
    confirmAdkToolCall: vi.fn(),
    rewindAdkSession: vi.fn(),
  };
});

import { AdkSessionPanel } from './AdkSessionPanel';
import * as adkSessionService from './adkSessionService';
import type { AgentDef } from './types';

const listSessionsMock = vi.mocked(adkSessionService.listAdkAgentSessions);
const getSessionMock = vi.mocked(adkSessionService.getAdkAgentSession);
const confirmToolMock = vi.mocked(adkSessionService.confirmAdkToolCall);
const rewindSessionMock = vi.mocked(adkSessionService.rewindAdkSession);

const testAgent: AgentDef = {
  id: 'agent-1',
  name: 'ADK Agent',
  description: 'for test',
  providerId: 'google',
  modelId: 'gemini-2.5-flash',
  systemPrompt: 'You are a helper.',
  temperature: 0.2,
  maxTokens: 1024,
  icon: 'bot',
  color: '#64748b',
  status: 'active',
};

const renderPanel = () => render(<AdkSessionPanel agent={testAgent} onClose={vi.fn()} />);

describe('AdkSessionPanel QA-601 regression matrix', () => {
  beforeEach(() => {
    listSessionsMock.mockReset();
    getSessionMock.mockReset();
    confirmToolMock.mockReset();
    rewindSessionMock.mockReset();

    listSessionsMock.mockResolvedValue([
      {
        id: 'session-1',
        raw: {
          session_id: 'session-1',
          last_used_at: 1710000000000,
        },
      },
    ]);
    confirmToolMock.mockResolvedValue({ status: 'completed', invocation_id: 'inv-after-confirm' });
    rewindSessionMock.mockResolvedValue({ status: 'rewound' });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('[M6] shows backend runtime strategy options and updates local draft display', async () => {
    getSessionMock.mockResolvedValue({
      id: 'session-1',
      raw: {
        session_id: 'session-1',
        runtime_policy: {
          runtime_strategy: 'official_only',
          strict_mode: true,
        },
        runtime_contract: {
          runtime_strategy_values: ['official_only', 'official_or_legacy', 'allow_legacy'],
        },
        events: [],
      },
    });

    renderPanel();

    const strategySelect = (await screen.findByLabelText('runtime_strategy 选择')) as HTMLSelectElement;
    const strictModeSwitch = screen.getByLabelText('strict_mode 切换') as HTMLInputElement;

    await waitFor(() => {
      expect(strategySelect).toHaveValue('official_only');
    });
    expect(screen.getByRole('option', { name: /official_only/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /official_or_legacy/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /allow_legacy/ })).toBeInTheDocument();

    fireEvent.change(strategySelect, { target: { value: 'allow_legacy' } });
    fireEvent.click(strictModeSwitch);

    expect(strategySelect).toHaveValue('allow_legacy');
    expect(strictModeSwitch.checked).toBe(false);
    expect(
      screen.getByText('已选择草案: strategy=allow_legacy · strict_mode=false（仅前端展示，尚未提交后端）')
    ).toBeInTheDocument();
  });

  it('[M1] submits approve request with approvalTicket object from selected candidate', async () => {
    getSessionMock.mockResolvedValue({
      id: 'session-1',
      raw: {
        session_id: 'session-1',
        events: [
          {
            invocation_id: 'inv-002',
            actions: {
              requested_tool_confirmations: {
                'fc-002': {
                  id: 'fc-002',
                  name: 'sheet_analyze',
                  hint: '第二个候选',
                  payload: {
                    source: 'candidate-2',
                  },
                  approval_ticket: {
                    session_id: 'session-1',
                    function_call_id: 'fc-002',
                    invocation_id: 'inv-002',
                    tenant_id: 'tenant-b',
                    nonce: 'nonce-002',
                    timestamp_ms: 1893456000000,
                    ttl_seconds: 120,
                  },
                  confirmation_ticket: 'ticket-002',
                  nonce: 'nonce-002',
                  nonce_expires_at: '2099-01-01T00:00:00.000Z',
                  tenant_id: 'tenant-b',
                },
              },
            },
          },
        ],
      },
    });

    renderPanel();

    await screen.findByLabelText('候选确认项列表');
    fireEvent.click(screen.getByRole('button', { name: '一键填充候选项' }));

    const hintInput = screen.getByPlaceholderText('hint (可选)') as HTMLInputElement;
    const payloadInput = screen.getByPlaceholderText('payload JSON (可选)') as HTMLTextAreaElement;

    fireEvent.change(hintInput, {
      target: {
        value: '手工覆盖 hint',
      },
    });
    fireEvent.change(payloadInput, {
      target: {
        value: '{"manual":true}',
      },
    });

    fireEvent.click(screen.getByRole('button', { name: '提交批准' }));

    await waitFor(() => {
      expect(confirmToolMock).toHaveBeenCalled();
    });

    expect(confirmToolMock).toHaveBeenCalledWith(
      'agent-1',
      'session-1',
      expect.objectContaining({
        functionCallId: 'fc-002',
        confirmed: true,
        hint: '手工覆盖 hint',
        payload: { manual: true },
        invocationId: 'inv-002',
        ticket: 'ticket-002',
        approvalTicket: expect.objectContaining({
          session_id: 'session-1',
          function_call_id: 'fc-002',
          invocation_id: 'inv-002',
          tenant_id: 'tenant-b',
          nonce: 'nonce-002',
          timestamp_ms: 1893456000000,
          ttl_seconds: 120,
        }),
        nonce: 'nonce-002',
        nonceExpiresAt: '2099-01-01T00:00:00.000Z',
        tenantId: 'tenant-b',
        candidateId: 'fc-002',
      })
    );
  });

  it('[M2] shows explicit reject action only when backend contract supports it', async () => {
    getSessionMock.mockResolvedValue({
      id: 'session-1',
      raw: {
        session_id: 'session-1',
        confirm_tool_contract: {
          supports_reject: true,
        },
        events: [],
      },
    });

    renderPanel();

    const functionCallIdInput = await screen.findByPlaceholderText('function_call_id');
    fireEvent.change(functionCallIdInput, {
      target: {
        value: 'manual-fc-999',
      },
    });

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith('agent-1', 'session-1');
      expect(screen.getByLabelText('拒绝')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText('拒绝'));
    expect(screen.getByRole('button', { name: '提交拒绝' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '提交拒绝' }));

    await waitFor(() => {
      expect(confirmToolMock).toHaveBeenCalledWith(
        'agent-1',
        'session-1',
        expect.objectContaining({
          functionCallId: 'manual-fc-999',
          confirmed: false,
        })
      );
    });
  });

  it('[M3] keeps session read path available and hides reject submit when unsupported', async () => {
    getSessionMock.mockResolvedValue({
      id: 'session-1',
      raw: {
        session_id: 'session-1',
        runtime_state: {
          runtime_available: false,
        },
        events: [],
      },
    });

    renderPanel();

    await waitFor(() => {
      expect(listSessionsMock).toHaveBeenCalledWith('agent-1');
      expect(getSessionMock).toHaveBeenCalledWith('agent-1', 'session-1');
    });

    expect(await screen.findByRole('button', { name: '提交批准' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '提交拒绝' })).not.toBeInTheDocument();
    expect(screen.getByText(/session_id/)).toBeInTheDocument();
  });

  it('[M7] allows manual approve submission when no confirm candidates are extracted', async () => {
    getSessionMock.mockResolvedValue({
      id: 'session-1',
      raw: {
        session_id: 'session-1',
        events: [],
      },
    });

    renderPanel();

    fireEvent.change(await screen.findByPlaceholderText('function_call_id'), {
      target: { value: 'manual-fc-101' },
    });
    fireEvent.change(screen.getByPlaceholderText('invocation_id (批准必填)'), {
      target: { value: 'manual-inv-101' },
    });
    fireEvent.change(screen.getByPlaceholderText('confirmation_ticket'), {
      target: { value: 'manual-ticket-101' },
    });
    fireEvent.change(screen.getByPlaceholderText('nonce'), {
      target: { value: 'manual-nonce-101' },
    });
    fireEvent.change(screen.getByPlaceholderText('nonce_expires_at (ISO/ms)'), {
      target: { value: '2099-01-01T00:00:00.000Z' },
    });

    fireEvent.click(screen.getByRole('button', { name: '提交批准' }));

    await waitFor(() => {
      expect(confirmToolMock).toHaveBeenCalledWith(
        'agent-1',
        'session-1',
        expect.objectContaining({
          functionCallId: 'manual-fc-101',
          invocationId: 'manual-inv-101',
          ticket: 'manual-ticket-101',
          nonce: 'manual-nonce-101',
          nonceExpiresAt: '2099-01-01T00:00:00.000Z',
          confirmed: true,
        })
      );
    });
  });
});
