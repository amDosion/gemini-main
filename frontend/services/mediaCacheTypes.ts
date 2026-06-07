import { type MediaCacheMetadata } from './mediaCacheIndexedDb';

export interface MediaCacheSource {
  id?: string | null;
  attachmentId?: string | null;
  url?: string | null;
  tempUrl?: string | null;
  temp_url?: string | null;
  cloudUrl?: string | null;
  cloud_url?: string | null;
  previewUrl?: string | null;
  mimeType?: string | null;
  mime_type?: string | null;
  name?: string | null;
  file?: Blob | null;
  uploadStatus?: string | null;
  upload_status?: string | null;
  uploadTaskId?: string | null;
  upload_task_id?: string | null;
  storageRevision?: number | string | null;
  updatedAt?: number | string | null;
  createdAt?: number | string | null;
  userScope?: string | null;
  fileUri?: string | null;
  file_uri?: string | null;
}

export interface MediaCacheIdentity {
  cacheKey: string;
  attachmentId?: string | null;
  sourceUrl: string;
  canonicalUrl: string;
  versionSignature: string;
  storageRevision?: string | null;
  userScope: string;
  persistable: boolean;
  sourceBlob?: Blob | null;
  seedUrl?: string | null;
  temporary?: boolean;
}

export type MediaCacheStatus =
  | 'idle'
  | 'memory-hit'
  | 'persistent-hit'
  | 'loading'
  | 'fresh'
  | 'fresh-memory-only'
  | 'stale'
  | 'stale-error'
  | 'raw-fallback'
  | 'error';

export interface CachedMedia {
  objectUrl: string;
  status: 'fresh' | 'fresh-memory-only' | 'persistent-hit' | 'stale' | 'not-modified';
  metadata?: MediaCacheMetadata | null;
}

export type MediaCacheDiagnosticEventType =
  | 'memory-hit'
  | 'persistent-hit'
  | 'persistent-miss'
  | 'network-fetch'
  | 'network-dedupe'
  | 'network-304'
  | 'cache-write'
  | 'cache-write-memory-only'
  | 'prune-entry'
  | 'clear-entry';

export interface MediaCacheDiagnosticEvent {
  type: MediaCacheDiagnosticEventType;
  cacheKey?: string;
  sourceUrl?: string;
  userScope?: string;
  size?: number | null;
  reason?: string;
  timestamp: number;
}

export interface MediaCacheDiagnosticsSnapshot {
  enabled: boolean;
  counters: Partial<Record<MediaCacheDiagnosticEventType, number>>;
  recentEvents: MediaCacheDiagnosticEvent[];
}

export interface MemoryEntry {
  objectUrl: string;
  versionSignature: string;
  updatedAt: number;
  lastAccessedAt: number;
}

export interface FetchAndStoreOptions {
  allowRevalidate?: boolean;
  replaceObjectUrl?: boolean;
}

export interface SaveMediaBlobOptions {
  contentType?: string | null;
  etag?: string | null;
  lastModified?: string | null;
}

export interface GetCachedOptions {
  allowStale?: boolean;
  allowMemory?: boolean;
  replaceObjectUrl?: boolean;
}

export interface AttachmentCloudUrlResponse {
  url?: string | null;
  cloudUrl?: string | null;
  cloud_url?: string | null;
  uploadStatus?: string | null;
  upload_status?: string | null;
}
