// @vitest-environment jsdom
import React from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const chatControlsRenderSpy = vi.hoisted(() => vi.fn());

vi.mock('../../controls/modes', () => ({
  ChatControls: (props: unknown) => {
    chatControlsRenderSpy(props);
    return <div data-testid="chat-controls" />;
  },
}));

import ChatInputArea from './ChatInputArea';
import type { ChatOptions, ModelConfig } from '../../types/types';

const model: ModelConfig = {
  id: 'gemini-2.5-flash',
  name: 'Gemini 2.5 Flash',
  description: '',
  capabilities: {
    vision: true,
    search: true,
    reasoning: true,
    coding: true,
  },
};

const stableProps = {
  onSend: vi.fn(
    (_text: string, _options: ChatOptions, _attachments: unknown[], _mode: string) => undefined
  ),
  onStop: vi.fn(),
  isLoading: true,
  currentModel: model,
  visibleModels: [model],
  mode: 'chat' as const,
  providerId: 'google',
  personas: [],
  activePersonaId: '',
  onSelectPersona: vi.fn(),
  temperature: 0.7,
  maxTokens: 8192,
  topP: 0.95,
  topK: 40,
};

describe('ChatInputArea memoization', () => {
  beforeEach(() => {
    chatControlsRenderSpy.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('does not re-render its toolbar when the parent re-renders with identical prop references', () => {
    const { rerender } = render(<ChatInputArea {...stableProps} />);

    expect(chatControlsRenderSpy).toHaveBeenCalledTimes(1);

    rerender(<ChatInputArea {...stableProps} />);

    expect(chatControlsRenderSpy).toHaveBeenCalledTimes(1);
  });
});
