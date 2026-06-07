import { describe, it, expect } from 'vitest';
import { extractImageHistoryPrompts } from './imageHistorySidebarHelpers';
import { Role, type Message, type Attachment } from '../../types/types';

const makeMessage = (overrides: Partial<Message>): Message => ({
  id: 'm1',
  role: Role.MODEL,
  content: '',
  timestamp: 0,
  ...overrides,
});

const makeAttachment = (overrides: Partial<Attachment>): Attachment =>
  ({ id: 'a1', ...overrides }) as Attachment;

describe('extractImageHistoryPrompts', () => {
  describe('default behavior (no options) — backward compatible', () => {
    it('splits a 📝/✨ prompt pair into original and enhanced parts', () => {
      const message = makeMessage({ content: '📝 a cat\n✨ a fluffy orange cat' });

      expect(extractImageHistoryPrompts(message)).toEqual({
        originalPrompt: 'a cat',
        enhancedPrompt: 'a fluffy orange cat',
      });
    });

    it('prefers message.enhancedPrompt over the ✨ segment', () => {
      const message = makeMessage({
        content: '📝 a cat\n✨ ignored',
        enhancedPrompt: 'preferred enhanced',
      });

      expect(extractImageHistoryPrompts(message)).toEqual({
        originalPrompt: 'a cat',
        enhancedPrompt: 'preferred enhanced',
      });
    });

    it('uses role-based fallback when content is empty', () => {
      expect(extractImageHistoryPrompts(makeMessage({ role: Role.MODEL })).originalPrompt).toBe(
        '模型响应'
      );
      expect(extractImageHistoryPrompts(makeMessage({ role: Role.USER })).originalPrompt).toBe(
        '用户消息'
      );
    });

    it('does NOT read attachment enhancedPrompt by default', () => {
      const message = makeMessage({
        content: 'plain prompt',
        attachments: [makeAttachment({ enhancedPrompt: 'attachment enhanced' })],
      });

      expect(extractImageHistoryPrompts(message).enhancedPrompt).toBe('');
    });

    it('does NOT recognize a ✨-only message by default', () => {
      const message = makeMessage({ content: '✨ only optimized' });

      // No 📝 pair → original stays as raw content, enhanced stays empty.
      expect(extractImageHistoryPrompts(message)).toEqual({
        originalPrompt: '✨ only optimized',
        enhancedPrompt: '',
      });
    });
  });

  describe('ImageGenView option combination', () => {
    const genOptions = {
      fallbackLabel: 'Generated Image Batch',
      includeAttachmentEnhanced: true,
      matchOptimizedOnly: true,
    };

    it('applies the custom fallback label for empty content', () => {
      expect(extractImageHistoryPrompts(makeMessage({}), genOptions).originalPrompt).toBe(
        'Generated Image Batch'
      );
    });

    it('falls back to an attachment-level enhancedPrompt when message has none', () => {
      const message = makeMessage({
        content: 'plain prompt',
        attachments: [
          makeAttachment({ id: 'a1', enhancedPrompt: '   ' }),
          makeAttachment({ id: 'a2', enhancedPrompt: 'from attachment' }),
        ],
      });

      expect(extractImageHistoryPrompts(message, genOptions)).toEqual({
        originalPrompt: 'plain prompt',
        enhancedPrompt: 'from attachment',
      });
    });

    it('recognizes a ✨-only optimized prompt (original text stays as the prompt)', () => {
      const message = makeMessage({ content: '✨ only optimized' });

      // The ✨-only branch fills enhancedPrompt but leaves originalPrompt as the
      // raw content (non-empty), so the fallback label does not apply here.
      expect(extractImageHistoryPrompts(message, genOptions)).toEqual({
        originalPrompt: '✨ only optimized',
        enhancedPrompt: 'only optimized',
      });
    });

    it('still prefers the 📝/✨ pair when present', () => {
      const message = makeMessage({ content: '📝 a cat\n✨ a fluffy cat' });

      expect(extractImageHistoryPrompts(message, genOptions)).toEqual({
        originalPrompt: 'a cat',
        enhancedPrompt: 'a fluffy cat',
      });
    });
  });
});
