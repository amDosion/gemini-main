/**
 * constants.ts 辅助函数单元测试
 * 测试分辨率映射和比例选项获取功能
 */
import { describe, it, expect } from 'vitest';
import {
  getPixelResolution,
  getAspectRatioLabel,
  getAvailableAspectRatios,
  getAvailableResolutionTiers,
  TONGYI_GEN_ASPECT_RATIOS,
  Z_IMAGE_ASPECT_RATIOS,
  WAN26_IMAGE_ASPECT_RATIOS,
  GOOGLE_GEN_ASPECT_RATIOS,
  TONGYI_GEN_RESOLUTION_TIERS,
  Z_IMAGE_RESOLUTION_TIERS,
  GOOGLE_GEN_RESOLUTION_TIERS
} from './constants';

describe('getPixelResolution', () => {
  describe('通义 wan2.x-t2i 模型', () => {
    it('应返回 1K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '1K', 'tongyi', 'wan2.6-t2i')).toBe('1280*1280');
      expect(getPixelResolution('16:9', '1K', 'tongyi', 'wan2.6-t2i')).toBe('1280*720');
      expect(getPixelResolution('9:16', '1K', 'tongyi', 'wan2.6-t2i')).toBe('720*1280');
    });

    it('应返回 1.25K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '1.25K', 'tongyi', 'wan2.6-t2i')).toBe('1440*1440');
      expect(getPixelResolution('16:9', '1.25K', 'tongyi', 'wan2.6-t2i')).toBe('1440*810');
    });
  });

  describe('通义 z-image-turbo 模型', () => {
    it('应返回 1K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '1K', 'tongyi', 'z-image-turbo')).toBe('1024*1024');
      expect(getPixelResolution('7:9', '1K', 'tongyi', 'z-image-turbo')).toBe('896*1152');
      expect(getPixelResolution('9:21', '1K', 'tongyi', 'z-image-turbo')).toBe('576*1344');
    });

    it('应返回 2K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '2K', 'tongyi', 'z-image-turbo')).toBe('2048*2048');
      expect(getPixelResolution('16:9', '2K', 'tongyi', 'z-image-turbo')).toBe('2730*1536');
    });

    it('应支持特有比例 7:9, 9:7, 9:21', () => {
      expect(getPixelResolution('7:9', '1.5K', 'tongyi', 'z-image-turbo')).toBe('1344*1728');
      expect(getPixelResolution('9:7', '1.5K', 'tongyi', 'z-image-turbo')).toBe('1728*1344');
      expect(getPixelResolution('9:21', '1.5K', 'tongyi', 'z-image-turbo')).toBe('864*2016');
    });
  });

  describe('通义 wan2.6-image 模型', () => {
    it('应返回单档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '1K', 'tongyi', 'wan2.6-image')).toBe('1280*1280');
      expect(getPixelResolution('1:4', '1K', 'tongyi', 'wan2.6-image')).toBe('640*2560');
      expect(getPixelResolution('4:1', '1K', 'tongyi', 'wan2.6-image')).toBe('2560*640');
    });
  });

  describe('Google 提供商', () => {
    it('应返回 1K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '1K', 'google')).toBe('1024*1024');
      expect(getPixelResolution('16:9', '1K', 'google')).toBe('1024*576');
    });

    it('应返回 2K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '2K', 'google')).toBe('2048*2048');
      expect(getPixelResolution('4:5', '2K', 'google')).toBe('1638*2048');
    });

    it('应返回 4K 档位的正确分辨率', () => {
      expect(getPixelResolution('1:1', '4K', 'google')).toBe('4096*4096');
      expect(getPixelResolution('21:9', '4K', 'google')).toBe('4096*1755');
    });
  });

  describe('边界条件', () => {
    it('无效比例应返回默认值', () => {
      const result = getPixelResolution('invalid', '1K', 'tongyi', 'wan2.6-t2i');
      expect(result).toBe('1280*1280'); // 默认 1:1
    });

    it('无效档位应返回默认档位', () => {
      const result = getPixelResolution('1:1', 'invalid', 'tongyi', 'wan2.6-t2i');
      expect(result).toBeTruthy();
    });
  });
});

describe('getAspectRatioLabel', () => {
  it('应返回带像素分辨率的标签', () => {
    expect(getAspectRatioLabel('1:1', '1K', 'tongyi', 'wan2.6-t2i')).toBe('1:1 (1280×1280)');
    expect(getAspectRatioLabel('16:9', '2K', 'google')).toBe('16:9 (2048×1152)');
  });

  it('应正确转换 * 为 ×', () => {
    const label = getAspectRatioLabel('1:1', '1K', 'google');
    expect(label).toContain('×');
    expect(label).not.toContain('*');
  });
});

describe('getAvailableAspectRatios', () => {
  it('通义 wan2.x-t2i 应返回 8 种比例', () => {
    const ratios = getAvailableAspectRatios('tongyi', 'wan2.6-t2i');
    expect(ratios).toEqual(TONGYI_GEN_ASPECT_RATIOS);
    expect(ratios.length).toBe(8);
  });

  it('通义 z-image-turbo 应返回 11 种比例', () => {
    const ratios = getAvailableAspectRatios('tongyi', 'z-image-turbo');
    expect(ratios).toEqual(Z_IMAGE_ASPECT_RATIOS);
    expect(ratios.length).toBe(11);
    // 验证特有比例
    expect(ratios.some(r => r.value === '7:9')).toBe(true);
    expect(ratios.some(r => r.value === '9:7')).toBe(true);
    expect(ratios.some(r => r.value === '9:21')).toBe(true);
  });

  it('通义 wan2.6-image 应返回 10 种比例', () => {
    const ratios = getAvailableAspectRatios('tongyi', 'wan2.6-image');
    expect(ratios).toEqual(WAN26_IMAGE_ASPECT_RATIOS);
    expect(ratios.length).toBe(10);
    // 验证极端比例
    expect(ratios.some(r => r.value === '1:4')).toBe(true);
    expect(ratios.some(r => r.value === '4:1')).toBe(true);
  });

  it('Google 应返回 10 种比例', () => {
    const ratios = getAvailableAspectRatios('google');
    expect(ratios).toEqual(GOOGLE_GEN_ASPECT_RATIOS);
    expect(ratios.length).toBe(10);
  });
});

describe('getAvailableResolutionTiers', () => {
  it('通义 wan2.x-t2i 应返回 2 个档位', () => {
    const tiers = getAvailableResolutionTiers('tongyi', 'wan2.6-t2i');
    expect(tiers).toEqual(TONGYI_GEN_RESOLUTION_TIERS);
    expect(tiers.length).toBe(2);
    expect(tiers.map(t => t.value)).toEqual(['1K', '1.25K']);
  });

  it('通义 z-image-turbo 应返回 4 个档位', () => {
    const tiers = getAvailableResolutionTiers('tongyi', 'z-image-turbo');
    expect(tiers).toEqual(Z_IMAGE_RESOLUTION_TIERS);
    expect(tiers.length).toBe(4);
    expect(tiers.map(t => t.value)).toEqual(['1K', '1.25K', '1.5K', '2K']);
  });

  it('通义 wan2.6-image 应返回空数组（单档位）', () => {
    const tiers = getAvailableResolutionTiers('tongyi', 'wan2.6-image');
    expect(tiers).toEqual([]);
    expect(tiers.length).toBe(0);
  });

  it('Google 应返回 3 个档位', () => {
    const tiers = getAvailableResolutionTiers('google');
    expect(tiers).toEqual(GOOGLE_GEN_RESOLUTION_TIERS);
    expect(tiers.length).toBe(3);
    expect(tiers.map(t => t.value)).toEqual(['1K', '2K', '4K']);
  });
});
