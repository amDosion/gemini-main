// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('@xyflow/react', () => ({
  Handle: () => <div data-testid="handle" />,
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  NodeResizeControl: () => null,
}));

vi.mock('../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source, ...props }: any) => (
    <img data-source-url={source?.url || ''} src={`cached:${src}`} alt={alt} {...props} />
  ),
}));

import { CustomNode } from './CustomNode';

describe('CustomNode media preview', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders audio and video previews inside result preview block', () => {
    render(
      <CustomNode
        id="node-media"
        type="custom"
        selected={false}
        positionAbsoluteX={0}
        positionAbsoluteY={0}
        zIndex={1}
        isConnectable
        draggable={false}
        selectable
        deletable
        dragging={false}
        data={{
          type: 'agent',
          label: 'Media Agent',
          description: 'media preview',
          icon: '🤖',
          iconColor: 'bg-teal-500',
          status: 'completed',
          result: {
            finalOutput: {
              text: '媒体完成',
              audioUrl: 'https://cdn.example.com/final.mp3',
              videoUrl: 'https://cdn.example.com/final.mp4',
            },
          },
        } as any}
      />,
    );

    expect(screen.getByText('输出预览')).toBeInTheDocument();
    expect(screen.getByText('视频 1 条')).toBeInTheDocument();
    expect(screen.getByText('音频 1 条')).toBeInTheDocument();
    expect(document.querySelector('video')).toBeTruthy();
    expect(document.querySelector('audio')).toBeTruthy();
  });

  it('emits a scoped gallery request when a result image thumbnail is clicked', () => {
    const listener = vi.fn();
    window.addEventListener('workflow:image-gallery-request', listener as EventListener);

    render(
      <div data-workflow-editor-scope="editor-gallery-test">
        <CustomNode
          id="node-image"
          type="custom"
          selected={false}
          positionAbsoluteX={0}
          positionAbsoluteY={0}
          zIndex={1}
          isConnectable
          draggable={false}
          selectable
          deletable
          dragging={false}
          data={{
            type: 'end',
            label: '结束',
            description: 'end node',
            icon: 'E',
            iconColor: 'bg-rose-500',
            status: 'completed',
            result: {
              finalOutput: {
                imageUrls: [
                  'https://cdn.example.com/final-1.png',
                  'https://cdn.example.com/final-2.png',
                ],
              },
            },
          } as any}
        />
      </div>
    );

    fireEvent.click(screen.getByRole('button', { name: '打开第 2 张输出图片' }));

    expect(listener).toHaveBeenCalledTimes(1);
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toMatchObject({
      editorScopeId: 'editor-gallery-test',
      nodeId: 'node-image',
      initialIndex: 1,
      title: '最终结果图片',
      imageUrls: [
        'https://cdn.example.com/final-1.png',
        'https://cdn.example.com/final-2.png',
      ],
    });

    window.removeEventListener('workflow:image-gallery-request', listener as EventListener);
  });

  it('renders workflow node image thumbnails through the shared cached image component', () => {
    render(
      <CustomNode
        id="node-cache"
        type="custom"
        selected={false}
        positionAbsoluteX={0}
        positionAbsoluteY={0}
        zIndex={1}
        isConnectable
        draggable={false}
        selectable
        deletable
        dragging={false}
        data={{
          type: 'agent',
          label: 'Cached Agent',
          description: 'cached image preview',
          icon: '🤖',
          iconColor: 'bg-teal-500',
          status: 'completed',
          agentReferenceImageUrl: '/api/storage/local-files/workflow/input.png',
          result: {
            imageUrls: ['/api/storage/local-files/workflow/output.png'],
          },
        } as any}
      />
    );

    expect(screen.getByAltText('node-input-image-node-cache-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/input.png'
    );
    expect(screen.getByAltText('node-input-image-node-cache-1')).not.toHaveAttribute('loading');
    expect(screen.getByAltText('node-result-image-node-cache-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/output.png'
    );
    expect(screen.getByAltText('node-result-image-node-cache-1')).not.toHaveAttribute('loading');
  });
});
