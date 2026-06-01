import { describe, expect, it } from 'vitest';

import {
  buildAgentNodeBindingPatch,
  resolveAgentNodeEffectiveTaskType,
} from './agentNodeBinding';
import { buildAgentNodeDefaultsFromAgent } from './agentNodeDefaults';
import type { AgentDef, WorkflowNodeData } from './types';

const makeAgent = (): AgentDef => ({
  id: 'agent-image',
  name: 'Image Agent',
  description: 'Creates product images',
  providerId: 'google',
  modelId: 'imagen-3.0-generate-002',
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 4096,
  icon: '🎨',
  color: '#d946ef',
  status: 'active',
  agentCard: {
    defaults: {
      defaultTaskType: 'image-gen',
      imageGeneration: {
        aspectRatio: '3:4',
        numberOfImages: 2,
        outputMimeType: 'image/png',
      },
    },
  },
});

describe('agent node binding contract', () => {
  it('binds agent identity, visual metadata, and effective task type without copying media defaults', () => {
    const patch = buildAgentNodeBindingPatch(makeAgent(), {
      label: '智能体',
      description: '核心执行单元：模型 + 指令 + 工具',
      icon: '🤖',
      iconColor: 'bg-teal-500',
    } as WorkflowNodeData);

    expect(patch).toMatchObject({
      agentId: 'agent-image',
      agentName: 'Image Agent',
      agentProviderId: 'google',
      agentModelId: 'imagen-3.0-generate-002',
      label: 'Image Agent',
      description: 'Creates product images',
      icon: '🎨',
      iconColor: '#d946ef',
      agentTaskType: 'image-gen',
    });
    expect(patch.agentAspectRatio).toBeUndefined();
    expect(patch.agentNumberOfImages).toBeUndefined();
    expect(patch.agentOutputMimeType).toBeUndefined();
  });

  it('resolves inherited agent default task type when the node has no explicit override', () => {
    const agent = makeAgent();

    expect(resolveAgentNodeEffectiveTaskType({}, agent)).toBe('image-gen');
    expect(resolveAgentNodeEffectiveTaskType({ agentTaskType: 'data-analysis' }, agent)).toBe(
      'data-analysis'
    );
    expect(resolveAgentNodeEffectiveTaskType({ agentTaskType: 'bad-task' }, agent)).toBe(
      'image-gen'
    );
  });

  it('clears stale starter preset key when a user manually rebinds the node to an agent', () => {
    const patch = buildAgentNodeBindingPatch(makeAgent(), {
      agentPresetKey: 'old-starter-agent',
      agentId: 'old-agent',
      agentName: 'Old Agent',
    } as WorkflowNodeData);

    expect(patch.agentId).toBe('agent-image');
    expect(patch.agentName).toBe('Image Agent');
    expect(patch.agentPresetKey).toBeUndefined();
  });

  it('preserves an explicitly authored chat task when hydrating a media-capable agent', () => {
    const patch = buildAgentNodeBindingPatch(makeAgent(), {
      agentId: 'agent-image',
      agentName: 'Image Agent',
      agentTaskType: 'chat',
      label: '创意规划',
    } as WorkflowNodeData);

    expect(patch).not.toHaveProperty('agentTaskType');
  });

  it('normalizes legacy video resolution defaults before applying agent card values to nodes', () => {
    const agent = makeAgent();
    agent.agentCard = {
      defaults: {
        defaultTaskType: 'video-gen',
        videoGeneration: {
          resolution: '2K',
          durationSeconds: 8,
        },
      },
    };

    expect(buildAgentNodeDefaultsFromAgent(agent)).toMatchObject({
      agentTaskType: 'video-gen',
      agentResolutionTier: '1080p',
      agentVideoDurationSeconds: 8,
    });
  });

  it('maps advanced image-edit agent card defaults to inherited node defaults', () => {
    const agent = makeAgent();
    agent.agentCard = {
      defaults: {
        defaultTaskType: 'image-edit',
        imageEdit: {
          editMode: 'image-chat-edit',
          imageSize: '1K',
          resolutionTier: '1K',
          numberOfImages: 1,
          outputMimeType: 'image/png',
          promptExtend: true,
          addMagicSuffix: true,
          preserveProductIdentity: true,
          productMatchThreshold: 72,
          maxRetries: 2,
          outputLanguage: 'en',
        },
      },
    };

    expect(buildAgentNodeDefaultsFromAgent(agent)).toMatchObject({
      agentTaskType: 'image-edit',
      agentEditMode: 'image-chat-edit',
      agentImageSize: '1K',
      agentResolutionTier: '1K',
      agentNumberOfImages: 1,
      agentOutputMimeType: 'image/png',
      agentPromptExtend: true,
      agentAddMagicSuffix: true,
      agentPreserveProductIdentity: true,
      agentProductMatchThreshold: 72,
      agentImageEditMaxRetries: 2,
      agentOutputLanguage: 'en',
    });
  });
});
