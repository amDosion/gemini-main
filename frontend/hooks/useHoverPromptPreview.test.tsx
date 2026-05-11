// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useHoverPromptPreview } from './useHoverPromptPreview';
import type { HoverPromptPreviewBase } from './useHoverPromptPreview';

interface ExtendedPayload extends HoverPromptPreviewBase {
  extensionCount: number;
}

function makePayload(id: string, anchorX = 100, anchorY = 100): HoverPromptPreviewBase {
  return {
    messageId: id,
    anchorX,
    anchorY,
    originalPrompt: `original-${id}`,
    optimizedPrompt: `optimized-${id}`,
  };
}

describe('useHoverPromptPreview', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('openPreview sets preview + position; closePreview clears state', () => {
    const { result } = renderHook(() => useHoverPromptPreview());
    expect(result.current.preview).toBeNull();
    expect(result.current.position).toBeNull();

    act(() => {
      result.current.openPreview(makePayload('msg-1', 500, 400));
    });
    expect(result.current.preview?.messageId).toBe('msg-1');
    expect(result.current.position).not.toBeNull();
    expect(result.current.position!.left).toBeGreaterThanOrEqual(8);
    expect(result.current.position!.top).toBeGreaterThanOrEqual(8);

    act(() => {
      result.current.closePreview();
    });
    expect(result.current.preview).toBeNull();
    expect(result.current.position).toBeNull();
    expect(result.current.size).toBeNull();
  });

  it('switching messageId leaves size null; re-open same msg keeps size null', () => {
    const { result } = renderHook(() => useHoverPromptPreview());

    act(() => {
      result.current.openPreview(makePayload('msg-1'));
    });
    expect(result.current.size).toBeNull();

    act(() => {
      result.current.openPreview(makePayload('msg-1', 200, 200));
    });
    expect(result.current.size).toBeNull();

    act(() => {
      result.current.openPreview(makePayload('msg-2'));
    });
    expect(result.current.preview?.messageId).toBe('msg-2');
    expect(result.current.size).toBeNull();
  });

  it('scheduleClose fires close after delay; cancelScheduledClose prevents it', () => {
    const { result } = renderHook(() => useHoverPromptPreview());

    act(() => {
      result.current.openPreview(makePayload('msg-1'));
    });
    expect(result.current.preview).not.toBeNull();

    act(() => {
      result.current.scheduleClose(300);
    });
    expect(result.current.preview).not.toBeNull();

    act(() => {
      result.current.cancelScheduledClose();
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.preview).not.toBeNull();

    act(() => {
      result.current.scheduleClose(100);
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current.preview).toBeNull();
  });

  it('cleanup on unmount removes window listeners (no setState-after-unmount)', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { result, unmount } = renderHook(() => useHoverPromptPreview());

    act(() => {
      result.current.openPreview(makePayload('msg-1'));
    });
    const fakeEvent = {
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
      clientX: 200,
      clientY: 200,
    } as unknown as React.MouseEvent;
    act(() => {
      result.current.startResize(fakeEvent);
    });
    expect(result.current.isResizing).toBe(true);

    unmount();

    const removedEvents = removeSpy.mock.calls.map((c) => c[0]);
    expect(removedEvents).toContain('mousemove');
    expect(removedEvents).toContain('mouseup');
    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });

  it('generic P accepts extended payload with extra fields (VideoGenView use case)', () => {
    const { result } = renderHook(() => useHoverPromptPreview<ExtendedPayload>());
    act(() => {
      result.current.openPreview({
        messageId: 'v-1',
        anchorX: 100,
        anchorY: 100,
        originalPrompt: 'o',
        optimizedPrompt: 'op',
        extensionCount: 4,
      });
    });
    expect(result.current.preview?.extensionCount).toBe(4);
  });
});
