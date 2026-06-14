import { describe, expect, it } from 'vitest';
import { filterModelImageBatches, isPlaceholderMessage } from './messageFilters';
import { Attachment, Message, Role } from '../types/types';

const attachment: Attachment = {
  id: 'attachment-1',
  mimeType: 'image/png',
  name: 'result.png',
};

const message = (overrides: Partial<Message>): Message => ({
  id: 'message',
  role: Role.MODEL,
  content: '',
  timestamp: 1,
  ...overrides,
});

describe('messageFilters', () => {
  describe('isPlaceholderMessage', () => {
    it('returns true for an empty non-error message without attachments', () => {
      expect(isPlaceholderMessage(message({ id: 'empty' }))).toBe(true);
    });

    it('returns false when content is present', () => {
      expect(isPlaceholderMessage(message({ id: 'content', content: 'hello' }))).toBe(false);
    });

    it('returns false when attachments are present', () => {
      expect(isPlaceholderMessage(message({ id: 'attachment', attachments: [attachment] }))).toBe(
        false
      );
    });

    it('returns false when the message is an error', () => {
      expect(isPlaceholderMessage(message({ id: 'error', isError: true }))).toBe(false);
    });
  });

  describe('filterModelImageBatches', () => {
    it('keeps model messages with attachments or errors and returns latest first', () => {
      const modelWithAttachment = message({
        id: 'model-with-attachment',
        attachments: [attachment],
        timestamp: 1,
      });
      const userWithAttachment = message({
        id: 'user-with-attachment',
        role: Role.USER,
        attachments: [attachment],
        timestamp: 2,
      });
      const modelWithoutAttachment = message({
        id: 'model-without-attachment',
        timestamp: 3,
      });
      const modelError = message({
        id: 'model-error',
        isError: true,
        timestamp: 4,
      });

      expect(
        filterModelImageBatches([
          modelWithAttachment,
          userWithAttachment,
          modelWithoutAttachment,
          modelError,
        ]).map((filteredMessage) => filteredMessage.id)
      ).toEqual(['model-error', 'model-with-attachment']);
    });
  });
});
