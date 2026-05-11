// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ActionMenuAnchorBase } from './useActionMenu';
import { useActionMenu } from './useActionMenu';

function makeAnchor(messageId: string, anchorX = 200, anchorY = 200): ActionMenuAnchorBase {
  return { messageId, anchorX, anchorY };
}

describe('useActionMenu', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, configurable: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('open sets anchor + position; close clears both; isOpen flips', () => {
    const { result } = renderHook(() => useActionMenu());
    expect(result.current.anchor).toBeNull();
    expect(result.current.position).toBeNull();
    expect(result.current.isOpen).toBe(false);

    act(() => {
      result.current.open(makeAnchor('msg-1', 300, 300));
    });
    expect(result.current.anchor?.messageId).toBe('msg-1');
    expect(result.current.position).not.toBeNull();
    expect(result.current.position!.left).toBeGreaterThanOrEqual(8);
    expect(result.current.position!.top).toBeGreaterThanOrEqual(8);
    expect(result.current.isOpen).toBe(true);

    act(() => {
      result.current.close();
    });
    expect(result.current.anchor).toBeNull();
    expect(result.current.position).toBeNull();
    expect(result.current.isOpen).toBe(false);
  });

  it('outside-click closes; click inside panel does NOT close; isExempted target does NOT close', () => {
    const exemptNode = document.createElement('div');
    document.body.appendChild(exemptNode);
    const isExempted = (t: EventTarget | null) => t === exemptNode;

    const { result } = renderHook(() => useActionMenu({ isExempted }));
    act(() => {
      result.current.open(makeAnchor('msg-1'));
    });

    const panel = document.createElement('div');
    document.body.appendChild(panel);
    const innerChild = document.createElement('span');
    panel.appendChild(innerChild);
    (result.current.panelRef as React.MutableRefObject<HTMLDivElement | null>).current = panel;

    act(() => {
      const ev = new MouseEvent('mousedown', { bubbles: true });
      Object.defineProperty(ev, 'target', { value: innerChild });
      window.dispatchEvent(ev);
    });
    expect(result.current.isOpen).toBe(true);

    act(() => {
      const ev = new MouseEvent('mousedown', { bubbles: true });
      Object.defineProperty(ev, 'target', { value: exemptNode });
      window.dispatchEvent(ev);
    });
    expect(result.current.isOpen).toBe(true);

    const outsideNode = document.createElement('div');
    document.body.appendChild(outsideNode);
    act(() => {
      const ev = new MouseEvent('mousedown', { bubbles: true });
      Object.defineProperty(ev, 'target', { value: outsideNode });
      window.dispatchEvent(ev);
    });
    expect(result.current.isOpen).toBe(false);

    document.body.removeChild(exemptNode);
    document.body.removeChild(panel);
    document.body.removeChild(outsideNode);
  });

  it('window scroll closes the menu', () => {
    const { result } = renderHook(() => useActionMenu());
    act(() => {
      result.current.open(makeAnchor('msg-1'));
    });
    expect(result.current.isOpen).toBe(true);

    act(() => {
      window.dispatchEvent(new Event('scroll'));
    });
    expect(result.current.isOpen).toBe(false);
  });

  it('open with different anchor updates position', () => {
    const { result } = renderHook(() => useActionMenu());
    act(() => {
      result.current.open(makeAnchor('msg-1', 100, 100));
    });
    const firstPos = result.current.position;

    act(() => {
      result.current.open(makeAnchor('msg-2', 600, 500));
    });
    const secondPos = result.current.position;

    expect(secondPos).not.toBeNull();
    expect(secondPos!.left).not.toBe(firstPos!.left);
    expect(result.current.anchor?.messageId).toBe('msg-2');
  });

  it('cleanup on unmount removes mousedown/resize/scroll listeners (no setState-after-unmount)', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const removeSpy = vi.spyOn(window, 'removeEventListener');

    const { result, unmount } = renderHook(() => useActionMenu());
    act(() => {
      result.current.open(makeAnchor('msg-1'));
    });

    unmount();

    const removedEvents = removeSpy.mock.calls.map((c) => c[0]);
    expect(removedEvents).toContain('mousedown');
    expect(removedEvents).toContain('resize');
    expect(removedEvents).toContain('scroll');

    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new MouseEvent('mousedown'));

    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });
});
