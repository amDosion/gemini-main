import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/http', () => ({
  requestJson: vi.fn(),
}));

import { requestJson } from '../../services/http';
import {
  confirmAdkToolCall,
  extractAdkConfirmActionSupport,
  extractAdkConfirmCandidates,
  extractAdkRuntimePolicyState,
  formatAdkRuntimeContractErrorMessage,
  getAdkAgentSession,
  listAdkAgentSessions,
} from './adkSessionService';

const requestJsonMock = vi.mocked(requestJson);
const FIXED_NOW_MS = 1_750_000_000_000;
const FIXED_APPROVAL_TTL_SECONDS = 30 * 60;
let dateNowSpy: ReturnType<typeof vi.spyOn> | null = null;

describe('adkSessionService QA-601 regression matrix', () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
    dateNowSpy = vi.spyOn(Date, 'now').mockReturnValue(FIXED_NOW_MS);
  });

  afterEach(() => {
    dateNowSpy?.mockRestore();
    dateNowSpy = null;
  });

  it('[M1] does not infer candidate id from object key fallback', () => {
    const snapshot = {
      events: [
        {
          invocation_id: 'inv-01',
          actions: {
            requested_tool_confirmations: {
              'fc-from-key-only': {
                name: 'sheet_analyze',
                hint: 'no authoritative id',
              },
            },
          },
        },
      ],
    };

    expect(extractAdkConfirmCandidates(snapshot)).toEqual([]);
  });

  it('[M1] builds full approval_ticket payload and keeps legacy fields for compatibility', async () => {
    requestJsonMock.mockResolvedValue({ status: 'completed' });

    await confirmAdkToolCall('agent-1', 'session-1', {
      functionCallId: 'fc-1',
      confirmed: true,
      invocationId: 'inv-1',
      ticket: 'legacy-ticket-1',
      nonce: 'nonce-1',
      nonceExpiresAt: '2099-01-01T00:00:00.000Z',
      tenantId: 'tenant-a',
    });

    const [requestUrl, requestInit] = requestJsonMock.mock.calls[0] as [string, RequestInit & { body?: string }];
    expect(requestUrl).toBe('/api/multi-agent/agents/agent-1/runtime/sessions/session-1/confirm-tool');
    const body = JSON.parse(String(requestInit.body || '{}'));

    expect(body.function_call_id).toBe('fc-1');
    expect(body.confirmed).toBe(true);
    expect(body.approval_ticket).toEqual(expect.objectContaining({
      session_id: 'session-1',
      function_call_id: 'fc-1',
      invocation_id: 'inv-1',
      tenant_id: 'tenant-a',
      nonce: 'nonce-1',
      ticket: 'legacy-ticket-1',
    }));
    expect(body.approval_ticket.timestamp_ms).toBe(FIXED_NOW_MS);
    expect(body.approval_ticket.ttl_seconds).toBe(FIXED_APPROVAL_TTL_SECONDS);

    expect(body.confirmation_ticket).toBe('legacy-ticket-1');
    expect(body.ticket).toBe('legacy-ticket-1');
    expect(body.nonce_expires_at).toBe('2099-01-01T00:00:00.000Z');
    expect(body.ticket_timestamp_ms).toBe(FIXED_NOW_MS);
    expect(body.ticket_ttl_seconds).toBe(FIXED_APPROVAL_TTL_SECONDS);
  });

  it('[M2] extracts explicit reject support from backend contract flags', () => {
    const supported = extractAdkConfirmActionSupport({
      confirm_tool_contract: {
        supports_reject: true,
      },
    });
    expect(supported.supportsExplicitReject).toBe(true);

    const unsupported = extractAdkConfirmActionSupport({
      session_id: 'session-1',
      events: [],
    });
    expect(unsupported.supportsExplicitReject).toBe(false);
  });

  it('[M3] keeps session read helpers available and normalizes ids', async () => {
    requestJsonMock
      .mockResolvedValueOnce({
        sessions: [
          { session_id: 'session-a', updated_at: 123 },
          { id: 'session-b', updated_at: 456 },
          { updated_at: 789 },
        ],
      })
      .mockResolvedValueOnce({
        session: {
          id: 'session-a',
          runtime_state: {
            runtime_available: false,
          },
        },
      });

    const sessions = await listAdkAgentSessions('agent-1');
    expect(requestJsonMock.mock.calls[0]?.[0]).toBe('/api/multi-agent/agents/agent-1/runtime/sessions');
    expect(sessions.map((item) => item.id)).toEqual(['session-a', 'session-b']);

    const snapshot = await getAdkAgentSession('agent-1', 'session-a');
    expect(requestJsonMock.mock.calls[1]?.[0]).toBe('/api/multi-agent/agents/agent-1/runtime/sessions/session-a');
    expect(snapshot.id).toBe('session-a');
    expect(snapshot.raw).toEqual(expect.objectContaining({ id: 'session-a' }));
  });

  it('[M6] uses backend runtime strategy enum values and removes legacy_only drift', () => {
    const policy = extractAdkRuntimePolicyState(
      {
        runtime_contract: {
          runtime_strategy: 'official_only',
          strict_mode: true,
          runtime_strategy_values: ['official_only', 'official_or_legacy', 'allow_legacy'],
        },
      },
      {
        selectedStrategy: 'allow_legacy',
        selectedStrictMode: false,
      }
    );

    expect(policy.effectiveStrategy).toBe('official_only');
    expect(policy.selectedStrategy).toBe('allow_legacy');
    expect(policy.options.map((item) => item.value)).toEqual(
      expect.arrayContaining(['official_only', 'official_or_legacy', 'allow_legacy'])
    );
    expect(policy.options.map((item) => item.value)).not.toContain('legacy_only');
  });

  it('[M4] maps strict runtime error codes to readable prompts', () => {
    const runtimeUnavailable = formatAdkRuntimeContractErrorMessage(
      new Error(JSON.stringify({
        error_code: 'ADK_RUNTIME_UNAVAILABLE',
        runtime_strategy: 'official_only',
        strict_mode: true,
      })),
      'fallback'
    );
    expect(runtimeUnavailable).toContain('官方 ADK runtime 当前不可用');
    expect(runtimeUnavailable).toContain('strict_mode=true');

    const fallbackForbidden = formatAdkRuntimeContractErrorMessage(
      new Error(JSON.stringify({
        error_code: 'ADK_FALLBACK_FORBIDDEN',
        runtime_strategy: 'official_or_legacy',
        strict_mode: true,
      })),
      'fallback'
    );
    expect(fallbackForbidden).toContain('禁止 fallback');
    expect(fallbackForbidden).toContain('runtime_strategy=official_or_legacy');
    expect(fallbackForbidden).toContain('strict_mode=true');

    const strategyViolationAllowLegacy = formatAdkRuntimeContractErrorMessage(
      new Error('Request failed: 409 {"error_code":"ADK_STRATEGY_VIOLATION","runtime_strategy":"allow_legacy","strict_mode":false}'),
      'fallback'
    );
    expect(strategyViolationAllowLegacy).toContain('运行策略冲突');
    expect(strategyViolationAllowLegacy).toContain('runtime_strategy=allow_legacy');
  });
});
