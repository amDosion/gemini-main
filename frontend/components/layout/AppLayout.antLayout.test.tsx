// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppLayout } from './AppLayout';

vi.mock('./Header', () => ({
  Header: () => <header data-testid="app-header" />,
}));

vi.mock('./InlineModeNavigation', () => ({
  default: () => <nav data-testid="mode-nav" />,
}));

afterEach(cleanup);

const createProps = (
  overrides: Partial<React.ComponentProps<typeof AppLayout>> = {}
): React.ComponentProps<typeof AppLayout> => ({
  children: null,
  sessions: [],
  currentSessionId: null,
  onNewChat: vi.fn(),
  onSelectSession: vi.fn(),
  onDeleteSession: vi.fn(),
  onUpdateSessionTitle: vi.fn(),
  isPersonaViewOpen: false,
  onOpenPersonaView: vi.fn(),
  isLoadingModels: false,
  isModelMenuOpen: false,
  setIsModelMenuOpen: vi.fn(),
  configApiKey: '',
  visibleModels: [],
  currentModelId: '',
  onModelSelect: vi.fn(),
  onOpenSettings: vi.fn(),
  onOpenCloudStorage: vi.fn(),
  appMode: 'chat',
  profiles: [],
  activeProfileId: null,
  onActivateProfile: vi.fn(),
  currentUser: null,
  onChangePassword: vi.fn(),
  showModeNavigation: true,
  setAppMode: vi.fn(),
  modeCatalog: [],
  ...overrides,
});

describe('AppLayout Ant Design shell', () => {
  it('places mode navigation in a full-height left aside before header and content', () => {
    render(
      <AppLayout {...createProps()}>
        <main data-testid="page-content" />
      </AppLayout>
    );

    const shell = screen.getByTestId('app-shell');
    const aside = screen.getByRole('complementary', { name: '应用导航' });
    const header = screen.getByTestId('app-header');
    const content = screen.getByTestId('app-content');

    expect(shell.firstElementChild).toBe(aside);
    expect(aside.contains(screen.getByTestId('mode-nav'))).toBe(true);
    expect(content.contains(screen.getByTestId('page-content'))).toBe(true);
    expect(
      Boolean(aside.compareDocumentPosition(header) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
  });

  it('omits the app aside when mode navigation is disabled', () => {
    render(
      <AppLayout {...createProps({ showModeNavigation: false })}>
        <main data-testid="page-content" />
      </AppLayout>
    );

    expect(screen.queryByRole('complementary', { name: '应用导航' })).toBeNull();
    expect(screen.queryByTestId('mode-nav')).toBeNull();
  });
});
