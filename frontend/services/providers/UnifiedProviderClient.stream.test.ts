import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UnifiedProviderClient } from './UnifiedProviderClient';
import type { ChatOptions, Message } from '../../types/types';
import { removeAccessToken, setAccessToken } from '../authTokenStore';
import {
  buildExecutionStatusFromHistoryDetail,
  normalizeSnapshotForApply,
} from '../../components/views/multiagent/executionStatusUtils';
import { resolveWorkflowExecutionStatePayload } from '../workflowStateService';

const defaultOptions: ChatOptions = {
  enableSearch: false,
  enableThinking: false,
  enableCodeExecution: false,
  imageAspectRatio: '1:1',
  imageResolution: '1024x1024',
};

describe('UnifiedProviderClient stream handling', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      removeItem: () => undefined,
    });
  });

  afterEach(() => {
    removeAccessToken();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('uses cookie-first auth for chat streaming even when a stale memory token exists', async () => {
    setAccessToken('stale-access-token');
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"chunkType":"done","text":""}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () =>
        new Response(stream, {
          status: 200,
          headers: { 'content-type': 'text/event-stream' },
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    for await (const _update of client.sendMessageStream(
      'gemini-3.1-pro-preview',
      [] as Message[],
      'stream with cookie',
      [],
      defaultOptions,
      '',
      ''
    )) {
      // drain stream
    }

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    const headers = new Headers(init?.headers);
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('include');
  });

  it('redacts sensitive credentials from chat stream HTTP errors', async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        'provider failed for https://files.example.com/output.png?token=stream-secret-token&safe=1 with Bearer stream-secret-bearer and api_key=stream-secret-key',
        {
          status: 502,
          headers: { 'content-type': 'text/plain' },
        }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    let message = '';

    try {
      for await (const _update of client.sendMessageStream(
        'gemini-3.1-pro-preview',
        [] as Message[],
        'stream error',
        [],
        defaultOptions,
        '',
        ''
      )) {
        // drain stream
      }
    } catch (error) {
      message = (error as Error).message;
    }

    expect(message).toContain('Chat failed:');
    expect(message).not.toContain('stream-secret-token');
    expect(message).not.toContain('stream-secret-bearer');
    expect(message).not.toContain('stream-secret-key');
    expect(message).toContain('token=REDACTED');
    expect(message).toContain('safe=1');
    expect(message).toContain('Bearer REDACTED');
    expect(message).toContain('api_key=REDACTED');
  });

  it('parses split SSE payloads with tool events', async () => {
    const encoder = new TextEncoder();
    const sseFrames = [
      'data: {"chunkType":"content","text":"He',
      'llo"}\n\n',
      'data: {"chunkType":"tool_call","toolName":"web_search","toolArgs":{"query":"keyboard"},"callId":"call_1","toolType":"function_call","browserOperationId":"browser:test:web_search:call_1"}\n\n',
      'data: {"chunkType":"tool_result","toolName":"web_search","toolResult":"ok","callId":"call_1","browserOperationId":"browser:test:web_search:call_1"}\n\n',
      'data: {"chunkType":"done","text":""}\n\n',
    ];

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        sseFrames.forEach((frame) => controller.enqueue(encoder.encode(frame)));
        controller.close();
      },
    });

    const fetchMock = vi.fn(async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    const updates = [];

    for await (const update of client.sendMessageStream(
      'gemini-3.1-pro-preview',
      [] as Message[],
      'test message',
      [],
      defaultOptions,
      '',
      ''
    )) {
      updates.push(update);
    }

    const contentChunks = updates.filter((item: any) => item.text !== '');
    const toolCalls = updates.filter((item: any) => item.toolCall);
    const toolResults = updates.filter((item: any) => item.toolResult);

    expect(contentChunks.length).toBeGreaterThan(0);
    expect(contentChunks[0].text).toBe('Hello');
    expect(toolCalls).toHaveLength(1);
    expect(toolCalls[0].toolCall).toMatchObject({
      id: 'call_1',
      type: 'function_call',
      name: 'web_search',
    });
    expect(toolCalls[0].browserOperationId).toBe('browser:test:web_search:call_1');
    expect(toolResults).toHaveLength(1);
    expect(toolResults[0].toolResult).toMatchObject({
      callId: 'call_1',
      name: 'web_search',
      result: 'ok',
    });
    expect(toolResults[0].browserOperationId).toBe('browser:test:web_search:call_1');
  });

  it('returns cleanly when upstream abort signal is triggered', async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal as AbortSignal | undefined;
        if (signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        signal?.addEventListener(
          'abort',
          () => reject(new DOMException('Aborted', 'AbortError')),
          { once: true }
        );
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    const upstreamAbort = new AbortController();

    const iterator = client.sendMessageStream(
      'gemini-3.1-pro-preview',
      [] as Message[],
      'abort me',
      [],
      defaultOptions,
      '',
      '',
      upstreamAbort.signal
    );

    const nextPromise = iterator.next();
    upstreamAbort.abort('user-stop');
    const result = await nextPromise;

    expect(result.done).toBe(true);
  });

  it('ignores SSE heartbeat comments from backend keepalive frames', async () => {
    const encoder = new TextEncoder();
    const sseFrames = [
      ': keep-alive\n\n',
      'data: {"chunkType":"content","text":"ok"}\n\n',
      ': keep-alive\n\n',
      'data: {"chunkType":"done","text":""}\n\n',
    ];

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        sseFrames.forEach((frame) => controller.enqueue(encoder.encode(frame)));
        controller.close();
      },
    });

    const fetchMock = vi.fn(async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    const updates = [];

    for await (const update of client.sendMessageStream(
      'gemini-3.1-pro-preview',
      [] as Message[],
      'heartbeat test',
      [],
      defaultOptions,
      '',
      ''
    )) {
      updates.push(update);
    }

    const content = updates.map((item: any) => item.text).join('');
    expect(content).toContain('ok');
  });
});

describe('workflow contract compatibility regressions', () => {
  it('accepts workflow execution state from wrapped and direct backend payloads', () => {
    expect(
      resolveWorkflowExecutionStatePayload({
        execution_state: { status: 'running', nodeStatuses: { n1: 'running' } },
      })
    ).toEqual({
      status: 'running',
      nodeStatuses: { n1: 'running' },
    });

    expect(
      resolveWorkflowExecutionStatePayload({
        executionState: { status: 'completed', nodeStatuses: { n1: 'completed' } },
      })
    ).toEqual({
      status: 'completed',
      nodeStatuses: { n1: 'completed' },
    });

    expect(
      resolveWorkflowExecutionStatePayload({
        status: 'running',
        nodeStatuses: { n2: 'running' },
      })
    ).toEqual({
      status: 'running',
      nodeStatuses: { n2: 'running' },
    });
  });

  it('normalizes history snapshot state/runtime fields for mixed legacy and new shapes', () => {
    const normalized = normalizeSnapshotForApply({
      id: 'exec-contract-1',
      status: 'paused',
      nodeExecutions: [
        {
          nodeId: 'node-1',
          status: 'completed',
          progress: 98.6,
          runtime: 'official_adk',
          output: {
            runtimeHint: 'legacy-adapter',
            text: 'done',
          },
        },
      ],
      nodeStatuses: {
        'node-2': 'FAILED',
      },
      nodeProgress: {
        'node-2': '45.4',
      },
      nodeRuntimes: {
        'node-2': 'llm_adapter',
      },
      resultSummary: {
        runtimeHints: ['google-adk-official', 'legacy-adapter'],
      },
    });

    expect(normalized.status).toBe('workflow_paused');
    expect(normalized.nodeStatuses).toMatchObject({
      'node-1': 'completed',
      'node-2': 'failed',
    });
    expect(normalized.nodeProgress).toMatchObject({
      'node-1': 99,
      'node-2': 45,
    });
    expect(normalized.nodeRuntimes).toMatchObject({
      'node-1': 'adk-official',
      'node-2': 'adapter',
    });
    expect(normalized.runtimeHints).toEqual(['adk-official', 'adapter']);
    expect(normalized.primaryRuntime).toBe('adk-official');
  });

  it('restores history execution status with runtime priority and preview filtering', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_700_000_001_234);

    const restored = buildExecutionStatusFromHistoryDetail(
      {
        id: 'exec-contract-2',
        status: 'completed',
        result: { text: 'ok' },
        resultSummary: {
          runtimeHints: ['legacy-adapter', 'adkofficial'],
        },
        nodeExecutions: [
          {
            nodeId: 'node-a',
            status: 'completed',
            output: {
              runtime: 'google-adk',
            },
          },
        ],
        completedAt: 1_700_000_000_999,
      },
      {
        imageUrls: ['data:image/png;base64,abc', '   ', '', 'https://example.com/result.png'],
      }
    );

    expect(restored.executionId).toBe('exec-contract-2');
    expect(restored.finalStatus).toBe('completed');
    expect(restored.finalRuntime).toBe('adk-official');
    expect(restored.runtimeHints).toEqual(['adapter', 'adk-official', 'adk']);
    expect(restored.resultPreviewImageUrls).toEqual([
      'data:image/png;base64,abc',
      'https://example.com/result.png',
    ]);
    expect(restored.finalError).toBeUndefined();
    expect(restored.logs[0].message).toContain('runtime: adk-official');
  });
});
