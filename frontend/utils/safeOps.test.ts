import { describe, expect, it } from 'vitest';

import { safeJsonParse } from './safeOps';

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

describe('safeJsonParse', () => {
  it('returns parsed object on valid JSON without guard', () => {
    expect(safeJsonParse('{"a":1}', null)).toEqual({ a: 1 });
    expect(safeJsonParse('[1,2,3]', [])).toEqual([1, 2, 3]);
    expect(safeJsonParse('"hello"', '')).toBe('hello');
    expect(safeJsonParse('null', 'fallback')).toBe(null);
  });

  it('returns fallback on invalid JSON', () => {
    expect(safeJsonParse('not json', null)).toBe(null);
    expect(safeJsonParse('', 'x')).toBe('x');
    expect(safeJsonParse('{broken', 42)).toBe(42);
  });

  it('returns fallback when guard fails on parsed value', () => {
    expect(safeJsonParse('"plain-string"', null, isRecord)).toBe(null);
    expect(safeJsonParse('[1,2,3]', null, isRecord)).toBe(null);
    expect(safeJsonParse('42', null, isRecord)).toBe(null);
  });

  it('returns parsed when guard passes', () => {
    expect(safeJsonParse('{"x":10}', null, isRecord)).toEqual({ x: 10 });
    expect(safeJsonParse('[1,2]', null, Array.isArray)).toEqual([1, 2]);
  });

  it('returns fallback when JSON.parse succeeds with null but guard rejects null', () => {
    expect(safeJsonParse('null', { default: true } as Record<string, unknown>, isRecord)).toEqual({
      default: true,
    });
  });

  it('preserves backward-compat: 2-arg call still works', () => {
    expect(safeJsonParse('{"a":1}', null)).toEqual({ a: 1 });
    expect(safeJsonParse('bad', null)).toBe(null);
  });
});
