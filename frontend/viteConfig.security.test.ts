import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  resolveAllowedHosts,
  resolveDevCorsOrigins,
  resolveManualChunk,
  shouldEmitBuildSourcemap,
} from '../vite.config';

describe('Vite build security defaults', () => {
  it('keeps production source maps disabled unless explicitly enabled', () => {
    expect(shouldEmitBuildSourcemap(undefined)).toBe(false);
    expect(shouldEmitBuildSourcemap('')).toBe(false);
    expect(shouldEmitBuildSourcemap('true')).toBe(false);
    expect(shouldEmitBuildSourcemap('0')).toBe(false);
    expect(shouldEmitBuildSourcemap('1')).toBe(true);
  });
});

describe('Vite dev server security defaults', () => {
  it('rejects wildcard allowedHosts entries', () => {
    expect(resolveAllowedHosts('*, app.example.com')).toEqual(['app.example.com']);
    expect(resolveAllowedHosts('*')).toEqual([
      'gemini.lspon.com',
      'geminiai.lspon.com',
      'gemini.dicry.cn',
    ]);
  });

  it('rejects wildcard and non-origin CORS values', () => {
    expect(resolveDevCorsOrigins('*, https://app.example.com, javascript:alert(1)')).toEqual([
      'https://app.example.com',
    ]);
    expect(resolveDevCorsOrigins('*')).toEqual([
      'http://localhost:21573',
      'http://127.0.0.1:21573',
    ]);
  });
});

describe('HTML shell security defaults', () => {
  it('does not load production dependencies from remote import maps', () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf-8');

    expect(html).not.toContain('type="importmap"');
    expect(html).not.toContain('aistudiocdn.com');
    expect(html).not.toMatch(/https:\/\/[^"']+/);
  });
});

describe('Vite build chunking', () => {
  it('keeps syntax highlighting dependencies out of the eager markdown vendor chunk', () => {
    expect(
      resolveManualChunk('/repo/node_modules/react-syntax-highlighter/dist/esm/index.js')
    ).toBe('syntax-vendor');
    expect(resolveManualChunk('/repo/node_modules/refractor/core.js')).toBe('syntax-vendor');
    expect(resolveManualChunk('/repo/node_modules/react-markdown/index.js')).toBe(
      'markdown-vendor'
    );
  });

  it('keeps Ant Design and rc ecosystem code out of the app entry chunk', () => {
    expect(resolveManualChunk('/repo/node_modules/antd/es/layout/index.js')).toBe(
      'antd-vendor'
    );
    expect(resolveManualChunk('/repo/node_modules/@ant-design/cssinjs/es/index.js')).toBe(
      'antd-vendor'
    );
    expect(resolveManualChunk('/repo/node_modules/@rc-component/trigger/es/index.js')).toBe(
      'antd-vendor'
    );
    expect(resolveManualChunk('/repo/node_modules/rc-select/es/index.js')).toBe(
      'antd-vendor'
    );
  });
});
