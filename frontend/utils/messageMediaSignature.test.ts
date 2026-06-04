import { describe, expect, it } from 'vitest';
import { buildAttachmentMediaSignature } from './messageMediaSignature';
import type { Attachment } from '../types/types';

describe('messageMediaSignature', () => {
  it('tracks camelCase media fields (attachments reach the frontend camelCase-only)', () => {
    // The case-conversion middleware delivers every attachment camelCase; there is no
    // snake_case attachment source anymore, so the signature tracks camelCase fields.
    const baseAttachment = {
      id: 'att-media',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-thumbnail',
    } as Attachment;

    const pendingSignature = buildAttachmentMediaSignature({
      ...baseAttachment,
      cloudUrl: '',
      uploadStatus: 'pending',
    } as Attachment);

    const completedSignature = buildAttachmentMediaSignature({
      ...baseAttachment,
      cloudUrl: '/api/storage/local-files/2026/06/01/result.png',
      uploadStatus: 'completed',
    } as Attachment);

    expect(completedSignature).not.toBe(pendingSignature);
    expect(completedSignature).toContain('/api/storage/local-files/2026/06/01/result.png');
    expect(completedSignature).toContain('completed');
  });
});
