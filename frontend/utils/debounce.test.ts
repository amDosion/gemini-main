import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { debounce } from './debounce';

describe('debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('invokes fn only once after the wait window when called multiple times', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('a');
    debounced('b');
    debounced('c');

    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(99);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('c');
  });

  it('cancel() prevents pending fn from firing', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 50);

    debounced('x');
    debounced.cancel();

    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });

  it('flush() invokes pending fn synchronously with last args', () => {
    const fn = vi.fn();
    const debounced = debounce<[string, number]>(fn, 200);

    debounced('id-1', 1);
    debounced('id-2', 2);
    expect(fn).not.toHaveBeenCalled();

    debounced.flush();
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('id-2', 2);

    // After flush, no pending: further timer ticks must not re-fire
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('flush() with no pending invocation is a safe no-op', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 50);

    expect(() => debounced.flush()).not.toThrow();
    expect(fn).not.toHaveBeenCalled();
  });

  it('waitMs=0 still defers via macrotask (not synchronous)', () => {
    // 锁定 JSDoc 行为：waitMs=0 走 setTimeout(0)（macrotask），非同步触发
    const fn = vi.fn();
    const debounced = debounce(fn, 0);

    debounced('immediate');
    // 调用立即返回但 fn 不应同步执行
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('immediate');
  });

  it('waitMs=-1 (negative) is clamped to 0, not synchronous', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, -1);

    debounced('negative');
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
