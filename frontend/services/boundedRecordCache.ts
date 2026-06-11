interface UpsertBoundedRecordParams<T> {
  record: Record<string, T>;
  key: string;
  value: T;
  maxEntries: number;
  protectedKeys?: Array<string | null | undefined>;
}

const normalizeRecordKey = (key: string | null | undefined): string => {
  return String(key || '').trim();
};

const toEvictionProtectedSet = (
  protectedKeys: Array<string | null | undefined> | undefined
): Set<string> => {
  const entries = Array.isArray(protectedKeys) ? protectedKeys : [];
  const normalized = entries
    .map((item) => normalizeRecordKey(item))
    .filter((item) => item.length > 0);
  return new Set(normalized);
};

const normalizeMaxEntries = (rawMaxEntries: number): number => {
  if (!Number.isFinite(rawMaxEntries)) return 0;
  return Math.max(0, Math.floor(rawMaxEntries));
};

export const upsertBoundedRecord = <T>({
  record,
  key,
  value,
  maxEntries,
  protectedKeys,
}: UpsertBoundedRecordParams<T>): Record<string, T> => {
  const normalizedKey = normalizeRecordKey(key);
  if (!normalizedKey) {
    return record;
  }

  const normalizedMaxEntries = normalizeMaxEntries(maxEntries);
  const next: Record<string, T> = { ...record };
  if (Object.prototype.hasOwnProperty.call(next, normalizedKey)) {
    delete next[normalizedKey];
  }
  next[normalizedKey] = value;

  if (normalizedMaxEntries <= 0) {
    return { [normalizedKey]: value };
  }

  const keys = Object.keys(next);
  let excess = keys.length - normalizedMaxEntries;
  if (excess > 0) {
    const evictionProtectedSet = toEvictionProtectedSet(protectedKeys);
    for (const candidateKey of keys) {
      if (excess <= 0) break;
      if (evictionProtectedSet.has(candidateKey)) continue;
      delete next[candidateKey];
      excess -= 1;
    }
  }

  return next;
};

export const removeRecordKey = <T>(record: Record<string, T>, key: string): Record<string, T> => {
  const normalizedKey = normalizeRecordKey(key);
  if (!normalizedKey || !Object.prototype.hasOwnProperty.call(record, normalizedKey)) {
    return record;
  }
  const next = { ...record };
  delete next[normalizedKey];
  return next;
};
