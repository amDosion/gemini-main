import { describe, expect, it, vi, beforeEach } from 'vitest';
import { VideoGenHandler } from './AllHandlerClasses';
import { llmService } from '../../services/llmService';

vi.mock('../../services/llmService', () => ({
  llmService: {
    generateVideo: vi.fn(),
  },
}));

describe('VideoGenHandler', () => {
  const baseContext = {
    sessionId: 'session-1',
    userMessageId: 'user-msg-1',
    modelMessageId: 'model-msg-1',
    mode: 'video-gen',
    text: 'A cinematic sunrise over the ocean',
    attachments: [],
    currentModel: { id: 'veo-2.0-generate-001', name: 'Veo 2' },
    options: {},
    protocol: 'google',
    llmService: {} as any,
    storageService: {} as any,
    pollingManager: { startPolling: vi.fn(), stopPolling: vi.fn(), cleanup: vi.fn() },
  } as any;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('stores plain prompt content without legacy prefix', async () => {
    vi.mocked(llmService.generateVideo).mockResolvedValue({
      url: 'https://cdn.example.com/video.mp4',
      mimeType: 'video/mp4',
      attachmentId: 'att-1',
      uploadStatus: 'pending',
    } as any);

    const handler = new VideoGenHandler();
    const result = await handler.execute(baseContext);

    expect(result.content).toBe('A cinematic sunrise over the ocean');
    expect(result.content).not.toContain('Video generated for:');
  });

  it('stores original and enhanced prompts when enhanced prompt is returned', async () => {
    vi.mocked(llmService.generateVideo).mockResolvedValue({
      url: 'https://cdn.example.com/video.mp4',
      mimeType: 'video/mp4',
      attachmentId: 'att-1',
      uploadStatus: 'pending',
      enhancedPrompt: 'A cinematic sunrise over the ocean with slow dolly motion and golden haze',
    } as any);

    const handler = new VideoGenHandler();
    const result = await handler.execute(baseContext);

    expect(result.content).toBe(
      '📝 A cinematic sunrise over the ocean\n✨ A cinematic sunrise over the ocean with slow dolly motion and golden haze'
    );
    expect(result.attachments[0]?.enhancedPrompt).toBe(
      'A cinematic sunrise over the ocean with slow dolly motion and golden haze'
    );
  });

  it('surfaces extension metadata so it can be persisted into session history', async () => {
    vi.mocked(llmService.generateVideo).mockResolvedValue({
      url: 'https://cdn.example.com/video.mp4',
      mimeType: 'video/mp4',
      attachmentId: 'att-1',
      uploadStatus: 'completed',
      continuationStrategy: 'video_extension_chain',
      videoExtensionCount: 1,
      videoExtensionApplied: 1,
      totalDurationSeconds: 15,
      continuedFromVideo: true,
    } as any);

    const handler = new VideoGenHandler();
    const result = await handler.execute(baseContext);

    expect(result.continuationStrategy).toBe('video_extension_chain');
    expect(result.videoExtensionCount).toBe(1);
    expect(result.videoExtensionApplied).toBe(1);
    expect(result.totalDurationSeconds).toBe(15);
    expect(result.continuedFromVideo).toBe(true);
  });

  it('appends subtitle sidecar attachments returned by the backend', async () => {
    vi.mocked(llmService.generateVideo).mockResolvedValue({
      url: 'https://cdn.example.com/video.mp4',
      mimeType: 'video/mp4',
      attachmentId: 'att-video',
      uploadStatus: 'completed',
      sidecarFiles: [
        {
          kind: 'subtitle',
          mimeType: 'text/vtt',
          filename: 'generated.vtt',
          url: 'https://cdn.example.com/generated.vtt',
          attachmentId: 'att-vtt',
          uploadStatus: 'completed',
          language: 'zh-CN',
        },
      ],
    } as any);

    const handler = new VideoGenHandler();
    const result = await handler.execute(baseContext);

    expect(result.attachments).toHaveLength(2);
    expect(result.attachments[1]?.mimeType).toBe('text/vtt');
    expect(result.attachments[1]?.kind).toBe('subtitle');
    expect(result.attachments[1]?.language).toBe('zh-CN');
    expect(result.subtitleAttachmentIds).toEqual(['att-vtt']);
  });
});
