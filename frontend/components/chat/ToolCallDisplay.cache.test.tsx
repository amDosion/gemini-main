// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../common/CachedImage';
import ToolCallDisplay from './ToolCallDisplay';

const cachedImageSpy = vi.fn();

vi.mock('../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageSpy(props);
    return <img data-testid="tool-call-cached-image" src={props.src || ''} alt={props.alt || ''} />;
  },
}));

describe('ToolCallDisplay media cache integration', () => {
  afterEach(() => {
    cleanup();
    cachedImageSpy.mockClear();
  });

  it('renders screenshot urls through the shared cached image component', () => {
    render(
      <ToolCallDisplay
        toolCall={{
          type: 'function_call',
          name: 'capture_page',
          arguments: { url: 'https://example.com' },
          id: 'tool-call-1',
        }}
        toolResult={{
          name: 'capture_page',
          callId: 'tool-call-1',
          result: { ok: true },
          screenshotUrl: '/api/storage/local-files/tool-screenshots/result.png',
        }}
      />
    );

    expect(screen.getByTestId('tool-call-cached-image')).toHaveAttribute(
      'src',
      '/api/storage/local-files/tool-screenshots/result.png'
    );
    expect(cachedImageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        src: '/api/storage/local-files/tool-screenshots/result.png',
        source: expect.objectContaining({
          url: '/api/storage/local-files/tool-screenshots/result.png',
        }),
      })
    );
  });
});
