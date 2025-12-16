
/**
 * BlobStorageService
 * 
 * Implements a client-side object storage using IndexedDB.
 * This mimics the backend's "Storage Service" but for the browser.
 * It prevents localStorage 5MB limit issues by storing binary data (images, audio)
 * in IndexedDB and returning lightweight identifiers.
 */

const DB_NAME = 'GeminiFluxStorage';
const STORE_NAME = 'blobs';
const DB_VERSION = 1;

class BlobStorageService {
    private dbPromise: Promise<IDBDatabase>;

    constructor() {
        // Handle init failure silently here, errors will be thrown when methods are called
        this.dbPromise = this.initDB().catch(err => {
            console.warn('[BlobStorageService] Initialization failed (IndexedDB access likely denied). Storage will not work.', err);
            throw err;
        });
        // We add a no-op catch to the promise itself to prevent "Unhandled Promise Rejection" 
        // logs during app startup if IndexedDB is blocked (e.g. Incognito/iframe).
        // The actual error will be re-thrown when 'store' or 'get' awaits it.
        this.dbPromise.catch(() => {});
    }

    private initDB(): Promise<IDBDatabase> {
        return new Promise((resolve, reject) => {
            try {
                const request = indexedDB.open(DB_NAME, DB_VERSION);

                request.onerror = () => reject(request.error);
                request.onsuccess = () => resolve(request.result);

                request.onupgradeneeded = (event) => {
                    const db = (event.target as IDBOpenDBRequest).result;
                    if (!db.objectStoreNames.contains(STORE_NAME)) {
                        db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                    }
                };
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * Stores a file/blob and returns a unique ID.
     */
    public async store(blob: Blob): Promise<string> {
        const db = await this.dbPromise;
        const id = crypto.randomUUID();
        
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction([STORE_NAME], 'readwrite');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.add({ id, blob, createdAt: Date.now() });

                request.onsuccess = () => resolve(id);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * Retrieves a blob by ID.
     */
    public async get(id: string): Promise<Blob | null> {
        const db = await this.dbPromise;
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction([STORE_NAME], 'readonly');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.get(id);

                request.onsuccess = () => {
                    resolve(request.result ? request.result.blob : null);
                };
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * Helper: Creates a temporary object URL for an ID.
     * Useful for displaying images.
     */
    public async getUrl(id: string): Promise<string | null> {
        try {
            const blob = await this.get(id);
            if (!blob) return null;
            return URL.createObjectURL(blob);
        } catch (e) {
            console.warn(`[BlobStorageService] Failed to get URL for ${id}`, e);
            return null;
        }
    }

    /**
     * Cleanup old blobs (Simple GC).
     * Keeps blobs for 7 days by default.
     */
    public async cleanup(maxAgeMs = 7 * 24 * 60 * 60 * 1000) {
        try {
            const db = await this.dbPromise;
            const now = Date.now();
            
            const transaction = db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const cursorRequest = store.openCursor();

            cursorRequest.onsuccess = (e) => {
                const cursor = (e.target as IDBRequest).result as IDBCursorWithValue;
                if (cursor) {
                    if (now - cursor.value.createdAt > maxAgeMs) {
                        cursor.delete();
                    }
                    cursor.continue();
                }
            };
        } catch (e) {
            console.warn('[BlobStorageService] Cleanup failed', e);
        }
    }
}

export const blobStorage = new BlobStorageService();
