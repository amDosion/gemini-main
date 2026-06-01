import { describe, expect, it } from 'vitest';
import { getPreferredGoogleExpandModelId } from './googleExpandModelSelection';
import type { ModelConfig } from '../types/types';

const makeModel = (id: string): ModelConfig => ({
  id,
  name: id,
  description: id,
  capabilities: {
    vision: true,
    search: false,
    reasoning: false,
    coding: false,
  },
});

describe('getPreferredGoogleExpandModelId', () => {
  const models = [
    makeModel('imagen-3.0-capability-001'),
    makeModel('imagen-4.0-upscale-preview'),
  ];

  it.each(['ratio', 'scale', 'offset'] as const)(
    'uses the Imagen edit/capability model for %s outpainting',
    (outpaintMode) => {
      expect(getPreferredGoogleExpandModelId(outpaintMode, models)).toBe(
        'imagen-3.0-capability-001'
      );
    }
  );

  it('uses the upscale model for upscale mode', () => {
    expect(getPreferredGoogleExpandModelId('upscale', models)).toBe(
      'imagen-4.0-upscale-preview'
    );
  });

  it('does not force a model that is not exposed for the current profile', () => {
    expect(getPreferredGoogleExpandModelId('ratio', [makeModel('imagen-4.0-upscale-preview')]))
      .toBeNull();
  });
});
