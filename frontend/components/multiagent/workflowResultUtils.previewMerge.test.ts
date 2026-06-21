import { describe, expect, it } from 'vitest';
import { DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES } from '../../utils/safeMediaDataUrl';
import {
  extractImageUrls,
  extractTextContent,
  extractAudioUrls,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  mergePreviewMediaIntoResult,
  mergePreviewImagesIntoResult,
  PREVIEW_IMAGE_MAX_ENTRIES,
} from './workflowResultUtils';

describe('mergePreviewImagesIntoResult', () => {
  it('deduplicates image urls for object payloads', () => {
    const payload = {
      imageUrl: 'https://cdn.example.com/base.png',
      imageUrls: [
        'https://cdn.example.com/base.png',
        ' https://cdn.example.com/base.png ',
        'https://cdn.example.com/existing.png',
      ],
      text: 'object payload',
    };

    const merged = mergePreviewImagesIntoResult(payload, [
      'https://cdn.example.com/existing.png',
      ' https://cdn.example.com/new.png ',
      'https://cdn.example.com/new.png',
    ]) as { imageUrl: string; imageUrls: string[] };

    expect(merged.imageUrl).toBe('https://cdn.example.com/base.png');
    expect(merged.imageUrls).toEqual([
      'https://cdn.example.com/base.png',
      'https://cdn.example.com/existing.png',
      'https://cdn.example.com/new.png',
    ]);
  });

  it('caps merged image urls for object payloads at preview max entries', () => {
    const existing = Array.from(
      { length: PREVIEW_IMAGE_MAX_ENTRIES - 1 },
      (_, index) => `https://cdn.example.com/existing-${index}.png`
    );
    const preview = Array.from(
      { length: PREVIEW_IMAGE_MAX_ENTRIES + 8 },
      (_, index) => `https://cdn.example.com/preview-${index}.png`
    );
    const payload = {
      imageUrl: existing[0],
      imageUrls: existing,
      text: 'object payload with many urls',
    };

    const merged = mergePreviewImagesIntoResult(payload, preview) as { imageUrls: string[] };

    expect(merged.imageUrls).toHaveLength(PREVIEW_IMAGE_MAX_ENTRIES);
    expect(merged.imageUrls.at(-1)).toBe('https://cdn.example.com/preview-0.png');
    expect(merged.imageUrls).not.toContain(
      `https://cdn.example.com/preview-${PREVIEW_IMAGE_MAX_ENTRIES}.png`
    );
  });

  it('returns the original object when preview image urls are already merged', () => {
    const payload = {
      imageUrl: 'data:image/png;base64,preview-0',
      imageUrls: ['data:image/png;base64,preview-0', 'data:image/png;base64,preview-1'],
      text: 'already merged preview images',
    };

    expect(
      mergePreviewImagesIntoResult(payload, [
        'data:image/png;base64,preview-0',
        'data:image/png;base64,preview-1',
      ])
    ).toBe(payload);
  });

  it('deduplicates image urls for non-object payloads', () => {
    const merged = mergePreviewImagesIntoResult('plain text payload', [
      'https://cdn.example.com/non-object-a.png',
      'https://cdn.example.com/non-object-a.png',
      'https://cdn.example.com/non-object-b.png',
    ]) as {
      imageUrl: string;
      imageUrls: string[];
      text: string;
    };

    expect(merged.imageUrl).toBe('https://cdn.example.com/non-object-a.png');
    expect(merged.imageUrls).toEqual([
      'https://cdn.example.com/non-object-a.png',
      'https://cdn.example.com/non-object-b.png',
    ]);
    expect(merged.text).toBe('plain text payload');
  });

  it('caps image urls for non-object payloads at preview max entries', () => {
    const preview = Array.from(
      { length: PREVIEW_IMAGE_MAX_ENTRIES + 6 },
      (_, index) => `https://cdn.example.com/non-object-${index}.png`
    );

    const merged = mergePreviewImagesIntoResult('plain text payload', preview) as {
      imageUrl: string;
      imageUrls: string[];
    };

    expect(merged.imageUrl).toBe('https://cdn.example.com/non-object-0.png');
    expect(merged.imageUrls).toHaveLength(PREVIEW_IMAGE_MAX_ENTRIES);
    expect(merged.imageUrls[0]).toBe('https://cdn.example.com/non-object-0.png');
    expect(merged.imageUrls.at(-1)).toBe(
      `https://cdn.example.com/non-object-${PREVIEW_IMAGE_MAX_ENTRIES - 1}.png`
    );
    expect(merged.imageUrls).not.toContain(
      `https://cdn.example.com/non-object-${PREVIEW_IMAGE_MAX_ENTRIES + 6}.png`
    );
  });

  it('deduplicates audio preview urls for object payloads', () => {
    const payload = {
      audioUrl: 'https://cdn.example.com/base.mp3',
      audioUrls: [
        'https://cdn.example.com/base.mp3',
        ' https://cdn.example.com/base.mp3 ',
        'https://cdn.example.com/existing.mp3',
      ],
      text: 'audio payload',
    };

    const merged = mergePreviewMediaIntoResult(payload, 'audio', [
      'https://cdn.example.com/existing.mp3',
      ' https://cdn.example.com/new.mp3 ',
      'https://cdn.example.com/new.mp3',
    ]) as { audioUrl: string; audioUrls: string[] };

    expect(merged.audioUrl).toBe('https://cdn.example.com/base.mp3');
    expect(merged.audioUrls).toEqual([
      'https://cdn.example.com/base.mp3',
      'https://cdn.example.com/existing.mp3',
      'https://cdn.example.com/new.mp3',
    ]);
  });

  it('returns the original object when preview media urls are already merged', () => {
    const payload = {
      videoUrl: 'https://cdn.example.com/preview-0.mp4',
      videoUrls: ['https://cdn.example.com/preview-0.mp4', 'https://cdn.example.com/preview-1.mp4'],
      text: 'already merged preview video',
    };

    expect(
      mergePreviewMediaIntoResult(payload, 'video', [
        'https://cdn.example.com/preview-0.mp4',
        'https://cdn.example.com/preview-1.mp4',
      ])
    ).toBe(payload);
  });

  it('merges video preview urls into non-object payloads', () => {
    const merged = mergePreviewMediaIntoResult('plain text payload', 'video', [
      'https://cdn.example.com/video-a.mp4',
      'https://cdn.example.com/video-a.mp4',
      'https://cdn.example.com/video-b.mp4',
    ]) as {
      videoUrl: string;
      videoUrls: string[];
      text: string;
    };

    expect(merged.videoUrl).toBe('https://cdn.example.com/video-a.mp4');
    expect(merged.videoUrls).toEqual([
      'https://cdn.example.com/video-a.mp4',
      'https://cdn.example.com/video-b.mp4',
    ]);
    expect(merged.text).toBe('plain text payload');
  });

  it('does not treat audio or video data urls as text content', () => {
    expect(extractTextContent('data:audio/mpeg;base64,AAAA')).toBe('');
    expect(extractTextContent('data:video/mp4;base64,BBBB')).toBe('');
  });

  it('recognizes temp attachment urls as audio when enclosing mimeType is audio', () => {
    const payload = {
      audio: {
        url: '/api/temp-images/audio-attachment-id',
        mimeType: 'audio/mpeg',
      },
    };

    expect(extractAudioUrls(payload)).toEqual(['/api/temp-images/audio-attachment-id']);
  });

  it('recognizes temp attachment urls as video when enclosing mimeType is video', () => {
    const payload = {
      finalOutput: {
        asset: {
          previewUrl: '/api/temp-images/video-attachment-id',
          mimeType: 'video/mp4',
        },
      },
    };

    expect(extractVideoUrls(payload)).toEqual(['/api/temp-images/video-attachment-id']);
  });

  it('recognizes absolute temp attachment urls when enclosing contentType is present', () => {
    const payload = {
      finalOutput: {
        asset: {
          previewUrl: 'https://example.com/api/temp-images/video-attachment-id',
          contentType: 'video/mp4',
        },
      },
    };

    expect(extractVideoUrls(payload)).toEqual([
      'https://example.com/api/temp-images/video-attachment-id',
    ]);
  });

  it('does not treat browser-local blob urls as directly renderable workflow result media', () => {
    expect(isDirectlyRenderableImageUrl('blob:https://gemini.dicry.cn:18443/stale-image')).toBe(
      false
    );
    expect(isDirectlyRenderableAudioUrl('blob:https://gemini.dicry.cn:18443/stale-audio')).toBe(
      false
    );
    expect(isDirectlyRenderableVideoUrl('blob:https://gemini.dicry.cn:18443/stale-video')).toBe(
      false
    );
    expect(extractAudioUrls({ audioUrl: 'blob:https://gemini.dicry.cn:18443/stale-audio' })).toEqual(
      []
    );
    expect(extractVideoUrls({ videoUrl: 'blob:https://gemini.dicry.cn:18443/stale-video' })).toEqual(
      []
    );
  });

  it('only treats safe raster data image urls as directly renderable workflow result images', () => {
    expect(isDirectlyRenderableImageUrl('data:image/png;base64,YWJj')).toBe(true);
    expect(isDirectlyRenderableImageUrl('data:image/svg+xml;base64,PHN2Zy8+')).toBe(false);
    expect(isDirectlyRenderableImageUrl('data:image/png,<svg onload=alert(1)>')).toBe(false);
  });

  it('does not directly render oversized inline workflow result images', () => {
    const payloadLength = Math.ceil(((DEFAULT_SAFE_INLINE_IMAGE_MAX_BYTES + 1) * 4) / 3);
    const oversizedImageUrl = `data:image/png;base64,${'A'.repeat(payloadLength)}`;

    expect(isDirectlyRenderableImageUrl(oversizedImageUrl)).toBe(false);
  });

  it('ignores source and reference images when extracting generated result images', () => {
    const payload = {
      sourceImageUrl: '/api/storage/local-files/source.png',
      referenceImages: [
        {
          imageUrl: '/api/storage/local-files/reference.png',
        },
      ],
      finalOutput: {
        imageUrl: '/api/storage/local-files/generated.png',
        imageUrls: ['/api/storage/local-files/generated.png'],
      },
    };

    expect(extractImageUrls(payload)).toEqual(['/api/storage/local-files/generated.png']);
  });

  it('ignores source-video containers and source-video url hints when extracting result videos', () => {
    const payload = {
      finalOutput: {
        sourceVideoUrl: 'https://cdn.example.com/source-direct.mp4',
        sourceVideo: {
          videoUrl: 'https://cdn.example.com/source-nested.mp4',
          videoUrls: ['https://cdn.example.com/source-nested.mp4'],
        },
        result: {
          videoUrl: 'https://cdn.example.com/generated.mp4',
          videoUrls: ['https://cdn.example.com/generated.mp4'],
        },
      },
    };

    expect(extractVideoUrls(payload)).toEqual(['https://cdn.example.com/generated.mp4']);
  });
});
