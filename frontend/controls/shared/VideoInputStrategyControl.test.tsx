// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { VideoInputStrategyControl } from './VideoInputStrategyControl';

describe('VideoInputStrategyControl', () => {
  it('localizes backend strategy labels before rendering options', () => {
    render(
      <VideoInputStrategyControl
        value="text_to_video"
        onChange={vi.fn()}
        strategies={[
          { id: 'text_to_video', label: 'Text to video', requires: [] },
          { id: 'image_to_video', label: 'Image to video', requires: ['source_image'] },
          {
            id: 'first_last_frame',
            label: 'First and last frame to video',
            requires: ['source_image', 'last_frame_image'],
          },
          { id: 'video_extension', label: 'Extend source video', requires: ['source_video'] },
          {
            id: 'masked_video_edit',
            label: 'Mask-based video edit',
            requires: ['source_video', 'video_mask_image'],
          },
        ]}
      />
    );

    expect(screen.getByRole('option', { name: '文生视频（无需素材）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '图生视频（首帧）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '首尾帧生视频（首帧 + 尾帧）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '视频延长（视频）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '遮罩视频编辑（视频 + 遮罩）' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Text to video/ })).not.toBeInTheDocument();
  });
});
