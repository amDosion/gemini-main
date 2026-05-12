/**
 * Header 内部工具函数集合（图标 / 数字格式化 / 常量）。
 *
 * 1:1 抽离自 `Header.tsx` L39-91（< 800 行合规拆分）。
 */

import React from 'react';
import {
  Cpu,
  Flame,
  Globe,
  Server,
  Sparkles,
  Zap,
  Video,
  Mic,
  Brain,
  BrainCircuit,
  Image as ImageIcon,
} from 'lucide-react';
import { ModelConfig } from '../../types/types';

export const getModelIcon = (model: ModelConfig) => {
  const id = model.id.toLowerCase();
  // 视频生成模型
  if (id.includes('veo') || id.includes('sora') || id.includes('luma')) return Video;
  // 音频生成模型
  if (id.includes('tts') || id.includes('audio') || id.includes('speech')) return Mic;
  // 文生图模型：统一使用 Zap 图标
  if (
    id.includes('-t2i') ||
    id.includes('z-image') ||
    id.includes('wanx') ||
    id.includes('wan2') ||
    id.includes('dall') ||
    id.includes('flux') ||
    id.includes('midjourney') ||
    id.includes('imagen')
  )
    return Zap;
  // 代码模型
  if (model.capabilities.coding) return BrainCircuit;
  // 推理模型
  if (model.capabilities.reasoning) return Brain;
  // 搜索模型
  if (model.capabilities.search) return Globe;
  // 视觉理解模型（不是文生图）
  if (model.capabilities.vision) return ImageIcon;
  // Pro 模型
  if (id.includes('pro')) return BrainCircuit;
  // 默认
  return Zap;
};

export const getProviderIcon = (pid: string) => {
  if (pid.includes('google')) return <Zap size={14} />;
  if (pid.includes('deepseek')) return <Cpu size={14} />;
  if (pid.includes('tongyi')) return <Globe size={14} />;
  if (pid.includes('openai')) return <Sparkles size={14} />;
  if (pid.includes('grok')) return <Flame size={14} className="text-orange-400" />;
  return <Server size={14} />;
};

export const formatBytes = (bytes?: number | null): string => {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const base = Math.floor(Math.log(bytes) / Math.log(1024));
  const index = Math.min(base, units.length - 1);
  const value = bytes / Math.pow(1024, index);
  return `${value.toFixed(value >= 100 || index === 0 ? 0 : 1)} ${units[index]}`;
};

export const formatPercent = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
};

export const normalizeNumberInput = (value: string): number | '' => {
  if (value === '') return '';
  const n = Number(value);
  return Number.isFinite(n) ? n : '';
};

export const SYSTEM_STATUS_POLL_INTERVAL_MS = 2000;
