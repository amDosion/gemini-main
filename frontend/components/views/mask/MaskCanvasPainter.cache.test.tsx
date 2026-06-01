// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../../common/CachedImage';
import { MaskCanvasPainter } from './MaskCanvasPainter';
import {
  __resetMediaCacheForTest,
  revokeManagedMediaObjectUrl,
} from '../../../services/mediaCache';

const cachedImageSpy = vi.fn();

vi.mock('../../common/CachedImage', () => ({
  CachedImage: React.forwardRef<HTMLImageElement, CachedImageProps>((props, ref) => {
    cachedImageSpy(props);
    return <img ref={ref} alt={props.alt || ''} src={props.src || ''} />;
  }),
}));

describe('MaskCanvasPainter cache-safe images', () => {
  beforeEach(() => {
    __resetMediaCacheForTest();
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:unused-created-mask-preview'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    cachedImageSpy.mockClear();
  });

  afterEach(() => {
    cleanup();
    __resetMediaCacheForTest();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const renderPainter = (overrides: Partial<React.ComponentProps<typeof MaskCanvasPainter>> = {}) =>
    render(
      <MaskCanvasPainter
        loadingState="idle"
        isCompareMode={false}
        activeAttachments={[]}
        activeImageUrl="/api/storage/local-files/2026/06/01/mask-source.png"
        originalImageUrl={null}
        zoom={1}
        isDragging={false}
        canvasStyle={{}}
        onWheel={vi.fn()}
        onMouseDown={vi.fn()}
        onMouseMove={vi.fn()}
        onMouseUp={vi.fn()}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
        onReset={vi.fn()}
        activeMaskTool="move"
        onMaskToolChange={vi.fn()}
        brushSize={24}
        onBrushSizeChange={vi.fn()}
        maskMode="MASK_MODE_USER_PROVIDED"
        onMaskModeChange={vi.fn()}
        isMaskInverted={false}
        onToggleMaskInvert={vi.fn()}
        selectionRects={[]}
        currentSelectionRect={null}
        isSelecting={false}
        onSelectionStart={vi.fn()}
        onSelectionMove={vi.fn()}
        onSelectionEnd={vi.fn()}
        onDeleteSelection={vi.fn()}
        maskPreviewUrl={null}
        maskPreviewNotice={null}
        maskPreviewError={null}
        imageRef={React.createRef<HTMLImageElement>()}
        onBrushStart={vi.fn()}
        onBrushMove={vi.fn()}
        onBrushEnd={vi.fn()}
        isPainting={false}
        maskCanvasUrl={null}
        brushCursorRef={React.createRef<HTMLDivElement>()}
        onBrushCursorMove={vi.fn()}
        maskCanvasRef={React.createRef<HTMLCanvasElement>()}
        displayCanvasRef={React.createRef<HTMLCanvasElement>()}
        {...overrides}
      />
    );

  it('renders the active mask canvas image through CachedImage', () => {
    renderPainter();

    expect(cachedImageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        src: '/api/storage/local-files/2026/06/01/mask-source.png',
        source: expect.objectContaining({
          url: '/api/storage/local-files/2026/06/01/mask-source.png',
          mimeType: 'image/png',
        }),
        alt: 'Main Canvas',
      })
    );
  });

  it('retains the visible mask preview object url until the preview unmounts', () => {
    vi.useFakeTimers();
    const maskPreviewUrl = 'blob:visible-mask-preview';
    const { unmount } = renderPainter({ maskPreviewUrl });

    revokeManagedMediaObjectUrl(maskPreviewUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(maskPreviewUrl);

    unmount();

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(maskPreviewUrl);

    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(maskPreviewUrl);
  });
});
