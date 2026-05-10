// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ModelSelectionPanel, getModelUsage } from './ModelSelectionPanel';

describe('ModelSelectionPanel', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders selected state, usage, and capability icons in one horizontal row without orange unselected styling', () => {
    const onToggleModel = vi.fn();

    render(
      <ModelSelectionPanel
        models={[
          {
            id: 'veo-3.1-generate-001',
            name: 'Veo 3.1',
            description: 'Generic Google model',
            capabilities: { vision: false, search: false, reasoning: false, coding: false },
          },
          {
            id: 'gemini-2.5-flash',
            name: 'Gemini 2.5 Flash',
            capabilities: { vision: true, search: true, reasoning: true, coding: false },
          },
        ]}
        selectedModelIds={new Set(['veo-3.1-generate-001'])}
        onToggleModel={onToggleModel}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        testIdPrefix="shared"
      />
    );

    const selectedCard = screen.getByTestId('shared-card-veo-3.1-generate-001');
    const unselectedCard = screen.getByTestId('shared-card-gemini-2.5-flash');
    const unselectedMeta = screen.getByTestId('shared-meta-gemini-2.5-flash');

    expect(within(selectedCard).getByText('视频生成')).toBeTruthy();
    expect(within(unselectedMeta).getByText('对话 / 推理 / 检索')).toBeTruthy();
    expect(within(unselectedMeta).getByText('未选择')).toBeTruthy();
    expect(within(unselectedMeta).getByTitle('Vision')).toBeTruthy();
    expect(within(unselectedMeta).getByTitle('Search')).toBeTruthy();
    expect(within(unselectedMeta).getByTitle('Reasoning')).toBeTruthy();
    expect(unselectedMeta.className).toContain('flex');
    expect(unselectedMeta.className).toContain('items-center');
    expect(unselectedCard.className).not.toContain('amber');
    expect(unselectedCard.className).not.toContain('opacity-60');

    fireEvent.click(unselectedCard);
    expect(onToggleModel).toHaveBeenCalledWith('gemini-2.5-flash');
  });

  it('maps model ids to concrete usage labels', () => {
    expect(getModelUsage({ id: 'imagen-4.0-upscale-preview', name: 'upscale' })).toBe('图片放大');
    expect(getModelUsage({ id: 'image-segmentation-001', name: 'segmentation' })).toBe('图像分割');
    expect(getModelUsage({ id: 'virtual-try-on-001', name: 'try-on' })).toBe('虚拟试衣');
    expect(getModelUsage({ id: 'gemini-2.5-flash-image', name: 'Gemini 2.5 Flash Image' })).toBe('图片生成 / 编辑');
  });
});
