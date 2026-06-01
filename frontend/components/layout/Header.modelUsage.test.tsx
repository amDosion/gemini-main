// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Header } from './Header';
import { getModelSelectorWidthCh } from './HeaderModelSelector';
import { getProfileSelectorWidthCh } from './HeaderProfileSelector';
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

  it('sizes the model selector from the longest model name in the dropdown list', () => {
    const selectedModel: ModelConfig = {
      id: 'gemini-flash',
      name: 'Gemini Flash',
      description: 'Selected short model',
      capabilities: {
        vision: true,
        search: false,
        reasoning: true,
        coding: false,
      },
      contextWindow: 0,
    };
    const longestDropdownModel: ModelConfig = {
      id: 'claude-mythos-long-display-name',
      name: 'Claude Mythos Preview for Vertex AI With Very Long Display Name',
      description: 'Long dropdown model',
      capabilities: {
        vision: true,
        search: false,
        reasoning: true,
        coding: true,
      },
      contextWindow: 0,
    };
    const profile: ConfigProfile = {
      id: 'profile-1',
      name: 'Vertex AI',
      providerId: 'google-vertex',
      apiKey: 'key',
      baseUrl: '',
      protocol: 'google',
      isProxy: false,
      hiddenModels: [],
      cachedModelCount: 2,
      savedModels: [selectedModel, longestDropdownModel],
      createdAt: 1,
      updatedAt: 1,
    };

    const visibleModels = [selectedModel, longestDropdownModel];
    const expectedDropdownWidth = `${getModelSelectorWidthCh(visibleModels)}ch`;
    const selectedOnlyWidth = `${getModelSelectorWidthCh([selectedModel])}ch`;

    const { container } = render(
      <Header
        isSidebarOpen={false}
        setIsSidebarOpen={vi.fn()}
        isLoadingModels={false}
        isModelMenuOpen={false}
        setIsModelMenuOpen={vi.fn()}
        activeModelConfig={selectedModel}
        configApiKey="key"
        visibleModels={visibleModels}
        currentModelId={selectedModel.id}
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

    const headerControls = container.querySelector('[data-testid="header-primary-controls"]');
    const modelSelector = container.querySelector('[data-testid="header-model-selector"]');
    const modelSelect = container.querySelector('.header-model-select');

    expect(headerControls).not.toBeNull();
    expect(modelSelector).not.toBeNull();
    expect(modelSelect).not.toBeNull();
    expect(headerControls!.className).toContain('w-fit');
    expect(headerControls!.className).not.toContain('flex-1');
    expect(modelSelector!.className).toContain('w-fit');
    expect(modelSelector!.className).toContain('max-w-full');
    expect(modelSelector!.className).not.toContain('flex-1');
    expect(modelSelector!.className).not.toContain('min-w-[280px]');
    expect(modelSelector!.className).not.toContain('max-w-[560px]');
    expect((modelSelect as HTMLElement).style.width).toBe(expectedDropdownWidth);
    expect((modelSelect as HTMLElement).style.width).not.toBe(selectedOnlyWidth);
    expect(modelSelect!.className).not.toContain('flex-1');
    expect(modelSelect!.className).not.toContain('min-w-[180px]');
  });

  it('sizes the provider selector from the longest profile name in the dropdown list', async () => {
    const model: ModelConfig = {
      id: 'gemini-flash',
      name: 'Gemini Flash',
      description: 'Test model',
      capabilities: {
        vision: true,
        search: false,
        reasoning: false,
        coding: false,
      },
      contextWindow: 0,
    };
    const selectedProfile: ConfigProfile = {
      id: 'profile-short',
      name: 'G',
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
    const longestDropdownProfile: ConfigProfile = {
      id: 'profile-long',
      name: 'Enterprise Vertex AI Provider Configuration',
      providerId: 'google-vertex',
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

    const profiles = [selectedProfile, longestDropdownProfile];
    const expectedDropdownWidth = `${getProfileSelectorWidthCh(profiles)}ch`;
    const selectedOnlyWidth = `${getProfileSelectorWidthCh([selectedProfile])}ch`;

    const { container } = render(
      <Header
        isSidebarOpen={false}
        setIsSidebarOpen={vi.fn()}
        isLoadingModels={false}
        isModelMenuOpen={false}
        setIsModelMenuOpen={vi.fn()}
        activeModelConfig={model}
        configApiKey="key"
        visibleModels={[model]}
        currentModelId={model.id}
        onModelSelect={vi.fn()}
        onOpenSettings={vi.fn()}
        appMode="chat"
        profiles={profiles}
        activeProfileId={selectedProfile.id}
        onActivateProfile={vi.fn()}
        currentUser={null}
        onChangePassword={vi.fn()}
      />
    );

    const providerSelect = container.querySelector('.header-provider-select');

    expect(providerSelect).not.toBeNull();
    expect((providerSelect as HTMLElement).style.width).toBe(expectedDropdownWidth);
    expect((providerSelect as HTMLElement).style.width).not.toBe(selectedOnlyWidth);
    expect(providerSelect!.className).not.toContain('w-[190px]');

    const providerSelector = providerSelect!.querySelector('.ant-select-selector');
    expect(providerSelector).not.toBeNull();
    fireEvent.mouseDown(providerSelector!);

    const dropdownProfileName = await screen.findByText(longestDropdownProfile.name);
    expect(dropdownProfileName.className).not.toContain('truncate');
    expect(dropdownProfileName.className).toContain('whitespace-nowrap');
  });
});
