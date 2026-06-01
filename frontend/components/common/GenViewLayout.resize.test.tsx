// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GenViewLayout } from './GenViewLayout';

describe('GenViewLayout sidebar resizing', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('does not re-render sidebar content for every mousemove while dragging', () => {
    let sidebarRenderCount = 0;

    const SidebarProbe = () => {
      sidebarRenderCount += 1;
      return <div>history content</div>;
    };

    render(
      <GenViewLayout
        sidebarTitle="History"
        sidebar={<SidebarProbe />}
        main={<div>Main</div>}
        isMobileHistoryOpen={false}
        setIsMobileHistoryOpen={vi.fn()}
        hideSessionSwitcher
      />
    );

    const initialRenderCount = sidebarRenderCount;
    const resizeHandle = screen.getByTitle('拖动调整左侧宽度');

    fireEvent.mouseDown(resizeHandle, { clientX: 380 });
    const renderCountAfterStart = sidebarRenderCount;

    fireEvent.mouseMove(window, { clientX: 400 });
    fireEvent.mouseMove(window, { clientX: 430 });
    fireEvent.mouseMove(window, { clientX: 460 });

    expect(renderCountAfterStart).toBeGreaterThanOrEqual(initialRenderCount);
    expect(sidebarRenderCount).toBe(renderCountAfterStart);

    fireEvent.mouseUp(window);
    expect(sidebarRenderCount).toBeGreaterThanOrEqual(renderCountAfterStart);
  });

  it('does not persist intermediate widths while the drag is still active', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    render(
      <GenViewLayout
        sidebarTitle="History"
        sidebar={<div>history content</div>}
        main={<div>Main</div>}
        isMobileHistoryOpen={false}
        setIsMobileHistoryOpen={vi.fn()}
        hideSessionSwitcher
      />
    );

    const resizeHandle = screen.getByTitle('拖动调整左侧宽度');
    fireEvent.mouseDown(resizeHandle, { clientX: 380 });
    fireEvent.mouseMove(window, { clientX: 460 });

    act(() => {
      vi.advanceTimersByTime(400);
    });

    const widthWritesDuringDrag = setItemSpy.mock.calls.filter(
      ([key]) => key === 'gen-view-layout:left-width'
    );
    expect(widthWritesDuringDrag).toHaveLength(0);

    fireEvent.mouseUp(window);
    act(() => {
      vi.advanceTimersByTime(400);
    });

    const widthWritesAfterCommit = setItemSpy.mock.calls.filter(
      ([key]) => key === 'gen-view-layout:left-width'
    );
    expect(widthWritesAfterCommit).toHaveLength(1);
  });
});
