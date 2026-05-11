/**
 * Mask 编辑共享 types / constants / helpers。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx` L66-101（JIRA-frontend-view-decomposition.md P0 #2 Step 1）。
 * 被后续 MaskCanvasPainter / MaskToolbar / useMaskIO / useMaskSegmentation 共同依赖；
 * 提前抽出避免子模块拆分时产生循环依赖或重复定义。
 */

// Mask 工具类型（增加 move 用于拖动图片）
export type MaskTool = 'move' | 'select' | 'brush' | 'eraser';

// 选区矩形（mask 编辑器画布上的多选区域）
export interface SelectionRect {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}

// Mask 模式（对应 Vertex AI MaskReferenceConfig.mask_mode）
export type MaskMode =
  | 'MASK_MODE_USER_PROVIDED' // 用户提供遮罩（手动绘制）
  | 'MASK_MODE_BACKGROUND' // 自动检测背景
  | 'MASK_MODE_FOREGROUND' // 自动检测前景
  | 'MASK_MODE_SEMANTIC'; // 语义分割（人物等）

export const SEMANTIC_PERSON_CLASS_ID = 125;

export const getMaskModeDisplayLabel = (mode: MaskMode): string => {
  switch (mode) {
    case 'MASK_MODE_BACKGROUND':
      return '自动背景';
    case 'MASK_MODE_FOREGROUND':
      return '自动前景';
    case 'MASK_MODE_SEMANTIC':
      return '人物分割';
    case 'MASK_MODE_USER_PROVIDED':
    default:
      return '手动 Mask';
  }
};

export const isMaskPreviewAccessDenied = (message: string): boolean => {
  return (
    /image-segmentation-001/i.test(message) &&
    /model access denied|request access|404/i.test(message)
  );
};

export const getMaskPreviewUnavailableMessage = (mode: MaskMode): string => {
  return `${getMaskModeDisplayLabel(mode)} Mask 预览模型未开通；生成请求会直接使用官方 Mask 编辑，不依赖该预览模型`;
};
