const RUNTIME_PRIORITY: Record<string, number> = {
  'adk-official': 400,
  adk: 300,
  multimodal: 200,
  adapter: 100,
};

export const normalizeRuntimeHint = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase().replace(/_/g, '-');
  if (!normalized) return undefined;
  const aliases: Record<string, string> = {
    'official-adk': 'adk-official',
    'google-adk-official': 'adk-official',
    adkofficial: 'adk-official',
    'google-adk': 'adk',
    'legacy-adapter': 'adapter',
    'llm-adapter': 'adapter',
  };
  return aliases[normalized] || normalized;
};

export const mergeRuntimeHints = (left: string[] = [], right: string[] = []): string[] => {
  const merged: string[] = [];
  const seen = new Set<string>();
  [...left, ...right].forEach((item) => {
    const normalized = normalizeRuntimeHint(item);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    merged.push(normalized);
  });
  return merged;
};

export const pickPrimaryRuntime = (hints: string[] = []): string | undefined => {
  if (!Array.isArray(hints) || hints.length === 0) return undefined;
  const normalized = hints
    .map((hint) => normalizeRuntimeHint(hint))
    .filter((hint): hint is string => Boolean(hint));
  if (normalized.length === 0) return undefined;
  return normalized.sort((a, b) => {
    const diff = (RUNTIME_PRIORITY[b] || 0) - (RUNTIME_PRIORITY[a] || 0);
    if (diff !== 0) return diff;
    return 0;
  })[0];
};

export const extractRuntimeHints = (payload: unknown, depth = 0, allowScalar = false): string[] => {
  if (depth > 24 || payload === null || payload === undefined) return [];
  if (typeof payload === 'string') {
    const normalized = allowScalar ? normalizeRuntimeHint(payload) : undefined;
    return normalized ? [normalized] : [];
  }
  if (Array.isArray(payload)) {
    return payload.reduce<string[]>((acc, item) => mergeRuntimeHints(acc, extractRuntimeHints(item, depth + 1, allowScalar)), []);
  }
  if (typeof payload !== 'object') {
    return [];
  }

  const result: string[] = [];
  Object.entries(payload).forEach(([key, value]) => {
    const normalizedKey = String(key || '').trim().toLowerCase().replace(/_/g, '');
    if (['runtime', 'primaryruntime', 'runtimehints', 'runtimehint'].includes(normalizedKey)) {
      result.push(...extractRuntimeHints(value, depth + 1, true));
      return;
    }
    result.push(...extractRuntimeHints(value, depth + 1, false));
  });
  return mergeRuntimeHints([], result);
};
