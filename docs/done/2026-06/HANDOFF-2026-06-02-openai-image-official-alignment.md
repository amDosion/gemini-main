# Handoff: OpenAI Image Official Alignment And Current Runtime

Date: 2026-06-02 Asia/Shanghai
Repo: `/mnt/user/appdata/gemini-main`

## User Priority

The latest explicit direction is:

- Do not keep doing patch-style fixes.
- For text-to-image and image-to-image, strictly align with official OpenAI Image API behavior.
- Do not invent fallback/compensation flows that hide upstream contract failures.
- Shared concerns should be implemented as shared modules/components, not duplicated per mode.
- The next CLI should continue from evidence, not from guessing.

## Runtime State

Both dev services are running:

- Frontend: `http://127.0.0.1:21573`, process `3538085`
- Backend: `http://127.0.0.1:21574`, process `3579001`
- Backend health check returned HTTP 200 with DB, Redis, provider, worker pool, and Gemini pool healthy.

Runtime pid files were corrected after restart:

- `frontend.dev.pid` -> `3538085`
- `backend.dev.pid` -> `3579001`

Useful checks:

```bash
cd /mnt/user/appdata/gemini-main
ss -ltnp | grep -E ':21573|:21574'
curl -sS -m 10 http://127.0.0.1:21574/health
tail -160 /tmp/gemini-main-backend-21574.log
```

## OpenAI Official Contract Decisions

Official docs used as source of truth:

- `https://developers.openai.com/api/docs/guides/image-generation?api=image`
- `https://developers.openai.com/api/docs/guides/image-generation?api=image&multi-turn=responseid`
- `https://developers.openai.com/api/docs/guides/images-vision?format=file`
- `https://developers.openai.com/api/docs/models/gpt-image-2`

Local SDK inspected:

- OpenAI Python SDK version: `2.31.0`
- `client.images.generate(...)` supports native `n`
- `client.images.edit(...)` supports native `n`

Implemented policy:

- `image-gen` maps to native Image API generation: `client.images.generate(...)`.
- `image-chat-edit` and derived edit modes map to native Image API edit: `client.images.edit(...)`.
- Responses API image flow is only for stateful/multi-turn image conversation where a previous response id is present.
- Removed `openai_image_api` as a frontend/provider switch that was leaking into modes where it should not determine routing.
- No manual fallback from native `n` to parallel `n=1`.
- If OpenAI returns fewer images than requested, the backend raises a contract error instead of silently filling the rest.

## Files Touched In The Current OpenAI Slice

Core OpenAI backend:

- `backend/app/services/openai/image_generator.py`
- `backend/app/services/openai/image_editor.py`
- `backend/app/services/openai/_shared.py`
- `backend/app/services/openai/image_route_contract.py`
- `backend/app/services/openai/openai_service.py`
- `backend/app/core/provider_param_whitelist.py`
- `backend/app/config/mode_controls_catalog.json`

Instrumentation and persistence:

- `backend/app/services/common/attachment_service.py`

Relevant tests:

- `backend/tests/test_openai_image_model_routing.py`
- `backend/tests/test_modes_media_message_persistence.py`
- `backend/tests/test_modes_video_attachment_params.py`
- frontend focused OpenAI/control tests listed below

The worktree is very dirty from many prior tasks across frontend/backend/workflow/video/cache. Do not use broad reset or broad revert. Inspect exact diffs before modifying shared files.

## What Was Fixed

### Native OpenAI Image API routing

`image-gen` now calls:

```python
image_client.images.generate(model=model, prompt=prompt, **request_kwargs)
```

`image-chat-edit` now calls:

```python
image_client.images.edit(model=model, prompt=prompt, image=image_files, **call_kwargs)
```

This keeps text-to-image and image-to-image aligned with official OpenAI Image API semantics.

### Removed patchy batch fallback

The previous direction that fell back from native multi-image request to manual parallel `n=1` compensation was removed. This matters because the user explicitly rejected hiding provider failures behind local compensation.

Current behavior:

- Request native `n`.
- Convert the response.
- If response count is lower than requested, raise an explicit error.

### Prompt enhancement default

OpenAI prompt enhancement default was changed to off in the controls catalog for `gpt-image-2`, so latency evidence is not polluted by hidden prompt-enhancement calls unless the user intentionally enables it.

### Stage timing logs

Added timing logs so the next run can identify where a slow OpenAI request spends time:

- Prompt enhancement phase
- Reference image load phase for image edit
- OpenAI Images API phase
- Response conversion phase
- AI result persistence: source bytes read, local storage upload, DB status update

This is diagnostic instrumentation, not behavioral fallback.

### Fixed latest runtime failure

During a real UI `image-chat-edit` run, OpenAI returned 200 successfully, but persistence failed:

```text
[Persist] 第 1 张图片 失败: name 'time' is not defined
```

Root cause:

- `attachment_service.py` used `time.perf_counter()` in newly added timing logs but did not import `time`.

Fix:

- Added `import time` to `backend/app/services/common/attachment_service.py`.

This fix is loaded after backend restart.

## Evidence From Last Real UI Run

The user ran OpenAI `image-chat-edit` through the UI after instrumentation.

Backend log evidence:

- Continuity attachment resolved in about `10ms`.
- Provider service creation took about `6904ms`.
- Reference image load took about `43ms`.
- OpenAI `/images/edits` returned HTTP 200.
- OpenAI Images Edit API phase took about `32421ms`.
- Response conversion took about `3ms`.
- Total editor service method time was about `32468ms`.
- The request then failed only during local persistence because of the missing `time` import, which has now been fixed.

Important inference:

- That failure was not an OpenAI routing failure.
- For that run, dominant time was upstream OpenAI-compatible `/images/edits`, not local file IO.
- A new real UI run is still needed after the `time` import fix to confirm end-to-end success and collect persistence timings.

## Verification Already Run

Backend tests:

```bash
cd /mnt/user/appdata/gemini-main/backend
.venv/bin/python -m pytest tests/test_openai_image_model_routing.py -q
```

Result:

```text
43 passed in 30.00s
```

Backend media persistence tests:

```bash
cd /mnt/user/appdata/gemini-main/backend
.venv/bin/python -m pytest tests/test_modes_media_message_persistence.py tests/test_modes_video_attachment_params.py -q
```

Result:

```text
20 passed in 24.89s
```

Earlier frontend focused suite after OpenAI controls/routing changes:

```bash
npm test -- --run \
  frontend/controls/modes/openai/ImageGenControls.test.tsx \
  frontend/controls/modes/openai/ImageEditControls.test.tsx \
  frontend/controls/modes/openai/ImageDerivedControls.test.tsx \
  frontend/components/views/ImageGenView.outputMime.test.tsx \
  frontend/components/chat/ChatEditInputArea.test.tsx \
  frontend/services/providers/UnifiedProviderClient.mode.test.ts
```

Result:

```text
6 files passed, 48 tests passed
```

Earlier typecheck:

```bash
npx tsc --noEmit --pretty false
```

Result:

```text
passed
```

Backend health after restart:

```bash
curl -sS -m 10 http://127.0.0.1:21574/health
```

Result:

```text
status: healthy
```

## Not Yet Verified After The Last Fix

The latest `time` import fix has tests and backend health verification, but there has not yet been a fresh real UI generation after the restart.

Next required validation:

1. In the UI, choose OpenAI provider and `gpt-image-2`.
2. Run `image-gen` with one image first.
3. Run `image-chat-edit` with one reference image from the active canvas.
4. Then test native `n > 1` for `image-gen`.
5. Then test native `n > 1` for `image-chat-edit`.
6. Watch `/tmp/gemini-main-backend-21574.log`.

Expected log markers:

```text
[OpenAI ImageGenerator] Request options ...
[OpenAI ImageGenerator] Images Generate API completed ...
[OpenAI ImageGenerator] Response conversion completed ...
[OpenAI ImageEditor] Reference load completed ...
[OpenAI ImageEditor] Request options ...
[OpenAI ImageEditor] Images Edit API completed ...
[AttachmentService] local storage source data read ...
[AttachmentService] local storage upload ...
[AttachmentService] DB attachment status update ...
```

If OpenAI returns fewer images than requested, that is now a visible contract failure and should be investigated against provider/API behavior, not hidden by local fallback.

## Known Next Issues To Continue

### Frontend OpenAI API option leakage

The user reported that `chat`, `chat-edit`, and other modes show `OpenAI 图片接口`. This should be removed or scoped because mode routing should be determined by the app mode contract:

- `gen`: text-to-image -> Images Generate
- `chat-edit`: image-to-image -> Images Edit
- Responses API only when stateful image conversation is truly active

Likely files:

- `frontend/controls/modes/openai/OpenAIImageControls.tsx`
- `frontend/controls/modes/openai/ImageGenControls.tsx`
- `frontend/controls/modes/openai/ImageEditControls.tsx`
- `frontend/controls/modes/openai/ImageDerivedControls.tsx`
- `frontend/coordinators/ModeControlsCoordinator.tsx`
- `frontend/services/providers/UnifiedProviderClient.ts`
- `backend/app/config/mode_controls_catalog.json`

Do not add another per-mode duplicate control. Use the existing shared OpenAI image controls and filter by mode capability.

### Need fresh E2E/UI equivalent tests

There is a script:

- `scripts/e2e/openai_image_ui_e2e.py`

Before trusting UI behavior, inspect and run/extend it. The user wants equivalent UI testing from login to generation to returned result.

Do not write credentials into repo files. Use existing environment/session or prompt-safe local handling.

### Cache/history work remains separate

Earlier work has many cache/history changes. The user still cares about:

- Global media cache should accelerate unchanged media.
- History thumbnails and hover preview should use the same stable media loading policy.
- Avoid blob URL stale reads such as `ERR_FILE_NOT_FOUND`.
- Cache must be mode/session aware without duplicating cache stores.

Likely files:

- `frontend/services/mediaCache.ts`
- `frontend/services/mediaCacheIndexedDb.ts`
- `frontend/services/sessionCache.ts`
- `frontend/hooks/useCachedImageSrc.ts`
- `frontend/hooks/useStableAttachmentImageUrl.ts`
- `frontend/components/common/CachedImage.tsx`
- `frontend/components/common/ImageHistoryListRow.tsx`
- `frontend/components/common/ImageHistoryHoverPreviewPanel.tsx`

Do not reintroduce multiple competing cache layers.

### Workflow/agent work remains separate

The worktree contains broad workflow/agent/template edits. The user previously objected to duplicate agent definitions between templates and agent management. Continue only after a focused audit because the worktree is broad.

Likely files:

- `backend/app/services/agent/*`
- `backend/app/services/gemini/agent/starter_templates/*`
- `frontend/components/multiagent/*`
- workflow history/result image components

## Recommended Next CLI Sequence

1. Read this file first.
2. Confirm runtime:

```bash
cd /mnt/user/appdata/gemini-main
ss -ltnp | grep -E ':21573|:21574'
curl -sS -m 10 http://127.0.0.1:21574/health
```

3. Tail backend logs while doing UI validation:

```bash
tail -f /tmp/gemini-main-backend-21574.log
```

4. Run a real OpenAI `image-gen` and `image-chat-edit` UI flow.
5. If a failure occurs, classify by phase from the timing logs before editing.
6. Only after root cause is clear, make cohesive changes in the shared routing/control layer.

## Important Process Notes

- Do not use `git reset --hard` or broad checkout. The worktree contains many active changes.
- Do not read or leak secrets from `SERVICES.md` into committed docs.
- Use official OpenAI docs for OpenAI API behavior.
- Keep `image-gen` and `image-chat-edit` behavior strict:
  - text-to-image -> Image API generate
  - image-to-image -> Image API edit with reference images
  - no local parallel compensation unless the user explicitly changes the product decision
- If adding frontend controls, use shared components and mode capability filtering.
- If adding backend parameters, put them through the catalog/whitelist contract, not ad hoc request keys.
