// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it } from 'vitest';
import { ComponentLibrary } from './ComponentLibrary';

describe('ComponentLibrary', () => {
  it('renders inline search controls and supports collapse/expand', () => {
    render(<ComponentLibrary />);

    expect(screen.getByText('组件库')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('搜索...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '收起组件库' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '收起组件库' }));

    expect(screen.queryByPlaceholderText('搜索...')).not.toBeInTheDocument();
    expect(screen.queryByText('拖拽节点到画布')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开组件库' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '展开组件库' }));

    expect(screen.getByPlaceholderText('搜索...')).toBeInTheDocument();
  });
});
