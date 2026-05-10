// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Header } from './Header';
import type { ModelConfig } from '../../types/types';
import type { ConfigProfile } from '../../services/db';

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

describe('Header model dropdown usage labels', () => {
  afterEach(() => {
    cleanup();
  });

  it('shows concrete usage labels instead of generic provider descriptions', () => {
    const model: ModelConfig = {
      id: 'gemini-2.5-flash',
      name: 'Gemini 2.5 Flash',
      description: 'Advanced multimodal model with vision, search, and reasoning',
      capabilities: {
        vision: true,
        search: true,
        reasoning: true,
        coding: false,
      },
      contextWindow: 0,
    };
    const profile: ConfigProfile = {
      id: 'profile-1',
      name: 'Google',
      providerId: 'google',
      apiKey: 'key',
      baseUrl: '',
      protocol: 'google',
      isProxy: false,
      hiddenModels: [],
      cachedModelCount: 1,
      savedModels: [model],
      createdAt: 1,
      updatedAt: 1,
    };

    render(
      <Header
        isSidebarOpen={false}
        setIsSidebarOpen={vi.fn()}
        isLoadingModels={false}
        isModelMenuOpen={true}
        setIsModelMenuOpen={vi.fn()}
        activeModelConfig={model}
        configApiKey="key"
        visibleModels={[model]}
        currentModelId={model.id}
        onModelSelect={vi.fn()}
        onOpenSettings={vi.fn()}
        appMode="chat"
        profiles={[profile]}
        activeProfileId={profile.id}
        onActivateProfile={vi.fn()}
        currentUser={null}
        onChangePassword={vi.fn()}
      />
    );

    expect(screen.getByText('对话 / 推理 / 检索')).toBeTruthy();
    expect(screen.queryByText('Advanced multimodal model with vision, search, and reasoning')).toBeNull();
  });
});
