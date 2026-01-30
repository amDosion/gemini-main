/**
 * Mask 矢量化面板
 *
 * 将 Mask PNG 转换为 SVG 路径，支持：
 * - 简化容差调节
 * - 平滑迭代次数
 * - 贝塞尔曲线选项
 * - 预览和下载
 */

import React, { useState, useCallback } from 'react';
import {
  Wand2,
  Download,
  Play,
  Loader2,
  Settings,
  ChevronDown,
  Image as ImageIcon,
  FileCode,
  Copy,
  Check,
} from 'lucide-react';
import type { VectorizeOptions } from '../../types/layeredDesign';

interface VectorizePanelProps {
  onVectorize: (maskDataUrl: string, options: VectorizeOptions) => Promise<{
    success: boolean;
    svg?: string;
    path?: string;
    error?: string;
  }>;
  loading: boolean;
  disabled?: boolean;
  maskImageUrl: string | null;
}

export const VectorizePanel: React.FC<VectorizePanelProps> = ({
  onVectorize,
  loading,
  disabled,
  maskImageUrl,
}) => {
  // 矢量化选项
  const [options, setOptions] = useState<VectorizeOptions>({
    simplifyTolerance: 2.0,
    smoothIterations: 2,
    useBezier: true,
    bezierSmoothness: 0.25,
    threshold: 128,
    blurRadius: 0,
  });

  // 结果状态
  const [result, setResult] = useState<{
    svg: string;
    path: string;
  } | null>(null);

  // 高级选项展开状态
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // 复制状态
  const [copied, setCopied] = useState<'svg' | 'path' | null>(null);

  // 处理矢量化
  const handleVectorize = useCallback(async () => {
    if (!maskImageUrl) return;

    const response = await onVectorize(maskImageUrl, options);
    if (response.success && response.svg && response.path) {
      setResult({
        svg: response.svg,
        path: response.path,
      });
    } else {
      setResult(null);
    }
  }, [maskImageUrl, options, onVectorize]);

  // 复制到剪贴板
  const handleCopy = useCallback(async (type: 'svg' | 'path') => {
    if (!result) return;

    const text = type === 'svg' ? result.svg : result.path;
    await navigator.clipboard.writeText(text);
    setCopied(type);
    setTimeout(() => setCopied(null), 2000);
  }, [result]);

  // 下载 SVG
  const handleDownload = useCallback(() => {
    if (!result?.svg) return;

    const blob = new Blob([result.svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `vectorized-mask-${Date.now()}.svg`;
    link.click();
    URL.revokeObjectURL(url);
  }, [result]);

  const isDisabled = disabled || loading || !maskImageUrl;

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
        <Wand2 size={12} className="text-green-400" />
        <span>Mask 矢量化</span>
      </div>

      {/* 无 Mask 提示 */}
      {!maskImageUrl && (
        <div className="flex flex-col items-center justify-center py-6 text-slate-500">
          <ImageIcon size={24} className="mb-2 opacity-50" />
          <p className="text-xs">请先选择或绘制 Mask</p>
        </div>
      )}

      {/* Mask 预览 */}
      {maskImageUrl && (
        <div className="relative rounded-lg overflow-hidden border border-slate-700 bg-slate-800">
          <img
            src={maskImageUrl}
            alt="Mask Preview"
            className="w-full h-32 object-contain"
          />
          <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/60 rounded text-xs text-slate-300">
            Mask 预览
          </div>
        </div>
      )}

      {/* 基本选项 */}
      {maskImageUrl && (
        <div className="space-y-3">
          {/* 简化容差 */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">简化容差</span>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0.5}
                max={10}
                step={0.5}
                value={options.simplifyTolerance}
                onChange={(e) =>
                  setOptions((prev) => ({
                    ...prev,
                    simplifyTolerance: Number(e.target.value),
                  }))
                }
                className="w-20 accent-green-500"
                disabled={isDisabled}
              />
              <span className="text-xs text-white font-mono w-8 text-right">
                {options.simplifyTolerance}
              </span>
            </div>
          </div>

          {/* 平滑迭代 */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">平滑迭代</span>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={5}
                step={1}
                value={options.smoothIterations}
                onChange={(e) =>
                  setOptions((prev) => ({
                    ...prev,
                    smoothIterations: Number(e.target.value),
                  }))
                }
                className="w-20 accent-green-500"
                disabled={isDisabled}
              />
              <span className="text-xs text-white font-mono w-8 text-right">
                {options.smoothIterations}
              </span>
            </div>
          </div>

          {/* 贝塞尔曲线 */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">贝塞尔曲线</span>
            <button
              onClick={() =>
                setOptions((prev) => ({ ...prev, useBezier: !prev.useBezier }))
              }
              disabled={isDisabled}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                options.useBezier
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-slate-700 text-slate-400'
              }`}
            >
              {options.useBezier ? '开启' : '关闭'}
            </button>
          </div>

          {/* 高级选项 */}
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors w-full justify-center py-1"
          >
            <Settings size={10} />
            <span>高级选项</span>
            <ChevronDown
              size={10}
              className={`transition-transform ${isAdvancedOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {isAdvancedOpen && (
            <div className="p-3 bg-slate-800/50 rounded-lg space-y-3">
              {/* 阈值 */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">二值化阈值</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={1}
                    max={255}
                    step={1}
                    value={options.threshold}
                    onChange={(e) =>
                      setOptions((prev) => ({
                        ...prev,
                        threshold: Number(e.target.value),
                      }))
                    }
                    className="w-16 accent-green-500"
                    disabled={isDisabled}
                  />
                  <span className="text-xs text-white font-mono w-8 text-right">
                    {options.threshold}
                  </span>
                </div>
              </div>

              {/* 贝塞尔平滑度 */}
              {options.useBezier && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">曲线平滑度</span>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min={0.1}
                      max={0.5}
                      step={0.05}
                      value={options.bezierSmoothness}
                      onChange={(e) =>
                        setOptions((prev) => ({
                          ...prev,
                          bezierSmoothness: Number(e.target.value),
                        }))
                      }
                      className="w-16 accent-green-500"
                      disabled={isDisabled}
                    />
                    <span className="text-xs text-white font-mono w-8 text-right">
                      {options.bezierSmoothness}
                    </span>
                  </div>
                </div>
              )}

              {/* 模糊半径 */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">预处理模糊</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={5}
                    step={0.5}
                    value={options.blurRadius}
                    onChange={(e) =>
                      setOptions((prev) => ({
                        ...prev,
                        blurRadius: Number(e.target.value),
                      }))
                    }
                    className="w-16 accent-green-500"
                    disabled={isDisabled}
                  />
                  <span className="text-xs text-white font-mono w-8 text-right">
                    {options.blurRadius}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* 执行按钮 */}
          <button
            onClick={handleVectorize}
            disabled={isDisabled}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-green-500 to-teal-500 hover:from-green-400 hover:to-teal-400 text-white text-sm font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            <span>矢量化</span>
          </button>
        </div>
      )}

      {/* 结果区域 */}
      {result && (
        <div className="space-y-3 pt-3 border-t border-slate-800">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
            <FileCode size={12} className="text-green-400" />
            <span>矢量化结果</span>
          </div>

          {/* SVG 预览 */}
          <div
            className="relative rounded-lg overflow-hidden border border-slate-700 bg-white p-2"
            dangerouslySetInnerHTML={{ __html: result.svg }}
            style={{ maxHeight: '150px' }}
          />

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <button
              onClick={() => handleCopy('svg')}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg transition-colors"
            >
              {copied === 'svg' ? <Check size={12} /> : <Copy size={12} />}
              <span>复制 SVG</span>
            </button>
            <button
              onClick={() => handleCopy('path')}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg transition-colors"
            >
              {copied === 'path' ? <Check size={12} /> : <Copy size={12} />}
              <span>复制路径</span>
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 text-xs rounded-lg transition-colors"
            >
              <Download size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default VectorizePanel;
