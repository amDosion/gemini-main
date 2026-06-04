import { describe, expect, it } from 'vitest';
import { normalizeChatSession } from './sessionNormalizer';
import { Role } from '../types/types';

describe('normalizeChatSession', () => {
  it('normalizes history attachment fields at the session boundary (camelCase contract)', () => {
    // Backend session endpoints are guaranteed camelCase (always_convert_response),
    // so the normalizer's job is number coercion + durable-url recovery, not case
    // conversion.
    const rawSession = {
      id: 'session-attachments',
      title: 'History',
      mode: 'image-gen',
      createdAt: '1779624958194',
      messages: [
        {
          id: 'message-1',
          role: Role.MODEL,
          content: 'generated',
          timestamp: 1779624958194,
          attachments: [
            {
              id: 'attachment-1',
              name: 'result.png',
              mimeType: 'image/png',
              url: 'blob:https://gemini.dicry.cn:18443/stale-history-preview',
              cloudUrl: '/api/storage/local-files/2026/05/31/result.png',
              fileUri: '/api/storage/local-files/2026/05/31/result-file.png',
              tempUrl: 'https://temporary.example.com/result.png',
              uploadStatus: 'completed',
              uploadTaskId: 'upload-task-1',
              createdAt: '1779624958194',
            },
          ],
        },
      ],
    };
    const session = normalizeChatSession(
      rawSession as unknown as Parameters<typeof normalizeChatSession>[0]
    );

    expect(session.createdAt).toBe(1779624958194);
    expect(session.messages[0].attachments?.[0]).toMatchObject({
      id: 'attachment-1',
      mimeType: 'image/png',
      // stale blob preview is recovered to the durable cloud url
      url: '/api/storage/local-files/2026/05/31/result.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/result.png',
      fileUri: '/api/storage/local-files/2026/05/31/result-file.png',
      tempUrl: 'https://temporary.example.com/result.png',
      uploadStatus: 'completed',
      uploadTaskId: 'upload-task-1',
      createdAt: 1779624958194,
    });
  });

  it('keeps live temporary urls only when no durable storage url exists', () => {
    const session = normalizeChatSession({
      id: 'session-live-upload',
      mode: 'image-gen',
      messages: [
        {
          id: 'message-live-upload',
          role: Role.USER,
          content: 'uploading',
          attachments: [
            {
              id: 'attachment-live-upload',
              name: 'local.png',
              mimeType: 'image/png',
              url: 'blob:https://gemini.dicry.cn:18443/live-upload',
              uploadStatus: 'uploading',
            },
          ],
        },
      ],
    } as Parameters<typeof normalizeChatSession>[0]);

    expect(session.messages[0].attachments?.[0]).toMatchObject({
      id: 'attachment-live-upload',
      url: 'blob:https://gemini.dicry.cn:18443/live-upload',
      uploadStatus: 'uploading',
    });
  });
});
