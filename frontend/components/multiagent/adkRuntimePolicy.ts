/**
 * ADK Runtime Policy + Confirm Action Support 提取器。
 *
 * 1:1 抽离自 `adkSessionService.ts` L1006-1243
 * （JIRA-frontend-deep-architecture-split.md #2 Step 2）。
 *
 * 包括：
 * - resolveRuntimeStrategyLabel / normalizeRuntimeStrategyValue 显示标签
 * - collectRuntimeStrategyValues 从 envelope 收集策略候选
 * - buildRuntimePolicyOptions 构造 UI 选项
 * - probeRuntimePolicy 递归探测 envelope 中的 policy 子树
 * - extractAdkRuntimePolicyState 主入口
 * - detectExplicitRejectSupport / extractAdkConfirmActionSupport
 */

import type {
  AdkRuntimePolicyOption,
  AdkRuntimePolicyState,
  AdkConfirmActionSupport,
} from './adkSessionTypes';
import {
  toSafeString,
  isRecord,
  pickFirstString,
  pickFirstValue,
  toBoolean,
  DEFAULT_RUNTIME_STRATEGY,
  RUNTIME_STRATEGY_KEYS,
  STRICT_MODE_KEYS,
  BACKEND_RUNTIME_STRATEGY_OPTIONS,
  RUNTIME_STRATEGY_OPTIONS_KEYS,
  RUNTIME_STRATEGY_LABELS,
  EXPLICIT_REJECT_SUPPORT_KEYS,
  EXPLICIT_REJECT_CONTAINER_KEYS,
} from './adkSessionService';

// 局部类型别名（避免循环类型导入）
type UnknownRecord = Record<string, unknown>;

const resolveRuntimeStrategyLabel = (strategy: string): string =>
  RUNTIME_STRATEGY_LABELS[strategy] || `自定义策略（${strategy}）`;

const normalizeRuntimeStrategyValue = (value: unknown): string => toSafeString(value).toLowerCase();

const collectRuntimeStrategyValues = (sessionSnapshot: unknown): string[] => {
  const collector = new Set<string>();
  const visited = new WeakSet<object>();

  const addStrategy = (rawValue: unknown): void => {
    if (Array.isArray(rawValue)) {
      rawValue.forEach((item) => addStrategy(item));
      return;
    }
    const text = normalizeRuntimeStrategyValue(rawValue);
    if (!text) return;
    collector.add(text);
  };

  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach((item) => visit(item));
      return;
    }
    if (!isRecord(value)) return;
    if (visited.has(value)) return;
    visited.add(value);

    const runtimeStrategy = pickFirstString(value, RUNTIME_STRATEGY_KEYS);
    if (runtimeStrategy) {
      addStrategy(runtimeStrategy);
    }

    for (const key of RUNTIME_STRATEGY_OPTIONS_KEYS) {
      if (!(key in value)) continue;
      addStrategy(value[key]);
    }

    Object.values(value).forEach((nested) => visit(nested));
  };

  visit(sessionSnapshot);

  return Array.from(collector);
};

const buildRuntimePolicyOptions = ({
  sessionSnapshot,
  effectiveStrategy,
  selectedStrategy,
}: {
  sessionSnapshot: unknown;
  effectiveStrategy: string;
  selectedStrategy: string;
}): AdkRuntimePolicyOption[] => {
  const discoveredValues = collectRuntimeStrategyValues(sessionSnapshot);
  const ordered = [
    ...(discoveredValues.length > 0 ? discoveredValues : BACKEND_RUNTIME_STRATEGY_OPTIONS),
    effectiveStrategy,
    selectedStrategy,
  ].filter(Boolean);

  const seen = new Set<string>();
  const deduped: string[] = [];
  ordered.forEach((item) => {
    const normalized = normalizeRuntimeStrategyValue(item);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    deduped.push(normalized);
  });

  return deduped.map((value) => ({
    value,
    label: resolveRuntimeStrategyLabel(value),
  }));
};

interface RuntimePolicyProbe {
  runtimeStrategy: string;
  strictMode: boolean;
  score: number;
  sourcePath: string;
}

const probeRuntimePolicy = (
  value: unknown,
  path: string,
  visited: WeakSet<object>
): RuntimePolicyProbe | null => {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const nested = probeRuntimePolicy(value[index], `${path}[${index}]`, visited);
      if (nested) return nested;
    }
    return null;
  }

  if (!isRecord(value)) return null;
  if (visited.has(value)) return null;
  visited.add(value);

  const runtimeStrategy = pickFirstString(value, RUNTIME_STRATEGY_KEYS);
  const strictModeRaw = pickFirstValue(value, STRICT_MODE_KEYS);
  const hasStrategy = Boolean(runtimeStrategy);
  const hasStrictMode = strictModeRaw !== undefined;
  if (hasStrategy || hasStrictMode) {
    return {
      runtimeStrategy: runtimeStrategy || DEFAULT_RUNTIME_STRATEGY,
      strictMode: hasStrictMode ? toBoolean(strictModeRaw) : false,
      score: (hasStrategy ? 2 : 0) + (hasStrictMode ? 1 : 0),
      sourcePath: path,
    };
  }

  let best: RuntimePolicyProbe | null = null;
  for (const [key, nestedValue] of Object.entries(value)) {
    const nested = probeRuntimePolicy(nestedValue, `${path}.${key}`, visited);
    if (!nested) continue;
    if (!best || nested.score > best.score) {
      best = nested;
    }
  }
  return best;
};

export const extractAdkRuntimePolicyState = (
  sessionSnapshot: unknown,
  draft: Partial<Pick<AdkRuntimePolicyState, 'selectedStrategy' | 'selectedStrictMode'>> = {}
): AdkRuntimePolicyState => {
  const probe = probeRuntimePolicy(sessionSnapshot, 'snapshot', new WeakSet<object>());
  const effectiveStrategy = normalizeRuntimeStrategyValue(
    probe?.runtimeStrategy || DEFAULT_RUNTIME_STRATEGY
  );
  const effectiveStrictMode = probe?.strictMode ?? false;
  const selectedStrategy =
    normalizeRuntimeStrategyValue(draft.selectedStrategy) || effectiveStrategy;
  const selectedStrictMode =
    typeof draft.selectedStrictMode === 'boolean' ? draft.selectedStrictMode : effectiveStrictMode;

  return {
    effectiveStrategy,
    effectiveStrictMode,
    selectedStrategy,
    selectedStrictMode,
    sourcePath: probe?.sourcePath || 'snapshot(default)',
    options: buildRuntimePolicyOptions({
      sessionSnapshot,
      effectiveStrategy,
      selectedStrategy,
    }),
  };
};

const detectExplicitRejectSupport = (record: UnknownRecord): boolean | null => {
  const direct = pickFirstValue(record, EXPLICIT_REJECT_SUPPORT_KEYS);
  if (direct !== undefined) {
    return toBoolean(direct);
  }

  const supportedActions = pickFirstValue(record, [
    'supported_actions',
    'supportedActions',
    'actions',
  ]);
  if (Array.isArray(supportedActions)) {
    const normalized = supportedActions
      .map((item) => toSafeString(item).toLowerCase())
      .filter(Boolean);
    if (normalized.includes('reject') || normalized.includes('deny')) {
      return true;
    }
  }

  const confirmedValues = pickFirstValue(record, ['confirmed_values', 'confirmedValues']);
  if (Array.isArray(confirmedValues)) {
    const hasTrue = confirmedValues.some((item) => item === true || toSafeString(item) === 'true');
    const hasFalse = confirmedValues.some(
      (item) => item === false || toSafeString(item) === 'false'
    );
    if (hasTrue && hasFalse) {
      return true;
    }
  }

  return null;
};

export const extractAdkConfirmActionSupport = (
  sessionSnapshot: unknown
): AdkConfirmActionSupport => {
  const visited = new WeakSet<object>();
  const fallback: AdkConfirmActionSupport = {
    supportsExplicitReject: false,
    sourcePath: 'snapshot(default)',
  };

  const visit = (value: unknown, path: string): AdkConfirmActionSupport | null => {
    if (Array.isArray(value)) {
      for (let index = 0; index < value.length; index += 1) {
        const nested = visit(value[index], `${path}[${index}]`);
        if (nested) return nested;
      }
      return null;
    }

    if (!isRecord(value)) return null;
    if (visited.has(value)) return null;
    visited.add(value);

    const direct = detectExplicitRejectSupport(value);
    if (direct !== null) {
      return {
        supportsExplicitReject: direct,
        sourcePath: path,
      };
    }

    for (const [key, nestedValue] of Object.entries(value)) {
      const nestedPath = `${path}.${key}`;
      if (EXPLICIT_REJECT_CONTAINER_KEYS.has(key) && isRecord(nestedValue)) {
        const container = detectExplicitRejectSupport(nestedValue);
        if (container !== null) {
          return {
            supportsExplicitReject: container,
            sourcePath: nestedPath,
          };
        }
      }
      const nested = visit(nestedValue, nestedPath);
      if (nested) return nested;
    }

    return null;
  };

  return visit(sessionSnapshot, 'snapshot') || fallback;
};

