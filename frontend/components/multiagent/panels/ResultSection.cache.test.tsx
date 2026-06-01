// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source, ...props }: any) => (
    <img
      data-testid="cached-workflow-result-image"
      data-source-url={source?.url || ''}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import { PropertiesPanelResultSection } from './ResultSection';

describe('PropertiesPanelResultSection image cache integration', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders source and result image previews through the shared cached image component', () => {
    render(
      <PropertiesPanelResultSection
        nodeData={{ result: { ok: true } } as any}
        selectedNodeId="node-cache"
        sourcePreviewUrl="/api/storage/local-files/workflow/source.png"
        resultPreviewUrls={[
          '/api/storage/local-files/workflow/result-1.png',
          '/api/storage/local-files/workflow/result-2.png',
        ]}
        resultPreviewAudioUrls={[]}
        resultPreviewVideoUrls={[]}
        resultPreviewText="done"
        status="completed"
      />
    );

    expect(screen.getByAltText('source-preview')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/source.png'
    );
    expect(screen.getByAltText('source-preview')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/source.png'
    );
    expect(screen.getByAltText('result-preview-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/result-1.png'
    );
    expect(screen.getByAltText('result-preview-2')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/result-2.png'
    );
  });
});
