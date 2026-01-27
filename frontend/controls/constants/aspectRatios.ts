/**
 * 比例选项常量
 */

import { AspectRatioOption } from './types';

// 通用比例
export const GEN_ASPECT_RATIOS = [
  { label: "1:1 Square", value: "1:1" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
];

// Google 图像编辑比例
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

// OpenAI 比例
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

// 通义文生图专用比例（与官方分辨率映射一致）
export const TONGYI_GEN_ASPECT_RATIOS: AspectRatioOption[] = [
  { label: "1:1 Square", value: "1:1" },
  { label: "2:3 Portrait", value: "2:3" },
  { label: "3:2 Landscape", value: "3:2" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
  { label: "21:9 Ultrawide", value: "21:9" },
];

// z-image-turbo 专用比例（含特有比例 7:9, 9:7, 9:21）
export const Z_IMAGE_ASPECT_RATIOS: AspectRatioOption[] = [
  { label: "1:1 Square", value: "1:1" },
  { label: "2:3 Portrait", value: "2:3" },
  { label: "3:2 Landscape", value: "3:2" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "7:9 Portrait", value: "7:9" },
  { label: "9:7 Landscape", value: "9:7" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "9:21 Tall", value: "9:21" },
  { label: "16:9 Landscape", value: "16:9" },
  { label: "21:9 Ultrawide", value: "21:9" },
];

// wan2.6-image 专用比例（含极端比例 1:4, 4:1）
export const WAN26_IMAGE_ASPECT_RATIOS: AspectRatioOption[] = [
  { label: "1:1 Square", value: "1:1" },
  { label: "2:3 Portrait", value: "2:3" },
  { label: "3:2 Landscape", value: "3:2" },
  { label: "3:4 Portrait", value: "3:4" },
  { label: "4:3 Landscape", value: "4:3" },
  { label: "9:16 Portrait", value: "9:16" },
  { label: "16:9 Landscape", value: "16:9" },
  { label: "21:9 Ultrawide", value: "21:9" },
  { label: "1:4 Extreme Portrait", value: "1:4" },
  { label: "4:1 Extreme Landscape", value: "4:1" },
];

// Google 图片生成专用比例（10 种比例）
export const GOOGLE_GEN_ASPECT_RATIOS: AspectRatioOption[] = [
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

// 视频比例
export const VIDEO_ASPECT_RATIOS = [
  { label: "16:9 Landscape", value: "16:9" },
  { label: "9:16 Portrait", value: "9:16" },
];
