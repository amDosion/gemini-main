# Jira: Frontend AI Media Persistent Browser Cache

## Issue Type
Improvement

## Priority
High

## Summary
AI image views currently rely mostly on plain `<img src="...">` browser behavior. That means the application does not have one shared, cache-first media path for generated images, edited images, history thumbnails, hover previews, and carousel thumbnails.

The required capability is a frontend-owned browser cache that:

- reads already-loaded images from local browser cache before requesting the backend;
- survives normal page reloads and browser restarts;
- updates only media entries whose identity or revision changed;
- deduplicates concurrent cache misses;
- keeps old cached pixels visible while a changed item refreshes;
- avoids persistent caching for temporary `blob:` and `data:` URLs.

`in-flight` request dedupe is not the cache. It is only the protection used after both memory and persistent browser cache miss.

## Implementation Status
First implementation is complete for AI image surfaces.

Implemented:

- `frontend/services/mediaCache.ts`
- `frontend/services/mediaCacheIndexedDb.ts`
- `frontend/hooks/useCachedImageSrc.ts`
- `frontend/components/common/CachedImage.tsx`
- cache wiring for history rows, hover preview attachments, carousel thumbnails, result canvas, and workspace canvas
- cloud storage preview compatibility layer now writes new preview Blob downloads through `mediaCache.ts`
- legacy `cloud-storage-preview-v1` Cache Storage entries are read as a one-release migration fallback and are not written for new downloads
- logout, token invalidation, cross-tab logout, and successful user-switch login clear private shared media cache plus legacy preview cache
- persistent Cache Storage entries are pruned by LRU metadata with entry and byte limits
- dev/test diagnostics expose one shared media-cache counter and recent-event stream for memory hits, persistent hits/misses, network fetches, dedupe, writes, pruning, and clearing
- tests for persistent cache hit, Cache Storage + IndexedDB write, in-flight miss dedupe, data URL exclusion, cached image rendering, and source-switch fallback

Still pending:

- no required cache work remains; future UI can read `getMediaCacheDiagnosticsSnapshot()` if a visual debug panel is needed

## Current Evidence
Backend storage endpoints already expose useful cache semantics:

- `/api/storage/local-files/...` returns `Cache-Control: public, max-age=31536000, immutable`.
- `/api/storage/preview` returns `Cache-Control: private, max-age=86400, stale-while-revalidate=604800` plus `ETag` and `X-Storage-Revision`.

Frontend already has a partial cache implementation:

- `frontend/services/previewCache.ts`
- `frontend/components/views/cloudStorage/useXhrImagePreview.ts`

That cache uses `window.caches`, object URLs, and in-flight download dedupe, but it is only wired into cloud storage preview surfaces. The AI image surfaces still use raw `<img>` tags:

- `frontend/components/common/ImageResultCanvas.tsx`
- `frontend/components/common/ImageWorkspaceCanvas.tsx`
- `frontend/components/common/ImageHistoryListRow.tsx`
- `frontend/components/common/ImageHistoryHoverPreviewPanel.tsx`
- `frontend/components/common/ImageCarouselControls.tsx`

## Capability
After this ships, every AI image surface uses a shared cache-first media resolver. If the image is already in memory or browser persistent cache, it renders without a backend request. If a media revision changes, only that media entry refreshes and the rest of the history/canvas cache remains untouched.

## Non-Goals
- Do not cache `blob:` URLs persistently.
- Do not cache `data:` URLs persistently.
- Do not rewrite the backend storage system.
- Do not prefetch every image in a long history list.
- Do not depend on Service Worker registration.
- Do not use `in-flight` dedupe as a substitute for persistent browser cache.

## Required Cache Layers

### 1. Memory Object URL Cache
Purpose: fastest same-page reads.

- Keyed by canonical media cache key.
- Stores `{ objectUrl, versionSignature, contentType, size, updatedAt, lastAccessedAt }`.
- Reuses the same `blob:` object URL across canvas, history, hover preview, and carousel.
- Revokes object URLs on eviction or replacement.
- LRU bounded, default 400 entries or lower if browser storage estimate is tight.

### 2. Persistent Browser Cache
Purpose: survive reloads and normal browser restarts, and avoid backend requests when reopening sessions.

- Use Cache Storage API via `window.caches`.
- Store image Blob responses in Cache Storage under stable synthetic cache request keys, not raw signed URLs.
- Store metadata manifest in IndexedDB, not localStorage.
- Do not store large Blobs in IndexedDB for the first implementation; IndexedDB owns metadata, Cache Storage owns bytes.
- Browser restart must not clear this layer in normal browsing mode.
- Use `navigator.storage.persisted()` / `navigator.storage.persist()` where available to request best-effort persistent storage.
- Manifest fields:
  - `cacheKey`
  - `sourceUrl`
  - `canonicalUrl`
  - `versionSignature`
  - `etag`
  - `lastModified`
  - `storageRevision`
  - `contentType`
  - `size`
  - `cachedAt`
  - `lastAccessedAt`
  - `userScope`

### 2.1 IndexedDB Metadata Store
Current code has no `idb` or `dexie` dependency. Implement this with native IndexedDB to avoid package churn.

Database:

- name: `gemini-ai-media-cache`
- version: `1`

Object stores:

- `entries`, keyPath `cacheKey`
- indexes:
  - `byUserScope`
  - `byLastAccessedAt`
  - `byVersionSignature`

Entry shape:

```ts
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
```

Cache Storage key:

```text
/__gemini_media_cache__/<encodeURIComponent(cacheKey)>
```

### 3. Request Dedupe for Cache Misses
Purpose: prevent duplicate backend requests only after cache miss.

Flow:

```text
need image
  -> memory object URL hit: render, no backend request
  -> persistent Cache Storage hit: create/reuse object URL, render, no backend request
  -> persistent miss:
       if same cache key already downloading: await shared promise
       else request backend once
  -> store Blob in persistent cache and memory cache
  -> render
```

## Media Identity
The cache key must be stable across volatile URLs.

Priority:

1. `attachment.id` if present: `media:attachment:<attachment.id>`
2. durable storage path if present: `media:path:<normalized path>`
3. fallback URL hash: `media:url:<stableHash(canonicalUrl)>`

Canonical URL rules:

- Preserve same-origin durable paths such as `/api/storage/local-files/...`.
- For `/api/storage/preview?url=...&rev=...`, canonical identity is the nested `url` plus user scope; `rev` belongs in `versionSignature`.
- Drop volatile auth/signature query params from identity when safe.
- Keep query params that identify different image content.
- Never convert `blob:` or `data:` into persistent cache keys.

## Version Signature
The version signature decides whether cached bytes are still usable without contacting the backend.

Priority:

1. `storageRevision` or `rev` for storage preview URLs.
2. `attachment.updatedAt` / `createdAt` when reliable.
3. `attachment.uploadTaskId` transition from pending to completed.
4. `ETag` / `Last-Modified` captured from previous fetch.
5. Canonical URL string as final fallback.

Rules:

- If `cacheKey` and `versionSignature` are unchanged, render from cache and do not request the backend.
- If `cacheKey` is unchanged but `versionSignature` changed, keep old cached image visible while refreshing that key.
- If refresh returns `304`, update metadata only and keep existing Blob.
- If refresh returns `200`, replace the Blob, revoke old object URL, and update metadata.
- If refresh fails, keep stale cached image visible and mark status `stale-error`.

## Source Policy

### Persistently Cache
- Same-origin `/api/storage/local-files/...`
- Same-origin `/api/storage/preview?...`
- Other same-origin image endpoints that require cookies and are safe to fetch as Blob

### Memory Only
- `blob:`
- `data:`
- local `File` object previews

### Raw `<img>` Fallback
- Cross-origin URLs without CORS support
- URLs rejected by existing safety checks
- Non-image MIME types

## API Design

Create `frontend/services/mediaCache.ts`.

Current-code fit:

- Use the existing `frontend/services/httpProgress.ts` `downloadBlobWithXhr()` for Blob downloads and header capture.
- Use the existing `frontend/services/storagePreviewService.ts` URL safety helpers.
- Use the existing `frontend/services/CacheManager.ts` only for same-page object URL memory cache.
- Do not add third-party IndexedDB dependencies.

Core types:

```ts
export interface MediaCacheSource {
  attachmentId?: string | null;
  url?: string | null;
  previewUrl?: string | null;
  mimeType?: string | null;
  uploadStatus?: string | null;
  uploadTaskId?: string | null;
  storageRevision?: number | string | null;
  updatedAt?: number | string | null;
  createdAt?: number | string | null;
  userScope?: string | null;
}

export type MediaCacheStatus =
  | 'idle'
  | 'memory-hit'
  | 'persistent-hit'
  | 'loading'
  | 'fresh'
  | 'stale'
  | 'stale-error'
  | 'raw-fallback'
  | 'error';
```

Service functions:

```ts
resolveMediaCacheKey(source: MediaCacheSource): MediaCacheIdentity | null;
getCachedMediaObjectUrlSync(identity: MediaCacheIdentity): string | null;
getCachedMediaObjectUrl(identity: MediaCacheIdentity): Promise<string | null>;
fetchAndStoreMedia(identity: MediaCacheIdentity, options?: FetchOptions): Promise<CachedMedia>;
invalidateMediaCache(identityOrPrefix: string): Promise<void>;
clearUserMediaCache(userScope: string): Promise<void>;
```

Create `frontend/services/mediaCacheIndexedDb.ts`.

Responsibilities:

- open/upgrade native IndexedDB database;
- read/write/delete `MediaCacheMetadata`;
- list stale entries by `lastAccessedAt`;
- list entries by `userScope`;
- degrade cleanly when IndexedDB is unavailable.

Keep all IndexedDB code in this file so `mediaCache.ts` stays readable and testable.

Create `frontend/hooks/useCachedImageSrc.ts`.

Hook contract:

```ts
const { src, status, error, refresh } = useCachedImageSrc(source, {
  enabled: true,
  preferStale: true,
  revalidate: 'on-version-change',
});
```

Create `frontend/components/common/CachedImage.tsx`.

Component contract:

```tsx
<CachedImage
  source={attachment}
  src={fallbackUrl}
  alt="History preview"
  className="..."
  loading="lazy"
/>
```

The component must preserve standard `<img>` behavior while substituting cache-resolved `src`.

## Read and Update Flow

### Initial Render
1. Build identity from attachment/url.
2. Try memory object URL synchronously.
3. If found, render immediately.
4. Otherwise check persistent Cache Storage.
5. If found, create object URL and render.
6. If not found, fetch once, store Blob, render.

### Incremental Update
1. Receive new session messages or attachment metadata.
2. For each visible/active media item, compare `cacheKey + versionSignature`.
3. Unchanged entries: no network request.
4. Changed entries: refresh only that entry.
5. Deleted entries: do not immediately purge bytes unless cache pressure requires it; update manifest access metadata.

### Background Warmup
Only prewarm:

- active canvas image;
- visible history rows;
- hover-preview images after hover opens;
- carousel neighbors: current index - 1 and + 1.

Do not prewarm all historical images by default.

## Integration Points

### Phase 1: Shared Cache Service
- Add `mediaCache.ts`.
- Add `mediaCacheIndexedDb.ts`.
- Reuse and migrate logic from `previewCache.ts`.
- Keep `previewCache.ts` as a compatibility wrapper or move cloud storage to the new service in the same PR.

### Phase 2: Hook and Component
- Add `useCachedImageSrc`.
- Add `CachedImage`.
- Unit test memory hit, persistent hit, miss, version change, and raw fallback.

### Phase 3: AI Image Surfaces
Replace direct image tags in:

- `frontend/components/common/ImageHistoryListRow.tsx`
- `frontend/components/common/ImageHistoryHoverPreviewPanel.tsx`
- `frontend/components/common/ImageCarouselControls.tsx`
- `frontend/components/common/ImageResultCanvas.tsx`
- `frontend/components/common/ImageWorkspaceCanvas.tsx`

### Phase 4: Existing Cloud Storage Cache Migration
- Keep `useXhrImagePreview` queue/fallback logic intact.
- Repoint `previewCache.ts` writes to `mediaCache.ts`.
- Avoid maintaining two persistent cache formats for new writes.
- Keep backward-compatible read for `cloud-storage-preview-v1` during one release.
- Current migration source files:
  - `frontend/services/previewCache.ts`
  - `frontend/components/views/cloudStorage/useXhrImagePreview.ts`
  - `frontend/components/views/cloudStorage/useXhrImagePreview.test.tsx`

### Phase 5: Observability and Controls
- Development logging behind a flag:
  - memory hit
  - persistent hit
  - network miss
  - revalidate 304
  - revalidate 200
  - stale-error
- Optional debug UI counter for media cache hit rate.

## Security and Privacy
- Cache entries must be user-scoped.
- Clear private media cache on logout.
- Do not persist cache entries for unknown user scope unless the URL is public immutable local storage.
- Do not store Authorization headers.
- Do not expose cached object URLs outside the current page.
- Enforce existing safe URL checks before XHR/fetch.
- Respect browser quota and evict LRU entries before writes if needed.

## Concrete File Plan

Add:

- `frontend/services/mediaCacheIndexedDb.ts`
- `frontend/services/mediaCache.ts`
- `frontend/services/mediaCache.test.ts`
- `frontend/hooks/useCachedImageSrc.ts`
- `frontend/hooks/useCachedImageSrc.test.tsx`
- `frontend/components/common/CachedImage.tsx`
- `frontend/components/common/CachedImage.test.tsx`

Modify first wave:

- `frontend/components/common/ImageHistoryListRow.tsx`
- `frontend/components/common/ImageHistoryHoverPreviewPanel.tsx`
- `frontend/components/common/ImageCarouselControls.tsx`

Modify second wave:

- `frontend/components/common/ImageResultCanvas.tsx`
- `frontend/components/common/ImageWorkspaceCanvas.tsx`

Compatibility/migration:

- `frontend/services/previewCache.ts`
- `frontend/components/views/cloudStorage/useXhrImagePreview.ts`

Do not modify package dependencies for the initial implementation.

## Failure Behavior
- Cache read failure: fall back to raw URL.
- Cache write failure: render downloaded Blob/object URL for current session, but mark status `fresh-memory-only`.
- Backend fetch failure with stale cache: continue showing stale cache.
- Backend fetch failure without stale cache: show normal image load failure UI.
- Object URL revoke failure: ignore and continue eviction.

## Known Limitations and Tradeoffs
- Cache Storage and IndexedDB normally survive browser restarts, but they are not permanent storage.
- The browser may evict cached media under storage pressure unless persistent storage is granted.
- User actions such as clearing site data, logging out with cache clearing enabled, or using private/incognito mode can remove cached media.
- Cross-origin images without CORS support may need raw `<img>` fallback and may not be persistently cached by the app.
- Persisting generated media locally improves performance but consumes disk space; LRU and quota-based eviction are required.
- Requesting persistent storage is best-effort and browser-dependent; the app must continue to work when it is denied.

## Acceptance Criteria
- Rendering the same AI image twice in one page session uses the same object URL and does not request the backend twice.
- Reloading the page and opening a previously cached AI image reads from Cache Storage without a backend request when `versionSignature` is unchanged.
- Closing and reopening the browser in normal browsing mode still reads previously cached AI images from persistent browser cache when `versionSignature` is unchanged.
- Two components mounting the same uncached image at the same time produce one backend request, not two.
- Updating one image revision refreshes only that cache entry.
- `304 Not Modified` refreshes metadata without replacing the cached Blob.
- `blob:` and `data:` sources are never written to persistent cache.
- Logout clears user-scoped private media cache.
- History list, hover preview, carousel thumbnails, and active canvas all share the same cache.
- Existing cloud storage preview behavior remains compatible.
- If browser storage has been evicted or site data has been cleared, the app refetches from the backend and repopulates cache without breaking history rendering.

## Test Plan

### Unit Tests
- `mediaCache` returns memory object URL without calling fetch.
- `mediaCache` returns persistent Cache Storage Blob without calling fetch.
- `mediaCache` calls fetch once on miss and stores Blob.
- `mediaCache` writes Blob bytes to Cache Storage and metadata to IndexedDB.
- IndexedDB metadata lookup determines unchanged `versionSignature` without backend request.
- concurrent misses share one in-flight request.
- unchanged `versionSignature` skips backend request.
- changed `versionSignature` refreshes only one key.
- `304` keeps existing Blob and updates metadata.
- `blob:` and `data:` do not persist.
- LRU eviction revokes object URLs.

### Component Tests
- `CachedImage` renders cached `src` before network.
- `ImageHistoryListRow` uses cached image source.
- `ImageHistoryHoverPreviewPanel` uses cached image source.
- `ImageResultCanvas` uses cached image source.
- `ImageWorkspaceCanvas` uses cached image source.

### Manual Verification
1. Generate an image.
2. Open history hover preview and active canvas.
3. Confirm the first load writes cache.
4. Reload the page.
5. Open the same session and confirm cached image renders before any backend image request.
6. Generate a new version of one image and confirm only that image refreshes.

## Rollout
1. Ship behind feature flag `mediaCacheEnabled`.
2. Enable for history thumbnails and hover previews first.
3. Enable for carousel and main canvas.
4. Migrate cloud storage preview to shared service.
5. Remove compatibility wrapper after one release cycle.

## Open Questions
- What user identifier is safest for `userScope` in the frontend cache key?
- Should cache survive logout for local public files, or should all entries be cleared for simplicity?
- What default quota should be used: entry count, byte size, or both?

## Implementation Handoff
Initial implementation has shipped for AI image surfaces. Remaining follow-up lane:

1. decide final `userScope` value and logout clearing policy;
2. optionally add a visual debug panel that reads the existing shared diagnostics snapshot.
