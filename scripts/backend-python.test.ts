import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  parseCliArgs,
  resolveBackendPython,
  resolveRunCwd,
} from './backend-python.mjs';

describe('backend-python runner', () => {
  it('prefers an explicit BACKEND_PYTHON override', () => {
    expect(
      resolveBackendPython({
        repoRoot: 'E:/repo',
        env: { BACKEND_PYTHON: 'C:/Python/python.exe' },
        exists: () => false,
        platform: 'win32',
      })
    ).toBe('C:/Python/python.exe');
  });

  it('selects the Windows virtualenv interpreter when present', () => {
    const repoRoot = resolve('E:/repo');
    const expectedPython = join(repoRoot, 'backend', '.venv', 'Scripts', 'python.exe');

    expect(
      resolveBackendPython({
        repoRoot,
        env: {},
        exists: (candidate) => candidate === expectedPython,
        platform: 'win32',
      })
    ).toBe(expectedPython);
  });

  it('falls back to a platform Python command when no virtualenv exists', () => {
    expect(
      resolveBackendPython({
        repoRoot: '/repo',
        env: {},
        exists: () => false,
        platform: 'linux',
      })
    ).toBe('python3');
  });

  it('parses backend cwd and env placeholders without shell syntax', () => {
    expect(
      parseCliArgs(
        [
          '--cwd',
          'backend',
          '--env-default',
          'BACKEND_COV_MIN=35',
          '--',
          '-m',
          'pytest',
          '--cov-fail-under={env:BACKEND_COV_MIN}',
        ],
        {}
      )
    ).toEqual({
      cwd: 'backend',
      pythonArgs: ['-m', 'pytest', '--cov-fail-under=35'],
    });
  });

  it('resolves supported cwd options under the repository root', () => {
    const repoRoot = resolve('E:/repo');

    expect(resolveRunCwd(repoRoot, 'root')).toBe(repoRoot);
    expect(resolveRunCwd(repoRoot, 'backend')).toBe(join(repoRoot, 'backend'));
  });
});
