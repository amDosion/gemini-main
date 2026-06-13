// @vitest-environment jsdom
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import MarkdownRenderer from './MarkdownRenderer';

/**
 * W02R-019: chat/model-controlled markdown must not carry arbitrary inline CSS.
 * `style` was in the rehype-sanitize wildcard attribute allowlist, enabling CSS
 * injection / UI redress (e.g. position:fixed overlays). It must be stripped.
 */
describe('MarkdownRenderer sanitization (W02R-019)', () => {
  it('strips inline style attributes from chat-supplied markdown', () => {
    const { container } = render(
      <MarkdownRenderer
        content={'<span style="position:fixed;top:0;left:0;width:100vw;height:100vh">x</span>'}
      />
    );
    expect(container.querySelector('[style]')).toBeNull();
  });

  it('still renders safe content', () => {
    const { container } = render(<MarkdownRenderer content={'**bold**'} />);
    expect(container.querySelector('strong')).not.toBeNull();
  });

  it('renders fenced code while the highlighter chunk loads', () => {
    const { container } = render(<MarkdownRenderer content={'```ts\nconst value = 1;\n```'} />);
    expect(container.textContent).toContain('ts');
    expect(container.textContent).toContain('const value = 1;');
  });

  it('forces safe new-tab attributes on chat-supplied links', () => {
    const { container } = render(
      <MarkdownRenderer
        content={'<a href="https://example.com" target="_self" rel="opener">link</a>'}
      />
    );

    const link = container.querySelector('a');
    expect(link).not.toBeNull();
    expect(link?.getAttribute('target')).toBe('_blank');
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('removes navigation attributes from unsafe markdown links', () => {
    const { container } = render(
      <MarkdownRenderer content={'[js](javascript:alert(1)) [relative](/local/path)'} />
    );

    const links = Array.from(container.querySelectorAll('a'));
    expect(links).toHaveLength(2);
    links.forEach((link) => {
      expect(link.hasAttribute('href')).toBe(false);
      expect(link.hasAttribute('target')).toBe(false);
      expect(link.hasAttribute('rel')).toBe(false);
    });
  });

  it('removes navigation attributes from unsafe raw HTML links', () => {
    const { container } = render(
      <MarkdownRenderer
        content={'<a href="mailto:user@example.com">mail</a> <a href="/local">relative</a>'}
      />
    );

    const links = Array.from(container.querySelectorAll('a'));
    expect(links).toHaveLength(2);
    links.forEach((link) => {
      expect(link.hasAttribute('href')).toBe(false);
      expect(link.hasAttribute('target')).toBe(false);
      expect(link.hasAttribute('rel')).toBe(false);
    });
  });
});
