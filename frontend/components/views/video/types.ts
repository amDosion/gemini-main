/**
 * VideoGenView 子组件共享类型。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L63-72（ActionMenuAnchor / HoverPromptPreview）。
 */

import type { HoverPromptPreviewBase } from '../../../hooks/useHoverPromptPreview';
import type { ActionMenuAnchorBase } from '../../../hooks/useActionMenu';

export type ActionMenuAnchor = ActionMenuAnchorBase;

// 扩展 HoverPromptPreviewBase 添加 view 特有元数据（视频时长 / 策略标签 / 字幕等）
export interface HoverPromptPreview extends HoverPromptPreviewBase {
  extensionCount: number;
  totalDurationSeconds: number | null;
  strategyLabel: string | null;
  subtitleLabel: string | null;
  subtitleCount: number;
}
