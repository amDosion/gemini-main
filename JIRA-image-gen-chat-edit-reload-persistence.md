# Jira: image-chat-edit Generated Image Missing DB Path After Reload

## Issue Type
Bug

## Priority
High

## Summary
`image-chat-edit` can show the generated image immediately, then lose it after a full page reload. The immediate render works because the service returns a base64 data URL. The reload fails because the same result was marked with an `attachment_id` before any `MessageAttachment` row or durable storage path was created.

The precise bug is not that base64 exists. Base64 is expected for fast first paint. The bug is that `ConversationalImageEditService` claimed the base64 result was already an attachment by adding `attachment_id`, `message_id`, `session_id`, `upload_status`, and `cloud_url` metadata without writing the image through `AttachmentService`.

## Confirmed Root Cause
1. Gemini returns inline image bytes.
2. `ConversationalImageEditService` converts those bytes to `data:image/...;base64,...`.
3. The same service generated synthetic attachment metadata but did not create a DB attachment or local-storage URL.
4. `modes.py` treats a result containing `attachment_id` as already persisted and skips `AttachmentService.process_ai_result()`.
5. Later session save correctly refuses to store base64/blob URLs in `message_attachments.url`.
6. After reload, the session is rebuilt from DB, but the model attachment has no durable image URL.

## Database Evidence
Read-only inspection showed:

- `image-chat-edit` model image attachments inspected: `21`
- broken rows with `url = ''`: `17`
- broken rows with `temp_url IS NULL`: `17`
- broken rows with `upload_status = 'pending'`: `17`
- broken rows with `upload_task_id IS NULL`: `17`

Latest broken sample:

- `message_id = 640a3cd3-a44d-40b9-835f-df7d68fd69ca`
- `attachment_id = c6a68637-efeb-4598-bf80-ce4c26dde586`
- `content = 移除耳环，其余的保持不变，`
- `url = ''`
- `temp_url = NULL`
- `upload_status = pending`
- `upload_task_id = NULL`

Control sample:

- `image-gen` model image attachments inspected: `7`
- all `7` had `url LIKE '/api/storage/local-files/%'`
- all `7` had `upload_status = 'completed'`

## Cross-Mode Audit
The other requested modes should be checked, and were checked for the same failure pattern.

- `image-mask-edit`, `image-inpainting`, `image-background-edit`, and `image-recontext` route through the normal `edit_image` branch and do not create synthetic attachment IDs in their edit services.
- `image-outpainting` routes through `expand_image` and returns raw image output for the central mode router to persist.
- `virtual-try-on` has service-level persistence before returning `attachment_id`; it does not have the same synthetic-ID-without-DB pattern.
- `video-gen` and `audio-gen` were reviewed for the same `attachment_id` pattern; no current DB sample showed this exact missing-image-path failure for those modes.

## Chosen Fix
Fix the source contract in `ConversationalImageEditService`.

- Do not generate `attachment_id` in `image-chat-edit` unless that code path actually writes the attachment.
- Do not generate a fake model `message_id`; the request already carries the frontend message ID used by the router persistence pipeline.
- Do not return `upload_status`, `upload_task_id`, or `cloud_url` from this service when the image has not been persisted.
- Return only the extracted image payload (`url`, `mime_type`, `size`) plus normal non-attachment metadata.
- Let the existing `modes.py -> AttachmentService.process_ai_result()` path create the real `MessageAttachment`, storage URL, status, and task metadata.
- For session-backed image results, fail the request if persistence fails instead of returning a raw non-persistent image.

This is not a fallback or downgrade path. It restores a single ownership rule: `AttachmentService` owns generated attachment IDs and database persistence.

## Expected Behavior
For a new `image-chat-edit` generation with session and message IDs:

1. Gemini inline bytes are returned as base64 by the provider service.
2. The mode router sees no pre-existing `attachment_id`.
3. The result is passed to `AttachmentService.process_ai_result()`.
4. Local storage writes the image and returns `/api/storage/local-files/...` when configured.
5. `message_attachments.url` contains a reloadable path.
6. Reloading the page renders the edited image from the DB-backed URL.

## Acceptance Criteria
- New `image-chat-edit` generated model images are saved with a real `message_attachments` row.
- New `image-chat-edit` generated model images have a non-empty durable `url` after local storage persistence.
- The frontend can still display the image immediately.
- Full page reload still displays the latest edited image.
- No new `image-chat-edit` model attachment is saved with all of these empty: `url`, `temp_url`, `file_uri`, `google_file_uri`.
- Existing broken rows are not repaired by this fix; rows with `url=''` and `temp_url=NULL` do not contain enough data to reconstruct the missing image.

## Test Plan
1. Run one new `image-chat-edit` generation.
2. Verify backend log shows `AttachmentService` processing the returned image.
3. Verify DB row for the model output has non-empty `url`, preferably `/api/storage/local-files/...` under current local-storage config.
4. Reload the web page and verify the edited image remains visible.
5. Smoke test `image-gen`, `image-mask-edit`, `image-inpainting`, `image-background-edit`, `image-recontext`, `image-outpainting`, `virtual-try-on`, `video-gen`, and `audio-gen` for the same invariant: generated media must either be persisted before returning `attachment_id`, or return no `attachment_id` and let the central persistence path create it.
