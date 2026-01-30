/**
 * 分层设计面板
 *
 * 自动分层：当有图片且没有图层时自动触发分层
 * 显示内容：
 * - 分解图层数参数
 * - 图层列表
 * - 渲染预览
 */

import React, { useState, useCallback } from 'react';
import {
  Layers,
  Play,
  Loader2,
  Image as ImageIcon,
  Download,
  RotateCcw,
  RefreshCw,
} from 'lucide-react';
import { LayerList } from './LayerList';
import type { Layer, LayerDoc } from '../../types/layeredDesign';

interface LayeredDesignPanelProps {
  // 图层状态
  layerDoc: LayerDoc | null;
  selectedLayerId: string | null;
  onSelectLayer: (layerId: string | null) => void;

  // 图层操作
  onUpdateLayer: (layerId: string, updates: Partial<Layer>) => void;
  onDeleteLayer: (layerId: string) => void;
  onReorderLayers: (newOrder: string[]) => void;
  onClearLayerDoc: () => void;

  // API 调用
  onDecomposeLayers: (layerCount: number) => Promise<void>;
  onRenderPreview: () => Promise<void>;

  // 渲染结果
  renderedImage: string | null;

  // 状态
  loading: boolean;
  disabled?: boolean;

  // 图片
  hasImage: boolean;
  imageUrl?: string; // 用于检测图片变化
}

export const LayeredDesignPanel: React.FC<LayeredDesignPanelProps> = ({
  layerDoc,
  selectedLayerId,
  onSelectLayer,
  onUpdateLayer,
  onDeleteLayer,
  onReorderLayers,
  onClearLayerDoc,
  onDecomposeLayers,
  onRenderPreview,
  renderedImage,
  loading,
  disabled,
  hasImage,
  imageUrl,
}) => {
  // 图层分解数量（用于手动重新分层）
  const [layerCount, setLayerCount] = useState(4);

  // 手动重新分层（分层由后端自动完成，此处用于用户想要重新分层的情况）
  const handleRedecompose = useCallback(async () => {
    await onDecomposeLayers(layerCount);
  }, [onDecomposeLayers, layerCount]);

  // 处理渲染预览
  const handleRenderPreview = useCallback(async () => {
    await onRenderPreview();
  }, [onRenderPreview]);

  // 切换图层可见性
  const handleToggleVisibility = useCallback((layerId: string) => {
    const layer = layerDoc?.layers.find((l) => l.id === layerId);
    if (layer) {
      onUpdateLayer(layerId, { opacity: layer.opacity === 0 ? 1 : 0 });
    }
  }, [layerDoc, onUpdateLayer]);

  // 下载渲染结果
  const handleDownload = useCallback(() => {
    if (!renderedImage) return;

    const link = document.createElement('a');
    link.href = renderedImage;
    link.download = `layered-design-${Date.now()}.png`;
    link.click();
  }, [renderedImage]);

  const isDisabled = disabled || loading;
  const hasLayers = layerDoc && layerDoc.layers.length > 0;

  return (
    <div className="space-y-3">
      {/* 无图片提示 */}
      {!hasImage && (
        <div className="flex flex-col items-center justify-center py-4 text-slate-500">
          <ImageIcon size={20} className="mb-1.5 opacity-50" />
          <p className="text-xs">请先生成或上传图片</p>
        </div>
      )}

      {/* 有图片时显示功能 */}
      {hasImage && (
        <>
          {/* 分解图层数参数 + 重新分层按钮 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">图层数</span>
              <input
                type="range"
                min={2}
                max={10}
                value={layerCount}
                onChange={(e) => setLayerCount(Number(e.target.value))}
                className="w-14 h-1 accent-purple-500"
                disabled={isDisabled}
              />
              <span className="text-xs text-white font-mono w-4">
                {layerCount}
              </span>
            </div>
            {hasLayers && (
              <button
                onClick={handleRedecompose}
                disabled={isDisabled}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-slate-500 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
                title="重新分层"
              >
                <RefreshCw size={10} />
                <span>重新分层</span>
              </button>
            )}
          </div>

          {/* 正在分层的提示 */}
          {loading && !hasLayers && (
            <div className="flex items-center justify-center gap-2 py-4 text-slate-400">
              <Loader2 size={16} className="animate-spin text-purple-400" />
              <span className="text-xs">正在分解图层...</span>
            </div>
          )}

          {/* 图层列表 */}
          {hasLayers && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Layers size={10} className="text-purple-400" />
                  <span>图层 ({layerDoc.layers.length})</span>
                </div>
                <button
                  onClick={onClearLayerDoc}
                  disabled={isDisabled}
                  className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-slate-500 hover:text-red-400 hover:bg-slate-800 transition-colors disabled:opacity-50"
                  title="清空图层"
                >
                  <RotateCcw size={10} />
                </button>
              </div>
              <LayerList
                layers={layerDoc.layers}
                selectedLayerId={selectedLayerId}
                onSelectLayer={onSelectLayer}
                onToggleVisibility={handleToggleVisibility}
                onDeleteLayer={onDeleteLayer}
                onReorderLayers={onReorderLayers}
                disabled={isDisabled}
              />
            </div>
          )}

          {/* 渲染预览和下载 */}
          {hasLayers && (
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <button
                onClick={handleRenderPreview}
                disabled={isDisabled}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white text-xs font-medium rounded-md transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Play size={12} />
                )}
                <span>渲染预览</span>
              </button>

              {renderedImage && (
                <button
                  onClick={handleDownload}
                  disabled={isDisabled}
                  className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium rounded-md transition-all disabled:opacity-50"
                >
                  <Download size={12} />
                  <span>下载结果</span>
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default LayeredDesignPanel;
