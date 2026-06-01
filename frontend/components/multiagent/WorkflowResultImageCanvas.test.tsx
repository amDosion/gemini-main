// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source: _source, ...props }: any) => (
    <img src={src} alt={alt} {...props} />
  ),
}));

import { WorkflowResultImageCanvas } from './WorkflowResultImageCanvas';

describe('WorkflowResultImageCanvas', () => {
  afterEach(() => {
    cleanup();
  });

  it('shows media images as cards and opens the shared carousel from a card', () => {
    render(
      <WorkflowResultImageCanvas
        open
        title="全部媒体图片"
        imageUrls={[
          'https://cdn.example.com/workflow/one.png',
          'https://cdn.example.com/workflow/two.png',
        ]}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('全部媒体图片')).toBeInTheDocument();
    expect(screen.getByText('2 张')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开第 2 张媒体图片' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开第 2 张媒体图片' }));

    expect(screen.getAllByText('2 / 2').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByAltText('工作流结果图片 2')).toHaveAttribute(
      'src',
      'https://cdn.example.com/workflow/two.png'
    );

    fireEvent.click(screen.getByRole('button', { name: '返回图片卡片' }));
    expect(screen.getByText('2 张')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开第 1 张媒体图片' })).toBeInTheDocument();
  });

  it('renders paginated lazy cards and delegates page changes', () => {
    const onPageChange = vi.fn();

    render(
      <WorkflowResultImageCanvas
        open
        title="全部媒体图片"
        imageUrls={[]}
        imageCards={[
          {
            id: 'workflow-history-image-loaded',
            title: '已加载图片',
            imageUrl: 'https://cdn.example.com/workflow/loaded.png',
            indexLabel: '24/25',
          },
          {
            id: 'workflow-history-image-loading',
            title: '加载中的图片',
            loadState: 'loading',
            indexLabel: '25/25',
          },
        ]}
        totalCount={25}
        page={2}
        totalPages={3}
        onPageChange={onPageChange}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('25 张')).toBeInTheDocument();
    expect(screen.getByText('第 2 / 3 页')).toBeInTheDocument();
    expect(screen.getByText('加载中')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    expect(onPageChange).toHaveBeenCalledWith(3);

    fireEvent.click(screen.getByRole('button', { name: '上一页' }));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});
