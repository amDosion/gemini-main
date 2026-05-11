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

  it('same-messageId re-open after resize uses preserved size for initial position', () => {
    const { result } = renderHook(() => useHoverPromptPreview());

    // Step 1: 用大 anchorY 让 panelH 影响 top 计算
    act(() => {
      result.current.openPreview(makePayload('msg-1', 500, 400));
    });
    const firstTop = result.current.position!.top; // panelH=ESTIMATED_PANEL_HEIGHT=260

    // Step 2: 触发 startResize — 内部会 setSize({rect?.width ?? 360, rect?.height ?? 280})
    const fakeEvent = {
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
      clientX: 0,
      clientY: 0,
    } as unknown as React.MouseEvent;
    act(() => {
      result.current.startResize(fakeEvent);
    });
    expect(result.current.size?.height).toBe(280); // RESIZE_FALLBACK_HEIGHT

    // Step 3: 同 messageId 重开 — openPreview 应当用 sizeRef.current.height=280 算 position
    act(() => {
      result.current.openPreview(makePayload('msg-1', 500, 400));
    });
    const secondTop = result.current.position!.top;

    // 验证：两次 top 不同（260 vs 280 panel 高度导致 anchorY - panelH/2 偏移 10px）
    expect(secondTop).not.toBe(firstTop);
    expect(result.current.size).not.toBeNull(); // size 在同 msg 重开时不被重置
  });

  it('window resize event closes preview', () => {
    const { result } = renderHook(() => useHoverPromptPreview());
    act(() => {
      result.current.openPreview(makePayload('msg-1'));
    });
    expect(result.current.preview).not.toBeNull();

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });
    expect(result.current.preview).toBeNull();
    expect(result.current.position).toBeNull();
  });

  it('window scroll closes preview when target is outside panel; inside panel does NOT close', () => {
    const { result } = renderHook(() => useHoverPromptPreview());

    // Setup: panelRef 指向 jsdom 中的真实节点
    const panel = document.createElement('div');
    document.body.appendChild(panel);
    const innerChild = document.createElement('span');
    panel.appendChild(innerChild);

    act(() => {
      result.current.openPreview(makePayload('msg-1'));
    });
    (result.current.panelRef as React.MutableRefObject<HTMLDivElement | null>).current = panel;

    // 1. scroll target 在 panel 内 → 仍开
    act(() => {
      const ev = new Event('scroll', { bubbles: true });
      Object.defineProperty(ev, 'target', { value: innerChild });
      window.dispatchEvent(ev);
    });
    expect(result.current.preview).not.toBeNull();

    // 2. scroll target 在 panel 外 → 关闭
    const outsideNode = document.createElement('div');
    document.body.appendChild(outsideNode);
    act(() => {
      const ev = new Event('scroll', { bubbles: true });
      Object.defineProperty(ev, 'target', { value: outsideNode });
      window.dispatchEvent(ev);
    });
    expect(result.current.preview).toBeNull();

    document.body.removeChild(panel);
    document.body.removeChild(outsideNode);
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
