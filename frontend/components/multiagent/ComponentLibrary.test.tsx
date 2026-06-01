// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ComponentLibrary } from './ComponentLibrary';

describe('ComponentLibrary', () => {
  afterEach(() => {
    cleanup();
  });

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

  it('does not expose the generic Agent node because concrete Agents are dragged from Agent Manager', () => {
    render(<ComponentLibrary />);

    expect(screen.queryByText('智能体')).not.toBeInTheDocument();
    expect(screen.getByText('工具')).toBeInTheDocument();
    expect(screen.getByText('人工审核')).toBeInTheDocument();
  });

  it('keeps structural nodes draggable from the component library', () => {
    const storedPayload = new Map<string, string>();
    const dataTransfer = {
      setData: vi.fn((type: string, value: string) => {
        storedPayload.set(type, value);
      }),
      effectAllowed: '',
    };

    render(<ComponentLibrary />);

    fireEvent.dragStart(screen.getByText('工具').closest('[draggable="true"]') as HTMLElement, {
      dataTransfer,
    });

    expect(storedPayload.get('application/reactflow')).toBe('tool');
    expect(dataTransfer.effectAllowed).toBe('move');
  });
});
