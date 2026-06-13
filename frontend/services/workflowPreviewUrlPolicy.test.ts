import { describe, expect, it } from 'vitest';
import { DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES } from '../utils/safeMediaDataUrl';
import {
  isSafeWorkflowPreviewImageUrl,
  isSafeWorkflowPreviewMediaUrl,
  normalizeWorkflowPreviewImageUrls,
} from './workflowPreviewUrlPolicy';

describe('workflowPreviewUrlPolicy', () => {
  it('allows safe workflow preview image URLs', () => {
    expect(isSafeWorkflowPreviewImageUrl('data:image/png;base64,YWJj')).toBe(true);
    expect(isSafeWorkflowPreviewImageUrl('/api/workflows/history/exec/images/1')).toBe(true);
    expect(isSafeWorkflowPreviewImageUrl('https://cdn.example.com/preview.png')).toBe(true);
    expect(isSafeWorkflowPreviewImageUrl('http://cdn.example.com/preview.png')).toBe(true);
  });

  it.each([
    ['browser-local blob', 'blob:https://gemini.dicry.cn:18443/stale-preview'],
    ['inline svg image', 'data:image/svg+xml;base64,PHN2Zy8+'],
    ['non-base64 image data', 'data:image/png,<svg onload=alert(1)>'],
    ['javascript url', 'javascript:alert(1)'],
  ])('rejects unsafe workflow preview image URL: %s', (_label, url) => {
    expect(isSafeWorkflowPreviewImageUrl(url)).toBe(false);
  });

  it('rejects oversized inline workflow preview images', () => {
    const payloadLength = Math.ceil(((DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES + 1) * 4) / 3);
    const oversizedImageUrl = `data:image/png;base64,${'A'.repeat(payloadLength)}`;

    expect(isSafeWorkflowPreviewImageUrl(oversizedImageUrl)).toBe(false);
  });

  it('normalizes preview image lists after filtering unsafe values', () => {
    expect(
      normalizeWorkflowPreviewImageUrls([
        ' data:image/png;base64,YWJj ',
        'data:image/png;base64,YWJj',
        'data:image/svg+xml;base64,PHN2Zy8+',
        '/api/workflows/history/exec/images/1',
        'blob:https://gemini.dicry.cn:18443/stale-preview',
      ])
    ).toEqual(['data:image/png;base64,YWJj', '/api/workflows/history/exec/images/1']);
  });

  it('allows safe workflow preview media URLs', () => {
    expect(isSafeWorkflowPreviewMediaUrl('data:audio/wav;base64,YWJj')).toBe(true);
    expect(isSafeWorkflowPreviewMediaUrl('data:video/mp4;base64,YWJj')).toBe(true);
    expect(isSafeWorkflowPreviewMediaUrl('/api/workflows/history/exec/audio/1')).toBe(true);
    expect(isSafeWorkflowPreviewMediaUrl('https://cdn.example.com/preview.mp4')).toBe(true);
  });

  it.each([
    ['browser-local blob', 'blob:https://gemini.dicry.cn:18443/stale-preview'],
    ['non-base64 audio data', 'data:audio/wav,not-base64'],
    ['non-media data', 'data:text/html;base64,PHNjcmlwdD4='],
    ['javascript url', 'javascript:alert(1)'],
  ])('rejects unsafe workflow preview media URL: %s', (_label, url) => {
    expect(isSafeWorkflowPreviewMediaUrl(url)).toBe(false);
  });

  it('rejects oversized inline workflow preview media', () => {
    const oversizedAudioUrl = `data:audio/wav;base64,${'A'.repeat(4096)}`;

    expect(isSafeWorkflowPreviewMediaUrl(oversizedAudioUrl)).toBe(false);
  });
});
