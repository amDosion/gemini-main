// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { generateMaskFromSelections, updateMaskCanvasUrl } from './maskDrawingHelpers';
import {
  __resetMediaCacheForTest,
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
} from '../../../services/mediaCache';

const createCanvasStub = (blobText: string): HTMLCanvasElement =>
  ({
    width: 10,
    height: 10,
    toBlob: (callback: BlobCallback) => {
      callback(new Blob([blobText], { type: 'image/png' }));
    },
    getContext: () => ({
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      drawImage: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      fillStyle: '',
      globalCompositeOperation: '',
    }),
  }) as unknown as HTMLCanvasElement;

describe('maskDrawingHelpers managed object urls', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    __resetMediaCacheForTest();
    let objectUrlIndex = 0;
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => {
        objectUrlIndex += 1;
        return `blob:mask-managed-${objectUrlIndex}`;
      }),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    __resetMediaCacheForTest();
    vi.restoreAllMocks();
  });

  it('defers brush mask preview revocation while shared media cache retains it', () => {
    const previousUrl = 'blob:mask-managed-old-brush';
    const maskPreviewBlobUrlRef = { current: previousUrl };
    retainMediaObjectUrl(previousUrl);

    updateMaskCanvasUrl({
      maskCanvasRef: { current: createCanvasStub('brush-mask') },
      hasBrushContentRef: { current: true },
      maskPreviewBlobUrlRef,
      setMaskCanvasUrl: vi.fn(),
      onAfterUpdate: vi.fn(),
    });

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(previousUrl);

    releaseMediaObjectUrl(previousUrl);
    // Revocation of a retired-while-retained url is intentionally deferred
    // (RETAINED_OBJECT_URL_REVOKE_DELAY_MS); advance fake timers to observe it.
    vi.runAllTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(previousUrl);
  });

  it('defers composite mask preview revocation while shared media cache retains it', () => {
    const previousUrl = 'blob:mask-managed-old-composite';
    const maskPreviewUrlRef = { current: previousUrl };
    retainMediaObjectUrl(previousUrl);

    generateMaskFromSelections({
      rects: [{ startX: 0, startY: 0, endX: 5, endY: 5 }],
      inverted: false,
      imageRef: {
        current: {
          naturalWidth: 10,
          naturalHeight: 10,
          clientWidth: 10,
          clientHeight: 10,
        } as HTMLImageElement,
      },
      maskCanvasRef: { current: null },
      hasBrushContentRef: { current: false },
      maskCompositeCanvasRef: { current: createCanvasStub('composite-mask') },
      maskPreviewUrlRef,
      isMountedRef: { current: true },
      setMaskPreviewUrl: vi.fn(),
      setMaskRequestDataUrl: vi.fn(),
      setMaskPreviewError: vi.fn(),
      showError: vi.fn(),
    });

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(previousUrl);

    releaseMediaObjectUrl(previousUrl);
    // Revocation of a retired-while-retained url is intentionally deferred
    // (RETAINED_OBJECT_URL_REVOKE_DELAY_MS); advance fake timers to observe it.
    vi.runAllTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(previousUrl);
  });
});
