import type { ModelConfig } from '../types/types';

export type GoogleOutpaintMode = 'ratio' | 'scale' | 'offset' | 'upscale';

export const GOOGLE_EXPAND_OUTPAINT_MODEL_ID = 'imagen-3.0-capability-001';
export const GOOGLE_EXPAND_UPSCALE_MODEL_ID = 'imagen-4.0-upscale-preview';

export const getPreferredGoogleExpandModelId = (
  outpaintMode: GoogleOutpaintMode | string,
  visibleModels: ReadonlyArray<Pick<ModelConfig, 'id'>>
): string | null => {
  const preferredModelId =
    outpaintMode === 'upscale'
      ? GOOGLE_EXPAND_UPSCALE_MODEL_ID
      : GOOGLE_EXPAND_OUTPAINT_MODEL_ID;

  return visibleModels.some((model) => model.id === preferredModelId)
    ? preferredModelId
    : null;
};
