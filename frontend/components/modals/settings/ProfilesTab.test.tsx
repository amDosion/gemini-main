// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProfilesTab } from './ProfilesTab';
import type { ConfigProfile } from '../../../services/db';

const mocks = vi.hoisted(() => ({
  showError: vi.fn(),
}));

vi.mock('../../../services/apiClient', () => ({
  getAuthHeaders: () => ({}),
}));

vi.mock('../../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showError: mocks.showError,
  }),
}));

const buildProfile = (): ConfigProfile => ({
  id: 'profile-1',
  name: 'Secure Profile',
  providerId: 'google',
  apiKey: '',
  baseUrl: '',
  protocol: 'google',
  isProxy: false,
  hiddenModels: [],
  cachedModelCount: 0,
  savedModels: [],
  createdAt: 1,
  updatedAt: 1,
});

describe('ProfilesTab', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('redacts sensitive credentials from failed model preview responses', async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          detail:
            'model list failed for https://files.example.com/models.json?token=secret-model-token&safe=1 with Bearer secret-model-bearer and api_key=secret-model-key',
        }),
        {
          status: 502,
          statusText: 'Bad Gateway',
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <ProfilesTab
        profiles={[buildProfile()]}
        activeProfileId={null}
        onActivateProfile={vi.fn()}
        onDeleteProfile={vi.fn()}
        onSaveProfile={vi.fn()}
        onEditProfile={vi.fn()}
        onCreateNew={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('Actions'));
    fireEvent.click(screen.getByText('View Models'));

    await waitFor(() => {
      expect(screen.getByText('Fetch Failed')).toBeInTheDocument();
      expect(screen.getByText(/token=REDACTED/)).toBeInTheDocument();
    });

    expect(document.body.textContent).not.toContain('secret-model-token');
    expect(document.body.textContent).not.toContain('secret-model-bearer');
    expect(document.body.textContent).not.toContain('secret-model-key');
    expect(document.body.textContent).toContain('safe=1');
    expect(document.body.textContent).toContain('Bearer REDACTED');
    expect(document.body.textContent).toContain('api_key=REDACTED');
  });
});
