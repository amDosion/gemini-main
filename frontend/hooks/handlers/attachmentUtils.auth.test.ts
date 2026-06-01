// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  prepareAttachmentForApi,
  fetchAttachmentStatus,
  processMediaResult,
  processUserAttachments,
} from './attachmentUtils';
import { removeAccessToken, setAccessToken } from '../../services/authTokenStore';

describe('attachmentUtils auth transport', () => {
  beforeEach(() => {
    removeAccessToken();
  });

  afterEach(() => {
    removeAccessToken();
    vi.unstubAllGlobals();
  });

  it('resolves continuity through cookie auth without sending stale bearer headers', async () => {
    setAccessToken('stale-memory-access-token');
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () => new Response(
        JSON.stringify({
          attachmentId: 'attachment-1',
          mimeType: 'image/png',
          filename: 'canvas.png',
          url: '/api/storage/local-files/canvas.png',
          status: 'completed',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const attachment = await prepareAttachmentForApi(
      '/api/storage/local-files/canvas.png',
      [],
      'session-1'
    );

    expect(attachment?.id).toBe('attachment-1');
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(requestInit.headers);
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.has('Authorization')).toBe(false);
    expect(requestInit.credentials).toBe('include');
  });

  it('checks attachment status through cookie auth without sending stale bearer headers', async () => {
    setAccessToken('stale-memory-access-token');
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      async () => new Response(
        JSON.stringify({
          url: '/api/storage/local-files/result.png',
          uploadStatus: 'completed',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const status = await fetchAttachmentStatus('session-1', 'attachment-1');

    expect(status?.url).toBe('/api/storage/local-files/result.png');
    const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(requestInit.headers);
    expect(headers.has('Authorization')).toBe(false);
    expect(requestInit.credentials).toBe('include');
  });

  it('keeps generated HTTP media URLs without front-end re-downloading them into blob URLs', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:should-not-be-created'),
    });

    const result = await processMediaResult(
      {
        url: 'https://provider.example.com/generated-temp.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/generated-stable.png',
        mimeType: 'image/png',
        filename: 'generated.png',
        attachmentId: 'generated-attachment',
        uploadStatus: 'completed',
      },
      { sessionId: 'session-1', modelMessageId: 'message-1' },
      'image'
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(result.displayAttachment).toMatchObject({
      id: 'generated-attachment',
      url: '/api/storage/local-files/2026/05/31/generated-stable.png',
      tempUrl: 'https://provider.example.com/generated-temp.png',
      uploadStatus: 'completed',
      cloudUrl: '/api/storage/local-files/2026/05/31/generated-stable.png',
    });
  });

  it('uses durable attachment URLs before stale blob URLs when preparing user attachments', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const attachments = await processUserAttachments(
      [
        {
          id: 'att-stale-with-cloud',
          name: 'stable-source.png',
          mimeType: 'image/png',
          url: 'blob:https://gemini.dicry.cn:18443/revoked-source',
          tempUrl: 'data:image/png;base64,abc',
          cloudUrl: '/api/storage/local-files/2026/05/31/stable-source.png',
          uploadStatus: 'completed',
        },
      ],
      '/api/storage/local-files/2026/05/31/stable-source.png',
      [],
      'session-1'
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(attachments).toHaveLength(1);
    expect(attachments[0]).toMatchObject({
      id: 'att-stale-with-cloud',
      url: '/api/storage/local-files/2026/05/31/stable-source.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/stable-source.png',
      uploadStatus: 'completed',
    });
  });

  it('does not send internal local-blob canvas keys to continuity resolution', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const attachments = await processUserAttachments(
      [],
      'local-blob:att-file-only-history',
      [],
      'session-1'
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(attachments).toEqual([]);
  });

  it('resolves internal local-blob canvas keys from matching in-memory file attachments', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['file-only-history-canvas'], 'history-canvas.png', {
      type: 'image/png',
    });

    const attachments = await processUserAttachments(
      [],
      'local-blob:att-history-canvas',
      [
        {
          id: 'message-with-file-only-history',
          role: 'user' as any,
          content: 'use this image',
          timestamp: Date.now(),
          attachments: [
            {
              id: 'att-history-canvas',
              name: 'history-canvas.png',
              mimeType: 'image/png',
              file,
              uploadStatus: 'pending',
            },
          ],
        },
      ],
      'session-1'
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(attachments).toHaveLength(1);
    expect(attachments[0]).toMatchObject({
      id: 'att-history-canvas',
      tempUrl: expect.stringMatching(/^data:image\/png;base64,/),
      file,
    });
    expect(attachments[0].url).toBe(attachments[0].tempUrl);
  });

  it('converts file-only user attachments to data urls before sending media requests', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['file-only-image'], 'file-only.png', { type: 'image/png' });

    const attachments = await processUserAttachments(
      [
        {
          id: 'att-file-only',
          name: 'file-only.png',
          mimeType: 'image/png',
          file,
          uploadStatus: 'pending',
        },
      ],
      null,
      [],
      'session-1'
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(attachments).toHaveLength(1);
    expect(attachments[0].url).toMatch(/^data:image\/png;base64,/);
    expect(attachments[0].tempUrl).toBe(attachments[0].url);
    expect(attachments[0].file).toBe(file);
  });
});
