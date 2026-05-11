// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useAsyncState } from './useAsyncState';

describe('useAsyncState', () => {
  it('success path: sets data, clears loading, no error', async () => {
    const asyncFn = vi.fn(async (x: number) => x * 2);
    const onSuccess = vi.fn();
    const { result } = renderHook(() => useAsyncState<number, [number]>(asyncFn, { onSuccess }));

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);

    let returned: number | null = null;
    await act(async () => {
      returned = await result.current.execute(21);
    });

    expect(returned).toBe(42);
    expect(result.current.data).toBe(42);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(onSuccess).toHaveBeenCalledWith(42);
  });

  it('failure path: error string comes from getErrorMessage; onError fired', async () => {
    const asyncFn = vi.fn(async () => {
      throw new Error('bad request');
    });
    const onError = vi.fn();
    const { result } = renderHook(() => useAsyncState<void, []>(asyncFn, { onError }));

    let returned: unknown = 'unset';
    await act(async () => {
      returned = await result.current.execute();
    });

    expect(returned).toBeNull();
    expect(result.current.error).toBe('bad request');
    expect(result.current.loading).toBe(false);
    expect(onError).toHaveBeenCalled();
  });

  it('execute after unmount does NOT setState (no warning)', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let resolveFn: ((v: number) => void) | null = null;
    const asyncFn = () =>
      new Promise<number>((resolve) => {
        resolveFn = resolve;
      });

    const { result, unmount } = renderHook(() => useAsyncState<number, []>(asyncFn));

    act(() => {
      void result.current.execute();
    });
    expect(result.current.loading).toBe(true);

    unmount();

    await act(async () => {
      resolveFn!(99);
      await Promise.resolve();
    });

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it('concurrent execute: stale result is discarded; latest wins', async () => {
    let firstResolve: ((v: string) => void) | null = null;
    let secondResolve: ((v: string) => void) | null = null;

    const asyncFn = vi.fn((tag: string) => {
      return new Promise<string>((resolve) => {
        if (tag === 'first') firstResolve = resolve;
        else secondResolve = resolve;
      });
    });

    const { result } = renderHook(() => useAsyncState<string, [string]>(asyncFn));

    act(() => {
      void result.current.execute('first');
    });
    act(() => {
      void result.current.execute('second');
    });

    await act(async () => {
      secondResolve!('result-second');
      await Promise.resolve();
    });
    expect(result.current.data).toBe('result-second');

    await act(async () => {
      firstResolve!('result-first');
      await Promise.resolve();
    });
    expect(result.current.data).toBe('result-second');
  });

  it('reset() clears data/error and bumps sequence to discard in-flight', async () => {
    let resolveFn: ((v: number) => void) | null = null;
    const asyncFn = () =>
      new Promise<number>((resolve) => {
        resolveFn = resolve;
      });

    const { result } = renderHook(() => useAsyncState<number, []>(asyncFn, { initialData: 10 }));

    expect(result.current.data).toBe(10);

    act(() => {
      void result.current.execute();
    });
    expect(result.current.loading).toBe(true);

    act(() => {
      result.current.reset();
    });
    expect(result.current.data).toBe(10);
    expect(result.current.loading).toBe(false);

    await act(async () => {
      resolveFn!(999);
      await Promise.resolve();
    });
    expect(result.current.data).toBe(10);
  });
});
