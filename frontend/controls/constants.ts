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
