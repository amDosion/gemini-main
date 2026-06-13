// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Header } from './Header';
import type { User as AuthUser } from '../../services/auth';
import type { ConfigProfile } from '../../services/db';
import type { SystemConfigPayload, SystemStatusPayload } from '../../services/systemAdmin';
import type { ModelConfig } from '../../types/types';

const mocks = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getStatus: vi.fn(),
  updateConfig: vi.fn(),
  cleanup: vi.fn(),
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

vi.mock('../../services/systemAdmin', () => ({
  systemAdminService: mocks,
  default: mocks,
}));

const configPayload: SystemConfigPayload = {
  values: {
    allow_registration: true,
  },
  fields: [
    {
      key: 'allow_registration',
      label: '允许注册',
      type: 'boolean',
      description: '控制新用户是否可注册',
    },
  ],
};

const statusPayload: SystemStatusPayload = {
  timestamp: '2026-06-11T00:00:00Z',
  collector: 'test',
  host: {
    hostname: 'test-host',
    platform: 'win32',
    pythonVersion: '3.12',
    cpuCount: 8,
    processUptimeSeconds: 10,
  },
  metrics: {
    cpu: {
      usagePercent: 12,
    },
    memory: {
      usagePercent: 34,
      usedBytes: 1024,
      totalBytes: 4096,
      availableBytes: 3072,
    },
    disk: {
      path: '/',
      usagePercent: 56,
      usedBytes: 2048,
      totalBytes: 8192,
      freeBytes: 6144,
      readBytes: 0,
      writeBytes: 0,
      readRateBps: 0,
      writeRateBps: 0,
    },
    network: {
      usagePercent: 1,
      bytesSent: 100,
      bytesRecv: 200,
      txRateBps: 10,
      rxRateBps: 20,
      maxLinkSpeedMbps: 1000,
    },
  },
};

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

const adminUser: AuthUser = {
  id: 'admin-1',
  email: 'admin@example.com',
  name: 'Admin',
  status: 'active',
  isAdmin: true,
};

const renderHeader = () =>
  render(
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
      profiles={[profile]}
      activeProfileId={profile.id}
      onActivateProfile={vi.fn()}
      currentUser={adminUser}
      onChangePassword={vi.fn()}
    />
  );

describe('Header system config dialog lazy loading', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('defers system admin requests until the admin opens the dialog', async () => {
    mocks.getConfig.mockResolvedValue(configPayload);
    mocks.getStatus.mockResolvedValue(statusPayload);

    renderHeader();

    expect(mocks.getConfig).not.toHaveBeenCalled();
    expect(mocks.getStatus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTitle('User Menu'));
    fireEvent.click(screen.getByText('系统配置'));

    await screen.findByRole('dialog', { name: '系统配置' });

    await waitFor(() => {
      expect(mocks.getConfig).toHaveBeenCalledTimes(1);
      expect(mocks.getStatus).toHaveBeenCalledTimes(1);
    });
  });
});
