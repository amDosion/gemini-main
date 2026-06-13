// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadSourceUrlInBrowser, triggerBrowserDownload } from './downloadService';

describe('downloadSourceUrlInBrowser', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('does not expose internal local-blob cache keys as browser downloads', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await downloadSourceUrlInBrowser({
      sourceUrl: 'local-blob:att-file-only-download',
      fileName: 'image.png',
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it('allows same-origin API downloads without fetching in JS', async () => {
    const clickedHrefs: string[] = [];
    const clickedDownloads: string[] = [];
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clickedHrefs.push(this.getAttribute('href') || '');
        clickedDownloads.push(this.getAttribute('download') || '');
      });
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await downloadSourceUrlInBrowser({
      sourceUrl: '/api/storage/local-files/audio.wav',
      fileName: '../bad:name\u0000audio.wav',
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(clickedHrefs).toEqual(['/api/storage/local-files/audio.wav']);
    expect(clickedDownloads).toEqual(['.._bad_name_audio.wav']);
  });

  it('trims remote source URLs before routing them through the storage proxy', async () => {
    const clickedHrefs: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      clickedHrefs.push(this.getAttribute('href') || '');
    });
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await downloadSourceUrlInBrowser({
      sourceUrl: ' https://cdn.example.com/file.png?token=secret ',
      fileName: 'file.png',
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(clickedHrefs).toEqual([
      '/api/storage/download?url=https%3A%2F%2Fcdn.example.com%2Ffile.png%3Ftoken%3Dsecret',
    ]);
  });

  it('rejects unsupported URL schemes without triggering a browser download', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      downloadSourceUrlInBrowser({
        sourceUrl: 'javascript:alert(1)',
        fileName: 'x.txt',
      })
    ).rejects.toThrow('Unsupported download URL scheme');

    expect(fetchMock).not.toHaveBeenCalled();
    expect(clickSpy).not.toHaveBeenCalled();
  });
});

describe('triggerBrowserDownload', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('allows workflow export data URLs and sanitizes filenames', () => {
    const clickedHrefs: string[] = [];
    const clickedDownloads: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      clickedHrefs.push(this.getAttribute('href') || '');
      clickedDownloads.push(this.getAttribute('download') || '');
    });

    triggerBrowserDownload({
      href: 'data:image/svg+xml;base64,PHN2Zy8+',
      fileName: '../workflow:export.svg',
    });

    expect(clickedHrefs).toEqual(['data:image/svg+xml;base64,PHN2Zy8+']);
    expect(clickedDownloads).toEqual(['.._workflow_export.svg']);
  });

  it.each(['javascript:alert(1)', 'vbscript:msgbox(1)', 'file:///etc/passwd', 'ftp://example.com/a'])(
    'rejects unsafe href %s before clicking',
    (href) => {
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

      expect(() => triggerBrowserDownload({ href, fileName: 'x.txt' })).toThrow(
        'Unsupported download URL scheme'
      );
      expect(clickSpy).not.toHaveBeenCalled();
    }
  );
});
