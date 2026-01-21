# ImageGen Click-to-Edit/Expand Attachment Display Flow (Current Code)

Purpose: document the current flow (no code changes) from ImageGen results to
Edit/Expand modes and how attachments are displayed, including temp-images and
cloud-url lookups.

Scope:
- Entry point: `frontend/components/views/ImageGenView.tsx` click handlers.
- Modes: `image-chat-edit` and `image-outpainting`.
- Attachment display: ImageGen -> Edit/Expand -> temp-images or cloud URL.

Key files:
- `frontend/components/views/ImageGenView.tsx`
- `frontend/hooks/useImageHandlers.ts`
- `frontend/hooks/handlers/attachmentUtils.ts`
- `frontend/components/views/StudioView.tsx`
- `frontend/components/views/ImageEditView.tsx`
- `frontend/components/views/ImageExpandView.tsx`
- `frontend/components/chat/InputArea.tsx`
- `backend/app/services/common/attachment_service.py`
- `backend/app/services/common/upload_worker_pool.py`
- `backend/app/routers/core/attachments.py`
- `backend/app/routers/user/sessions.py`

Attachment fields used:
- `url`: display URL; later becomes cloud URL when upload completes.
- `tempUrl`: Base64 or temporary URL.
- `uploadStatus`: `pending` | `uploading` | `completed`.
- `id`, `mimeType`, `name`.

Mermaid flow (current behavior):
```mermaid
flowchart TD
  A[AI generates images -> Message.attachments] --> B[ImageGenView renders <img src=att.url>]
  B --> C{Click button?}
  C -->|Edit| D[onEditImage(url)]
  C -->|Expand| P[onExpandImage(url)]

  %% Edit path
  D --> E[useImageHandlers.handleEditImage]
  E --> F[findAttachmentByUrl(url, messages)]
  F -->|Found| G[Reuse attachment.id/tempUrl/uploadStatus]
  F -->|Not found| H[Create new attachment with url]
  G --> I{uploadStatus == pending?}
  I -->|Yes| J[tryFetchCloudUrl -> /api/attachments/{id}/cloud-url]
  J --> K[AttachmentService.get_cloud_url]
  K --> L[If completed: newAttachment.url=cloud URL]
  I -->|No| L
  H --> L
  L --> M[setAppMode('image-chat-edit') + setInitialAttachments + setInitialPrompt]
  M --> N[StudioView -> ImageEditView]
  N --> O[initialAttachments -> activeAttachments -> activeImageUrl]
  O --> X[Canvas/InputArea display activeImageUrl]

  %% Expand path
  P --> Q[useImageHandlers.handleExpandImage]
  Q --> R[findAttachmentByUrl + (pending) tryFetchCloudUrl]
  R --> S[setAppMode('image-outpainting') + setInitialAttachments]
  S --> T[StudioView -> ImageExpandView]
  T --> U[initialAttachments -> activeAttachments -> activeImageUrl]
  U --> X

  %% Image loading resolution
  X --> Y{activeImageUrl type}
  Y -->|/api/temp-images| Z[GET /api/temp-images/{id}]
  Z --> AA[require_current_user -> compare attachment.user_id]
  AA --> AB{temp_url? / completed?}
  AB -->|Base64| AC[Decode and return bytes]
  AB -->|completed| AD[302 redirect to cloud URL]
  Y -->|http(s)/data/blob| AE[Browser loads directly]
```

Detailed flow (front-end):
1) ImageGen display:
   - `ImageGenView` renders `att.url` only (no fallback to `tempUrl`).
2) Edit/Expand click:
   - Buttons call `onEditImage(att.url)` / `onExpandImage(att.url)`.
3) useImageHandlers:
   - `findAttachmentByUrl` tries exact match on `att.url` or `att.tempUrl`.
   - Blob URLs use fallback to latest completed cloud image (strict).
   - If `uploadStatus=pending`, `tryFetchCloudUrl` calls
     `/api/attachments/{id}/cloud-url`.
4) Mode switch:
   - `setAppMode('image-chat-edit' | 'image-outpainting')`.
   - `setInitialAttachments([newAttachment])` passed to the new mode.
5) ImageEditView/ImageExpandView:
   - `initialAttachments` sync to `activeAttachments`.
   - `activeImageUrl = att.url || att.tempUrl || null`.
   - Canvas and InputArea render `activeImageUrl`.

Detailed flow (back-end):
1) AI result handling:
   - `AttachmentService.process_ai_result` creates `MessageAttachment`.
   - For Base64: `temp_url=ai_url`, `url=''`, and a `display_url` is returned.
2) Worker upload:
   - `UploadWorkerPool` decodes Base64 or downloads HTTP source.
   - On success: updates `message_attachments.url`, `upload_status=completed`,
     and clears `temp_url`.
3) Cloud URL lookup:
   - `/api/attachments/{id}/cloud-url` calls `AttachmentService.get_cloud_url`.
   - Prefers `UploadTask.target_url`, else `MessageAttachment.url`.
4) Temp image access:
   - `/api/temp-images/{id}` enforces `require_current_user`.
   - If user_id mismatches, returns 404.

Notes:
- `/api/temp-images` requests from `<img src>` do not include Authorization
  headers, only cookies. This explains user_id mismatch when cookie and
  header tokens differ.
- `InputArea` converts Blob URLs to Base64 before send for uploads, but
  ImageGen display uses the `att.url` it receives without conversion.

End of document.
