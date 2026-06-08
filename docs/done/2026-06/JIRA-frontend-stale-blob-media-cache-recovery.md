# Jira: Frontend Media Cache Recovers Revoked Blob Attachments

## Issue Type
Bug

## Priority
High

## Summary
When a user switches image history items quickly, an image may remain in the UI with a stale `blob:` URL before the cache write or backend upload state finishes. If the browser later revokes that object URL, switching back can produce:

```text
GET blob:https://gemini.dicry.cn:18443/... net::ERR_FILE_NOT_FOUND
```

The expected behavior is that image rendering never depends on a stale raw `blob:` URL once an attachment identity exists. The shared frontend media cache should recover the durable attachment URL through the existing backend `/api/attachments/{attachment_id}/cloud-url` contract, fetch the durable image once, store it in Cache Storage, and render the cached object URL.

## Confirmed Root Cause
- `frontend/services/mediaCache.ts` can identify temporary attachment images by `attachmentId`, but the identity does not retain `attachmentId` for later recovery.
- For a temporary identity without an in-memory `File`/`Blob`, `fetchMediaBlob()` fetches the original raw `blob:` URL directly.
- If that raw blob was revoked by the browser, the fetch fails.
- `frontend/hooks/useCachedImageSrc.ts` then falls back to `fallbackSrc`, which is often the same stale `blob:` URL, putting the broken URL back into the `<img>`.
- The backend already exposes `/api/attachments/{attachment_id}/cloud-url`, but the shared media cache does not use it.

## Impact
- Generated or uploaded images can disappear when users switch between history records before image loading completes.
- The error is most visible after fast history switching, reload-adjacent flows, or when the browser reclaims blob URLs.
- The issue affects all AI image surfaces that use the shared cached image path, including generated canvas, workspace canvas, history thumbnails, hover previews, and carousel thumbnails.

## Scope
The fix must stay centralized in the common media-loading path:

- `frontend/services/mediaCache.ts`
- `frontend/hooks/useCachedImageSrc.ts`
- targeted tests for these modules

The fix must not add separate recovery logic to each mode component. `image-gen`, `chat-edit`, `mask/background/recontext/inpainting`, attachment upload previews, canvas rendering, history rows, and hover previews should all benefit through the same shared cache path.

## Requirements
1. Temporary attachment identities must retain `attachmentId`.
2. A temporary attachment with no live `File`/`Blob` must query `/api/attachments/{attachment_id}/cloud-url` before attempting to use the raw `blob:` URL.
3. If the backend returns a durable same-origin storage URL, the cache must fetch that URL, write Cache Storage plus IndexedDB metadata under the same attachment cache key, and render the cached object URL.
4. If the backend returns an external storage URL that is allowed by the existing preview safety policy, the cache must use the same-origin `/api/storage/preview?url=...` proxy.
5. If recovery fails and the raw blob is unavailable, `useCachedImageSrc()` must not put the stale temporary URL back into the image element.
6. Existing successful paths must remain intact:
   - persistent `/api/storage/local-files/...` URLs
   - `/api/storage/preview?...` URLs
   - file-backed local upload blobs
   - memory cache hits
   - Cache Storage hits
   - in-flight request dedupe

## Acceptance Criteria
- Switching away from a not-yet-loaded temporary attachment and switching back does not render a revoked raw `blob:` URL.
- A stale temporary attachment with `attachmentId` recovers through `/api/attachments/{attachment_id}/cloud-url`.
- The recovered durable image is cached under `media:attachment:<attachmentId>`.
- The browser image `src` becomes a cache-owned object URL, not the stale raw `blob:` URL.
- When recovery fails, the hook reports an error state without reusing the stale temporary URL as fallback.
- No duplicated per-mode image recovery logic is introduced.

## Test Plan
- Add a media cache unit test for a stale temporary blob identity that recovers through `/api/attachments/{attachment_id}/cloud-url`.
- Add a hook unit test proving temporary recovery failure does not fall back to raw `blob:` URLs.
- Re-run the media cache, cached image, preview cache, image history row, auth/media cache, and session cache related tests.
- Run TypeScript type checking.

## Implementation Plan
1. Add failing tests for the stale blob recovery path and temporary fallback guard.
2. Extend `MediaCacheIdentity` with `attachmentId`.
3. Resolve a temporary identity into a durable fetch identity before network download:
   - use local `sourceBlob` immediately when present;
   - otherwise call `/api/attachments/{attachmentId}/cloud-url`;
   - normalize returned durable URLs through the existing storage preview safety rules;
   - preserve the same attachment cache key.
4. Fetch and persist using the recovered durable identity so metadata records the durable `sourceUrl`.
5. Change `useCachedImageSrc()` so temporary identities do not reapply raw temporary fallback URLs after cache recovery failure.

## Implementation Status
Completed in the shared frontend media path.

- `MediaCacheIdentity` now carries `attachmentId`.
- Temporary attachment identities without a live `File`/`Blob` now call `/api/attachments/{attachment_id}/cloud-url` before fetching media.
- Durable same-origin storage URLs are fetched directly.
- External durable URLs are normalized through `/api/storage/preview?url=...`.
- Recovered bytes are persisted under the original attachment cache key.
- Temporary recovery failures no longer put raw `blob:` fallback URLs back into the image element.
- `CachedImage` no longer re-applies raw `src` after the cache hook returns no usable image for a cache-managed source.
- `image-outpainting` history thumbnails, source preview, `image-inpainting` sidebar thumbnails, `image-background-edit` sidebar thumbnails, mask edit sidebar thumbnails, and `virtual-try-on` result/history images now route through `CachedImage` instead of direct `<img src={...}>`.
- Durable attachment identities now support seed bytes from already available frontend media:
  - `File`/`Blob` sources are written directly into the shared cache.
  - `data:image/...` sources are decoded locally into a Blob and written into the shared cache without any backend request.
  - local `blob:` seed URLs are tried before durable storage fetches when they are explicitly present beside a durable URL.
  - the cache key and metadata still use the durable attachment identity, so later reloads read from Cache Storage first.
- When Cache Storage misses but the browser HTTP cache already has the same same-origin image response, the shared media cache now seeds Cache Storage from `fetch(..., { cache: 'only-if-cached', mode: 'same-origin' })` before any backend network fetch.

## Verification
- RED confirmed before implementation:
  - `frontend/services/mediaCache.test.ts` failed because temporary identities had no `attachmentId`.
  - `frontend/hooks/useCachedImageSrc.test.tsx` failed because the hook fell back to the stale raw `blob:` URL.
  - `frontend/components/common/CachedImage.test.tsx` failed because the wrapper re-rendered raw `src` after hook recovery failure.
  - `frontend/components/views/expand/ExpandHistoryRow.test.tsx` failed because expand history thumbnails bypassed the shared cache wrapper.
  - `frontend/services/mediaCache.test.ts` failed because a durable attachment with available `data:image/...` bytes still tried to fetch the durable storage URL.
  - `frontend/services/mediaCache.test.ts` failed because a Cache Storage miss went straight to backend network fetch instead of first checking browser HTTP cache.
- GREEN after implementation:
  - `node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/services/mediaCache.test.ts frontend/hooks/useCachedImageSrc.test.tsx --environment jsdom`
  - `node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/services/mediaCache.test.ts frontend/hooks/useCachedImageSrc.test.tsx frontend/components/common/CachedImage.test.tsx frontend/services/previewCache.test.ts frontend/services/auth.mediaCache.test.ts frontend/components/common/ImageHistoryListRow.test.tsx frontend/hooks/useSessions.cache.test.tsx frontend/services/sessionCache.test.ts frontend/components/layout/SessionList.modeFilter.test.tsx --environment jsdom`
  - `node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/services/mediaCache.test.ts frontend/hooks/useCachedImageSrc.test.tsx frontend/components/common/CachedImage.test.tsx frontend/components/views/expand/ExpandHistoryRow.test.tsx frontend/components/views/ImageEditView.test.tsx frontend/components/views/ImageRecontextView.test.tsx frontend/components/common/ImageHistoryListRow.test.tsx --environment jsdom`
  - `node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/services/mediaCache.test.ts frontend/hooks/useCachedImageSrc.test.tsx frontend/components/common/CachedImage.test.tsx frontend/services/previewCache.test.ts frontend/services/auth.mediaCache.test.ts frontend/components/common/ImageHistoryListRow.test.tsx frontend/components/views/expand/ExpandHistoryRow.test.tsx frontend/hooks/useSessions.cache.test.tsx frontend/services/sessionCache.test.ts frontend/components/layout/SessionList.modeFilter.test.tsx frontend/components/views/ImageEditView.test.tsx frontend/components/views/ImageRecontextView.test.tsx --environment jsdom`
  - `node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/services/mediaCache.test.ts frontend/hooks/useCachedImageSrc.test.tsx frontend/components/common/CachedImage.test.tsx frontend/services/previewCache.test.ts frontend/services/auth.mediaCache.test.ts frontend/components/common/ImageHistoryListRow.test.tsx frontend/components/views/expand/ExpandHistoryRow.test.tsx frontend/hooks/useSessions.cache.test.tsx frontend/services/sessionCache.test.ts frontend/components/layout/SessionList.modeFilter.test.tsx frontend/components/views/ImageEditView.test.tsx frontend/components/views/ImageRecontextView.test.tsx --environment jsdom` passed with `57` tests.
  - `node_modules/.bin/tsc --noEmit --pretty false --project tsconfig.json`

## Non-Goals
- Do not repair historical rows that have no durable URL and no remaining temp bytes.
- Do not introduce a service worker.
- Do not duplicate cache code in individual image modes.
- Do not change backend attachment persistence semantics.

## Files
- `frontend/services/mediaCache.ts`
- `frontend/services/mediaCache.test.ts`
- `frontend/hooks/useCachedImageSrc.ts`
- `frontend/hooks/useCachedImageSrc.test.tsx`

## Rollback Plan
Revert the frontend media-cache recovery logic and hook fallback guard. Persistent media cache entries remain compatible because the cache key stays `media:attachment:<attachmentId>` and metadata remains additive.
