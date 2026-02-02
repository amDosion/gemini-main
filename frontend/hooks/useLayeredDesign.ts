/**
 * 分层设计 Hook
 *
 * 提供分层设计功能的 React Hook，包括：
 * - 布局建议 (suggestLayout)
 * - 图层分解 (decomposeLayers)
 * - Mask 矢量化 (vectorizeMask)
 * - LayerDoc 渲染 (renderLayerDoc)
 */

import { useState, useCallback } from 'react';
import { apiClient } from '../services/apiClient';
import type {
  LayerDoc,
  Layer,
  LayeredSuggestResponse,
  LayeredDecomposeResponse,
  LayeredVectorizeResponse,
  LayeredRenderResponse,
  SuggestLayoutOptions,
  DecomposeOptions,
  VectorizeOptions,
} from '../types/layeredDesign';

/**
 * 将图片 URL 转换为 base64 data URL
 * 支持 Blob URL、HTTP URL 和已有的 data URL
 */
async function convertToDataUrl(imageUrl: string): Promise<string> {
  // 如果已经是 data URL，直接返回
  if (imageUrl.startsWith('data:')) {
    return imageUrl;
  }

  // 对于 Blob URL 或 HTTP URL，需要加载并转换
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous'; // 允许跨域图片
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Failed to get canvas context'));
        return;
      }
      ctx.drawImage(img, 0, 0);
      try {
        const dataUrl = canvas.toDataURL('image/png');
        resolve(dataUrl);
      } catch (e) {
        reject(new Error(`Failed to convert image to data URL: ${e}`));
      }
    };
    img.onerror = () => {
      reject(new Error(`Failed to load image: ${imageUrl.substring(0, 100)}`));
    };
    img.src = imageUrl;
  });
}

interface UseLayeredDesignOptions {
  providerId: string;
  onError?: (error: string) => void;
}

interface UseLayeredDesignReturn {
  loading: boolean;
  layerDoc: LayerDoc | null;
  renderedImage: string | null;
  setLayerDoc: React.Dispatch<React.SetStateAction<LayerDoc | null>>;
  suggestLayout: (
    imageDataUrl: string,
    goal: string,
    options?: SuggestLayoutOptions
  ) => Promise<LayeredSuggestResponse>;
  decomposeLayers: (
    imageDataUrl: string,
    options?: DecomposeOptions
  ) => Promise<LayeredDecomposeResponse>;
  vectorizeMask: (
    maskDataUrl: string,
    options?: VectorizeOptions
  ) => Promise<LayeredVectorizeResponse>;
  renderLayerDoc: (doc: LayerDoc) => Promise<LayeredRenderResponse>;
  updateLayer: (layerId: string, updates: Partial<Layer>) => void;
  deleteLayer: (layerId: string) => void;
  reorderLayers: (newOrder: string[]) => void;
  addLayer: (layer: Layer) => void;
  clearLayerDoc: () => void;
}

export function useLayeredDesign({
  providerId,
  onError,
}: UseLayeredDesignOptions): UseLayeredDesignReturn {
  const [loading, setLoading] = useState(false);
  const [layerDoc, setLayerDoc] = useState<LayerDoc | null>(null);
  const [renderedImage, setRenderedImage] = useState<string | null>(null);

  /**
   * 布局建议
   */
  const suggestLayout = useCallback(
    async (
      imageDataUrl: string,
      goal: string,
      options?: SuggestLayoutOptions
    ): Promise<LayeredSuggestResponse> => {
      setLoading(true);
      try {
        // 确保图片是 base64 data URL 格式（支持 Blob URL 和 HTTP URL 转换）
        const dataUrl = await convertToDataUrl(imageDataUrl);

        const response = await apiClient.post<{
          success: boolean;
          data?: { layerDoc?: LayerDoc; error?: string };
        }>(`/api/modes/${providerId}/image-layered-suggest`, {
          modelId: options?.modelId || 'gemini-2.5-flash',
          prompt: goal,
          attachments: [{ url: dataUrl }],
          options: {
            canvasW: options?.canvasW || 2000,
            canvasH: options?.canvasH || 2000,
            maxTextBoxes: options?.maxTextBoxes || 3,
            locale: options?.locale || 'zh-CN',
          },
        });

        if (response.success && response.data?.layerDoc) {
          setLayerDoc(response.data.layerDoc);
          return { success: true, layerDoc: response.data.layerDoc };
        } else {
          const error = response.data?.error || 'Failed to suggest layout';
          onError?.(error);
          return { success: false, error };
        }
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : 'Unknown error';
        onError?.(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setLoading(false);
      }
    },
    [providerId, onError]
  );

  /**
   * 图层分解
   */
  const decomposeLayers = useCallback(
    async (
      imageDataUrl: string,
      options?: DecomposeOptions
    ): Promise<LayeredDecomposeResponse> => {
      setLoading(true);
      try {
        // 确保图片是 base64 data URL 格式
        const dataUrl = await convertToDataUrl(imageDataUrl);

        const response = await apiClient.post<{
          success: boolean;
          data?: LayeredDecomposeResponse;
        }>(`/api/modes/${providerId}/image-layered-decompose`, {
          modelId: '',
          prompt: options?.prompt || '',
          attachments: [{ url: dataUrl }],
          options: {
            layers: options?.layers || 4,
            seed: options?.seed ?? -1,
          },
        });

        if (response.success && response.data?.layers) {
          return { success: true, ...response.data };
        } else {
          const error =
            response.data?.error || 'Failed to decompose layers';
          const code = response.data?.code;
          onError?.(error);
          return { success: false, error, code };
        }
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : 'Unknown error';
        onError?.(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setLoading(false);
      }
    },
    [providerId, onError]
  );

  /**
   * Mask 矢量化
   */
  const vectorizeMask = useCallback(
    async (
      maskDataUrl: string,
      options?: VectorizeOptions
    ): Promise<LayeredVectorizeResponse> => {
      setLoading(true);
      try {
        // 确保 Mask 是 base64 data URL 格式
        const dataUrl = await convertToDataUrl(maskDataUrl);

        const response = await apiClient.post<{
          success: boolean;
          data?: LayeredVectorizeResponse;
        }>(`/api/modes/${providerId}/image-layered-vectorize`, {
          modelId: '',
          prompt: '',
          attachments: [{ url: dataUrl }],
          options: {
            simplifyTolerance: options?.simplifyTolerance ?? 2.0,
            smoothIterations: options?.smoothIterations ?? 2,
            useBezier: options?.useBezier ?? true,
            bezierSmoothness: options?.bezierSmoothness ?? 0.25,
            threshold: options?.threshold ?? 128,
            blurRadius: options?.blurRadius ?? 0.0,
          },
        });

        if (response.success && response.data?.svg) {
          return { success: true, ...response.data };
        } else {
          const error = response.data?.error || 'Failed to vectorize mask';
          onError?.(error);
          return { success: false, error };
        }
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : 'Unknown error';
        onError?.(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setLoading(false);
      }
    },
    [providerId, onError]
  );

  /**
   * 渲染 LayerDoc
   */
  const renderLayerDoc = useCallback(
    async (doc: LayerDoc): Promise<LayeredRenderResponse> => {
      setLoading(true);
      try {
        const response = await apiClient.post<{
          success: boolean;
          data?: LayeredRenderResponse;
        }>(`/api/modes/${providerId}/image-layered-render`, {
          modelId: '',
          prompt: '',
          attachments: [],
          options: { layerDoc: doc },
        });

        if (response.success && response.data?.imageBase64) {
          const imageUrl = `data:image/png;base64,${response.data.imageBase64}`;
          setRenderedImage(imageUrl);
          return { success: true, ...response.data };
        } else {
          const error = response.data?.error || 'Failed to render';
          onError?.(error);
          return { success: false, error };
        }
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : 'Unknown error';
        onError?.(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setLoading(false);
      }
    },
    [providerId, onError]
  );

  /**
   * 更新图层
   */
  const updateLayer = useCallback(
    (layerId: string, updates: Partial<Layer>) => {
      setLayerDoc((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          layers: prev.layers.map((layer) =>
            layer.id === layerId ? { ...layer, ...updates } : layer
          ) as Layer[],
        };
      });
    },
    []
  );

  /**
   * 删除图层
   */
  const deleteLayer = useCallback((layerId: string) => {
    setLayerDoc((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        layers: prev.layers.filter((layer) => layer.id !== layerId),
      };
    });
  }, []);

  /**
   * 重排图层顺序
   */
  const reorderLayers = useCallback((newOrder: string[]) => {
    setLayerDoc((prev) => {
      if (!prev) return prev;

      const layerMap = new Map(prev.layers.map((l) => [l.id, l]));
      const reordered = newOrder
        .map((id, index) => {
          const layer = layerMap.get(id);
          if (layer) {
            return { ...layer, z: index };
          }
          return null;
        })
        .filter((l): l is Layer => l !== null);

      return { ...prev, layers: reordered };
    });
  }, []);

  /**
   * 添加图层
   */
  const addLayer = useCallback((layer: Layer) => {
    setLayerDoc((prev) => {
      if (!prev) return prev;
      // 设置 z 为最高值
      const maxZ = Math.max(...prev.layers.map((l) => l.z), -1);
      const newLayer = { ...layer, z: maxZ + 1 };
      return {
        ...prev,
        layers: [...prev.layers, newLayer],
      };
    });
  }, []);

  /**
   * 清空 LayerDoc
   */
  const clearLayerDoc = useCallback(() => {
    setLayerDoc(null);
    setRenderedImage(null);
  }, []);

  return {
    loading,
    layerDoc,
    renderedImage,
    setLayerDoc,
    suggestLayout,
    decomposeLayers,
    vectorizeMask,
    renderLayerDoc,
    updateLayer,
    deleteLayer,
    reorderLayers,
    addLayer,
    clearLayerDoc,
  };
}

export default useLayeredDesign;
