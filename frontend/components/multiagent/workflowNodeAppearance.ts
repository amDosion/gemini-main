import type { CSSProperties } from 'react';
import type { NodeTypeConfig } from './nodeTypeConfigs';
import type { WorkflowNodeData } from './types';

const TAILWIND_COLOR_MAP: Record<string, string> = {
  'bg-blue-500': '#3b82f6',
  'bg-red-500': '#ef4444',
  'bg-emerald-500': '#10b981',
  'bg-lime-500': '#84cc16',
  'bg-indigo-500': '#6366f1',
  'bg-sky-500': '#0ea5e9',
  'bg-cyan-500': '#06b6d4',
  'bg-yellow-500': '#eab308',
  'bg-orange-500': '#f97316',
  'bg-amber-500': '#f59e0b',
  'bg-teal-500': '#14b8a6',
  'bg-pink-500': '#ec4899',
  'bg-violet-500': '#8b5cf6',
  'bg-slate-500': '#64748b',
};

export const isCssColorToken = (value: unknown): boolean => {
  const text = String(value || '').trim();
  return (
    text.startsWith('#') ||
    text.startsWith('rgb(') ||
    text.startsWith('rgba(') ||
    text.startsWith('hsl(') ||
    text.startsWith('hsla(')
  );
};

export const resolveNodeIconAppearance = (
  data: Partial<WorkflowNodeData>,
  config: NodeTypeConfig
): {
  icon: string;
  iconColorClassName: string;
  iconColorStyle: CSSProperties | undefined;
} => {
  const icon = String(data.icon || config.icon || '').trim() || config.icon;
  const iconColor = String(data.iconColor || config.iconColor || '').trim() || config.iconColor;
  if (isCssColorToken(iconColor)) {
    return {
      icon,
      iconColorClassName: '',
      iconColorStyle: { backgroundColor: iconColor },
    };
  }
  return {
    icon,
    iconColorClassName: iconColor,
    iconColorStyle: undefined,
  };
};

export const resolveNodeMiniMapColor = (
  data: Partial<WorkflowNodeData>,
  config: NodeTypeConfig
): string => {
  const iconColor = String(data.iconColor || config.iconColor || '').trim();
  if (isCssColorToken(iconColor)) {
    return iconColor;
  }
  return TAILWIND_COLOR_MAP[iconColor] || '#475569';
};
