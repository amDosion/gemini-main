/**
 * 虚拟试衣模式专用常量
 * 
 * 官方支持的配置参数（来源: docs/virtual_try_on_sdk_usage_zh.md）:
 * - number_of_images: 生成数量 (1-4) - 用户可选
 * - base_steps: 质量步数（数值越高质量越好、延迟越高）- 用户可选
 * - output_mime_type: 固定 image/jpeg（不提供 UI）
 * - output_compression_quality: 固定 100（不提供 UI）
 * - seed: 随机种子
 * 
 * 注意: CLOTHING_TYPES (上装/下装/全身) 不是官方 Virtual Try-On API 支持的参数
 */

/** Base Steps 滑块配置（质量/速度权衡）- 用户可选 */
export const BASE_STEPS_CONFIG = {
  min: 8,
  max: 48,
  step: 8,
  default: 32,
} as const;

/** Virtual Try-On 默认值 */
export const TRYON_DEFAULTS = {
  /** 默认 Base Steps（高质量）- 用户可选 */
  baseSteps: BASE_STEPS_CONFIG.default,
  /** 默认生成数量 - 用户可选 */
  numberOfImages: 1,
};
