// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { Role } from '../../types/types';
import { AudioGenView } from './AudioGenView';

// Render layout slots inline so we can query the main stage directly.
vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebar, main }: { sidebar: React.ReactNode; main: React.ReactNode }) => (
    <div>
      <div data-testid="sidebar">{sidebar}</div>
      <div data-testid="main">{main}</div>
    </div>
  ),
}));

// RetainedAudio normally wraps blob-url retention logic. For this test we just
// need a real <audio> element so the forwarded ref is attached and the isolated
// AudioProgressDisplay can subscribe to its media events.
vi.mock('../common/RetainedMedia', () => ({
  RetainedAudio: React.forwardRef<HTMLAudioElement, { src?: string | null }>(({ src }, ref) => (
    <audio ref={ref} data-testid="audio-el" data-src={src ?? ''} />
  )),
}));

vi.mock('../chat/ChatEditInputArea', () => ({
  __esModule: true,
  default: () => <div data-testid="audio-input" />,
}));

vi.mock('../../coordinators/ModeControlsCoordinator', () => ({
  ModeControlsCoordinator: () => <div data-testid="audio-controls" />,
}));

const useControlsStateMock = vi.fn();
vi.mock('../../hooks/useControlsState', () => ({
  useControlsState: (...args: unknown[]) => useControlsStateMock(...args),
}));

const baseProps = {
  setAppMode: vi.fn(),
  onSend: vi.fn(),
  onStop: vi.fn(),
  activeModelConfig: { id: 'tts', name: 'TTS', provider: 'google' } as never,
  providerId: 'google',
};

const buildMessages = () =>
  [
    {
      id: 'u1',
      role: Role.USER,
      content: 'hello world',
      attachments: [],
    },
    {
      id: 'm1',
      role: Role.MODEL,
      content: '',
      attachments: [
        {
          id: 'a1',
          url: 'blob:audio-1',
          name: 'speech.wav',
          mimeType: 'audio/wav',
        },
      ],
    },
  ] as never;

describe('AudioGenView progress isolation', () => {
  beforeEach(() => {
    useControlsStateMock.mockReturnValue({ voice: 'Puck', setVoice: vi.fn() });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderView = () =>
    render(<AudioGenView {...baseProps} messages={buildMessages()} loadingState="idle" />);

  it('drives progress UI from the audio element media events', () => {
    renderView();

    const audio = screen.getByTestId('audio-el') as HTMLAudioElement;

    // Simulate metadata + timeupdate the way the browser would.
    Object.defineProperty(audio, 'duration', { configurable: true, value: 10 });
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 3 });

    act(() => {
      fireEvent.loadedMetadata(audio);
      fireEvent.timeUpdate(audio);
    });

    // The isolated AudioProgressDisplay renders "3s / 10s" and "30%".
    expect(screen.getByText('3s / 10s')).toBeInTheDocument();
    expect(screen.getByText('30%')).toBeInTheDocument();
  });

  it('hides the progress readout until a duration is known', () => {
    renderView();

    // Before any loadedmetadata event, duration is 0 so the readout is absent.
    expect(screen.queryByText(/\d+s \/ \d+s/)).not.toBeInTheDocument();
  });

  it('resets progress to zero when playback ends', () => {
    renderView();

    const audio = screen.getByTestId('audio-el') as HTMLAudioElement;
    Object.defineProperty(audio, 'duration', { configurable: true, value: 8 });
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 5 });

    act(() => {
      fireEvent.loadedMetadata(audio);
      fireEvent.timeUpdate(audio);
    });
    expect(screen.getByText('5s / 8s')).toBeInTheDocument();

    act(() => {
      fireEvent.ended(audio);
    });
    expect(screen.getByText('0s / 8s')).toBeInTheDocument();
  });
});
