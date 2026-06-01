// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PdfHtmlView } from './PdfHtmlView';
import { PdfResultToolbar } from './PdfResultToolbar';
import type { PdfExtractionResult } from '../../../types/types';

const { downloadBlobInBrowserMock } = vi.hoisted(() => ({
  downloadBlobInBrowserMock: vi.fn(),
}));

vi.mock('../../../services/downloadService', () => ({
  downloadBlobInBrowser: downloadBlobInBrowserMock,
}));

describe('PDF result downloads', () => {
  beforeEach(() => {
    downloadBlobInBrowserMock.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('routes rendered HTML downloads through the shared browser download service', async () => {
    render(<PdfHtmlView data={{ title: 'Invoice', total: 12 }} />);

    fireEvent.click(screen.getByText('下载 HTML'));

    await waitFor(() => {
      expect(downloadBlobInBrowserMock).toHaveBeenCalledTimes(1);
    });
    const options = downloadBlobInBrowserMock.mock.calls[0]?.[0];
    expect(options.fileName).toMatch(/^pdf-extract-\d+\.html$/);
    expect(options.blob.type).toBe('text/html');
    await expect(options.blob.text()).resolves.toContain('PDF 提取结果');
  });

  it('routes JSON downloads through the shared browser download service', async () => {
    const result: PdfExtractionResult = {
      success: true,
      templateType: 'invoice',
      templateName: 'Invoice',
      data: { total: 12 },
    };

    render(<PdfResultToolbar viewMode="json" setViewMode={vi.fn()} result={result} />);

    fireEvent.click(screen.getByTitle('下载 JSON'));

    await waitFor(() => {
      expect(downloadBlobInBrowserMock).toHaveBeenCalledTimes(1);
    });
    const options = downloadBlobInBrowserMock.mock.calls[0]?.[0];
    expect(options.fileName).toMatch(/^extracted-invoice-\d+\.json$/);
    expect(options.blob.type).toBe('application/json');
    await expect(options.blob.text()).resolves.toContain('"total": 12');
  });
});
