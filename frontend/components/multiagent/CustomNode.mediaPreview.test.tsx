// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('reactflow', () => ({
  Handle: () => <div data-testid="handle" />,
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  NodeResizeControl: () => null,
}));

import { CustomNode } from './CustomNode';

describe('CustomNode media preview', () => {
  it('renders audio and video previews inside result preview block', () => {
    render(
      <CustomNode
        id="node-media"
        type="custom"
        selected={false}
        xPos={0}
        yPos={0}
        zIndex={1}
        isConnectable
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
});
