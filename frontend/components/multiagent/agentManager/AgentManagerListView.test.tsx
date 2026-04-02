// @vitest-environment jsdom
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import type { AgentDef } from '../types';
import { AgentManagerListView } from './AgentManagerListView';

const makeAgent = (id: string, taskType: string): AgentDef => ({
  id,
  name: `Agent ${id}`,
  description: '',
  providerId: 'google',
  modelId: id,
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 4096,
  icon: '🤖',
  color: '#14b8a6',
  status: 'active',
  runtime: {
    kind: '',
    label: '',
    supportsRun: false,
    supportsLiveRun: false,
    supportsSessions: false,
    supportsMemory: false,
    supportsOfficialOrchestration: false,
  },
  agentCard: {
    defaults: {
      defaultTaskType: taskType as any,
    },
  },
});

describe('AgentManagerListView', () => {
  it('does not render task count section', () => {
    render(
      <AgentManagerListView
        activeCount={3}
        inactiveCount={0}
        searchKeyword=""
        selectedStatus="active"
        notice={null}
        loading={false}
        agents={[
          makeAgent('chat-model', 'chat'),
          makeAgent('veo-3.1', 'video-gen'),
          makeAgent('tts-1', 'audio-gen'),
        ]}
        onSearchKeywordChange={vi.fn()}
        onSelectStatus={vi.fn()}
        onCreate={vi.fn()}
        onEdit={vi.fn()}
        onDisable={vi.fn()}
        onRestore={vi.fn()}
        onHardDelete={vi.fn()}
        onOpenRuntimeSessions={vi.fn()}
      />
    );

    expect(screen.queryByText('任务数量')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /🎬 视频生成/i })).not.toBeInTheDocument();
  });

  it('renders generic empty-state create label', () => {
    render(
      <AgentManagerListView
        activeCount={0}
        inactiveCount={0}
        searchKeyword=""
        selectedStatus="active"
        notice={null}
        loading={false}
        agents={[]}
        onSearchKeywordChange={vi.fn()}
        onSelectStatus={vi.fn()}
        onCreate={vi.fn()}
        onEdit={vi.fn()}
        onDisable={vi.fn()}
        onRestore={vi.fn()}
        onHardDelete={vi.fn()}
        onOpenRuntimeSessions={vi.fn()}
      />
    );

    expect(screen.getByText('还没有 Agent')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '创建第一个 Agent' })).toBeInTheDocument();
  });

  it('uses runtime metadata instead of agentType heuristics for runtime session action', () => {
    render(
      <AgentManagerListView
        activeCount={1}
        inactiveCount={0}
        searchKeyword=""
        selectedStatus="active"
        notice={null}
        loading={false}
        agents={[
          {
            ...makeAgent('runtime-custom', 'chat'),
            agentType: 'custom',
            source: {
              kind: 'seed',
              label: '官方 Seed',
              isSystem: true,
            },
            runtime: {
              kind: 'google-adk',
              label: 'Google ADK',
              supportsRun: true,
              supportsLiveRun: true,
              supportsSessions: true,
              supportsMemory: true,
              supportsOfficialOrchestration: true,
            },
          },
          {
            ...makeAgent('runtime-disabled', 'chat'),
            agentType: 'adk',
            runtime: {
              kind: '',
              label: '',
              supportsRun: false,
              supportsLiveRun: false,
              supportsSessions: false,
              supportsMemory: false,
              supportsOfficialOrchestration: false,
            },
          },
        ]}
        onSearchKeywordChange={vi.fn()}
        onSelectStatus={vi.fn()}
        onCreate={vi.fn()}
        onEdit={vi.fn()}
        onDisable={vi.fn()}
        onRestore={vi.fn()}
        onHardDelete={vi.fn()}
        onOpenRuntimeSessions={vi.fn()}
      />
    );

    expect(screen.getAllByTitle('管理运行时会话')).toHaveLength(1);
    expect(screen.getByText('来源: 官方 Seed')).toBeInTheDocument();
    expect(screen.getByText('Runtime: Google ADK')).toBeInTheDocument();
    expect(screen.getByText('官方编排')).toBeInTheDocument();
  });
});
