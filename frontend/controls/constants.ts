/**
 * Controls 模式参数控制常量定义
 */

// ============================================
// 类型定义
// ============================================

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
  '4:3': "1472*1140",
  '3:4': "1140*1472",
  '1:1': "1328*1328"
};

// Wan 图像编辑分辨率映射（wan2.6-image / wan2.5-i2i-preview）
// 官方文档: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference
// 规则: 总像素 [589824, 1638400] (768*768 至 1280*1280)，宽高比 [1:4, 4:1]
export const WAN_EDIT_RESOLUTIONS: Record<string, string> = {
  '1:1': "1280*1280",  // 或 1024*1024
  '2:3': "800*1200",
  '3:2': "1200*800",
  '3:4': "960*1280",
  '4:3': "1280*960",
  '9:16': "720*1280",
  '16:9': "1280*720",
  '21:9': "1344*576"
};

// ============================================
// 万相 V2 文生图分辨率映射 (wan2.x-t2i / wanx2.x-t2i / z-image)
// ============================================

// 官方文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2
// 总像素范围: [512*512, 2048*2048]
// 推荐范围: [1024*1024, 1536*1536]

// 通义万相 V2 文生图分辨率映射
// 官方文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2
// 总像素范围: [512*512, 2048*2048]，推荐范围: [1024*1024, 1536*1536]

// 1K 分辨率 (基准 1280×1280，官方推荐)
export const WAN_T2I_1K_RESOLUTIONS: Record<string, string> = {
  '1:1': "1280*1280",
  '2:3': "800*1200",
  '3:2': "1200*800",
  '3:4': "960*1280",
  '4:3': "1280*960",
  '9:16': "720*1280",
  '16:9': "1280*720",
  '21:9': "1344*576"
};

// 1.25K 分辨率 (基准 1440×1440) - 默认
export const WAN_T2I_1280_RESOLUTIONS: Record<string, string> = {
  '1:1': "1440*1440",
  '2:3': "900*1350",
  '3:2': "1350*900",
  '3:4': "1080*1440",
  '4:3': "1440*1080",
  '9:16': "810*1440",
  '16:9': "1440*810",
  '21:9': "1512*648"
};

// 1.5K 分辨率 (基准 1536×1536)
// 注意：此档位仅用于 z-image-turbo 模型（支持 [512*512, 2048*2048] 范围）
// wan2.6-t2i 模型不支持此档位（超出 1440*1440 上限）
export const WAN_T2I_1536_RESOLUTIONS: Record<string, string> = {
  '1:1': "1536*1536",
  '2:3': "960*1440",
  '3:2': "1440*960",
  '3:4': "1152*1536",
  '4:3': "1536*1152",
  '9:16': "864*1536",
  '16:9': "1536*864",
  '21:9': "1680*720"
};

// ============================================
// z-image-turbo 模型分辨率映射
// ============================================
// 官方文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2
// 总像素范围: [512*512, 2048*2048]
// 推荐范围: [1024*1024, 1536*1536]
// 特有比例: 7:9, 9:7, 9:21
// 支持 4 个分辨率档位: 1K, 1.25K, 1.5K, 2K
//
// 扩展说明:
// - 如需添加新比例，在所有 4 个档位映射中添加对应条目
// - 像素值需满足总像素范围限制
// - 建议保持宽高比精确匹配

// z-image-turbo 1K 分辨率 (基准 1024×1024 总像素)
export const Z_IMAGE_1K_RESOLUTIONS: Record<string, string> = {
  '1:1': "1024*1024",
  '2:3': "832*1248",
  '3:2': "1248*832",
  '3:4': "864*1152",
  '4:3': "1152*864",
  '7:9': "896*1152",
  '9:7': "1152*896",
  '9:16': "720*1280",
  '9:21': "576*1344",
  '16:9': "1280*720",
  '21:9': "1344*576"
};

// z-image-turbo 1.25K 分辨率 (基准 1280×1280 总像素)
export const Z_IMAGE_1280_RESOLUTIONS: Record<string, string> = {
  '1:1': "1280*1280",
  '2:3': "1024*1536",
  '3:2': "1536*1024",
  '3:4': "1104*1472",
  '4:3': "1472*1104",
  '7:9': "1120*1440",
  '9:7': "1440*1120",
  '9:16': "864*1536",
  '9:21': "720*1680",
  '16:9': "1536*864",
  '21:9': "1680*720"
};

// z-image-turbo 1.5K 分辨率 (基准 1536×1536 总像素，推荐)
export const Z_IMAGE_1536_RESOLUTIONS: Record<string, string> = {
  '1:1': "1536*1536",
  '2:3': "1248*1872",
  '3:2': "1872*1248",
  '3:4': "1296*1728",
  '4:3': "1728*1296",
  '7:9': "1344*1728",
  '9:7': "1728*1344",
  '9:16': "1152*2048",
  '9:21': "864*2016",
  '16:9': "2048*1152",
  '21:9': "2016*864"
};

// z-image-turbo 2K 分辨率 (基准 2048×2048 总像素，最大)
export const Z_IMAGE_2K_RESOLUTIONS: Record<string, string> = {
  '1:1': "2048*2048",
  '2:3': "1664*2496",
  '3:2': "2496*1664",
  '3:4': "1728*2304",
  '4:3': "2304*1728",
  '7:9': "1792*2304",
  '9:7': "2304*1792",
  '9:16': "1536*2730",
  '9:21': "1152*2688",
  '16:9': "2730*1536",
  '21:9': "2688*1152"
};

// ============================================
// wan2.6-image 模型分辨率映射 (图像编辑模式)
// ============================================
// 官方文档: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference
// 总像素范围: [589824, 1638400] (768×768 至 1280×1280)
// 宽高比范围: [1:4, 4:1]
// 单档位配置，无分辨率档位选择
//
// 扩展说明:
// - 如需添加新比例，确保总像素在范围内
// - 宽高比必须在 [1:4, 4:1] 范围内
// - 极端比例 (1:4, 4:1) 用于特殊场景

export const WAN26_IMAGE_RESOLUTIONS: Record<string, string> = {
  '1:1': "1280*1280",
  '2:3': "800*1200",
  '3:2': "1200*800",
  '3:4': "960*1280",
  '4:3': "1280*960",
  '9:16': "720*1280",
  '16:9': "1280*720",
  '21:9': "1344*576",
  '1:4': "640*2560",   // 极端竖向比例
  '4:1': "2560*640"    // 极端横向比例
};

// ============================================
// Google 图片生成分辨率映射
// ============================================
// Google GenAI Imagen 模型分辨率配置
// 支持 10 种比例 × 3 个分辨率档位 (1K, 2K, 4K)
//
// 扩展说明:
// - 如需添加新比例，在所有 3 个档位映射中添加对应条目
// - 像素值按比例计算，保持总像素与基准一致
// - 1K 基准: 1024×1024, 2K 基准: 2048×2048, 4K 基准: 4096×4096

// Google 1K 分辨率 (基准 1024×1024)
export const GOOGLE_GEN_1K_RESOLUTIONS: Record<string, string> = {
  '1:1': "1024*1024",
  '2:3': "682*1024",
  '3:2': "1024*682",
  '3:4': "768*1024",
  '4:3': "1024*768",
  '4:5': "819*1024",
  '5:4': "1024*819",
  '9:16': "576*1024",
  '16:9': "1024*576",
  '21:9': "1024*438"
};

// Google 2K 分辨率 (基准 2048×2048)
export const GOOGLE_GEN_2K_RESOLUTIONS: Record<string, string> = {
  '1:1': "2048*2048",
  '2:3': "1365*2048",
  '3:2': "2048*1365",
  '3:4': "1536*2048",
  '4:3': "2048*1536",
  '4:5': "1638*2048",
  '5:4': "2048*1638",
  '9:16': "1152*2048",
  '16:9': "2048*1152",
  '21:9': "2048*877"
};

// Google 4K 分辨率 (基准 4096×4096)
// 注意：此映射表保留供未来使用，当前 Google Imagen API 官方文档仅支持最大 2K 分辨率
// 4K 选项已从 GOOGLE_GEN_RESOLUTION_TIERS 中移除
export const GOOGLE_GEN_4K_RESOLUTIONS: Record<string, string> = {
  '1:1': "4096*4096",
  '2:3': "2730*4096",
  '3:2': "4096*2730",
  '3:4': "3072*4096",
  '4:3': "4096*3072",
  '4:5': "3276*4096",
  '5:4': "4096*3276",
  '9:16': "2304*4096",
  '16:9': "4096*2304",
  '21:9': "4096*1755"
};

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

// ============================================
// 分辨率档位选项配置
// ============================================
// 每个提供商/模型的分辨率档位选项
// 扩展说明:
// - 添加新档位时，同时更新对应的分辨率映射表
// - baseResolution 用于在 UI 中显示基准分辨率

// 通义 wan2.x-t2i 系列分辨率档位（2 档位）
// 官方文档限制：总像素 [768*768, 1440*1440]，即最大 2,073,600 像素
// 1536*1536 = 2,359,296 像素，超出限制，不支持
export const TONGYI_GEN_RESOLUTION_TIERS: ResolutionTierOption[] = [
  { label: "1K (1280×1280 base)", value: "1K", baseResolution: "1280×1280" },
  { label: "1.25K (1440×1440 base)", value: "1.25K", baseResolution: "1440×1440" },
];

// z-image-turbo 分辨率档位（4 档位，含 2K）
export const Z_IMAGE_RESOLUTION_TIERS: ResolutionTierOption[] = [
  { label: "1K (1024×1024 base)", value: "1K", baseResolution: "1024×1024" },
  { label: "1.25K (1280×1280 base)", value: "1.25K", baseResolution: "1280×1280" },
  { label: "1.5K (1536×1536 base)", value: "1.5K", baseResolution: "1536×1536" },
  { label: "2K (2048×2048 base)", value: "2K", baseResolution: "2048×2048" },
];

// Google 分辨率档位（2 档位）
// 注意：4K 档位已移除 - Google Imagen API 官方文档仅支持最大 2K 分辨率
export const GOOGLE_GEN_RESOLUTION_TIERS: ResolutionTierOption[] = [
  { label: "1K Standard (1024×1024 base)", value: "1K", baseResolution: "1024×1024" },
  { label: "2K High (2048×2048 base)", value: "2K", baseResolution: "2048×2048" },
];

// 通义文生图分辨率选项（旧版，保留兼容）
export const TONGYI_GEN_RESOLUTIONS = [
  { label: "1K (1024×1024)", value: "1K" },
  { label: "1.25K (1280×1280)", value: "1.25K" },
  { label: "1.5K (1536×1536)", value: "1.5K" },
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
  // Google Imagen 高级参数默认值
  // guidanceScale 已移除 - 官方文档未记录此参数
  // personGeneration 已移除 - 使用 API 默认值 (allow_adult)
  outputMimeType: "image/png",
  outputCompressionQuality: 80,
  enhancePrompt: false,
};

// ============================================
// 辅助函数
// ============================================
// 这些函数用于动态获取比例和分辨率配置
// UI 组件应使用这些函数而非直接访问映射表
//
// 扩展说明:
// - 添加新模型时，在 getResolutionMap() 中添加对应分支
// - 添加新比例时，更新对应的 ASPECT_RATIOS 数组
// - 添加新档位时，更新对应的 RESOLUTION_TIERS 数组

/**
 * 获取指定模型的分辨率映射表
 * @param provider 提供商: 'tongyi' | 'google'
 * @param modelId 模型ID（通义提供商需要）
 * @param tier 分辨率档位
 * @returns 分辨率映射表
 */
function getResolutionMap(
  provider: 'tongyi' | 'google',
  modelId: string | undefined,
  tier: string
): Record<string, string> {
  if (provider === 'google') {
    // 注意：4K 档位已移除 - Google Imagen API 官方文档仅支持最大 2K 分辨率
    switch (tier) {
      case '1K': return GOOGLE_GEN_1K_RESOLUTIONS;
      case '2K': return GOOGLE_GEN_2K_RESOLUTIONS;
      default: return GOOGLE_GEN_1K_RESOLUTIONS;
    }
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    switch (tier) {
      case '1K': return Z_IMAGE_1K_RESOLUTIONS;
      case '1.25K': return Z_IMAGE_1280_RESOLUTIONS;
      case '1.5K': return Z_IMAGE_1536_RESOLUTIONS;
      case '2K': return Z_IMAGE_2K_RESOLUTIONS;
      default: return Z_IMAGE_1280_RESOLUTIONS;
    }
  }

  if (modelId?.includes('wan2.6-image')) {
    return WAN26_IMAGE_RESOLUTIONS;
  }

  // wan2.x-t2i 系列模型（默认）
  switch (tier) {
    case '1K': return WAN_T2I_1K_RESOLUTIONS;
    case '1.25K': return WAN_T2I_1280_RESOLUTIONS;
    case '1.5K': return WAN_T2I_1536_RESOLUTIONS;
    default: return WAN_T2I_1280_RESOLUTIONS;
  }
}

/**
 * 获取像素分辨率
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商，如 "tongyi" | "google"
 * @param modelId 模型ID（可选，用于通义提供商区分模型）
 * @returns 像素分辨率，如 "1280*1280"；如果找不到则返回默认值
 * 
 * @example
 * getPixelResolution('1:1', '1K', 'tongyi', 'wan2.6-t2i') // "1280*1280"
 * getPixelResolution('16:9', '2K', 'google') // "2048*1152"
 */
export function getPixelResolution(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string {
  const resolutionMap = getResolutionMap(provider, modelId, tier);
  return resolutionMap[aspectRatio] || resolutionMap['1:1'] || '1024*1024';
}

/**
 * 获取带像素分辨率的比例标签
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 标签，如 "1:1 (1280×1280)"
 * 
 * @example
 * getAspectRatioLabel('1:1', '1K', 'tongyi', 'wan2.6-t2i') // "1:1 (1280×1280)"
 * getAspectRatioLabel('16:9', '2K', 'google') // "16:9 (2048×1152)"
 */
export function getAspectRatioLabel(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string {
  const pixelRes = getPixelResolution(aspectRatio, tier, provider, modelId);
  // 将 "1280*1280" 格式转换为 "1280×1280" 格式
  const formattedRes = pixelRes.replace('*', '×');
  return `${aspectRatio} (${formattedRes})`;
}

/**
 * 获取指定提供商和模型的可用比例列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 比例选项数组
 * 
 * @example
 * getAvailableAspectRatios('google') // 返回 Google 支持的 10 种比例
 * getAvailableAspectRatios('tongyi', 'z-image-turbo') // 返回 z-image-turbo 支持的 11 种比例
 */
export function getAvailableAspectRatios(
  provider: 'tongyi' | 'google',
  modelId?: string
): AspectRatioOption[] {
  if (provider === 'google') {
    return GOOGLE_GEN_ASPECT_RATIOS;
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    return Z_IMAGE_ASPECT_RATIOS;
  }

  if (modelId?.includes('wan2.6-image')) {
    return WAN26_IMAGE_ASPECT_RATIOS;
  }

  // wan2.x-t2i 系列模型（默认）
  return TONGYI_GEN_ASPECT_RATIOS;
}

/**
 * 获取指定提供商和模型的可用分辨率档位列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 分辨率档位选项数组
 * 
 * @example
 * getAvailableResolutionTiers('google') // 返回 [1K, 2K, 4K]
 * getAvailableResolutionTiers('tongyi', 'z-image-turbo') // 返回 [1K, 1.25K, 1.5K, 2K]
 */
export function getAvailableResolutionTiers(
  provider: 'tongyi' | 'google',
  modelId?: string
): ResolutionTierOption[] {
  if (provider === 'google') {
    return GOOGLE_GEN_RESOLUTION_TIERS;
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    return Z_IMAGE_RESOLUTION_TIERS;
  }

  if (modelId?.includes('wan2.6-image')) {
    // wan2.6-image 只有单档位，返回空数组表示不显示档位选择器
    return [];
  }

  // wan2.x-t2i 系列模型（默认）
  return TONGYI_GEN_RESOLUTION_TIERS;
}
