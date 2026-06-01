import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const COMPONENT_DIRS = [
  path.join('frontend', 'components', 'common'),
  path.join('frontend', 'components', 'views'),
  path.join('frontend', 'components', 'multiagent'),
  path.join('frontend', 'components', 'message'),
  path.join('frontend', 'components', 'chat'),
];

const ALLOWED_IMAGE_RENDER_FILES = new Set([
  path.join('frontend', 'components', 'common', 'CachedImage.tsx'),
  path.join('frontend', 'components', 'common', 'RetainedImage.tsx'),
]);

const isSourceFile = (filePath: string): boolean =>
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

describe('image render boundary guard', () => {
  it('keeps raw img elements behind approved image lifecycle components', () => {
    const componentFiles = COMPONENT_DIRS.flatMap((dir) =>
      walkFiles(path.resolve(process.cwd(), dir))
    );

    const violations = componentFiles.flatMap((filePath) => {
      const relativePath = path.relative(process.cwd(), filePath);
      if (ALLOWED_IMAGE_RENDER_FILES.has(relativePath)) return [];

      return fs
        .readFileSync(filePath, 'utf8')
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const sourceLine = stripLineComment(line);
          if (!sourceLine.includes('<img')) return [];
          return [`${relativePath}:${index + 1}: ${line.trim()}`];
        });
    });

    expect(violations).toEqual([]);
  });
});
