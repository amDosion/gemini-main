// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import InlineModeNavigation from './InlineModeNavigation';

describe('InlineModeNavigation mode-first behavior', () => {
  it('renders the compact Gemini brand mark without a text label in the rail header', () => {
    render(
      <InlineModeNavigation
        currentMode="chat"
        setMode={vi.fn()}
        modeCatalog={[]}
        onOpenSettings={vi.fn()}
        onOpenCloudStorage={vi.fn()}
        isPersonaViewOpen={false}
        onOpenPersonaView={vi.fn()}
      />
    );

    expect(screen.getByLabelText('Gemini')).toBeTruthy();
    expect(screen.queryByText('模式')).toBeNull();
  });

  it('allows switching even when the current provider has no models for that mode', () => {
    const setMode = vi.fn();

    render(
      <InlineModeNavigation
        currentMode="chat"
        setMode={setMode}
        modeCatalog={[
          {
            id: 'chat',
            label: 'Chat',
            description: 'chat mode',
            group: 'core',
            hasModels: true,
            availableModelCount: 4,
            visibleInNavigation: true,
          },
          {
            id: 'video-gen',
            label: 'Video',
            description: 'video mode',
            group: 'creative',
            hasModels: false,
            availableModelCount: 0,
            visibleInNavigation: true,
          },
        ]}
        onOpenSettings={vi.fn()}
        onOpenCloudStorage={vi.fn()}
        isPersonaViewOpen={false}
        onOpenPersonaView={vi.fn()}
      />
    );

    const button = screen.getByRole('button', { name: 'Video' });
    expect(button.hasAttribute('disabled')).toBe(false);

    fireEvent.click(button);
    expect(setMode).toHaveBeenCalledWith('video-gen');
  });
});
