// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { UrlContextStatus } from './UrlContextStatus';

describe('UrlContextStatus', () => {
  afterEach(() => {
    cleanup();
  });

  it('uses links for safe retrieved URLs and text for unsafe URLs', () => {
    render(
      <UrlContextStatus
        metadata={{
          urlMetadata: [
            {
              retrievedUrl: 'https://example.com/result',
              urlRetrievalStatus: 'URL_RETRIEVAL_STATUS_SUCCESS',
            },
            {
              retrievedUrl: 'javascript:alert(1)',
              urlRetrievalStatus: 'URL_RETRIEVAL_STATUS_UNSAFE',
            },
          ],
        }}
      />
    );

    const safeLink = screen.getByRole('link', { name: 'https://example.com/result' });
    expect(safeLink.getAttribute('href')).toBe('https://example.com/result');
    expect(safeLink.getAttribute('target')).toBe('_blank');
    expect(safeLink.getAttribute('rel')).toBe('noopener noreferrer');

    const unsafeText = screen.getByText('javascript:alert(1)');
    expect(unsafeText.tagName.toLowerCase()).toBe('span');
    expect(screen.queryByRole('link', { name: 'javascript:alert(1)' })).toBeNull();
  });
});
