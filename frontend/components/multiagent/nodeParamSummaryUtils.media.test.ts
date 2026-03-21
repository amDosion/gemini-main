import { describe, expect, it } from 'vitest';
import { buildNodeParamChipItems } from './nodeParamSummaryUtils';

describe('nodeParamSummaryUtils media support', () => {
  it('summarizes video task nodes without degrading the task type', () => {
    const chips = buildNodeParamChipItems({
      type: 'agent',
      agentTaskType: 'video_generation',
      agentVideoDurationSeconds: 8,
    }).map((item) => item.text);

    expect(chips).toContain('任务: video-gen');
    expect(chips).toContain('视频时长: 8');
    expect(chips).toContain('分辨率: 720p');
  });

  it('summarizes audio input nodes using the bounded audio field labels', () => {
    const chips = buildNodeParamChipItems({
      type: 'input_audio',
      startAudioUrls: ['audio.mp3'],
    }).map((item) => item.text);

    expect(chips).toContain('音频输入列表: audio.mp3');
  });
});
