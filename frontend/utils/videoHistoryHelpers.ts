/**
 * VideoGenView 历史消息解析工具集。
 *
 * 1:1 抽离自 `components/views/VideoGenView.tsx` L58-150
 * （JIRA-frontend-view-decomposition.md P1 #4 Step 1）。
 *
 * 注意：ImageGenView / ImageExpandView 也有同名 extractHistoryPrompts，但返回类型
 * 与默认 fallback 文案不同（`enhancedPrompt` vs `optimizedPrompt`，"Generated Image Batch"
 * vs "Generated Video Batch"），不可合并。
 */

import type { Message } from '../types/types';

/**
 * 从 video 历史 Message 中提取原始 prompt + 优化 prompt。
 * 支持多种历史格式：
 * - 旧版："Video generated for: \"原文\""
 * - 双行：📝原文 \n ✨优化
 * - 单行：📝原文 或 ✨优化
 */
export const extractHistoryPrompts = (
  msg: Message
): { originalPrompt: string; optimizedPrompt: string } => {
  const rawContent = (msg.content || '').trim();
  const attachmentEnhancedPrompt = msg.attachments
    ?.find((att) => att.enhancedPrompt?.trim())
    ?.enhancedPrompt?.trim();

  let originalPrompt = rawContent;
  let optimizedPrompt = msg.enhancedPrompt?.trim() || attachmentEnhancedPrompt || '';

  const legacyPromptMatch = rawContent.match(/^Video generated for:\s*"([\s\S]*)"$/);
  if (legacyPromptMatch) {
    originalPrompt = (legacyPromptMatch[1] || '').trim();
  }

  const promptPairMatch = rawContent.match(/^📝\s*([\s\S]*?)(?:\n✨\s*([\s\S]*))?$/);
  if (promptPairMatch) {
    originalPrompt = (promptPairMatch[1] || '').trim();
    if (!optimizedPrompt && promptPairMatch[2]) {
      optimizedPrompt = promptPairMatch[2].trim();
    }
  } else {
    const originalOnlyMatch = rawContent.match(/^📝\s*([\s\S]*)$/);
    if (originalOnlyMatch) {
      originalPrompt = originalOnlyMatch[1].trim();
    }

    if (!optimizedPrompt) {
      const optimizedOnlyMatch = rawContent.match(/^✨\s*([\s\S]*)$/);
      if (optimizedOnlyMatch) {
        optimizedPrompt = optimizedOnlyMatch[1].trim();
      }
    }
  }

  return {
    originalPrompt: originalPrompt || 'Generated Video Batch',
    optimizedPrompt,
  };
};

/**
 * 从 video 历史 Message 中提取元数据（延长次数 / 总时长 / 策略标签 / 字幕信息）。
 * 用于历史卡片的小标签展示。
 */
export const extractVideoHistoryMeta = (
  msg: Message
): {
  extensionCount: number;
  totalDurationSeconds: number | null;
  strategyLabel: string | null;
  subtitleLabel: string | null;
  subtitleCount: number;
} => {
  const extensionCount = Number.isFinite(msg.videoExtensionApplied)
    ? Number(msg.videoExtensionApplied)
    : Number.isFinite(msg.videoExtensionCount)
      ? Number(msg.videoExtensionCount)
      : 0;
  const totalDurationSeconds = Number.isFinite(msg.totalDurationSeconds)
    ? Number(msg.totalDurationSeconds)
    : null;
  const continuationStrategy = String(msg.continuationStrategy || '').trim();

  let strategyLabel: string | null = null;
  if (continuationStrategy === 'video_extension_chain') {
    strategyLabel = '官方延长';
  } else if (continuationStrategy === 'last_frame_bridge_chain') {
    strategyLabel = '末帧桥接延长';
  } else if (continuationStrategy === 'video_extension') {
    strategyLabel = '视频续接';
  } else if (continuationStrategy === 'last_frame_bridge') {
    strategyLabel = '末帧桥接';
  }

  const subtitleMode = String(msg.subtitleMode || '')
    .trim()
    .toLowerCase();
  const subtitleCount = Array.isArray(msg.subtitleAttachmentIds)
    ? msg.subtitleAttachmentIds.length
    : 0;
  let subtitleLabel: string | null = null;
  if (subtitleMode === 'both' || subtitleMode === 'vtt' || subtitleMode === 'srt') {
    subtitleLabel = '字幕';
  } else if (subtitleCount > 0) {
    subtitleLabel = '字幕附件';
  }

  return {
    extensionCount: extensionCount > 0 ? extensionCount : 0,
    totalDurationSeconds,
    strategyLabel,
    subtitleLabel,
    subtitleCount,
  };
};
