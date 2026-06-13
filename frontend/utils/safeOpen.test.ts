// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getBrowserOrigin,
  isSameOriginBlobUrl,
  openSafeUrlInNewTab,
  toSafeNewTabUrl,
} from './safeOpen';

describe('shared URL helpers', () => {
  it('exposes the browser origin and same-origin blob policy', () => {
    expect(getBrowserOrigin()).toBe(window.location.origin);
    expect(isSameOriginBlobUrl(`blob:${window.location.origin}/audio`)).toBe(true);
    expect(isSameOriginBlobUrl('blob:https://evil.example/audio')).toBe(false);
    expect(isSameOriginBlobUrl('blob:not-a-valid-url')).toBe(false);
  });
});

describe('toSafeNewTabUrl', () => {
  it('allows absolute http and https URLs', () => {
    expect(toSafeNewTabUrl('https://example.com/docs')).toBe('https://example.com/docs');
    expect(toSafeNewTabUrl('http://example.com/docs')).toBe('http://example.com/docs');
  });

  it('allows relative URLs only when explicitly enabled', () => {
    expect(toSafeNewTabUrl('/api/storage/audio/1')).toBeNull();
    expect(toSafeNewTabUrl('/api/storage/audio/1', { allowRelative: true })).toBe(
      `${window.location.origin}/api/storage/audio/1`
    );
  });

  it('allows local media schemes only when explicitly enabled', () => {
    const sameOriginBlobUrl = `blob:${window.location.origin}/audio`;
    expect(toSafeNewTabUrl(sameOriginBlobUrl)).toBeNull();
    expect(toSafeNewTabUrl(sameOriginBlobUrl, { allowBlob: true })).toBe(sameOriginBlobUrl);

    expect(toSafeNewTabUrl('data:audio/wav;base64,AAAA')).toBeNull();
    expect(
      toSafeNewTabUrl('data:audio/wav;base64,AAAA', { allowInlineAudioData: true })
    ).toBe('data:audio/wav;base64,AAAA');
  });

  it('rejects cross-origin and malformed blob URLs', () => {
    expect(toSafeNewTabUrl('blob:https://evil.example/audio', { allowBlob: true })).toBeNull();
    expect(toSafeNewTabUrl('blob:not-a-valid-url', { allowBlob: true })).toBeNull();
  });

  it('rejects script and non-audio data URLs', () => {
    expect(toSafeNewTabUrl('javascript:alert(1)', { allowRelative: true })).toBeNull();
    expect(
      toSafeNewTabUrl('data:text/html,<script>alert(1)</script>', {
        allowInlineAudioData: true,
      })
    ).toBeNull();
  });

  it('rejects unsafe inline audio data URLs', () => {
    expect(
      toSafeNewTabUrl('data:audio/wav,not-base64', {
        allowInlineAudioData: true,
      })
    ).toBeNull();
    expect(
      toSafeNewTabUrl(`data:audio/wav;base64,${'A'.repeat(4096)}`, {
        allowInlineAudioData: true,
      })
    ).toBeNull();
  });
});

describe('openSafeUrlInNewTab', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not call window.open for unsafe URLs', () => {
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null);

    expect(openSafeUrlInNewTab('javascript:alert(1)', { allowRelative: true })).toBe(false);
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('opens safe URLs with noopener and clears opener defensively', () => {
    const openedWindow = { opener: window } as unknown as Window;
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(openedWindow);

    expect(openSafeUrlInNewTab('https://example.com/docs')).toBe(true);

    expect(openSpy).toHaveBeenCalledWith(
      'https://example.com/docs',
      '_blank',
      'noopener,noreferrer'
    );
    expect(openedWindow.opener).toBeNull();
  });
});
