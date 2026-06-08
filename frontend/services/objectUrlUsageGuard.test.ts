import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const FRONTEND_DIR = path.resolve(process.cwd(), 'frontend');
const ALLOWED_DIRECT_OBJECT_URL_FILES = new Set([
  path.join('frontend', 'services', 'mediaCache.ts'),
  // services-11: object-URL lifecycle extracted into this mediaCache sibling.
  path.join('frontend', 'services', 'mediaCacheObjectUrls.ts'),
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
  return (
    !filePath.includes(`${path.sep}node_modules${path.sep}`) &&
    !filePath.endsWith('.test.ts') &&
    !filePath.endsWith('.test.tsx')
  );
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

// Walk + read every source file ONCE; all four guards scan this shared snapshot
// instead of re-walking and re-reading the whole frontend/ tree four times. This
// keeps the checks deterministic (one snapshot) and fast enough to never trip the
// test timeout under parallel test-suite I/O.
const SOURCE_FILES: ReadonlyArray<{ relativePath: string; lines: readonly string[] }> = walkFiles(
  FRONTEND_DIR
).map((filePath) => ({
  relativePath: path.relative(process.cwd(), filePath),
  lines: fs.readFileSync(filePath, 'utf8').split(/\r?\n/),
}));

const findViolations = (
  matches: (sourceLine: string) => boolean,
  isAllowed: (relativePath: string) => boolean
): string[] =>
  SOURCE_FILES.flatMap(({ relativePath, lines }) =>
    isAllowed(relativePath)
      ? []
      : lines.flatMap((line, index) =>
          matches(stripLineComment(line)) ? [`${relativePath}:${index + 1}: ${line.trim()}`] : []
        )
  );

describe('object URL lifecycle guard', () => {
  it('keeps direct object URL browser APIs inside the shared media cache lifecycle', () => {
    const violations = findViolations(
      (sourceLine) =>
        sourceLine.includes('URL.createObjectURL') || sourceLine.includes('URL.revokeObjectURL'),
      (relativePath) => ALLOWED_DIRECT_OBJECT_URL_FILES.has(relativePath)
    );

    expect(violations).toEqual([]);
  });

  it('keeps synchronous media object URL reads inside shared cache loaders', () => {
    const violations = findViolations(
      (sourceLine) => sourceLine.includes('getCachedMediaObjectUrlSync'),
      (relativePath) => ALLOWED_SYNC_MEDIA_CACHE_READ_FILES.has(relativePath)
    );

    expect(violations).toEqual([]);
  });

  it('keeps synchronous preview object URL reads inside the preview cache module', () => {
    const violations = findViolations(
      (sourceLine) => sourceLine.includes('getCachedPreviewObjectUrlSync'),
      (relativePath) => ALLOWED_SYNC_PREVIEW_CACHE_READ_FILES.has(relativePath)
    );

    expect(violations).toEqual([]);
  });

  it('requires runtime preview cache callers to opt out of memory object urls', () => {
    const violations = findViolations(
      (sourceLine) => sourceLine.includes('getCachedPreviewObjectUrl('),
      (relativePath) => ALLOWED_MEMORY_PREVIEW_CACHE_CALL_FILES.has(relativePath)
    );

    expect(violations).toEqual([]);
  });
});
