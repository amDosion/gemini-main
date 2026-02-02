/**
 * 图层属性编辑器
 *
 * 编辑选中图层的属性：
 * - 透明度
 * - 混合模式
 * - 变换（位置、缩放、旋转）
 * - 文字属性（仅文字图层）
 */

import React, { useCallback, useState } from 'react';
import {
  Sliders,
  Move,
  RotateCcw,
  Maximize2,
  Type,
  Palette,
  Eye,
  Layers,
} from 'lucide-react';
import type {
  Layer,
  RasterLayer,
  TextLayer,
  ShapeLayer,
  GradientLayer,
  BlendMode,
  Transform,
} from '../../types/layeredDesign';

interface LayerPropertyEditorProps {
  layer: Layer | null;
  onUpdateLayer: (layerId: string, updates: Partial<Layer>) => void;
  disabled?: boolean;
}

// 混合模式选项
const BLEND_MODES: { value: BlendMode; label: string }[] = [
  { value: 'normal', label: '正常' },
  { value: 'multiply', label: '正片叠底' },
  { value: 'screen', label: '滤色' },
  { value: 'overlay', label: '叠加' },
];

// 数值输入组件
interface NumberInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  disabled?: boolean;
}

const NumberInput: React.FC<NumberInputProps> = ({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  disabled,
}) => (
  <div className="flex items-center justify-between">
    <span className="text-xs text-slate-400">{label}</span>
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        className="w-16 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-white text-right focus:outline-none focus:border-purple-500/50"
      />
      {unit && <span className="text-xs text-slate-500 w-6">{unit}</span>}
    </div>
  </div>
);

// 滑块输入组件
interface SliderInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  disabled?: boolean;
}

const SliderInput: React.FC<SliderInputProps> = ({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  unit = '%',
  disabled,
}) => (
  <div className="flex items-center justify-between">
    <span className="text-xs text-slate-400">{label}</span>
    <div className="flex items-center gap-2">
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        className="w-20 accent-purple-500"
      />
      <span className="text-xs text-white font-mono w-10 text-right">
        {value}{unit}
      </span>
    </div>
  </div>
);

export const LayerPropertyEditor: React.FC<LayerPropertyEditorProps> = ({
  layer,
  onUpdateLayer,
  disabled,
}) => {
  // 更新属性的快捷函数
  const updateProperty = useCallback(
    <K extends keyof Layer>(key: K, value: Layer[K]) => {
      if (layer) {
        onUpdateLayer(layer.id, { [key]: value });
      }
    },
    [layer, onUpdateLayer]
  );

  // 更新变换属性
  const updateTransform = useCallback(
    <K extends keyof Transform>(key: K, value: Transform[K]) => {
      if (layer) {
        onUpdateLayer(layer.id, {
          transform: {
            ...layer.transform,
            [key]: value,
          },
        });
      }
    },
    [layer, onUpdateLayer]
  );

  if (!layer) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-slate-500">
        <Layers size={24} className="mb-2 opacity-50" />
        <p className="text-xs">选择一个图层以编辑属性</p>
      </div>
    );
  }

  const isDisabled = disabled;

  return (
    <div className="space-y-4">
      {/* 图层基本信息 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Sliders size={12} className="text-purple-400" />
          <span>图层属性</span>
        </div>

        {/* 图层名称 */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">名称</span>
          <input
            type="text"
            value={layer.name || layer.id}
            onChange={(e) => updateProperty('name', e.target.value)}
            disabled={isDisabled}
            className="w-32 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-white text-right focus:outline-none focus:border-purple-500/50"
          />
        </div>

        {/* 图层类型（只读） */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">类型</span>
          <span className="text-xs text-white bg-slate-800 px-2 py-1 rounded">
            {layer.type === 'raster' && '图片'}
            {layer.type === 'text' && '文字'}
            {layer.type === 'shape' && '形状'}
            {layer.type === 'gradient' && '渐变'}
          </span>
        </div>
      </div>

      {/* 外观属性 */}
      <div className="space-y-2 pt-2 border-t border-slate-800">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Eye size={12} className="text-blue-400" />
          <span>外观</span>
        </div>

        {/* 透明度 */}
        <SliderInput
          label="透明度"
          value={Math.round(layer.opacity * 100)}
          onChange={(v) => updateProperty('opacity', v / 100)}
          min={0}
          max={100}
          step={1}
          unit="%"
          disabled={isDisabled}
        />

        {/* 混合模式 */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">混合模式</span>
          <select
            value={layer.blend}
            onChange={(e) => updateProperty('blend', e.target.value as BlendMode)}
            disabled={isDisabled}
            className="w-24 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-purple-500/50"
          >
            {BLEND_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>

        {/* Z 顺序 */}
        <NumberInput
          label="图层顺序"
          value={layer.z}
          onChange={(v) => updateProperty('z', v)}
          min={0}
          max={100}
          step={1}
          disabled={isDisabled}
        />
      </div>

      {/* 变换属性 */}
      <div className="space-y-2 pt-2 border-t border-slate-800">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Move size={12} className="text-green-400" />
          <span>变换</span>
        </div>

        {/* 位置 */}
        <div className="grid grid-cols-2 gap-2">
          <NumberInput
            label="X"
            value={layer.transform.x}
            onChange={(v) => updateTransform('x', v)}
            min={-10000}
            max={10000}
            step={1}
            unit="px"
            disabled={isDisabled}
          />
          <NumberInput
            label="Y"
            value={layer.transform.y}
            onChange={(v) => updateTransform('y', v)}
            min={-10000}
            max={10000}
            step={1}
            unit="px"
            disabled={isDisabled}
          />
        </div>

        {/* 缩放 */}
        <SliderInput
          label="缩放"
          value={Math.round(layer.transform.scale * 100)}
          onChange={(v) => updateTransform('scale', v / 100)}
          min={10}
          max={500}
          step={1}
          unit="%"
          disabled={isDisabled}
        />

        {/* 旋转 */}
        <SliderInput
          label="旋转"
          value={layer.transform.rotate}
          onChange={(v) => updateTransform('rotate', v)}
          min={-180}
          max={180}
          step={1}
          unit="°"
          disabled={isDisabled}
        />

        {/* 锚点 */}
        <div className="grid grid-cols-2 gap-2">
          <NumberInput
            label="锚点 X"
            value={layer.transform.anchorX}
            onChange={(v) => updateTransform('anchorX', v)}
            min={0}
            max={1}
            step={0.1}
            disabled={isDisabled}
          />
          <NumberInput
            label="锚点 Y"
            value={layer.transform.anchorY}
            onChange={(v) => updateTransform('anchorY', v)}
            min={0}
            max={1}
            step={0.1}
            disabled={isDisabled}
          />
        </div>
      </div>

      {/* 文字属性（仅文字图层） */}
      {layer.type === 'text' && (
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
            <Type size={12} className="text-yellow-400" />
            <span>文字</span>
          </div>

          {/* 文字内容 */}
          <div className="space-y-1">
            <span className="text-xs text-slate-400">内容</span>
            <textarea
              value={(layer as TextLayer).text || ''}
              onChange={(e) =>
                onUpdateLayer(layer.id, { text: e.target.value } as Partial<TextLayer>)
              }
              disabled={isDisabled}
              className="w-full h-16 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-white resize-none focus:outline-none focus:border-purple-500/50"
            />
          </div>

          {/* 字体大小 */}
          {(layer as TextLayer).style && (
            <>
              <NumberInput
                label="字号"
                value={(layer as TextLayer).style?.fontSize || 16}
                onChange={(v) =>
                  onUpdateLayer(layer.id, {
                    style: { ...(layer as TextLayer).style, fontSize: v },
                  } as Partial<TextLayer>)
                }
                min={8}
                max={200}
                step={1}
                unit="px"
                disabled={isDisabled}
              />

              {/* 字体颜色 */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">颜色</span>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={(layer as TextLayer).style?.fontColor || '#ffffff'}
                    onChange={(e) =>
                      onUpdateLayer(layer.id, {
                        style: { ...(layer as TextLayer).style, fontColor: e.target.value },
                      } as Partial<TextLayer>)
                    }
                    disabled={isDisabled}
                    className="w-8 h-6 rounded cursor-pointer"
                  />
                  <span className="text-xs text-white font-mono">
                    {(layer as TextLayer).style?.fontColor || '#ffffff'}
                  </span>
                </div>
              </div>

              {/* 对齐方式 */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">对齐</span>
                <div className="flex gap-1">
                  {(['left', 'center', 'right'] as const).map((align) => (
                    <button
                      key={align}
                      onClick={() =>
                        onUpdateLayer(layer.id, {
                          style: { ...(layer as TextLayer).style, align },
                        } as Partial<TextLayer>)
                      }
                      disabled={isDisabled}
                      className={`px-2 py-1 text-xs rounded transition-colors ${
                        (layer as TextLayer).style?.align === align
                          ? 'bg-purple-500/20 text-purple-400'
                          : 'bg-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      {align === 'left' && '左'}
                      {align === 'center' && '中'}
                      {align === 'right' && '右'}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* 渐变属性（仅渐变图层） */}
      {layer.type === 'gradient' && (layer as GradientLayer).gradient && (
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
            <Palette size={12} className="text-pink-400" />
            <span>渐变</span>
          </div>

          {/* 渐变类型 */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">类型</span>
            <span className="text-xs text-white bg-slate-800 px-2 py-1 rounded">
              {(layer as GradientLayer).gradient?.type === 'linear' && '线性'}
              {(layer as GradientLayer).gradient?.type === 'radial' && '径向'}
            </span>
          </div>

          {/* 渐变预览 */}
          <div
            className="h-6 rounded border border-slate-700"
            style={{
              background: `linear-gradient(to right, ${(layer as GradientLayer).gradient?.stops
                ?.map((s) => s.color)
                .join(', ')})`,
            }}
          />
        </div>
      )}
    </div>
  );
};

export default LayerPropertyEditor;
