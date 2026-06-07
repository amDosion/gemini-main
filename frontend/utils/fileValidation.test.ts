import { describe, expect, it } from 'vitest';

import type { AppMode } from '../types/types';
import {
  getAcceptedTypes,
  isValidFileSize,
  isValidFileType,
  validateFiles,
  validateFilesForMode,
} from './fileValidation';

const MAX_FILE_SIZE = 100 * 1024 * 1024;

/**
 * Build a File whose reported `size` and MIME `type` are controllable.
 * jsdom derives `size` from the blob contents, so we override the property
 * to keep tests fast and deterministic regardless of payload length.
 */
function makeFile(name: string, options: { type?: string; size?: number } = {}): File {
  const { type = '', size = 1 } = options;
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size, configurable: true });
  return file;
}

describe('getAcceptedTypes', () => {
  it('returns the broad attachment list for chat mode', () => {
    const types = getAcceptedTypes('chat');
    expect(types).toContain('image/*');
    expect(types).toContain('video/*');
    expect(types).toContain('audio/*');
    expect(types).toContain('application/pdf');
    expect(types).toContain('application/json');
  });

  it('restricts image-only modes to image/*', () => {
    const imageOnlyModes: AppMode[] = [
      'image-gen',
      'image-chat-edit',
      'image-mask-edit',
      'image-inpainting',
      'image-background-edit',
      'image-recontext',
      'image-outpainting',
      'virtual-try-on',
      'image-upscale',
      'image-segmentation',
      'product-recontext',
    ];
    for (const mode of imageOnlyModes) {
      expect(getAcceptedTypes(mode)).toEqual(['image/*']);
    }
  });

  it('accepts both images and videos for video-gen', () => {
    expect(getAcceptedTypes('video-gen')).toEqual(['image/*', 'video/*']);
  });

  it('accepts pdf extension and mime for pdf-extract', () => {
    expect(getAcceptedTypes('pdf-extract')).toEqual(['.pdf', 'application/pdf']);
  });

  it('returns an empty list for modes that accept no attachments', () => {
    expect(getAcceptedTypes('multi-agent')).toEqual([]);
    expect(getAcceptedTypes('audio-gen')).toEqual([]);
  });

  it('falls back to an empty list for an unknown mode', () => {
    expect(getAcceptedTypes('totally-unknown' as AppMode)).toEqual([]);
  });
});

describe('isValidFileType', () => {
  it('rejects every file when the accepted list is empty', () => {
    const file = makeFile('photo.png', { type: 'image/png' });
    expect(isValidFileType(file, [])).toBe(false);
  });

  it('matches wildcard MIME prefixes', () => {
    const png = makeFile('photo.png', { type: 'image/png' });
    const mp4 = makeFile('clip.mp4', { type: 'video/mp4' });
    expect(isValidFileType(png, ['image/*'])).toBe(true);
    expect(isValidFileType(mp4, ['image/*'])).toBe(false);
  });

  it('matches by extension when an accepted entry starts with a dot', () => {
    // .pdf entry should match by filename even when the MIME type is absent.
    const pdf = makeFile('report.PDF', { type: '' });
    expect(isValidFileType(pdf, ['.pdf'])).toBe(true);
    const docx = makeFile('report.docx', { type: '' });
    expect(isValidFileType(docx, ['.pdf'])).toBe(false);
  });

  it('matches exact MIME types', () => {
    const json = makeFile('data.json', { type: 'application/json' });
    expect(isValidFileType(json, ['application/json'])).toBe(true);
    const xml = makeFile('data.xml', { type: 'application/xml' });
    expect(isValidFileType(xml, ['application/json'])).toBe(false);
  });

  it('is case-insensitive for extension, wildcard, and exact matching', () => {
    const pdfUpper = makeFile('REPORT.PDF', { type: '' });
    expect(isValidFileType(pdfUpper, ['.pdf'])).toBe(true);

    const pngUpperType = makeFile('photo.png', { type: 'IMAGE/PNG' });
    expect(isValidFileType(pngUpperType, ['image/*'])).toBe(true);

    const jsonUpper = makeFile('data.json', { type: 'APPLICATION/JSON' });
    expect(isValidFileType(jsonUpper, ['application/json'])).toBe(true);
  });

  it('accepts a file matching any one of several accepted entries', () => {
    const mp4 = makeFile('clip.mp4', { type: 'video/mp4' });
    expect(isValidFileType(mp4, ['image/*', 'video/*'])).toBe(true);
  });
});

describe('isValidFileSize', () => {
  it('accepts a file at the boundary and rejects one byte over', () => {
    const atLimit = makeFile('a.bin', { size: MAX_FILE_SIZE });
    const overLimit = makeFile('b.bin', { size: MAX_FILE_SIZE + 1 });
    expect(isValidFileSize(atLimit)).toBe(true);
    expect(isValidFileSize(overLimit)).toBe(false);
  });

  it('accepts a zero-byte file', () => {
    const empty = makeFile('empty.txt', { size: 0 });
    expect(isValidFileSize(empty)).toBe(true);
  });

  it('honours a custom max size argument', () => {
    const file = makeFile('small.bin', { size: 1024 });
    expect(isValidFileSize(file, 512)).toBe(false);
    expect(isValidFileSize(file, 2048)).toBe(true);
  });
});

describe('validateFiles', () => {
  it('returns empty result buckets for an empty input list', () => {
    const result = validateFiles([], ['image/*']);
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([]);
    expect(result.errors).toEqual([]);
  });

  it('partitions valid and invalid files by type', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const txt = makeFile('notes.txt', { type: 'text/plain', size: 10 });
    const result = validateFiles([png, txt], ['image/*']);

    expect(result.valid).toEqual([png]);
    expect(result.invalid).toEqual([txt]);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0]).toContain('notes.txt');
    expect(result.errors[0]).toContain('text/plain');
  });

  it('reports an unknown-type label when the MIME type is empty', () => {
    const noType = makeFile('mystery.dat', { type: '', size: 10 });
    const result = validateFiles([noType], ['image/*']);
    expect(result.invalid).toEqual([noType]);
    expect(result.errors[0]).toContain('未知类型');
  });

  it('rejects an oversized file even when its type is accepted', () => {
    const bigImage = makeFile('huge.png', { type: 'image/png', size: MAX_FILE_SIZE + 1 });
    const result = validateFiles([bigImage], ['image/*']);

    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([bigImage]);
    expect(result.errors[0]).toContain('huge.png');
    expect(result.errors[0]).toContain('文件大小超过限制');
  });

  it('checks type before size so a wrong-type oversized file reports a type error', () => {
    const bad = makeFile('huge.txt', { type: 'text/plain', size: MAX_FILE_SIZE + 1 });
    const result = validateFiles([bad], ['image/*']);
    expect(result.errors[0]).toContain('不支持的文件类型');
    expect(result.errors[0]).not.toContain('文件大小超过限制');
  });

  it('honours a custom max size for size validation', () => {
    const file = makeFile('photo.png', { type: 'image/png', size: 1024 });
    const result = validateFiles([file], ['image/*'], 512);
    expect(result.invalid).toEqual([file]);
    expect(result.errors[0]).toContain('文件大小超过限制');
  });

  it('rejects all files when the accepted list is empty', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const result = validateFiles([png], []);
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([png]);
    expect(result.errors).toHaveLength(1);
  });
});

describe('validateFilesForMode', () => {
  it('uses the mode accepted types to validate (rejects non-image in image-gen)', () => {
    const txt = makeFile('notes.txt', { type: 'text/plain', size: 10 });
    const result = validateFilesForMode([txt], 'image-gen');
    expect(result.invalid).toEqual([txt]);
    expect(result.valid).toEqual([]);
  });

  it('accepts a valid image in image-gen mode', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const result = validateFilesForMode([png], 'image-gen');
    expect(result.valid).toEqual([png]);
    expect(result.invalid).toEqual([]);
    expect(result.errors).toEqual([]);
  });

  it('rejects all new files in image-outpainting when an attachment already exists', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const result = validateFilesForMode([png], 'image-outpainting', 1);
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([png]);
    expect(result.errors[0]).toContain('扩图模式只支持一张图片');
  });

  it('keeps only the first file in image-outpainting when several are provided', () => {
    const first = makeFile('a.png', { type: 'image/png', size: 10 });
    const second = makeFile('b.png', { type: 'image/png', size: 10 });
    const third = makeFile('c.png', { type: 'image/png', size: 10 });
    const result = validateFilesForMode([first, second, third], 'image-outpainting', 0);

    expect(result.valid).toEqual([first]);
    expect(result.invalid).toEqual([second, third]);
    expect(result.errors[0]).toContain('已自动选择第一张');
  });

  it('validates a single image-outpainting file through the normal type/size checks', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const result = validateFilesForMode([png], 'image-outpainting', 0);
    expect(result.valid).toEqual([png]);
    expect(result.invalid).toEqual([]);
    expect(result.errors).toEqual([]);
  });

  it('rejects everything for a no-attachment mode such as audio-gen', () => {
    const png = makeFile('photo.png', { type: 'image/png', size: 10 });
    const result = validateFilesForMode([png], 'audio-gen');
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([png]);
    expect(result.errors).toHaveLength(1);
  });

  it('returns an empty result for an empty file list', () => {
    const result = validateFilesForMode([], 'chat');
    expect(result.valid).toEqual([]);
    expect(result.invalid).toEqual([]);
    expect(result.errors).toEqual([]);
  });
});
