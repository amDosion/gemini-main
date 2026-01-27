/**
 * Controls 常量类型定义
 */

/** 比例选项接口 */
export interface AspectRatioOption {
  label: string;      // 显示标签，如 "1:1 Square"
  value: string;      // 比例值，如 "1:1"
}

/** 分辨率档位选项接口 */
export interface ResolutionTierOption {
  label: string;      // 显示标签，如 "1K (1280×1280 base)"
  value: string;      // 档位值，如 "1K"
  baseResolution: string; // 基准分辨率，如 "1280×1280"
}
