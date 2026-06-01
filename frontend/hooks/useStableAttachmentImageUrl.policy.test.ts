import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const VIEW_DIR = path.join('frontend', 'components', 'views');

const isSourceViewFile = (filePath: string): boolean =>
  filePath.endsWith('.tsx') &&
  !filePath.endsWith('.test.tsx') &&
  !filePath.includes(`${path.sep}node_modules${path.sep}`);

const walkFiles = (dir: string): string[] => {
  if (!fs.existsSync(dir)) return [];
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
    } else if (entry.isFile() && isSourceViewFile(fullPath)) {
      files.push(fullPath);
    }
  }
  return files;
};

const findHookCallBlocks = (source: string): Array<{ startLine: number; block: string }> => {
  const calls: Array<{ startLine: number; block: string }> = [];
  let searchIndex = 0;
  const needle = 'useStableAttachmentImageUrl(';

  while (searchIndex < source.length) {
    const start = source.indexOf(needle, searchIndex);
    if (start < 0) break;

    let depth = 0;
    let end = start;
    for (; end < source.length; end += 1) {
      const char = source[end];
      if (char === '(') depth += 1;
      if (char === ')') {
        depth -= 1;
        if (depth === 0) {
          end += 1;
          break;
        }
      }
    }

    const block = source.slice(start, end);
    const startLine = source.slice(0, start).split(/\r?\n/).length;
    calls.push({ startLine, block });
    searchIndex = end;
  }

  return calls;
};

describe('useStableAttachmentImageUrl production call policy', () => {
  it('requires views to explicitly opt in or out of file object url creation', () => {
    const violations = walkFiles(path.resolve(process.cwd(), VIEW_DIR)).flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);
      const source = fs.readFileSync(filePath, 'utf8');
      return findHookCallBlocks(source)
        .filter(({ block }) => !block.includes('createFileObjectUrls:'))
        .map(({ startLine }) => `${relativePath}:${startLine}`);
    });

    expect(violations).toEqual([]);
  });
});
