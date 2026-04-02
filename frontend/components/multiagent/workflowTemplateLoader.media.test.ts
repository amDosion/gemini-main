import { describe, expect, it, vi } from 'vitest';
import type { Edge, Node } from 'reactflow';
import { loadTemplateIntoEditor } from './workflowTemplateLoader';
import type { WorkflowNodeData } from './types';

vi.mock('../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImages: vi.fn(async () => []),
}));

describe('workflowTemplateLoader media support', () => {
  it('hydrates template sample video/audio inputs into start and media input nodes', async () => {
    let capturedNodes: Node<WorkflowNodeData>[] = [];
    let capturedEdges: Edge[] = [];

    await loadTemplateIntoEditor({
      template: {
        id: 'template-media',
        name: 'Media Template',
        promptExample: JSON.stringify({
          text: 'Describe this clip',
          video_urls: ['https://cdn.example.com/a.mp4', 'https://cdn.example.com/b.mp4'],
          audioUrl: 'https://cdn.example.com/narration.mp3',
        }),
        sampleInput: {
          video_urls: ['https://cdn.example.com/a.mp4', 'https://cdn.example.com/b.mp4'],
          audio_urls: ['https://cdn.example.com/narration.mp3', 'https://cdn.example.com/backup.mp3'],
        },
        config: {
          nodes: [
            {
              id: 'start-1',
              type: 'custom',
              position: { x: 0, y: 0 },
              data: {
                type: 'start',
                startVideoUrl: '{{ input.videoUrls[1] }}',
                startAudioUrl: '{{ input.audioUrl }}',
              },
            },
            {
              id: 'video-1',
              type: 'custom',
              position: { x: 120, y: 0 },
              data: {
                type: 'input_video',
                startVideoUrl: '{{ input.videoUrl }}',
              },
            },
            {
              id: 'audio-1',
              type: 'custom',
              position: { x: 240, y: 0 },
              data: {
                type: 'input_audio',
                startAudioUrl: '{{ input.audioUrls[1] }}',
              },
            },
          ],
          edges: [],
        },
      },
      setWorkflowPrompt: vi.fn(),
      setWorkflowInputImageUrl: vi.fn(),
      setWorkflowInputFileUrl: vi.fn(),
      setNodes: (value) => {
        capturedNodes = typeof value === 'function' ? value(capturedNodes) : value;
      },
      setEdges: (value) => {
        capturedEdges = typeof value === 'function' ? value(capturedEdges) : value;
      },
      setActiveTemplateMeta: vi.fn(),
      setActiveTemplateFingerprint: vi.fn(),
      setFinalResult: vi.fn(),
      setFinalError: vi.fn(),
      setFinalCompletedAt: vi.fn(),
      setFinalRuntime: vi.fn(),
      setFinalRuntimeHints: vi.fn(),
      setShowTemplateSelector: vi.fn(),
      setPendingFitToken: vi.fn(),
      addLog: vi.fn(),
      hydrateAgentBindingsFromRegistry: async (inputNodes) => inputNodes,
    });

    expect(capturedEdges).toEqual([]);

    const startNode = capturedNodes.find((node) => node.id === 'start-1');
    const videoNode = capturedNodes.find((node) => node.id === 'video-1');
    const audioNode = capturedNodes.find((node) => node.id === 'audio-1');

    expect(startNode?.data?.startVideoUrl).toBe('https://cdn.example.com/b.mp4');
    expect(startNode?.data?.startVideoUrls).toEqual([
      'https://cdn.example.com/b.mp4',
      'https://cdn.example.com/a.mp4',
    ]);
    expect(startNode?.data?.startAudioUrl).toBe('https://cdn.example.com/narration.mp3');
    expect(startNode?.data?.startAudioUrls).toEqual([
      'https://cdn.example.com/narration.mp3',
      'https://cdn.example.com/backup.mp3',
    ]);
    expect(videoNode?.data?.startVideoUrl).toBe('https://cdn.example.com/a.mp4');
    expect(videoNode?.data?.startVideoUrls).toEqual(['https://cdn.example.com/a.mp4']);
    expect(audioNode?.data?.startAudioUrl).toBe('https://cdn.example.com/backup.mp3');
    expect(audioNode?.data?.startAudioUrls).toEqual(['https://cdn.example.com/backup.mp3']);
  });

  it('merges sample summary audio and video into end-node result preview', async () => {
    let capturedNodes: Node<WorkflowNodeData>[] = [];
    let capturedFinalResult: any = null;

    await loadTemplateIntoEditor({
      template: {
        id: 'template-media-result',
        name: 'Media Result Template',
        sampleResult: {
          finalOutput: {
            text: '样例执行完成',
          },
        },
        sampleResultSummary: {
          hasResult: true,
          audioUrls: ['https://cdn.example.com/sample.mp3'],
          videoUrls: ['https://cdn.example.com/sample.mp4'],
        },
        config: {
          nodes: [
            {
              id: 'end-1',
              type: 'custom',
              position: { x: 0, y: 0 },
              data: {
                type: 'end',
              },
            },
          ],
          edges: [],
        },
      },
      setWorkflowPrompt: vi.fn(),
      setWorkflowInputImageUrl: vi.fn(),
      setWorkflowInputFileUrl: vi.fn(),
      setNodes: (value) => {
        capturedNodes = typeof value === 'function' ? value(capturedNodes) : value;
      },
      setEdges: vi.fn(),
      setActiveTemplateMeta: vi.fn(),
      setActiveTemplateFingerprint: vi.fn(),
      setFinalResult: (value) => {
        capturedFinalResult = typeof value === 'function' ? value(capturedFinalResult) : value;
      },
      setFinalError: vi.fn(),
      setFinalCompletedAt: vi.fn(),
      setFinalRuntime: vi.fn(),
      setFinalRuntimeHints: vi.fn(),
      setShowTemplateSelector: vi.fn(),
      setPendingFitToken: vi.fn(),
      addLog: vi.fn(),
      hydrateAgentBindingsFromRegistry: async (inputNodes) => inputNodes,
    });

    const endNode = capturedNodes.find((node) => node.id === 'end-1');

    expect(endNode?.data?.status).toBe('completed');
    expect(endNode?.data?.result?.audioUrl).toBe('https://cdn.example.com/sample.mp3');
    expect(endNode?.data?.result?.videoUrl).toBe('https://cdn.example.com/sample.mp4');
    expect(capturedFinalResult?.audioUrl).toBe('https://cdn.example.com/sample.mp3');
    expect(capturedFinalResult?.videoUrl).toBe('https://cdn.example.com/sample.mp4');
  });
});
