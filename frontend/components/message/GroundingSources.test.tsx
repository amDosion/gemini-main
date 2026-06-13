// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GroundingSources } from './GroundingSources';

describe('GroundingSources', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders only safe http and https source links', () => {
    render(
      <GroundingSources
        chunks={[
          { web: { uri: ' https://example.com/docs?q=1 ', title: 'Docs' } },
          { web: { uri: 'javascript:alert(1)', title: 'Script' } },
          { web: { uri: 'data:text/html;base64,PHNjcmlwdD4=', title: 'Data' } },
        ]}
      />
    );

    const docsLink = screen.getByRole('link', { name: /Docs/i });
    expect(docsLink.getAttribute('href')).toBe('https://example.com/docs?q=1');
    expect(docsLink.getAttribute('target')).toBe('_blank');
    expect(docsLink.getAttribute('rel')).toBe('noopener noreferrer');
    expect(screen.queryByText('Script')).toBeNull();
    expect(screen.queryByText('Data')).toBeNull();
  });
});
