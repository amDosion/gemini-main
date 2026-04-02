import { describe, expect, it } from 'vitest';
import { removeRecordKey, upsertBoundedRecord } from './boundedRecordCache';

describe('upsertBoundedRecord', () => {
  it('evicts oldest entries when record grows beyond max entries', () => {
    const withA = upsertBoundedRecord({
      record: {},
      key: 'a',
      value: ['a'],
      maxEntries: 2,
    });
    const withB = upsertBoundedRecord({
      record: withA,
      key: 'b',
      value: ['b'],
      maxEntries: 2,
    });
    const withC = upsertBoundedRecord({
      record: withB,
      key: 'c',
      value: ['c'],
      maxEntries: 2,
    });

    expect(Object.keys(withC)).toEqual(['b', 'c']);
    expect(withC.a).toBeUndefined();
  });

  it('moves updated key to newest position before eviction', () => {
    const refreshed = upsertBoundedRecord({
      record: { a: 1, b: 2 },
      key: 'a',
      value: 11,
      maxEntries: 2,
    });
    const withC = upsertBoundedRecord({
      record: refreshed,
      key: 'c',
      value: 3,
      maxEntries: 2,
    });

    expect(Object.keys(withC)).toEqual(['a', 'c']);
    expect(withC.a).toBe(11);
  });

  it('keeps protected keys during eviction', () => {
    const next = upsertBoundedRecord({
      record: { a: 1, b: 2, c: 3 },
      key: 'd',
      value: 4,
      maxEntries: 2,
      protectedKeys: ['a'],
    });

    expect(Object.keys(next)).toEqual(['a', 'd']);
  });

  it('keeps all entries when max is exceeded only by protected keys', () => {
    const next = upsertBoundedRecord({
      record: { a: 1, b: 2 },
      key: 'c',
      value: 3,
      maxEntries: 1,
      protectedKeys: ['a', 'b', 'c'],
    });

    expect(Object.keys(next)).toEqual(['a', 'b', 'c']);
  });

  it('ignores blank keys', () => {
    const initial = { a: 1 };
    const next = upsertBoundedRecord({
      record: initial,
      key: '   ',
      value: 2,
      maxEntries: 3,
    });
    expect(next).toBe(initial);
  });
});

describe('removeRecordKey', () => {
  it('returns same object when key is absent', () => {
    const initial = { a: 1 };
    const next = removeRecordKey(initial, 'missing');
    expect(next).toBe(initial);
  });

  it('removes existing key', () => {
    const next = removeRecordKey({ a: 1, b: 2 }, 'a');
    expect(next).toEqual({ b: 2 });
  });
});
