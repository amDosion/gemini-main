// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ViewSideParamsPanel } from './ViewSideParamsPanel';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe('ViewSideParamsPanel resizing', () => {
  it('lets desktop users drag the left edge to resize the parameters panel', () => {
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});

    render(
      <ViewSideParamsPanel
        title="视频参数"
        resetParams={vi.fn()}
        controlsContent={<div>controls</div>}
        editAreaContent={<div>input</div>}
      />
    );

    const panel = screen.getByTestId('view-side-params-panel');
    const handle = screen.getByRole('separator', { name: '拖动调整参数面板宽度' });

    expect(panel).toHaveStyle({ width: '288px' });

    fireEvent.mouseDown(handle, { clientX: 500 });
    fireEvent.mouseMove(window, { clientX: 420 });
    fireEvent.mouseUp(window);

    expect(panel).toHaveStyle({ width: '368px' });
    expect(window.localStorage.getItem('view-side-params-panel:width')).toBe('368');
  });
});
