// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceTagViews } from './WorkspaceTagViews';

describe('WorkspaceTagViews', () => {
  afterEach(cleanup);

  it('renders open modes as switchable tags using mode catalog labels', () => {
    const onSelectMode = vi.fn();

    render(
      <WorkspaceTagViews
        activeMode="chat"
        openModes={['chat', 'image-gen']}
        modeCatalog={[
          {
            id: 'chat',
            label: 'Chat',
            description: 'chat mode',
            group: 'core',
            hasModels: true,
            availableModelCount: 1,
          },
          {
            id: 'image-gen',
            label: 'Image',
            description: 'image mode',
            group: 'creative',
            hasModels: true,
            availableModelCount: 1,
          },
        ]}
        onSelectMode={onSelectMode}
        onCloseMode={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('tab', { name: /Image/ }));
    expect(onSelectMode).toHaveBeenCalledWith('image-gen');
  });

  it('allows closing inactive tags but keeps the last remaining tag open', () => {
    const onCloseMode = vi.fn();

    const { rerender } = render(
      <WorkspaceTagViews
        activeMode="chat"
        openModes={['chat', 'image-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={onCloseMode}
      />
    );

    fireEvent.click(screen.getByLabelText('关闭 Image Gen'));
    expect(onCloseMode).toHaveBeenCalledWith('image-gen');

    onCloseMode.mockClear();
    rerender(
      <WorkspaceTagViews
        activeMode="chat"
        openModes={['chat']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={onCloseMode}
      />
    );

    expect(screen.queryByLabelText('关闭 Chat')).toBeNull();
  });

  it('renders dark active tag styling instead of the default white tab surface', () => {
    render(
      <WorkspaceTagViews
        activeMode="image-gen"
        openModes={['chat', 'image-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
      />
    );

    const activeTag = screen.getByTestId('workspace-tag-image-gen');
    expect(activeTag.className).toContain('bg-slate-800');
    expect(activeTag.className).toContain('text-slate-100');
  });

  it('supports pinning and unpinning a tag from its action menu', () => {
    render(
      <WorkspaceTagViews
        activeMode="image-gen"
        openModes={['chat', 'image-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
      />
    );

    expect(screen.queryByLabelText('打开 Image Gen 选项卡菜单')).toBeNull();

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-image-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '固定选项卡' }));

    expect(screen.getByText('📌')).not.toBeNull();
    expect(screen.getByLabelText('Image Gen 已固定')).not.toBeNull();
    expect(screen.queryByLabelText('关闭 Image Gen')).toBeNull();

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-image-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '取消固定选项卡' }));

    expect(screen.queryByText('📌')).toBeNull();
    expect(screen.queryByLabelText('Image Gen 已固定')).toBeNull();
    expect(screen.getByLabelText('关闭 Image Gen')).not.toBeNull();
  });

  it('keeps the original tag order when a tag is pinned', () => {
    render(
      <WorkspaceTagViews
        activeMode="video-gen"
        openModes={['chat', 'image-gen', 'video-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
      />
    );

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-image-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '固定选项卡' }));

    const tagList = screen.getByRole('tablist', { name: '工作区选项卡' });
    const tagOrder = Array.from(
      tagList.querySelectorAll('[data-testid^="workspace-tag-"]')
    ).map((node) => node.getAttribute('data-testid'));

    expect(tagOrder).toEqual([
      'workspace-tag-chat',
      'workspace-tag-image-gen',
      'workspace-tag-video-gen',
    ]);
  });

  it('closes left, right, and other unpinned tags through the action menu', () => {
    const onCloseModes = vi.fn();

    render(
      <WorkspaceTagViews
        activeMode="video-gen"
        openModes={['chat', 'image-gen', 'video-gen', 'audio-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
        onCloseModes={onCloseModes}
      />
    );

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-video-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '关闭左侧' }));
    expect(onCloseModes).toHaveBeenLastCalledWith(['chat', 'image-gen']);

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-video-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '关闭右侧' }));
    expect(onCloseModes).toHaveBeenLastCalledWith(['audio-gen']);

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-video-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '关闭其他' }));
    expect(onCloseModes).toHaveBeenLastCalledWith(['chat', 'image-gen', 'audio-gen']);
  });

  it('keeps pinned tags when closing other tags', () => {
    const onCloseModes = vi.fn();

    render(
      <WorkspaceTagViews
        activeMode="video-gen"
        openModes={['chat', 'image-gen', 'video-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
        onCloseModes={onCloseModes}
      />
    );

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-image-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '固定选项卡' }));

    fireEvent.contextMenu(screen.getByTestId('workspace-tag-video-gen'));
    fireEvent.click(screen.getByRole('menuitem', { name: '关闭其他' }));

    expect(onCloseModes).toHaveBeenCalledWith(['chat']);
  });

  it('reloads the active tab from the right-side toolbar button', () => {
    const onReloadMode = vi.fn();

    render(
      <WorkspaceTagViews
        activeMode="image-gen"
        openModes={['chat', 'image-gen']}
        modeCatalog={[]}
        onSelectMode={vi.fn()}
        onCloseMode={vi.fn()}
        onReloadMode={onReloadMode}
      />
    );

    fireEvent.click(screen.getByLabelText('重载当前选项卡'));

    expect(onReloadMode).toHaveBeenCalledWith('image-gen');
  });
});
