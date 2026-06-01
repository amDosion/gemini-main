// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { PromptEnhanceControl } from './PromptEnhanceControl';

describe('PromptEnhanceControl', () => {
  it('supports locked mandatory prompt enhancement without local duplicate switch markup', () => {
    const onEnabledChange = vi.fn();

    render(
      <PromptEnhanceControl
        enabled
        onEnabledChange={onEnabledChange}
        modelId=""
        onModelIdChange={vi.fn()}
        modelOptions={[]}
        allowAutoModel
        disabled
        disabledHint="当前模型必须启用 AI 增强提示词。"
      />
    );

    const toggle = screen.getByRole('switch', { name: 'AI 增强提示词' });
    expect(toggle).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByText('当前模型必须启用 AI 增强提示词。')).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(onEnabledChange).not.toHaveBeenCalled();
  });
});
