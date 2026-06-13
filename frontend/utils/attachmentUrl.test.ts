// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Attachment } from '../types/types';
import { __resetMediaCacheForTest } from '../services/mediaCache';
import {
  getLocalBlobAttachmentId,
  getPreferredAttachmentUrl,
  getPreferredImageAttachmentUrl,
  getRenderableAttachmentUrl,
  isBlobAttachmentUrl,
  isDataAttachmentUrl,
  isHttpAttachmentUrl,
  isRenderableAttachmentUrl,
  revokeAttachmentObjectUrls,
  isTemporaryAttachmentUrl,
} from './attachmentUrl';

describe('attachmentUrl', () => {
  beforeEach(() => {
    __resetMediaCacheForTest();
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    __resetMediaCacheForTest();
    vi.restoreAllMocks();
  });

  it('prefers durable media urls before temporary blob or data urls', () => {
    const attachment: Attachment = {
      id: 'att-durable',
      name: 'image.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-preview',
      tempUrl: 'data:image/png;base64,abc',
      cloudUrl: '/api/storage/local-files/2026/05/31/image.png',
      fileUri: '/api/storage/local-files/2026/05/31/file-uri.png',
    };

    expect(getPreferredAttachmentUrl(attachment)).toBe(
      '/api/storage/local-files/2026/05/31/image.png'
    );
    expect(getPreferredImageAttachmentUrl(attachment)).toBe(
      '/api/storage/local-files/2026/05/31/image.png'
    );
  });

  it('falls back to fileUri and then temporary urls only when no durable source exists', () => {
    expect(
      getPreferredAttachmentUrl({
        fileUri: '/api/storage/local-files/2026/05/31/file-only.png',
      })
    ).toBe('/api/storage/local-files/2026/05/31/file-only.png');

    expect(
      getPreferredAttachmentUrl({
        url: 'blob:https://gemini.dicry.cn:18443/local-preview',
        tempUrl: 'data:image/png;base64,abc',
      })
    ).toBe('blob:https://gemini.dicry.cn:18443/local-preview');
  });

  it('does not expose stale blob urls for rendered history media when no live file is present', () => {
    expect(
      getRenderableAttachmentUrl({
        id: 'att-stale-video',
        name: 'stale.mp4',
        mimeType: 'video/mp4',
        url: 'blob:https://gemini.dicry.cn:18443/stale-video',
      } as Attachment)
    ).toBeNull();

    expect(
      getRenderableAttachmentUrl({
        id: 'att-live-video',
        name: 'live.mp4',
        mimeType: 'video/mp4',
        url: 'blob:https://gemini.dicry.cn:18443/live-video',
        file: new File(['video'], 'live.mp4', { type: 'video/mp4' }),
      } as Attachment)
    ).toBe('blob:https://gemini.dicry.cn:18443/live-video');
  });

  it('rejects non-renderable schemes and mismatched data media for rendered attachments', () => {
    expect(
      getRenderableAttachmentUrl({
        id: 'att-unsafe-image',
        name: 'unsafe.png',
        mimeType: 'image/png',
        url: 'javascript:alert(1)',
      } as Attachment)
    ).toBeNull();

    expect(
      getRenderableAttachmentUrl({
        id: 'att-data-html',
        name: 'unsafe.png',
        mimeType: 'image/png',
        url: 'data:text/html,<script>alert(1)</script>',
      } as Attachment)
    ).toBeNull();

    expect(
      isRenderableAttachmentUrl('data:audio/wav;base64,AAAA', {
        mimeType: 'image/png',
      })
    ).toBe(false);
    expect(
      isRenderableAttachmentUrl('data:image/png;base64,AAAA', {
        mimeType: 'image/png',
      })
    ).toBe(true);
  });

  it('prefers local storage fileUri over remote temporary provider urls', () => {
    expect(
      getPreferredAttachmentUrl({
        url: 'blob:https://gemini.dicry.cn:18443/stale-preview',
        tempUrl: 'https://temporary.example.com/generated-temp.png',
        fileUri: '/api/storage/local-files/2026/05/31/stored-result.png',
      })
    ).toBe('/api/storage/local-files/2026/05/31/stored-result.png');
  });

  it('accepts backend snake_case durable url fields loaded from history', () => {
    expect(
      getPreferredAttachmentUrl({
        url: 'blob:https://gemini.dicry.cn:18443/stale-history-preview',
        cloud_url: '/api/storage/local-files/2026/05/31/history-cloud.png',
        file_uri: '/api/storage/local-files/2026/05/31/history-file.png',
        temp_url: 'https://temporary.example.com/history.png',
      } as unknown as Attachment)
    ).toBe('/api/storage/local-files/2026/05/31/history-cloud.png');
  });

  it('identifies browser-local temporary urls', () => {
    expect(isTemporaryAttachmentUrl('blob:https://gemini.dicry.cn:18443/local-preview')).toBe(true);
    expect(isTemporaryAttachmentUrl('data:image/png;base64,abc')).toBe(true);
    expect(isTemporaryAttachmentUrl('local-blob:attachment-1')).toBe(true);
    expect(isTemporaryAttachmentUrl('/api/storage/local-files/2026/05/31/image.png')).toBe(false);
    expect(isBlobAttachmentUrl('blob:https://gemini.dicry.cn:18443/local-preview')).toBe(true);
    expect(isDataAttachmentUrl('data:image/png;base64,abc')).toBe(true);
    expect(isHttpAttachmentUrl('https://temporary.example.com/image.png')).toBe(true);
    expect(isHttpAttachmentUrl('/api/storage/local-files/2026/05/31/image.png')).toBe(false);
  });

  it('extracts attachment ids from local-blob cache keys', () => {
    expect(getLocalBlobAttachmentId('local-blob:attachment-1')).toBe('attachment-1');
    expect(getLocalBlobAttachmentId(' local-blob:attachment-2 ')).toBe('attachment-2');
    expect(getLocalBlobAttachmentId('blob:https://gemini.dicry.cn/attachment-1')).toBeNull();
  });

  it('revokes only unique blob object urls from an attachment', () => {
    expect(
      revokeAttachmentObjectUrls({
        url: 'blob:https://gemini.dicry.cn:18443/local-preview',
        tempUrl: 'blob:https://gemini.dicry.cn:18443/local-preview',
        cloudUrl: '/api/storage/local-files/2026/05/31/image.png',
        fileUri: 'data:image/png;base64,abc',
      })
    ).toBe(1);

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(
      'blob:https://gemini.dicry.cn:18443/local-preview'
    );
  });
});
