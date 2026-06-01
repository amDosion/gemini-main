// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source, ...props }: any) => (
    <img
      data-testid="cached-start-input-image"
      data-source-url={source?.url || ''}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import { StartInputNodeConfigPanel } from './StartInputNodeConfigPanel';

describe('StartInputNodeConfigPanel media cache integration', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders start/input image url previews through the shared cached image component', () => {
    render(
      <StartInputNodeConfigPanel
        nodeData={{
          startImageUrl: '/api/storage/local-files/workflow/input-1.png',
          startImageUrls: [
            '/api/storage/local-files/workflow/input-1.png',
            '/api/storage/local-files/workflow/input-2.png',
          ],
        } as any}
        nodeType={'input_image' as any}
        selectedNode={{ id: 'input-image-node', data: {} } as any}
        updateNodeData={vi.fn()}
      />
    );

    expect(screen.getByAltText('输入图片-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/input-1.png'
    );
    expect(screen.getByAltText('输入图片-1')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/input-1.png'
    );
    expect(screen.getByAltText('输入图片-2')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/input-2.png'
    );
  });
});
