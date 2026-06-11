/**
 * Workflow 视频/图片 分辨率与时长规范化工具集。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L76-204
 * （JIRA-frontend-view-decomposition.md P0 #1 Step 1）。
 *
 * 用于将旧版/外部传入的不规范 resolution / seconds / extension 值
 * 归一到当前模式 schema 中合法的取值，并给出适当 fallback。
 */

import {
  getPixelResolutionFromSchema,
  useModeControlsSchema,
} from '../../hooks/useModeControlsSchema';
import { normalizeWorkflowVideoResolution } from './workflowContract';

/** 静态分辨率映射（tier × ratio → "WxH" 字符串），用于无 schema 信息时的标签 fallback */
export const WORKFLOW_RESOLUTION_MAP: Record<string, Record<string, string>> = {
  '1K': {
    '1:1': '1024×1024',
    '2:3': '682×1024',
    '3:2': '1024×682',
    '3:4': '768×1024',
    '4:3': '1024×768',
    '4:5': '819×1024',
    '5:4': '1024×819',
    '9:16': '576×1024',
    '16:9': '1024×576',
    '21:9': '1024×438',
  },
  '1.5K': {
    '1:1': '1536×1536',
    '2:3': '1248×1872',
    '3:2': '1872×1248',
    '3:4': '1152×1536',
    '4:3': '1536×1152',
    '4:5': '1228×1536',
    '5:4': '1536×1228',
    '9:16': '864×1536',
    '16:9': '1536×864',
    '21:9': '1536×658',
  },
  '2K': {
    '1:1': '2048×2048',
    '2:3': '1365×2048',
    '3:2': '2048×1365',
    '3:4': '1536×2048',
    '4:3': '2048×1536',
    '4:5': '1638×2048',
    '5:4': '2048×1638',
    '9:16': '1152×2048',
    '16:9': '2048×1152',
    '21:9': '2048×877',
  },
  '4K': {
    '1:1': '4096×4096',
    '2:3': '2730×4096',
    '3:2': '4096×2730',
    '3:4': '3072×4096',
    '4:3': '4096×3072',
    '4:5': '3276×4096',
    '5:4': '4096×3276',
    '9:16': '2304×4096',
    '16:9': '4096×2304',
    '21:9': '4096×1755',
  },
};

export function getResolutionLabel(tier: string, ratio: string): string {
  const map = WORKFLOW_RESOLUTION_MAP[tier];
  if (!map) return tier;
  return map[ratio] || map['1:1'] || tier;
}

export function normalizeWorkflowVideoResolutionSelection(
  value: unknown,
  validValues: string[],
  fallbackValue: string
): string {
  const raw = String(value || '').trim();
  if (!raw) {
    return fallbackValue;
  }
  if (validValues.includes(raw)) {
    return raw;
  }
  const alias = normalizeWorkflowVideoResolution(raw);
  if (alias && validValues.includes(alias)) {
    return alias;
  }
  return fallbackValue;
}

export function normalizeWorkflowVideoSecondsSelection(
  value: unknown,
  validValues: string[],
  fallbackValue: string
): string {
  const raw = String(value ?? '').trim();
  if (!raw) {
    return fallbackValue;
  }
  if (validValues.length === 0 || validValues.includes(raw)) {
    return raw;
  }
  return fallbackValue;
}

export function normalizeWorkflowVideoExtensionSelection(
  value: unknown,
  validValues: number[],
  fallbackValue: number
): number {
  const parsed = Number(value);
  if (Number.isFinite(parsed) && validValues.includes(parsed)) {
    return parsed;
  }
  if (validValues.includes(fallbackValue)) {
    return fallbackValue;
  }
  return validValues[0] ?? fallbackValue;
}

export function getWorkflowVideoResolutionLabel(
  aspectRatio: string,
  resolution: string,
  schema: ReturnType<typeof useModeControlsSchema>['schema']
): string {
  const schemaLabel =
    schema?.resolutionTiers?.find((item) => item.value === resolution)?.label || resolution;
  const pixels = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
  if (pixels) {
    return `${schemaLabel} (${pixels})`;
  }
  return schemaLabel;
}
