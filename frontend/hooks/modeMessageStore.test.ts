// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AppMode, Message, Role } from '../types/types';
import {
  getModeMessages,
  resetModeMessages,
  setModeMessages,
  useModeMessages,
} from './modeMessageStore';

const message = (id: string, mode: AppMode): Message => ({
  id,
  role: Role.MODEL,
  content: id,
  timestamp: 1,
  attachments: [],
  mode,
});

describe('modeMessageStore', () => {
  beforeEach(() => {
    resetModeMessages();
  });

  afterEach(() => {
    resetModeMessages();
  });

  it('sets one mode without affecting another mode cell', () => {
    const chatBefore = getModeMessages('chat');
    const imageMessages = [message('image-1', 'image-gen')];

    setModeMessages('image-gen', imageMessages);

    expect(getModeMessages('image-gen')).toBe(imageMessages);
    expect(getModeMessages('chat')).toBe(chatBefore);
  });

  it('notifies only subscribers for the changed mode', () => {
    let chatRenderCount = 0;
    let imageRenderCount = 0;

    renderHook(() => {
      chatRenderCount += 1;
      return useModeMessages('chat');
    });
    renderHook(() => {
      imageRenderCount += 1;
      return useModeMessages('image-gen');
    });

    const chatBefore = chatRenderCount;
    const imageBefore = imageRenderCount;

    act(() => {
      setModeMessages('image-gen', [message('image-1', 'image-gen')]);
    });

    expect(chatRenderCount).toBe(chatBefore);
    expect(imageRenderCount).toBeGreaterThan(imageBefore);
  });

  it('does not notify when setting the same reference', () => {
    let renderCount = 0;
    const messages = [message('chat-1', 'chat')];

    renderHook(() => {
      renderCount += 1;
      return useModeMessages('chat');
    });

    act(() => {
      setModeMessages('chat', messages);
    });
    const renderCountAfterFirstSet = renderCount;

    act(() => {
      setModeMessages('chat', messages);
    });

    expect(renderCount).toBe(renderCountAfterFirstSet);
  });

  it('returns a stable empty array for unwritten modes', () => {
    const first = getModeMessages('video-gen');
    const second = getModeMessages('video-gen');

    expect(first).toBe(second);
    expect(first).toEqual([]);
  });

  it('returns a frozen shared empty array for unwritten modes', () => {
    const imageEmpty = getModeMessages('image-gen');
    const videoEmpty = getModeMessages('video-gen');

    expect(Object.isFrozen(imageEmpty)).toBe(true);
    expect(imageEmpty).toBe(videoEmpty);

    setModeMessages('chat', [message('chat-1', 'chat')]);

    expect(getModeMessages('image-gen')).toBe(imageEmpty);
    expect(getModeMessages('image-gen')).toEqual([]);
    expect(Object.isFrozen(getModeMessages('image-gen'))).toBe(true);
  });
});
