// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadSourceUrlInBrowser } from './downloadService';

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
});
