// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AppMode, Message, ModelConfig, Persona, Role } from '../../types/types';
import { resetModeMessages, setModeMessages } from '../../hooks/modeMessageStore';
import { StudioView } from './StudioView';

const { renderCounts } = vi.hoisted(() => ({
  renderCounts: {
    imageGen: 0,
    videoGen: 0,
  },
}));

vi.mock('./ImageGenView', async () => {
  const ReactModule = await import('react');

  return {
    ImageGenView: ({ messages }: { messages: Message[] }) => {
      renderCounts.imageGen += 1;

      return ReactModule.createElement(
        'div',
        { 'data-testid': 'image-gen-view', 'data-message-count': messages.length },
        'image-gen-view'
      );
    },
  };
});

vi.mock('./VideoGenView', async () => {
  const ReactModule = await import('react');

  return {
    VideoGenView: ({ messages }: { messages: Message[] }) => {
      renderCounts.videoGen += 1;

      return ReactModule.createElement(
        'div',
        { 'data-testid': 'video-gen-view', 'data-message-count': messages.length },
        'video-gen-view'
      );
    },
  };
});

const message = (id: string, mode: AppMode): Message => ({
  id,
  role: Role.MODEL,
  content: id,
  timestamp: 1,
  mode,
});

const noop = () => {};
const sendNoop = () => {};
const submitResearchNoop = async () => {};
const EMPTY_MODELS: ModelConfig[] = [];
const EMPTY_PERSONAS: Persona[] = [];

const renderStudioView = (mode: AppMode) => (
  <StudioView
    mode={mode}
    setAppMode={noop}
    onImageClick={noop}
    loadingState="idle"
    onSend={sendNoop}
    onStop={noop}
    activeModelConfig={undefined}
    onModelSelect={noop}
    visibleModels={EMPTY_MODELS}
    allVisibleModels={EMPTY_MODELS}
    onEditImage={noop}
    onExpandImage={noop}
    providerId="google"
    sessionId="session-1"
    onDeleteMessage={noop}
    apiKey="test-api-key"
    onSubmitResearchAction={submitResearchNoop}
    personas={EMPTY_PERSONAS}
    activePersonaId={undefined}
    onSelectPersona={noop}
  />
);

describe('StudioView keep-alive message partitioning', () => {
  beforeEach(() => {
    resetModeMessages();
    renderCounts.imageGen = 0;
    renderCounts.videoGen = 0;
  });

  afterEach(() => {
    cleanup();
    resetModeMessages();
  });

  it('does not re-render a hidden mode when another mode receives a new message', async () => {
    const firstImageMessage = message('first-image-message', 'image-gen');
    const secondImageMessage = message('second-image-message', 'image-gen');
    const firstVideoMessage = message('first-video-message', 'video-gen');
    const secondVideoMessage = message('second-video-message', 'video-gen');

    const imageMessages = [firstImageMessage];
    const nextImageMessages = [firstImageMessage, secondImageMessage];
    const videoMessages = [firstVideoMessage];
    const nextVideoMessages = [firstVideoMessage, secondVideoMessage];

    act(() => {
      setModeMessages('image-gen', imageMessages);
      setModeMessages('video-gen', videoMessages);
    });

    const { rerender } = render(renderStudioView('image-gen'));

    await screen.findByTestId('image-gen-view');

    rerender(renderStudioView('video-gen'));
    await screen.findByTestId('video-gen-view');

    rerender(renderStudioView('image-gen'));
    await waitFor(() => expect(screen.getByTestId('image-gen-view')).toBeTruthy());
    const videoRenderCountBeforeImageUpdate = renderCounts.videoGen;

    act(() => {
      setModeMessages('image-gen', nextImageMessages);
    });

    await waitFor(() =>
      expect(screen.getByTestId('image-gen-view').getAttribute('data-message-count')).toBe('2')
    );
    expect(renderCounts.videoGen).toBe(videoRenderCountBeforeImageUpdate);

    act(() => {
      setModeMessages('video-gen', nextVideoMessages);
    });

    await waitFor(() =>
      expect(screen.getByTestId('video-gen-view').getAttribute('data-message-count')).toBe('2')
    );
    expect(renderCounts.videoGen).toBeGreaterThan(videoRenderCountBeforeImageUpdate);
  });
});
