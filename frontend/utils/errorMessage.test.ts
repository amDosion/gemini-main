import { describe, expect, it } from 'vitest';

import { getErrorMessage } from './errorMessage';

describe('getErrorMessage', () => {
  it('returns Error.message for Error instances', () => {
    const err = new Error('database unreachable');
    expect(getErrorMessage(err)).toBe('database unreachable');
  });

  it('returns the string itself when err is a string', () => {
    expect(getErrorMessage('rate limit exceeded')).toBe('rate limit exceeded');
  });

  it('returns fallback when err is null or undefined', () => {
    expect(getErrorMessage(null)).toBe('Unknown error');
    expect(getErrorMessage(undefined)).toBe('Unknown error');
    expect(getErrorMessage(null, 'fallback msg')).toBe('fallback msg');
    expect(getErrorMessage(undefined, 'fallback msg')).toBe('fallback msg');
  });

  it('returns err.message for axios-like duck-typed { message: string }', () => {
    const axiosLike = { message: 'Request failed with status code 500', code: 'ERR_BAD_RESPONSE' };
    expect(getErrorMessage(axiosLike)).toBe('Request failed with status code 500');
  });

  it('falls back to String(err) for plain objects without message and for circular references', () => {
    // Plain object without message
    expect(getErrorMessage({ code: 'X', detail: 'Y' })).toBe('[object Object]');

    // Circular reference must not throw (regression: never use JSON.stringify)
    const circular: Record<string, unknown> = { name: 'cyc' };
    circular.self = circular;
    expect(() => getErrorMessage(circular)).not.toThrow();
    expect(getErrorMessage(circular)).toBe('[object Object]');

    // Non-string message should NOT short-circuit to err.message
    expect(getErrorMessage({ message: 42 })).toBe('[object Object]');

    // message=undefined should NOT short-circuit (locks in chosen semantics)
    expect(getErrorMessage({ message: undefined })).toBe('[object Object]');
  });

  it('ignores message on prototype chain (own-property only)', () => {
    // 防御性测试：原型上的 message 不应被采纳（hasOwnProperty.call 而非 in）
    class WithProtoMessage {}
    (WithProtoMessage.prototype as { message?: string }).message = 'prototype-leak';
    const obj = new WithProtoMessage();
    expect(getErrorMessage(obj)).toBe('[object Object]');
  });

  it('handles primitive non-string err: number / boolean / bigint / Symbol', () => {
    expect(getErrorMessage(42)).toBe('42');
    expect(getErrorMessage(0)).toBe('0');
    expect(getErrorMessage(true)).toBe('true');
    expect(getErrorMessage(false)).toBe('false');
    expect(getErrorMessage(123n)).toBe('123');
    expect(getErrorMessage(Symbol('x'))).toBe('Symbol(x)');
  });
});
