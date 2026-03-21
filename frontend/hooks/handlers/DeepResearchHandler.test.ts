import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeepResearchHandler } from './DeepResearchHandler';
import type { ExecutionContext } from './types';

class MockEventSource {
  static instances: MockEventSource[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);

    setTimeout(() => {
      this.readyState = 1;
      this.onopen?.({ type: 'open' } as Event);
    }, 0);
  }

  close() {
    this.readyState = 2;
  }
}

const emitSse = (instance: MockEventSource, payload: unknown) => {
  instance.onmessage?.({
    data: JSON.stringify(payload),
  } as MessageEvent);
};

describe('DeepResearchHandler', () => {
  beforeEach(() => {
    MockEventSource.instances = [];

    vi.stubGlobal('EventSource', MockEventSource as any);
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(() => null),
      length: 0,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('passes previous_interaction_id and cancels via /api/research/stream/cancel', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url === '/api/research/stream/start') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_new_123' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url === '/api/research/stream/cancel/interaction_new_123') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_new_123', status: 'cancelled' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    vi.stubGlobal('fetch', fetchMock);

    const updates: any[] = [];
    let cancelFn: (() => void) | null = null;

    const context: ExecutionContext = {
      sessionId: 's1',
      userMessageId: 'u1',
      modelMessageId: 'm1',
      mode: 'chat',
      text: '请帮我深度研究这个主题',
      attachments: [],
      currentModel: {
        id: 'gemini-2.5-pro',
        name: 'Gemini 2.5 Pro',
        description: 'test',
        capabilities: { vision: true, search: true, reasoning: true, coding: true },
      },
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        enableDeepResearch: true,
        deepResearchAgentId: 'deep-research-pro-preview-12-2025',
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
      },
      protocol: 'google',
      previousResearchInteractionId: 'interaction_prev_456',
      llmService: {} as any,
      storageService: {} as any,
      pollingManager: {
        startPolling: vi.fn(async () => undefined),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
      onStreamUpdate: (update) => {
        updates.push(update);
      },
      registerCancel: (fn) => {
        cancelFn = fn;
      },
    };

    const handler = new DeepResearchHandler();
    const executionPromise = handler.execute(context);

    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research/stream/start',
      expect.objectContaining({ method: 'POST' })
    );

    const startCall = fetchMock.mock.calls.find((call) => String(call[0]) === '/api/research/stream/start');
    const startRequestBody = JSON.parse((startCall?.[1]?.body as string) || '{}');
    expect(startRequestBody.agent).toBe('deep-research-pro-preview-12-2025');
    expect(startRequestBody.previous_interaction_id).toBe('interaction_prev_456');
    expect(startRequestBody).not.toHaveProperty('researchMode');

    expect(cancelFn).toBeTypeOf('function');
    cancelFn?.();

    const result = await executionPromise;

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research/stream/cancel/interaction_new_123',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result.researchInteractionId).toBe('interaction_new_123');
    expect(result.researchStatus?.status).toBe('cancelled');

    const startUpdate = updates.find((item) => item.researchInteractionId === 'interaction_new_123');
    expect(startUpdate).toBeTruthy();
  });

  it('handles structured content.delta tool events and status_update required_action', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/research/stream/start') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_tool_001' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    vi.stubGlobal('fetch', fetchMock);

    const updates: any[] = [];

    const context: ExecutionContext = {
      sessionId: 's2',
      userMessageId: 'u2',
      modelMessageId: 'm2',
      mode: 'chat',
      text: '请做深度研究',
      attachments: [],
      currentModel: {
        id: 'gemini-2.5-pro',
        name: 'Gemini 2.5 Pro',
        description: 'test',
        capabilities: { vision: true, search: true, reasoning: true, coding: true },
      },
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        enableDeepResearch: true,
        deepResearchAgentId: 'deep-research-pro-preview-12-2025',
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
      },
      protocol: 'google',
      llmService: {} as any,
      storageService: {} as any,
      pollingManager: {
        startPolling: vi.fn(async () => undefined),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
      onStreamUpdate: (update) => {
        updates.push(update);
      },
      registerCancel: vi.fn(),
    };

    const handler = new DeepResearchHandler();
    const executionPromise = handler.execute(context);

    await new Promise((resolve) => setTimeout(resolve, 10));
    const sse = MockEventSource.instances[0];
    expect(sse).toBeTruthy();

    emitSse(sse, {
      eventType: 'content.delta',
      eventId: 'evt_1',
      delta: {
        type: 'function_call',
        id: 'call_1',
        name: 'google_search',
        args: { q: 'Gemini Interactions API' },
      },
    });

    emitSse(sse, {
      eventType: 'content.delta',
      eventId: 'evt_2',
      delta: {
        type: 'function_result',
        callId: 'call_1',
        name: 'google_search',
        result: { total: 3 },
      },
    });

    emitSse(sse, {
      eventType: 'interaction.status_update',
      eventId: 'evt_3',
      interaction: {
        status: 'requires_action',
        requiresAction: {
          act: { name: 'confirm_scope' },
          inputs: ['最近30天', '最近90天'],
        },
      },
    });

    emitSse(sse, {
      eventType: 'content.delta',
      eventId: 'evt_4',
      delta: {
        type: 'text',
        text: '研究结论',
      },
    });

    emitSse(sse, {
      eventType: 'interaction.complete',
      eventId: 'evt_5',
    });

    const result = await executionPromise;

    expect(result.toolCalls).toHaveLength(1);
    expect(result.toolCalls?.[0].id).toBe('call_1');
    expect(result.toolResults).toHaveLength(1);
    expect(result.toolResults?.[0].callId).toBe('call_1');
    expect(result.content).toContain('研究结论');
    expect(result.researchRequiredAction).toBeUndefined();

    const awaitingActionUpdate = updates.find(
      (item) => item.researchStatus?.status === 'awaiting_action'
    );
    expect(awaitingActionUpdate).toBeTruthy();
    expect(awaitingActionUpdate.researchRequiredAction?.act?.name).toBe('confirm_scope');
  });

  it('submits requires_action input and resumes stream with new interaction id', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/research/stream/start') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_action_1' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url === '/api/research/stream/action') {
        const body = JSON.parse(String(init?.body || '{}'));
        expect(body.agent).toBe('deep-research-pro-preview-12-2025');
        expect(body.previous_interaction_id).toBe('interaction_action_1');
        expect(body.call_id).toBe('call_scope_1');
        expect(body.result).toBe('最近30天');

        return new Response(
          JSON.stringify({ interactionId: 'interaction_action_2' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const updates: any[] = [];
    const actionHandlers = new Map<string, (selectedInput: unknown) => Promise<void>>();

    const context: ExecutionContext = {
      sessionId: 's3',
      userMessageId: 'u3',
      modelMessageId: 'm3',
      mode: 'chat',
      text: '继续研究',
      attachments: [],
      currentModel: {
        id: 'gemini-2.5-pro',
        name: 'Gemini 2.5 Pro',
        description: 'test',
        capabilities: { vision: true, search: true, reasoning: true, coding: true },
      },
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        enableDeepResearch: true,
        deepResearchAgentId: 'deep-research-pro-preview-12-2025',
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
      },
      protocol: 'google',
      llmService: {} as any,
      storageService: {} as any,
      pollingManager: {
        startPolling: vi.fn(async () => undefined),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
      onStreamUpdate: (update) => {
        updates.push(update);
      },
      registerCancel: vi.fn(),
      registerResearchActionHandler: (interactionId, handler) => {
        if (handler) {
          actionHandlers.set(interactionId, handler);
        } else {
          actionHandlers.delete(interactionId);
        }
      },
    };

    const handler = new DeepResearchHandler();
    const executionPromise = handler.execute(context);

    await new Promise((resolve) => setTimeout(resolve, 10));
    const firstSse = MockEventSource.instances[0];
    expect(firstSse).toBeTruthy();

    emitSse(firstSse, {
      eventType: 'content.delta',
      eventId: 'evt_a1',
      delta: {
        type: 'function_call',
        id: 'call_scope_1',
        name: 'confirm_scope',
        args: { label: '时间范围' },
      },
    });

    emitSse(firstSse, {
      eventType: 'interaction.status_update',
      eventId: 'evt_a2',
      interaction: {
        status: 'requires_action',
        requiresAction: {
          act: { name: 'confirm_scope' },
          inputs: ['最近30天', '最近90天'],
        },
      },
    });

    const submitAction = actionHandlers.get('interaction_action_1');
    expect(submitAction).toBeTypeOf('function');
    await submitAction?.('最近30天');

    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(actionHandlers.has('interaction_action_1')).toBe(false);
    expect(actionHandlers.has('interaction_action_2')).toBe(true);

    const secondSse = MockEventSource.instances[1];
    expect(secondSse).toBeTruthy();
    expect(secondSse.url).toBe('/api/research/stream/interaction_action_2');

    emitSse(secondSse, {
      eventType: 'content.delta',
      eventId: 'evt_a3',
      delta: {
        type: 'text',
        text: '继续研究结果',
      },
    });
    emitSse(secondSse, {
      eventType: 'interaction.complete',
      eventId: 'evt_a4',
    });

    const result = await executionPromise;
    expect(result.researchInteractionId).toBe('interaction_action_2');
    expect(result.content).toContain('继续研究结果');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research/stream/action',
      expect.objectContaining({ method: 'POST' })
    );

    const resumedUpdate = updates.find((item) => item.researchInteractionId === 'interaction_action_2');
    expect(resumedUpdate).toBeTruthy();
  });

  it('recovers by polling status endpoint and completes when status is completed', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/research/stream/start') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_status_done' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url === '/api/research/stream/status/interaction_status_done') {
        return new Response(
          JSON.stringify({
            interactionId: 'interaction_status_done',
            status: 'completed',
            outputs: [{ type: 'text', text: '状态恢复完成结果' }],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const context: ExecutionContext = {
      sessionId: 's4',
      userMessageId: 'u4',
      modelMessageId: 'm4',
      mode: 'chat',
      text: '状态恢复测试',
      attachments: [],
      currentModel: {
        id: 'gemini-2.5-pro',
        name: 'Gemini 2.5 Pro',
        description: 'test',
        capabilities: { vision: true, search: true, reasoning: true, coding: true },
      },
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        enableDeepResearch: true,
        deepResearchAgentId: 'deep-research-pro-preview-12-2025',
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
      },
      protocol: 'google',
      llmService: {} as any,
      storageService: {} as any,
      pollingManager: {
        startPolling: vi.fn(async () => undefined),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
      registerCancel: vi.fn(),
    };

    const handler = new DeepResearchHandler();
    const executionPromise = handler.execute(context);

    await new Promise((resolve) => setTimeout(resolve, 10));
    const firstSse = MockEventSource.instances[0];
    expect(firstSse).toBeTruthy();

    firstSse.readyState = MockEventSource.CLOSED;
    firstSse.onerror?.({ type: 'error' } as Event);

    const result = await executionPromise;
    expect(result.researchStatus?.status).toBe('completed');
    expect(result.content).toContain('状态恢复完成结果');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research/stream/status/interaction_status_done',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('reconnects with last_event_id query after closed stream', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/research/stream/start') {
        return new Response(
          JSON.stringify({ interactionId: 'interaction_resume_1' }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url === '/api/research/stream/status/interaction_resume_1') {
        return new Response(
          JSON.stringify({
            interactionId: 'interaction_resume_1',
            status: 'in_progress',
            outputs: [],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      throw new Error(`Unexpected fetch URL: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const context: ExecutionContext = {
      sessionId: 's5',
      userMessageId: 'u5',
      modelMessageId: 'm5',
      mode: 'chat',
      text: '断线续连测试',
      attachments: [],
      currentModel: {
        id: 'gemini-2.5-pro',
        name: 'Gemini 2.5 Pro',
        description: 'test',
        capabilities: { vision: true, search: true, reasoning: true, coding: true },
      },
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        enableDeepResearch: true,
        deepResearchAgentId: 'deep-research-pro-preview-12-2025',
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
      },
      protocol: 'google',
      llmService: {} as any,
      storageService: {} as any,
      pollingManager: {
        startPolling: vi.fn(async () => undefined),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
      registerCancel: vi.fn(),
    };

    const handler = new DeepResearchHandler();
    const executionPromise = handler.execute(context);

    await new Promise((resolve) => setTimeout(resolve, 10));
    const firstSse = MockEventSource.instances[0];
    expect(firstSse).toBeTruthy();

    emitSse(firstSse, {
      eventType: 'content.delta',
      eventId: 'evt_resume_1',
      delta: {
        type: 'text',
        text: '第一段输出',
      },
    });

    firstSse.readyState = MockEventSource.CLOSED;
    firstSse.onerror?.({ type: 'error' } as Event);

    await new Promise((resolve) => setTimeout(resolve, 10));
    const secondSse = MockEventSource.instances[1];
    expect(secondSse).toBeTruthy();
    expect(secondSse.url).toBe('/api/research/stream/interaction_resume_1?last_event_id=evt_resume_1');

    emitSse(secondSse, {
      eventType: 'interaction.complete',
      eventId: 'evt_resume_2',
      interaction: {
        outputs: [{ type: 'text', text: '最终输出' }],
      },
    });

    const result = await executionPromise;
    expect(result.researchStatus?.status).toBe('completed');
    expect(result.content).toContain('最终输出');
  });
});
