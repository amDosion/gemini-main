// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import type { AppMode } from '../../types/types';
import { getProviderControls, getProviderControlByMode, normalizeProviderId } from './registry';

// Modes that are intentionally mapped to a side-panel control slot. The remaining
// AppMode values ('image-upscale', 'image-segmentation', 'product-recontext') have
// no dedicated panel control and are expected to resolve to null.
const MAPPED_MODES: AppMode[] = [
  'chat',
  'image-gen',
  'image-chat-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-mask-edit',
  'image-outpainting',
  'video-gen',
  'audio-gen',
  'pdf-extract',
  'virtual-try-on',
  'multi-agent',
];

const UNMAPPED_MODES: AppMode[] = ['image-upscale', 'image-segmentation'];

describe('registry / normalizeProviderId', () => {
  it('defaults empty or whitespace provider ids to "google"', () => {
    expect(normalizeProviderId(undefined)).toBe('google');
    expect(normalizeProviderId('')).toBe('google');
    expect(normalizeProviderId('   ')).toBe('google');
  });

  it('resolves provider aliases (google-custom -> google)', () => {
    expect(normalizeProviderId('google-custom')).toBe('google');
  });

  it('passes through unknown provider ids unchanged', () => {
    expect(normalizeProviderId('openai')).toBe('openai');
    expect(normalizeProviderId('mystery')).toBe('mystery');
  });
});

describe('registry / getProviderControlByMode', () => {
  it('returns a non-null component for every mapped mode (default provider)', () => {
    for (const mode of MAPPED_MODES) {
      const control = getProviderControlByMode(undefined, mode);
      expect(control, `expected a control for mode "${mode}"`).not.toBeNull();
      expect(typeof control).not.toBe('undefined');
    }
  });

  it('returns null for modes with no dedicated panel control', () => {
    for (const mode of UNMAPPED_MODES) {
      expect(getProviderControlByMode('google', mode)).toBeNull();
    }
  });
});

describe('registry / provider overrides', () => {
  it('uses provider-specific overrides in preference to the common defaults', () => {
    const google = getProviderControls('google');
    const openai = getProviderControls('openai');

    // openai overrides these slots, so they must differ from the common implementation.
    expect(openai.ImageGenControls).not.toBe(google.ImageGenControls);
    expect(openai.ImageEditControls).not.toBe(google.ImageEditControls);
    expect(openai.ImageMaskEditControls).not.toBe(google.ImageMaskEditControls);
    expect(openai.ImageOutpaintControls).not.toBe(google.ImageOutpaintControls);
    expect(openai.VirtualTryOnControls).not.toBe(google.VirtualTryOnControls);
  });

  it('falls back to the common implementation for slots a provider does not override', () => {
    const google = getProviderControls('google');
    const openai = getProviderControls('openai');

    // openai does not override these slots, so they fall back to the common defaults.
    expect(openai.ChatControls).toBe(google.ChatControls);
    expect(openai.VideoGenControls).toBe(google.VideoGenControls);
    expect(openai.AudioGenControls).toBe(google.AudioGenControls);
    expect(openai.MultiAgentControls).toBe(google.MultiAgentControls);
  });

  it('routes a mode through the matching provider override component', () => {
    const openaiImageGen = getProviderControlByMode('openai', 'image-gen');
    const googleImageGen = getProviderControlByMode('google', 'image-gen');
    expect(openaiImageGen).not.toBeNull();
    expect(openaiImageGen).not.toBe(googleImageGen);
  });

  it('resolves aliased providers to the same control set as their target', () => {
    expect(getProviderControls('google-custom')).toBe(getProviderControls('google'));
  });

  it('returns a stable (cached) control set for repeated calls', () => {
    expect(getProviderControls('openai')).toBe(getProviderControls('openai'));
  });
});
