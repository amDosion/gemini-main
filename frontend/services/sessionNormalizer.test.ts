import { describe, expect, it } from 'vitest';
import { normalizeChatSession } from './sessionNormalizer';
import { Role } from '../types/types';

describe('normalizeChatSession', () => {
  it('normalizes history attachment snake_case fields at the session boundary', () => {
    const rawSession = {
      id: 'session-snake-attachments',
      title: 'History',
      mode: 'image-gen',
      created_at: '1779624958194',
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
              mime_type: 'image/png',
              url: 'blob:https://gemini.dicry.cn:18443/stale-history-preview',
              cloud_url: '/api/storage/local-files/2026/05/31/result.png',
              file_uri: '/api/storage/local-files/2026/05/31/result-file.png',
              temp_url: 'https://temporary.example.com/result.png',
              upload_status: 'completed',
              upload_task_id: 'upload-task-1',
              created_at: '1779624958194',
            },
          ],
        },
      ],
    };
    const session = normalizeChatSession(rawSession as Parameters<typeof normalizeChatSession>[0]);

    expect(session.createdAt).toBe(1779624958194);
    expect(session.messages[0].attachments?.[0]).toMatchObject({
      id: 'attachment-1',
      mimeType: 'image/png',
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
              mime_type: 'image/png',
              url: 'blob:https://gemini.dicry.cn:18443/live-upload',
              upload_status: 'uploading',
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
