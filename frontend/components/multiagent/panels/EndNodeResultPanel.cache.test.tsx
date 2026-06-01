// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source, ...props }: any) => (
    <img
      data-testid="cached-end-result-image"
      data-source-url={source?.url || ''}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import { EndNodeResultPanel } from './EndNodeResultPanel';

describe('EndNodeResultPanel image cache integration', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders final result image previews through the shared cached image component', () => {
    render(
      <EndNodeResultPanel
        nodeData={{ result: { images: ['done'] } } as any}
        selectedNodeId="end-cache"
        status="completed"
        resultPreviewUrls={[
          '/api/storage/local-files/workflow/end-1.png',
          '/api/storage/local-files/workflow/end-2.png',
        ]}
        resultPreviewVideoUrls={[]}
        resultPreviewAudioUrls={[]}
        resultPreviewText=""
      />
    );

    expect(screen.getByAltText('end-result-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/end-1.png'
    );
    expect(screen.getByAltText('end-result-1')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/end-1.png'
    );
    expect(screen.getByAltText('end-result-2')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/end-2.png'
    );
  });
});
