// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PdfMarkdownView } from './PdfMarkdownView';

describe('PdfMarkdownView link safety', () => {
  it('allows only absolute http/https links to navigate in a safe new tab', () => {
    const { container } = render(
      <PdfMarkdownView
        data={{
          markdown:
            '[safe](https://example.com/report.pdf) [js](javascript:alert(1)) [relative](/local)',
        }}
      />
    );

    const links = Array.from(container.querySelectorAll('a'));
    expect(links).toHaveLength(3);

    expect(links[0].getAttribute('href')).toBe('https://example.com/report.pdf');
    expect(links[0].getAttribute('target')).toBe('_blank');
    expect(links[0].getAttribute('rel')).toBe('noopener noreferrer');

    expect(links[1].hasAttribute('href')).toBe(false);
    expect(links[1].hasAttribute('target')).toBe(false);
    expect(links[1].hasAttribute('rel')).toBe(false);
    expect(links[2].hasAttribute('href')).toBe(false);
    expect(links[2].hasAttribute('target')).toBe(false);
    expect(links[2].hasAttribute('rel')).toBe(false);
  });
});
