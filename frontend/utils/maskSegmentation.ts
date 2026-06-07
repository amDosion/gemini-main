/**
 * Mask 预览 / 语义分割 API 调用纯函数。
 *
 * 抽离自 `ImageMaskEditView.tsx` L1278-1340 的 inline fetch+parse 逻辑
 * （JIRA-frontend-view-decomposition.md P0 #2 Step 2）。
 *
 * 设计为**纯函数**（非 React hook）：
 * - 输入：activeImageUrl / providerId / mode
 * - 输出：AutoMaskPreviewResult { maskUrl | notice | error } 三选一非空
 * - 调用方（useMaskIO）负责将 result 映射到 React state（避免 hook 接受 N 个 setter）
 *
 * 与 plan 工单标题 `hooks/useMaskSegmentation.ts` 不同的命名：实际无 React state，
 * 改放 `utils/` 更精准（按 §0 #3 精准修复原则）。
 */

import { apiClient } from '../services/apiClient';
import { fileToBase64 } from '../hooks/handlers/attachmentUtils';
import { getErrorMessage } from './errorMessage';
import {
  type MaskMode,
  getMaskModeDisplayLabel,
  getMaskPreviewUnavailableMessage,
  isMaskPreviewAccessDenied,
} from './maskHelpers';

/** Typed shape of the image-mask-preview API response envelope. */
interface MaskPreviewApiResponse {
  success?: boolean;
  masks?: Array<{ url: string }>;
  error?: string;
  data?: MaskPreviewApiResponse;
}

/** Narrows an untrusted API payload to the {@link MaskPreviewApiResponse} envelope. */
const toMaskPreviewResponse = (value: unknown): MaskPreviewApiResponse => {
  return value && typeof value === 'object' ? (value as MaskPreviewApiResponse) : {};
};

/** Returns the first usable mask URL from a (possibly nested) envelope, or null. */
const extractFirstMaskUrl = (envelope: MaskPreviewApiResponse): string | null => {
  const masks = envelope.masks;
  if (envelope.success === true && Array.isArray(masks) && masks.length > 0) {
    const url = masks[0]?.url;
    if (typeof url === 'string' && url.length > 0) {
      return url;
    }
  }
  return null;
};

export interface AutoMaskPreviewResult {
  /** 成功获取的 mask 预览 URL；失败时 null */
  maskUrl: string | null;
  /** 模型未开通等"非错误"提示（access denied）；失败时 null */
  notice: string | null;
  /** 真正的错误消息；其他情况 null。非 null 时调用方应当 showError */
  error: string | null;
}

/**
 * 调用后端 image-mask-preview API 获取自动 mask 预览。
 *
 * 三种返回情况（mutually exclusive — 仅一个字段非 null）：
 * 1. 成功：maskUrl 非 null
 * 2. 模型未开通：notice 非 null
 * 3. 其他失败：error 非 null
 */
export const fetchAutoMaskPreview = async (
  activeImageUrl: string,
  providerId: string | undefined,
  mode: MaskMode
): Promise<AutoMaskPreviewResult> => {
  try {
    // 获取图片的 base64 数据
    const response = await fetch(activeImageUrl);
    if (!response.ok) {
      throw new Error(`Image fetch failed: ${response.status}`);
    }
    const blob = await response.blob();
    const dataUrl = await fileToBase64(blob);
    // 移除 data:image/...;base64, 前缀
    const base64 = dataUrl.split(',')[1] || dataUrl;

    // 调用 mask 预览 API
    const rawResult = await apiClient.request<unknown>(
      `/api/modes/${providerId || 'google'}/image-mask-preview`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modelId: 'image-segmentation-001',
          prompt: '',
          attachments: [
            {
              name: 'image',
              mimeType: 'image/png',
              base64Data: base64,
            },
          ],
          extra: {
            maskMode: mode,
          },
        }),
      }
    );

    // 响应格式: { success: true, data: { success: true, masks: [...] }, provider: ..., mode: ... }
    const result = toMaskPreviewResponse(rawResult);
    const maskData = result.data ?? result;
    const maskUrl = extractFirstMaskUrl(maskData);
    if (maskUrl) {
      return { maskUrl, notice: null, error: null };
    }

    const errorMsg = maskData?.error || result?.error || 'Unknown error';
    if (isMaskPreviewAccessDenied(errorMsg)) {
      return { maskUrl: null, notice: getMaskPreviewUnavailableMessage(mode), error: null };
    }
    return {
      maskUrl: null,
      notice: null,
      error: `未能提取 ${getMaskModeDisplayLabel(mode)} Mask：${errorMsg}`,
    };
  } catch (error) {
    const errorText = getErrorMessage(error);
    if (isMaskPreviewAccessDenied(errorText)) {
      return { maskUrl: null, notice: getMaskPreviewUnavailableMessage(mode), error: null };
    }
    return {
      maskUrl: null,
      notice: null,
      error: `未能提取 ${getMaskModeDisplayLabel(mode)} Mask，请重试`,
    };
  }
};
