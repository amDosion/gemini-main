const RUNTIME_PRIORITY: Record<string, number> = {
  'adk-official': 400,
  adk: 300,
  multimodal: 200,
  adapter: 100,
};

const RUNTIME_HINT_ALIASES: Record<string, string> = {
  'official-adk': 'adk-official',
  'google-adk-official': 'adk-official',
  adkofficial: 'adk-official',
  'google-adk': 'adk',
  'legacy-adapter': 'adapter',
  'llm-adapter': 'adapter',
};

const RUNTIME_HINT_KEYS = new Set(['runtime', 'primaryruntime', 'runtimehints', 'runtimehint']);

export const normalizeRuntimeHint = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase().replace(/_/g, '-');
  if (!normalized) return undefined;
  return RUNTIME_HINT_ALIASES[normalized] || normalized;
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
  if (hints.length === 0) return undefined;
  const normalized = hints
    .map((hint) => normalizeRuntimeHint(hint))
    .filter((hint): hint is string => Boolean(hint));
  if (normalized.length === 0) return undefined;
  return normalized.sort((a, b) => (RUNTIME_PRIORITY[b] || 0) - (RUNTIME_PRIORITY[a] || 0))[0];
};

export const extractRuntimeHints = (payload: unknown, depth = 0, allowScalar = false): string[] => {
  if (depth > 24 || payload === null || payload === undefined) return [];
  if (typeof payload === 'string') {
    const normalized = allowScalar ? normalizeRuntimeHint(payload) : undefined;
    return normalized ? [normalized] : [];
  }
  if (Array.isArray(payload)) {
    return payload.reduce<string[]>(
      (acc, item) => mergeRuntimeHints(acc, extractRuntimeHints(item, depth + 1, allowScalar)),
      []
    );
  }
  if (typeof payload !== 'object') {
    return [];
  }

  const result: string[] = [];
  Object.entries(payload).forEach(([key, value]) => {
    const normalizedKey = key.trim().toLowerCase().replace(/_/g, '');
    result.push(...extractRuntimeHints(value, depth + 1, RUNTIME_HINT_KEYS.has(normalizedKey)));
  });
  return mergeRuntimeHints([], result);
};
