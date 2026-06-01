import { describe, expect, it } from 'vitest';
import { buildAttachmentMediaSignature } from './messageMediaSignature';
import type { Attachment } from '../types/types';

describe('messageMediaSignature', () => {
  it('tracks snake_case media fields from raw history attachments', () => {
    const baseAttachment = {
      id: 'att-snake-media',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-thumbnail',
    } as Attachment;

    const pendingSignature = buildAttachmentMediaSignature({
      ...baseAttachment,
      cloud_url: '',
      upload_status: 'pending',
    } as Attachment & { cloud_url?: string; upload_status?: string });

    const completedSignature = buildAttachmentMediaSignature({
      ...baseAttachment,
      cloud_url: '/api/storage/local-files/2026/06/01/result.png',
      upload_status: 'completed',
    } as Attachment & { cloud_url?: string; upload_status?: string });

    expect(completedSignature).not.toBe(pendingSignature);
    expect(completedSignature).toContain('/api/storage/local-files/2026/06/01/result.png');
    expect(completedSignature).toContain('completed');
  });
});
