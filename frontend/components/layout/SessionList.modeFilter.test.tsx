// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionList } from './SessionList';
import { ChatSession } from '../../types/types';

afterEach(cleanup);

const createSession = (id: string, mode: ChatSession['mode'], title: string): ChatSession => ({
  id,
  title,
  mode,
  createdAt: Date.now(),
  messages: [],
});

describe('SessionList mode filtering', () => {
  it('renders and selects only sessions for the active mode', () => {
    const onSelectSession = vi.fn();
    render(
      <SessionList
        appMode="chat"
        sessions={[
          createSession('image-session', 'image-gen', 'Image session title'),
          createSession('chat-session', 'chat', 'Chat session title'),
        ]}
        currentSessionId={null}
        onNewChat={vi.fn()}
        onSelectSession={onSelectSession}
      />
    );

    expect(screen.getByText('Chat session title')).not.toBeNull();
    expect(screen.queryByText('Image session title')).toBeNull();

    fireEvent.click(screen.getByText('Chat session title'));

    expect(onSelectSession).toHaveBeenCalledWith('chat-session');
  });
});
