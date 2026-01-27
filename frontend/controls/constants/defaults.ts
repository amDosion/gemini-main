/**
 * 默认值常量
 */

// 图片数量选项（试衣生成数量、文生图数量等共用）
export const IMAGE_COUNTS = [1, 2, 3, 4] as const;

/** 输出格式选项（试衣、Imagen 等共用） */
export const OUTPUT_MIME_OPTIONS = [
  { value: 'image/png' as const, label: 'PNG' },
  { value: 'image/jpeg' as const, label: 'JPEG' },
] as const;

// 默认控件值
export const DEFAULT_CONTROLS = {
  aspectRatio: "1:1",
  resolution: "1K",
  numberOfImages: 1,
  style: "None",
  voice: "Puck",
  scaleFactor: 2.0,
  seed: -1,
  negativePrompt: "",
  pdfTemplate: "invoice",
  pdfAdditionalInstructions: "",
  outPaintingMode: "scale" as const,
  offsetPixels: { left: 0, right: 0, top: 0, bottom: 0 },
  // Google Imagen 高级参数默认值
  // guidanceScale 已移除 - 官方文档未记录此参数
  // personGeneration 已移除 - 使用 API 默认值 (allow_adult)
  outputMimeType: "image/png",
  outputCompressionQuality: 80,
  enhancePrompt: false,
};
