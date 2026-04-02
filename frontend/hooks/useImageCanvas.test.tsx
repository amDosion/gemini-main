// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useImageCanvas } from './useImageCanvas';

describe('useImageCanvas', () => {
  it('keeps resetView idempotent when the canvas is already at the default state', () => {
    let renderCount = 0;

    const { result } = renderHook(() => {
      renderCount += 1;
      return useImageCanvas({ initialZoom: 1 });
    });

    expect(renderCount).toBe(1);

    act(() => {
      result.current.resetView();
    });

    expect(renderCount).toBe(1);
    expect(result.current.zoom).toBe(1);
    expect(result.current.pan).toEqual({ x: 0, y: 0 });
    expect(result.current.isDragging).toBe(false);
  });
});
