/**
 * Controls 模式参数控制常量定义
 */

// ============================================
// Aspect Ratios
// ============================================

export const GEN_ASPECT_RATIOS = [
  { label: "1:1 Square", value: "1:1" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
];

export const GOOGLE_EDIT_ASPECT_RATIOS = [
  { label: "1:1 Square", value: "1:1" },
  { label: "2:3 Portrait", value: "2:3" },
  { label: "3:2 Landscape", value: "3:2" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "4:5 Portrait", value: "4:5" },
  { label: "5:4 Landscape", value: "5:4" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
  { label: "21:9 Ultrawide", value: "21:9" },
];

export const OPENAI_ASPECT_RATIOS = [
  { label: "1:1 Square", value: "1:1" },
  { label: "Portrait (1024x1792)", value: "9:16" },
  { label: "Landscape (1792x1024)", value: "16:9" },
];

// 通义图像编辑专用比例（完整支持 Wan2.6/Wan2.5 所有官方推荐比例）
export const TONGYI_EDIT_ASPECT_RATIOS = [
  { label: "1:1 Square", value: "1:1" },
  { label: "2:3 Portrait", value: "2:3" },
  { label: "3:2 Landscape", value: "3:2" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
  { label: "21:9 Ultrawide", value: "21:9" },
];

// ============================================
// Image Edit Resolution Mappings
// ============================================

// Qwen Image Edit 分辨率映射（固定的5种）
export const QWEN_EDIT_RESOLUTIONS: Record<string, string> = {
  '16:9': "1664*928",
  '9:16': "928*1664",
  '4:3':  "1472*1140",
  '3:4':  "1140*1472",
  '1:1':  "1328*1328"
};

// Wan 图像编辑分辨率映射（wan2.6-image / wan2.5-i2i-preview）
// 官方文档: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference
// 规则: 总像素 [589824, 1638400] (768*768 至 1280*1280)，宽高比 [1:4, 4:1]
export const WAN_EDIT_RESOLUTIONS: Record<string, string> = {
  '1:1':  "1280*1280",  // 或 1024*1024
  '2:3':  "800*1200",
  '3:2':  "1200*800",
  '3:4':  "960*1280",
  '4:3':  "1280*960",
  '9:16': "720*1280",
  '16:9': "1280*720",
  '21:9': "1344*576"
};

export const VIDEO_ASPECT_RATIOS = [
  { label: "16:9 Landscape", value: "16:9" },
  { label: "9:16 Portrait", value: "9:16" },
];


// ============================================
// Styles
// ============================================

export const STYLES = [
  { label: "No Style", value: "None" },
  { label: "Photorealistic", value: "Photorealistic" },
  { label: "Anime", value: "Anime" },
  { label: "Digital Art", value: "Digital Art" },
  { label: "Oil Painting", value: "Oil Painting" },
  { label: "Cyberpunk", value: "Cyberpunk" },
  { label: "Watercolor", value: "Watercolor" },
];

// ============================================
// Voices (Audio Generation)
// ============================================

export const VOICES = [
  { label: "Puck", value: "Puck" },
  { label: "Charon", value: "Charon" },
  { label: "Kore", value: "Kore" },
  { label: "Fenrir", value: "Fenrir" },
  { label: "Aoede", value: "Aoede" },
];

// ============================================
// Resolution Options
// ============================================

export const RESOLUTIONS = [
  { label: "1K Standard", value: "1K" },
  { label: "2K High", value: "2K" },
  { label: "4K Ultra", value: "4K" },
];

export const VIDEO_RESOLUTIONS = [
  { label: "720p (HD)", value: "1K" },
  { label: "1080p (FHD)", value: "2K" },
];

// ============================================
// Image Count Options
// ============================================

export const IMAGE_COUNTS = [1, 2, 3, 4];

// ============================================
// Default Values
// ============================================

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
};
