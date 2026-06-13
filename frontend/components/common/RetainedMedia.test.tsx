// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { RetainedAudio, RetainedVideo } from './RetainedMedia';

describe('RetainedMedia', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('retains blob video urls for the rendered video lifetime', () => {
    const { unmount } = render(
      <RetainedVideo src="blob:retained-video-preview" data-testid="retained-video" />
    );

    expect(screen.getByTestId('retained-video').getAttribute('src')).toBe(
      'blob:retained-video-preview'
    );
    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-video-preview'
    );
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalled();

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-video-preview'
    );
  });

  it('retains blob audio urls for the rendered audio lifetime', () => {
    const { unmount } = render(
      <RetainedAudio src="blob:retained-audio-preview" data-testid="retained-audio" />
    );

    expect(screen.getByTestId('retained-audio').getAttribute('src')).toBe(
      'blob:retained-audio-preview'
    );
    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-audio-preview'
    );

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith(
      'blob:retained-audio-preview'
    );
  });

  it('does not render internal local-blob video keys', () => {
    render(
      <RetainedVideo
        src="local-blob:retained-file-only-video"
        data-testid="internal-video"
      />
    );

    expect(screen.queryByTestId('internal-video')).toBeNull();
    expect(mediaCacheMock.retainMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('does not render internal local-blob audio keys', () => {
    render(
      <RetainedAudio
        src="local-blob:retained-file-only-audio"
        data-testid="internal-audio"
      />
    );

    expect(screen.queryByTestId('internal-audio')).toBeNull();
    expect(mediaCacheMock.retainMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('renders safe inline video data urls for retained video', () => {
    render(
      <RetainedVideo
        src="data:video/mp4;base64,YWJj"
        data-testid="inline-video"
      />
    );

    expect(screen.getByTestId('inline-video').getAttribute('src')).toBe(
      'data:video/mp4;base64,YWJj'
    );
  });

  it('renders safe inline audio data urls for retained audio', () => {
    render(
      <RetainedAudio
        src="data:audio/wav;base64,YWJj"
        data-testid="inline-audio"
      />
    );

    expect(screen.getByTestId('inline-audio').getAttribute('src')).toBe(
      'data:audio/wav;base64,YWJj'
    );
  });

  it('does not render unsafe inline or non-browser media urls', () => {
    render(
      <>
        <RetainedVideo
          src="data:audio/wav;base64,YWJj"
          data-testid="wrong-family-video"
        />
        <RetainedAudio
          src="data:audio/wav,not-base64"
          data-testid="non-base64-audio"
        />
        <RetainedVideo src="javascript:alert(1)" data-testid="script-video" />
        <RetainedAudio src="file:///tmp/audio.wav" data-testid="file-audio" />
      </>
    );

    expect(screen.queryByTestId('wrong-family-video')).toBeNull();
    expect(screen.queryByTestId('non-base64-audio')).toBeNull();
    expect(screen.queryByTestId('script-video')).toBeNull();
    expect(screen.queryByTestId('file-audio')).toBeNull();
  });

  it('lets callers recover failed retained video blobs before surfacing onError', () => {
    const onRecoverMediaError = vi.fn(() => true);
    const onError = vi.fn();

    render(
      <RetainedVideo
        src="blob:failed-retained-video"
        data-testid="recoverable-video"
        onRecoverMediaError={onRecoverMediaError}
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('recoverable-video'));

    expect(onRecoverMediaError).toHaveBeenCalledWith('blob:failed-retained-video');
    expect(onError).not.toHaveBeenCalled();
  });

  it('lets callers recover failed retained audio blobs before surfacing onError', () => {
    const onRecoverMediaError = vi.fn(() => true);
    const onError = vi.fn();

    render(
      <RetainedAudio
        src="blob:failed-retained-audio"
        data-testid="recoverable-audio"
        onRecoverMediaError={onRecoverMediaError}
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('recoverable-audio'));

    expect(onRecoverMediaError).toHaveBeenCalledWith('blob:failed-retained-audio');
    expect(onError).not.toHaveBeenCalled();
  });

  it('stops rendering a failed video blob after surfacing onError when no recovery is available', () => {
    const onError = vi.fn();

    render(
      <RetainedVideo
        src="blob:unrecoverable-retained-video"
        data-testid="unrecoverable-video"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('unrecoverable-video'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('unrecoverable-video')).toBeNull();
  });

  it('stops rendering a failed audio blob after surfacing onError when no recovery is available', () => {
    const onError = vi.fn();

    render(
      <RetainedAudio
        src="blob:unrecoverable-retained-audio"
        data-testid="unrecoverable-audio"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('unrecoverable-audio'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('unrecoverable-audio')).toBeNull();
  });

  it('stops rendering when video reports an equivalent resolved blob currentSrc', () => {
    const onError = vi.fn();

    render(
      <RetainedVideo
        src="blob:https://gemini.dicry.cn:18443/equivalent-video"
        data-testid="equivalent-video"
        onError={onError}
      />
    );

    const video = screen.getByTestId('equivalent-video');
    Object.defineProperty(video, 'currentSrc', {
      configurable: true,
      value: 'blob:https://gemini.dicry.cn:18443/equivalent-video#resolved',
    });

    fireEvent.error(video);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('equivalent-video')).toBeNull();
  });

  it('keeps non-blob video urls mounted after surfacing onError', () => {
    const onError = vi.fn();

    render(
      <RetainedVideo
        src="/api/storage/local-files/missing-video.mp4"
        data-testid="missing-video"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('missing-video'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('missing-video')).not.toBeNull();
  });

  it('keeps non-blob audio urls mounted after surfacing onError', () => {
    const onError = vi.fn();

    render(
      <RetainedAudio
        src="/api/storage/local-files/missing-audio.mp3"
        data-testid="missing-audio"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByTestId('missing-audio'));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('missing-audio')).not.toBeNull();
  });
});
