import { describe, expect, it } from 'vitest';

import { addCitations } from './groundingUtils';

describe('addCitations', () => {
  it('returns text unchanged when groundingMetadata is null', () => {
    expect(addCitations('hello world', null)).toBe('hello world');
  });

  it('returns text unchanged when groundingMetadata is undefined', () => {
    expect(addCitations('hello world', undefined)).toBe('hello world');
  });

  it('returns text unchanged when groundingSupports is missing', () => {
    expect(addCitations('hello world', { groundingChunks: [{ web: { uri: 'https://example.com' } }] })).toBe('hello world');
  });

  it('returns text unchanged when groundingChunks is missing', () => {
    expect(addCitations('hello world', { groundingSupports: [{ segment: { endIndex: 5 }, groundingChunkIndices: [0] }] })).toBe('hello world');
  });

  it('returns text unchanged when both arrays are empty', () => {
    expect(addCitations('hello world', { groundingSupports: [], groundingChunks: [] })).toBe('hello world');
  });

  it('injects a single citation at the correct position', () => {
    const text = 'hello world';
    const result = addCitations(text, {
      groundingSupports: [{ segment: { endIndex: 5 }, groundingChunkIndices: [0] }],
      groundingChunks: [{ web: { uri: 'https://example.com', title: 'Example' } }],
    });
    // endIndex=5 means insert after "hello"
    expect(result).toBe('hello [1](https://example.com) world');
  });

  it('injects multiple non-overlapping citations without offset corruption', () => {
    const text = 'foo bar baz';
    // Two citations at different positions; processed in descending endIndex order to avoid corruption
    const result = addCitations(text, {
      groundingSupports: [
        { segment: { endIndex: 3 }, groundingChunkIndices: [0] },  // after "foo"
        { segment: { endIndex: 7 }, groundingChunkIndices: [1] },  // after "foo bar"
      ],
      groundingChunks: [
        { web: { uri: 'https://a.com' } },
        { web: { uri: 'https://b.com' } },
      ],
    });
    expect(result).toBe('foo [1](https://a.com) bar [2](https://b.com) baz');
  });

  it('skips a citation when endIndex exceeds text length', () => {
    const text = 'short';
    const result = addCitations(text, {
      groundingSupports: [{ segment: { endIndex: 999 }, groundingChunkIndices: [0] }],
      groundingChunks: [{ web: { uri: 'https://example.com' } }],
    });
    // endIndex > text.length — the guard must suppress this citation
    expect(result).toBe('short');
  });

  it('skips a citation when chunk has no web.uri', () => {
    const text = 'hello world';
    const result = addCitations(text, {
      groundingSupports: [{ segment: { endIndex: 5 }, groundingChunkIndices: [0] }],
      groundingChunks: [{ web: undefined }],
    });
    expect(result).toBe('hello world');
  });

  it('skips a support entry when endIndex is missing', () => {
    const text = 'hello world';
    const result = addCitations(text, {
      groundingSupports: [{ segment: {}, groundingChunkIndices: [0] }],
      groundingChunks: [{ web: { uri: 'https://example.com' } }],
    });
    expect(result).toBe('hello world');
  });

  it('skips a support entry when groundingChunkIndices is empty', () => {
    const text = 'hello world';
    const result = addCitations(text, {
      groundingSupports: [{ segment: { endIndex: 5 }, groundingChunkIndices: [] }],
      groundingChunks: [{ web: { uri: 'https://example.com' } }],
    });
    expect(result).toBe('hello world');
  });

  it('handles a chunk index that is out of range', () => {
    const text = 'hello world';
    // Index 5 does not exist in the chunks array
    const result = addCitations(text, {
      groundingSupports: [{ segment: { endIndex: 5 }, groundingChunkIndices: [5] }],
      groundingChunks: [{ web: { uri: 'https://example.com' } }],
    });
    expect(result).toBe('hello world');
  });
});
