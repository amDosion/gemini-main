/**
 * 图层列表组件
 *
 * 显示 LayerDoc 中的图层，支持：
 * - 拖拽排序
 * - 可见性切换
 * - 选中状态
 * - 删除图层
 */

import React, { useCallback, useState } from 'react';
import {
  Eye,
  EyeOff,
  Trash2,
  GripVertical,
  Image as ImageIcon,
  Type,
  Square,
  Palette,
  ChevronDown,
  ChevronRight,
  Lock,
  Unlock,
} from 'lucide-react';
import type { Layer, RasterLayer, TextLayer, ShapeLayer, GradientLayer } from '../../types/layeredDesign';

interface LayerListProps {
  layers: Layer[];
  selectedLayerId: string | null;
  onSelectLayer: (layerId: string | null) => void;
  onToggleVisibility: (layerId: string) => void;
  onDeleteLayer: (layerId: string) => void;
  onReorderLayers: (newOrder: string[]) => void;
  disabled?: boolean;
}

// 图层类型图标
const LayerTypeIcon: React.FC<{ type: Layer['type']; className?: string }> = ({ type, className = '' }) => {
  const iconProps = { size: 14, className };

  switch (type) {
    case 'raster':
      return <ImageIcon {...iconProps} />;
    case 'text':
      return <Type {...iconProps} />;
    case 'shape':
      return <Square {...iconProps} />;
    case 'gradient':
      return <Palette {...iconProps} />;
    default:
      return <Square {...iconProps} />;
  }
};

// 图层类型名称
const getLayerTypeName = (type: Layer['type']): string => {
  switch (type) {
    case 'raster':
      return '图片';
    case 'text':
      return '文字';
    case 'shape':
      return '形状';
    case 'gradient':
      return '渐变';
    default:
      return '未知';
  }
};

// 图层缩略图
const LayerThumbnail: React.FC<{ layer: Layer }> = ({ layer }) => {
  if (layer.type === 'raster') {
    const rasterLayer = layer as RasterLayer;
    const src = rasterLayer.png_base64
      ? `data:image/png;base64,${rasterLayer.png_base64}`
      : rasterLayer.asset_url;

    if (src) {
      return (
        <img
          src={src}
          alt={layer.name || layer.id}
          className="w-10 h-10 object-cover rounded bg-slate-800"
        />
      );
    }
  }

  if (layer.type === 'text') {
    const textLayer = layer as TextLayer;
    return (
      <div className="w-10 h-10 rounded bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-400 overflow-hidden">
        <span className="truncate px-1">{textLayer.text?.substring(0, 2) || 'T'}</span>
      </div>
    );
  }

  if (layer.type === 'gradient') {
    const gradientLayer = layer as GradientLayer;
    const stops = gradientLayer.gradient?.stops || [];
    const gradientStyle = stops.length >= 2
      ? {
          background: `linear-gradient(to right, ${stops.map(s => s.color).join(', ')})`,
        }
      : { background: '#475569' };

    return <div className="w-10 h-10 rounded" style={gradientStyle} />;
  }

  // 默认占位
  return (
    <div className="w-10 h-10 rounded bg-slate-800 flex items-center justify-center">
      <LayerTypeIcon type={layer.type} className="text-slate-500" />
    </div>
  );
};

// 单个图层项
interface LayerItemProps {
  layer: Layer;
  isSelected: boolean;
  isVisible: boolean;
  onSelect: () => void;
  onToggleVisibility: () => void;
  onDelete: () => void;
  disabled?: boolean;
  isDragging?: boolean;
  dragHandleProps?: React.HTMLAttributes<HTMLDivElement>;
}

const LayerItem: React.FC<LayerItemProps> = ({
  layer,
  isSelected,
  isVisible,
  onSelect,
  onToggleVisibility,
  onDelete,
  disabled,
  isDragging,
  dragHandleProps,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={`
        flex items-center gap-2 p-2 rounded-lg transition-all cursor-pointer
        ${isSelected ? 'bg-pink-500/20 border border-pink-500/50' : 'bg-slate-800/50 border border-transparent hover:bg-slate-800'}
        ${isDragging ? 'opacity-50 scale-95' : ''}
        ${disabled ? 'opacity-50 pointer-events-none' : ''}
      `}
      onClick={onSelect}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* 拖拽手柄 */}
      <div
        {...dragHandleProps}
        className="cursor-grab active:cursor-grabbing text-slate-500 hover:text-slate-300 transition-colors"
      >
        <GripVertical size={14} />
      </div>

      {/* 缩略图 */}
      <LayerThumbnail layer={layer} />

      {/* 图层信息 */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-white truncate">
          {layer.name || layer.id}
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-500">
          <LayerTypeIcon type={layer.type} className="text-slate-500" />
          <span>{getLayerTypeName(layer.type)}</span>
          <span className="opacity-50">|</span>
          <span>{Math.round(layer.opacity * 100)}%</span>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className={`flex items-center gap-1 transition-opacity ${isHovered || isSelected ? 'opacity-100' : 'opacity-0'}`}>
        {/* 可见性切换 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleVisibility();
          }}
          className={`p-1.5 rounded transition-colors ${
            isVisible ? 'text-slate-400 hover:text-white' : 'text-slate-600 hover:text-slate-400'
          }`}
          title={isVisible ? '隐藏图层' : '显示图层'}
        >
          {isVisible ? <Eye size={14} /> : <EyeOff size={14} />}
        </button>

        {/* 删除 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-1.5 rounded text-slate-400 hover:text-red-400 transition-colors"
          title="删除图层"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
};

export const LayerList: React.FC<LayerListProps> = ({
  layers,
  selectedLayerId,
  onSelectLayer,
  onToggleVisibility,
  onDeleteLayer,
  onReorderLayers,
  disabled,
}) => {
  // 可见性状态（本地管理，实际应该在 layer 对象中）
  const [hiddenLayers, setHiddenLayers] = useState<Set<string>>(new Set());

  // 拖拽状态
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  // 切换可见性
  const handleToggleVisibility = useCallback((layerId: string) => {
    setHiddenLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layerId)) {
        next.delete(layerId);
      } else {
        next.add(layerId);
      }
      return next;
    });
    onToggleVisibility(layerId);
  }, [onToggleVisibility]);

  // 拖拽开始
  const handleDragStart = useCallback((e: React.DragEvent, layerId: string) => {
    setDraggedId(layerId);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', layerId);
  }, []);

  // 拖拽结束
  const handleDragEnd = useCallback(() => {
    setDraggedId(null);
    setDragOverId(null);
  }, []);

  // 拖拽悬停
  const handleDragOver = useCallback((e: React.DragEvent, layerId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (layerId !== draggedId) {
      setDragOverId(layerId);
    }
  }, [draggedId]);

  // 放置
  const handleDrop = useCallback((e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData('text/plain');

    if (sourceId && sourceId !== targetId) {
      const currentOrder = layers.map((l) => l.id);
      const sourceIndex = currentOrder.indexOf(sourceId);
      const targetIndex = currentOrder.indexOf(targetId);

      if (sourceIndex !== -1 && targetIndex !== -1) {
        const newOrder = [...currentOrder];
        newOrder.splice(sourceIndex, 1);
        newOrder.splice(targetIndex, 0, sourceId);
        onReorderLayers(newOrder);
      }
    }

    setDraggedId(null);
    setDragOverId(null);
  }, [layers, onReorderLayers]);

  // 按 z 值降序排列（最上层在前）
  const sortedLayers = [...layers].sort((a, b) => b.z - a.z);

  if (layers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-slate-500">
        <ImageIcon size={32} className="mb-2 opacity-50" />
        <p className="text-sm">暂无图层</p>
        <p className="text-xs opacity-50">使用布局建议或图层分解添加图层</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {sortedLayers.map((layer) => (
        <div
          key={layer.id}
          draggable={!disabled}
          onDragStart={(e) => handleDragStart(e, layer.id)}
          onDragEnd={handleDragEnd}
          onDragOver={(e) => handleDragOver(e, layer.id)}
          onDrop={(e) => handleDrop(e, layer.id)}
          className={`transition-all ${
            dragOverId === layer.id ? 'border-t-2 border-pink-500 pt-1' : ''
          }`}
        >
          <LayerItem
            layer={layer}
            isSelected={selectedLayerId === layer.id}
            isVisible={!hiddenLayers.has(layer.id)}
            onSelect={() => onSelectLayer(layer.id)}
            onToggleVisibility={() => handleToggleVisibility(layer.id)}
            onDelete={() => onDeleteLayer(layer.id)}
            disabled={disabled}
            isDragging={draggedId === layer.id}
          />
        </div>
      ))}
    </div>
  );
};

export default LayerList;
