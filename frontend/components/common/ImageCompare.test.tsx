// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ImageCompare } from './ImageCompare';

describe('ImageCompare', () => {
  afterEach(() => {
    cleanup();
  });

  it('updates the comparison divider while dragging', () => {
    const { container } = render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    const compare = container.firstElementChild as HTMLElement;
    expect(compare).toBeInTheDocument();

    vi.spyOn(compare, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 200,
      height: 200,
      right: 200,
      bottom: 200,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    Object.defineProperty(compare, 'setPointerCapture', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(compare, 'releasePointerCapture', {
      configurable: true,
      value: vi.fn(),
    });

    fireEvent.pointerDown(compare, { clientX: 50, pointerId: 1 });
    fireEvent.pointerMove(compare, { clientX: 150, pointerId: 1 });

    expect(compare.querySelector('div[style*="left: 75%"]')).toBeInTheDocument();
  });

  it('renders a sizing image so absolutely positioned compare layers have visible dimensions', () => {
    render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    const sizer = document.querySelector('[data-testid="image-compare-sizer"]') as HTMLImageElement | null;

    expect(sizer).toBeInTheDocument();
    expect(sizer).toHaveAttribute('src', '/result.png');
    expect(sizer).toHaveAttribute('aria-hidden', 'true');
  });

  it('adjusts the source image opacity with the opacity slider', () => {
    render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    fireEvent.change(screen.getByLabelText('原图透明度'), { target: { value: '45' } });

    expect(screen.getByTestId('image-compare-before-layer')).toHaveStyle({ opacity: '0.45' });
  });
});
