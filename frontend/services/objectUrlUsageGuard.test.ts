import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const FRONTEND_DIR = path.resolve(process.cwd(), 'frontend');
const ALLOWED_DIRECT_OBJECT_URL_FILES = new Set([
  path.join('frontend', 'services', 'mediaCache.ts'),
]);
const ALLOWED_SYNC_MEDIA_CACHE_READ_FILES = new Set([
  path.join('frontend', 'hooks', 'useCachedImageSrc.ts'),
  path.join('frontend', 'services', 'mediaCache.ts'),
  path.join('frontend', 'services', 'previewCache.ts'),
]);
const ALLOWED_SYNC_PREVIEW_CACHE_READ_FILES = new Set([
  path.join('frontend', 'services', 'previewCache.ts'),
]);
const ALLOWED_MEMORY_PREVIEW_CACHE_CALL_FILES = new Set([
  path.join('frontend', 'services', 'previewCache.ts'),
  path.join('frontend', 'components', 'views', 'cloudStorage', 'useXhrImagePreview.ts'),
]);

const SOURCE_EXTENSIONS = new Set(['.ts', '.tsx']);

const isSourceFile = (filePath: string): boolean => {
  const extension = path.extname(filePath);
  if (!SOURCE_EXTENSIONS.has(extension)) return false;
  return !filePath.includes(`${path.sep}node_modules${path.sep}`) &&
    !filePath.endsWith('.test.ts') &&
    !filePath.endsWith('.test.tsx');
};

const walkFiles = (dir: string): string[] => {
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
    } else if (entry.isFile() && isSourceFile(fullPath)) {
      files.push(fullPath);
    }
  }
  return files;
};

const stripLineComment = (line: string): string => {
  const trimmed = line.trim();
  if (trimmed.startsWith('//') || trimmed.startsWith('*')) return '';
  return line;
};

describe('object URL lifecycle guard', () => {
  it('keeps direct object URL browser APIs inside the shared media cache lifecycle', () => {
    const violations = walkFiles(FRONTEND_DIR).flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);
      if (ALLOWED_DIRECT_OBJECT_URL_FILES.has(relativePath)) return [];

      return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const sourceLine = stripLineComment(line);
          if (
            !sourceLine.includes('URL.createObjectURL') &&
            !sourceLine.includes('URL.revokeObjectURL')
          ) {
            return [];
          }
          return [`${relativePath}:${index + 1}: ${line.trim()}`];
        });
    });

    expect(violations).toEqual([]);
  });

  it('keeps synchronous media object URL reads inside shared cache loaders', () => {
    const violations = walkFiles(FRONTEND_DIR).flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);
      if (ALLOWED_SYNC_MEDIA_CACHE_READ_FILES.has(relativePath)) return [];

      return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const sourceLine = stripLineComment(line);
          if (!sourceLine.includes('getCachedMediaObjectUrlSync')) {
            return [];
          }
          return [`${relativePath}:${index + 1}: ${line.trim()}`];
        });
    });

    expect(violations).toEqual([]);
  });

  it('keeps synchronous preview object URL reads inside the preview cache module', () => {
    const violations = walkFiles(FRONTEND_DIR).flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);
      if (ALLOWED_SYNC_PREVIEW_CACHE_READ_FILES.has(relativePath)) return [];

      return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const sourceLine = stripLineComment(line);
          if (!sourceLine.includes('getCachedPreviewObjectUrlSync')) {
            return [];
          }
          return [`${relativePath}:${index + 1}: ${line.trim()}`];
        });
    });

    expect(violations).toEqual([]);
  });

  it('requires runtime preview cache callers to opt out of memory object urls', () => {
    const violations = walkFiles(FRONTEND_DIR).flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);

      return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const sourceLine = stripLineComment(line);
          if (!sourceLine.includes('getCachedPreviewObjectUrl(')) return [];
          if (ALLOWED_MEMORY_PREVIEW_CACHE_CALL_FILES.has(relativePath)) return [];
          return [`${relativePath}:${index + 1}: ${line.trim()}`];
        });
    });

    expect(violations).toEqual([]);
  });
});
