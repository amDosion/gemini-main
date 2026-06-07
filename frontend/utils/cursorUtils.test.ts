import { describe, it, expect } from 'vitest';
import { STREAMING_CURSOR_CLASSNAME } from './cursorUtils';

describe('cursorUtils', () => {
  it('exports a non-empty Tailwind className string for the streaming cursor', () => {
    expect(typeof STREAMING_CURSOR_CLASSNAME).toBe('string');
    expect(STREAMING_CURSOR_CLASSNAME.length).toBeGreaterThan(0);
  });

  it('drives the cursor animation via the Tailwind animate-pulse class', () => {
    // The cursor must animate using a Tailwind class so it survives the
    // Markdown sanitizer boundary (W02R-019), which strips inline `style`.
    expect(STREAMING_CURSOR_CLASSNAME).toContain('animate-pulse');
  });

  it('does not embed an inline style attribute (sanitizer would strip it)', () => {
    // Regression guard: the old implementation injected a raw HTML string with
    // `style="animation-duration:1s; vertical-align:text-bottom"`. The fix moves
    // the cursor into the React tree as a className-only element.
    expect(STREAMING_CURSOR_CLASSNAME).not.toContain('style');
    expect(STREAMING_CURSOR_CLASSNAME).not.toContain('<span');
    expect(STREAMING_CURSOR_CLASSNAME).not.toContain('animation-duration');
  });

  it('uses vertical alignment and inline-block sizing classes only', () => {
    expect(STREAMING_CURSOR_CLASSNAME).toContain('inline-block');
    expect(STREAMING_CURSOR_CLASSNAME).toContain('align-text-bottom');
  });
});
