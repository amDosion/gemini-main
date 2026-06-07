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
});
