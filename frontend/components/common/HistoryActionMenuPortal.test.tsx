// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryActionMenuPortal } from './HistoryActionMenuPortal';

describe('HistoryActionMenuPortal', () => {
  it('does not close the action menu when the pointer enters the menu', () => {
    const closeHoverPreviewOnly = vi.fn();
    const closeHoverPreview = vi.fn();
    const closeActionMenu = vi.fn();

    render(
      <HistoryActionMenuPortal
        openActionMenu={{ messageId: 'message-1', anchorX: 10, anchorY: 10 }}
        actionMenuPosition={{ top: 10, left: 10 }}
        actionMenuPanelRef={{ current: null }}
        closeHoverPreviewOnly={closeHoverPreviewOnly}
        closeHoverPreview={closeHoverPreview}
        closeActionMenu={closeActionMenu}
        isFavorite={() => false}
        isFavoritePending={() => false}
        toggleFavorite={vi.fn()}
        deleteItem={vi.fn()}
        hoverPreviewMessageId={null}
      />
    );

    fireEvent.mouseEnter(screen.getByText('收藏').closest('[data-history-action-menu]')!);

    expect(closeHoverPreviewOnly).toHaveBeenCalledTimes(1);
    expect(closeActionMenu).not.toHaveBeenCalled();
    expect(closeHoverPreview).not.toHaveBeenCalled();
  });
});
