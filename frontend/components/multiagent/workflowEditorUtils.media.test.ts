import { describe, expect, it } from 'vitest';
import {
  applyAgentBindingsToNodes,
  getDefaultNodeConfig,
  NODE_DEFAULT_FOCUS_FIELD_BY_TYPE,
  normalizeWorkflowInputForExecute,
  normalizeWorkflowNodeDataForExecute,
  normalizeTemplateSampleInput,
  resolveTemplateInputPlaceholder,
} from './workflowEditorUtils';

describe('workflowEditorUtils media support', () => {
  it('hydrates media agent bindings without downgrading authored task types to chat', () => {
    const imageAgent = {
      id: 'image-agent',
      name: 'Image Agent',
      description: '',
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
            aspectRatio: '1:1',
            numberOfImages: 1,
          },
        },
      },
    };

    const hydrated = applyAgentBindingsToNodes([
      {
        id: 'generate',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          type: 'agent',
          label: '主图生成',
          description: '',
          icon: '🎨',
          iconColor: '#d946ef',
          agentId: 'image-agent',
          agentName: 'Image Agent',
          agentTaskType: 'image-gen',
        },
      },
      {
        id: 'plan',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          type: 'agent',
          label: '创意规划',
          description: '',
          icon: '🎨',
          iconColor: '#d946ef',
          agentId: 'image-agent',
          agentName: 'Image Agent',
          agentTaskType: 'chat',
        },
      },
      {
        id: 'blank',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          type: 'agent',
          label: '主图生成',
          description: '',
          icon: '🎨',
          iconColor: '#d946ef',
          agentId: 'image-agent',
          agentName: 'Image Agent',
        },
      },
    ], [imageAgent as any]);

    expect(hydrated.find((node) => node.id === 'generate')?.data.agentTaskType).toBe('image-gen');
    expect(hydrated.find((node) => node.id === 'plan')?.data.agentTaskType).toBe('chat');
    expect(hydrated.find((node) => node.id === 'blank')?.data.agentTaskType).toBe('image-gen');
  });

  it('provides bounded defaults and focus fields for audio/video input nodes', () => {
    expect(getDefaultNodeConfig('input_video')).toMatchObject({
      startVideoUrl: '',
      startVideoUrls: [],
    });
    expect(getDefaultNodeConfig('input_audio')).toMatchObject({
      startAudioUrl: '',
      startAudioUrls: [],
    });
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_video).toBe('startVideoUrls');
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_audio).toBe('startAudioUrls');
  });

  it('normalizes top-level workflow media inputs', () => {
    expect(normalizeWorkflowInputForExecute({
      task: 'Create assets',
      video_url: 'https://cdn.example.com/a.mp4',
      videoUrls: ['https://cdn.example.com/a.mp4', 'https://cdn.example.com/b.mp4'],
      audio_urls: ['https://cdn.example.com/narration.mp3'],
    }, 'fallback')).toEqual({
      task: 'Create assets',
      videoUrl: 'https://cdn.example.com/a.mp4',
      videoUrls: ['https://cdn.example.com/a.mp4', 'https://cdn.example.com/b.mp4'],
      audioUrl: 'https://cdn.example.com/narration.mp3',
      audioUrls: ['https://cdn.example.com/narration.mp3'],
      audio_urls: ['https://cdn.example.com/narration.mp3'],
      video_url: 'https://cdn.example.com/a.mp4',
    });
  });

  it('preserves and clamps video task node fields', () => {
    expect(normalizeWorkflowNodeDataForExecute({
      agentTaskType: 'video_generate',
      agentAspectRatio: '9:16',
      agentResolutionTier: '4K',
      agentVideoDurationSeconds: 99,
      agentVideoMaskMode: 'remove-static',
      startVideoUrl: 'https://cdn.example.com/video.mp4',
      startVideoUrls: ['https://cdn.example.com/video.mp4'],
    })).toMatchObject({
      agentTaskType: 'video-gen',
      agent_task_type: 'video-gen',
      agentAspectRatio: '9:16',
      agentResolutionTier: '4k',
      agentVideoDurationSeconds: 20,
      agentVideoMaskMode: 'REMOVE_STATIC',
      startVideoUrl: 'https://cdn.example.com/video.mp4',
      startVideoUrls: ['https://cdn.example.com/video.mp4'],
    });
  });

  it('removes workflow image edit modes that are not executable image-edit variants', () => {
    const normalized = normalizeWorkflowNodeDataForExecute({
      agentTaskType: 'image-edit',
      agentEditMode: 'virtual-try-on',
    });

    expect(normalized).not.toHaveProperty('agentEditMode');
  });

  it('preserves and clamps audio task node fields', () => {
    expect(normalizeWorkflowNodeDataForExecute({
      agentTaskType: 'speech',
      agentVoice: '  nova  ',
      agentSpeechSpeed: 9.9,
      agentAudioFormat: 'WAV',
      startAudioUrl: 'https://cdn.example.com/narration.mp3',
      startAudioUrls: ['https://cdn.example.com/narration.mp3'],
    })).toMatchObject({
      agentTaskType: 'audio-gen',
      agent_task_type: 'audio-gen',
      agentVoice: 'nova',
      agentSpeechSpeed: 4,
      agentAudioFormat: 'wav',
      startAudioUrl: 'https://cdn.example.com/narration.mp3',
      startAudioUrls: ['https://cdn.example.com/narration.mp3'],
    });
  });

  it('normalizes media template sample inputs and placeholders', () => {
    const sampleInput = normalizeTemplateSampleInput({
      text: 'Describe this clip',
      video_url: 'https://cdn.example.com/sample.mp4',
      video_urls: ['https://cdn.example.com/sample.mp4', 'https://cdn.example.com/alt.mp4'],
      audioUrl: 'https://cdn.example.com/sample.mp3',
      audioUrls: ['https://cdn.example.com/sample.mp3'],
    });

    expect(sampleInput).toMatchObject({
      task: 'Describe this clip',
      videoUrl: 'https://cdn.example.com/sample.mp4',
      videoUrls: ['https://cdn.example.com/sample.mp4', 'https://cdn.example.com/alt.mp4'],
      audioUrl: 'https://cdn.example.com/sample.mp3',
      audioUrls: ['https://cdn.example.com/sample.mp3'],
    });

    expect(resolveTemplateInputPlaceholder(
      '{{ input.videoUrls[1] }} {{ input.audioUrl }}',
      sampleInput,
    )).toBe('https://cdn.example.com/alt.mp4 https://cdn.example.com/sample.mp3');
  });
});
