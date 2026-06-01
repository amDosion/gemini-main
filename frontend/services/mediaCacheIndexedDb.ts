export interface MediaCacheMetadata {
  cacheKey: string;
  sourceUrl: string;
  canonicalUrl: string;
  versionSignature: string;
  etag?: string | null;
  lastModified?: string | null;
  storageRevision?: string | null;
  contentType?: string | null;
  size?: number | null;
  cachedAt: number;
  lastAccessedAt: number;
  userScope: string;
}

const DB_NAME = 'gemini-ai-media-cache';
const DB_VERSION = 1;
const STORE_NAME = 'entries';

const canUseIndexedDb = (): boolean =>
  typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined';

const requestToPromise = <T>(request: IDBRequest<T>): Promise<T> =>
  new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed'));
  });

let dbPromise: Promise<IDBDatabase | null> | null = null;

const openMediaCacheDb = async (): Promise<IDBDatabase | null> => {
  if (!canUseIndexedDb()) return null;
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      const store = db.objectStoreNames.contains(STORE_NAME)
        ? request.transaction?.objectStore(STORE_NAME)
        : db.createObjectStore(STORE_NAME, { keyPath: 'cacheKey' });

      if (!store) return;
      if (!store.indexNames.contains('byUserScope')) {
        store.createIndex('byUserScope', 'userScope', { unique: false });
      }
      if (!store.indexNames.contains('byLastAccessedAt')) {
        store.createIndex('byLastAccessedAt', 'lastAccessedAt', { unique: false });
      }
      if (!store.indexNames.contains('byVersionSignature')) {
        store.createIndex('byVersionSignature', 'versionSignature', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
    request.onblocked = () => resolve(null);
  });

  return dbPromise;
};

const withStore = async <T>(
  mode: IDBTransactionMode,
  callback: (store: IDBObjectStore) => IDBRequest<T>
): Promise<T | null> => {
  const db = await openMediaCacheDb();
  if (!db) return null;

  try {
    const transaction = db.transaction(STORE_NAME, mode);
    const store = transaction.objectStore(STORE_NAME);
    return await requestToPromise(callback(store));
  } catch {
    return null;
  }
};

export const readMediaCacheMetadata = async (
  cacheKey: string
): Promise<MediaCacheMetadata | null> => {
  const normalizedKey = String(cacheKey || '').trim();
  if (!normalizedKey) return null;
  return await withStore<MediaCacheMetadata>('readonly', (store) => store.get(normalizedKey));
};

export const writeMediaCacheMetadata = async (
  metadata: MediaCacheMetadata
): Promise<void> => {
  if (!metadata.cacheKey) return;
  await withStore<IDBValidKey>('readwrite', (store) => store.put(metadata));
};

export const deleteMediaCacheMetadata = async (cacheKey: string): Promise<void> => {
  const normalizedKey = String(cacheKey || '').trim();
  if (!normalizedKey) return;
  await withStore<undefined>('readwrite', (store) => store.delete(normalizedKey));
};

export const listMediaCacheMetadata = async (): Promise<MediaCacheMetadata[]> => {
  const result = await withStore<MediaCacheMetadata[]>('readonly', (store) => store.getAll());
  return Array.isArray(result) ? result : [];
};

export const __resetMediaCacheIndexedDbForTest = (): void => {
  dbPromise = null;
};
