// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionProvider } from '../../contexts/SessionContext';
import { ChatSession } from '../../types/types';
import { SessionSwitcher } from './SessionSwitcher';

const sessions: ChatSession[] = [
  {
    id: 'video-session-1',
    title: 'Video session',
    messages: [],
    createdAt: 1,
    mode: 'video-gen',
  },
];

const renderSwitcher = ({
  onDeleteSession = vi.fn(),
  onUpdateSessionTitle = vi.fn(),
}: {
  onDeleteSession?: (id: string) => void;
  onUpdateSessionTitle?: (id: string, newTitle: string) => void;
} = {}) => {
  const onNewChat = vi.fn();
  const onSelectSession = vi.fn();

  render(
    <SessionProvider
      sessions={sessions}
      currentSessionId="video-session-1"
      onNewChat={onNewChat}
      onSelectSession={onSelectSession}
      onDeleteSession={onDeleteSession}
      onUpdateSessionTitle={onUpdateSessionTitle}
    >
      <SessionSwitcher />
    </SessionProvider>
  );

  return { onDeleteSession, onUpdateSessionTitle, onNewChat, onSelectSession };
};

describe('SessionSwitcher', () => {
  afterEach(() => {
    cleanup();
  });

  it('allows renaming a session from the compact session list', () => {
    const onUpdateSessionTitle = vi.fn();
    renderSwitcher({ onUpdateSessionTitle });

    fireEvent.click(screen.getByText('Video session'));
    fireEvent.click(screen.getByTitle('编辑标题'));

    const input = screen.getByDisplayValue('Video session');
    fireEvent.change(input, { target: { value: 'Renamed video session' } });
    fireEvent.click(screen.getByTitle('Save'));

    expect(onUpdateSessionTitle).toHaveBeenCalledWith(
      'video-session-1',
      'Renamed video session'
    );
  });

  it('confirms before deleting a session from the compact session list', () => {
    const onDeleteSession = vi.fn();
    renderSwitcher({ onDeleteSession });

    fireEvent.click(screen.getByText('Video session'));
    fireEvent.click(screen.getByTitle('删除会话'));
    fireEvent.click(screen.getByText('Yes'));

    expect(onDeleteSession).toHaveBeenCalledWith('video-session-1');
  });
});
