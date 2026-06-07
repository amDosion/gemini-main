const RETAINED_OBJECT_URL_REVOKE_DELAY_MS = 1_500;
const OBJECT_URL_RECORD_LIMIT = 1000;

const volatileObjectUrls = new Set<string>();
const selfOwnedObjectUrls = new Set<string>();
const retainedObjectUrls = new Map<string, number>();
const retiredObjectUrls = new Set<string>();
const failedObjectUrls = new Set<string>();
const revokedObjectUrls = new Set<string>();
const pendingRevokeObjectUrls = new Map<string, ReturnType<typeof setTimeout>>();
const scheduledFailedObjectUrls = new Set<string>();

export const normalizeString = (value: unknown): string => String(value || '').trim();

export const isTemporaryUrl = (url: string): boolean => {
  const lowered = url.toLowerCase();
  return (
    lowered.startsWith('blob:') || lowered.startsWith('data:') || lowered.startsWith('local-blob:')
  );
};

export const isBlobObjectUrl = (url: string | null | undefined): boolean =>
  normalizeString(url).toLowerCase().startsWith('blob:');

export const hashString = (value: string): string => {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(36);
};

export const canUseCacheStorage = (): boolean =>
  typeof window !== 'undefined' && typeof window.caches !== 'undefined';

export const canUseObjectUrl = (): boolean =>
  typeof window !== 'undefined' &&
  typeof URL !== 'undefined' &&
  typeof URL.createObjectURL === 'function';

const addBoundedObjectUrlRecord = (records: Set<string>, objectUrl: string): void => {
  records.delete(objectUrl);
  records.add(objectUrl);
  while (records.size > OBJECT_URL_RECORD_LIMIT) {
    const oldest = records.values().next().value;
    if (!oldest) break;
    records.delete(oldest);
  }
};

export const markFailedObjectUrl = (objectUrl: string | null | undefined): void => {
  const normalized = normalizeString(objectUrl);
  if (!isBlobObjectUrl(normalized)) return;
  addBoundedObjectUrlRecord(failedObjectUrls, normalized);
};

export const isFailedObjectUrl = (objectUrl: string): boolean => failedObjectUrls.has(objectUrl);

export const hasPendingObjectUrlRevoke = (objectUrl: string): boolean =>
  pendingRevokeObjectUrls.has(objectUrl);

export const clearFailedObjectUrl = (objectUrl: string): void => {
  failedObjectUrls.delete(objectUrl);
};

export const clearRevokedObjectUrl = (objectUrl: string): void => {
  revokedObjectUrls.delete(objectUrl);
};

const clearPendingObjectUrlRevoke = (objectUrl: string): void => {
  const pendingTimer = pendingRevokeObjectUrls.get(objectUrl);
  if (!pendingTimer) return;
  clearTimeout(pendingTimer);
  pendingRevokeObjectUrls.delete(objectUrl);
  if (scheduledFailedObjectUrls.delete(objectUrl)) {
    failedObjectUrls.delete(objectUrl);
  }
};

const revokeObjectUrlNow = (objectUrl: string): void => {
  clearPendingObjectUrlRevoke(objectUrl);
  markFailedObjectUrl(objectUrl);
  volatileObjectUrls.delete(objectUrl);
  selfOwnedObjectUrls.delete(objectUrl);
  retiredObjectUrls.delete(objectUrl);
  retainedObjectUrls.delete(objectUrl);
  if (revokedObjectUrls.has(objectUrl)) {
    return;
  }
  addBoundedObjectUrlRecord(revokedObjectUrls, objectUrl);
  if (!canUseObjectUrl()) return;
  try {
    URL.revokeObjectURL(objectUrl);
  } catch {
    // ignore revoke errors
  }
};

const scheduleObjectUrlRevoke = (objectUrl: string): void => {
  if (revokedObjectUrls.has(objectUrl) || pendingRevokeObjectUrls.has(objectUrl)) return;
  markFailedObjectUrl(objectUrl);
  scheduledFailedObjectUrls.add(objectUrl);
  const timer = setTimeout(() => {
    pendingRevokeObjectUrls.delete(objectUrl);
    scheduledFailedObjectUrls.delete(objectUrl);
    revokeObjectUrlNow(objectUrl);
  }, RETAINED_OBJECT_URL_REVOKE_DELAY_MS);
  pendingRevokeObjectUrls.set(objectUrl, timer);
};

export const revokeTrackedObjectUrl = (
  objectUrl: string,
  options: { force?: boolean; defer?: boolean } = {}
): void => {
  if (!objectUrl) return;
  const retainCount = retainedObjectUrls.get(objectUrl) || 0;
  if (!options.force && retainCount > 0) {
    retiredObjectUrls.add(objectUrl);
    return;
  }

  retiredObjectUrls.delete(objectUrl);
  retainedObjectUrls.delete(objectUrl);
  if (options.defer) {
    scheduleObjectUrlRevoke(objectUrl);
    return;
  }

  revokeObjectUrlNow(objectUrl);
};

export const revokeVolatileObjectUrls = (): void => {
  if (!canUseObjectUrl()) {
    volatileObjectUrls.clear();
    selfOwnedObjectUrls.clear();
    return;
  }
  const objectUrls = Array.from(volatileObjectUrls);
  volatileObjectUrls.clear();
  selfOwnedObjectUrls.clear();
  objectUrls.forEach((objectUrl) => revokeTrackedObjectUrl(objectUrl));
};

export const retainMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  clearPendingObjectUrlRevoke(objectUrl!);
  if (revokedObjectUrls.has(objectUrl!) || failedObjectUrls.has(objectUrl!)) return;
  const current = retainedObjectUrls.get(objectUrl!) || 0;
  retainedObjectUrls.set(objectUrl!, current + 1);
};

export const releaseMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  const current = retainedObjectUrls.get(objectUrl!) || 0;
  if (current <= 1) {
    retainedObjectUrls.delete(objectUrl!);
    if (retiredObjectUrls.has(objectUrl!)) {
      revokeTrackedObjectUrl(objectUrl!, { force: true, defer: true });
    } else if (selfOwnedObjectUrls.has(objectUrl!)) {
      volatileObjectUrls.delete(objectUrl!);
      selfOwnedObjectUrls.delete(objectUrl!);
      revokeTrackedObjectUrl(objectUrl!, { force: true, defer: true });
    }
    return;
  }
  retainedObjectUrls.set(objectUrl!, current - 1);
};

export const createVolatileObjectUrl = (
  blob: Blob,
  options: { selfOwned?: boolean } = {}
): string | null => {
  if (!canUseObjectUrl()) return null;
  const objectUrl = URL.createObjectURL(blob);
  failedObjectUrls.delete(objectUrl);
  revokedObjectUrls.delete(objectUrl);
  volatileObjectUrls.add(objectUrl);
  if (options.selfOwned) {
    selfOwnedObjectUrls.add(objectUrl);
  }
  return objectUrl;
};

export const createManagedMediaObjectUrl = (blob: Blob): string | null =>
  createVolatileObjectUrl(blob);

export const revokeManagedMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  volatileObjectUrls.delete(objectUrl!);
  selfOwnedObjectUrls.delete(objectUrl!);
  revokeTrackedObjectUrl(objectUrl!);
};

export const __resetObjectUrlRegistriesForTest = (): void => {
  volatileObjectUrls.clear();
  selfOwnedObjectUrls.clear();
  retainedObjectUrls.clear();
  retiredObjectUrls.clear();
  failedObjectUrls.clear();
  revokedObjectUrls.clear();
  pendingRevokeObjectUrls.forEach((timer) => clearTimeout(timer));
  pendingRevokeObjectUrls.clear();
  scheduledFailedObjectUrls.clear();
};
