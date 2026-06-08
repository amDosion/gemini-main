# JIRA: Video Advanced Workflows Provider Contract

Date: 2026-05-27

## Objective

Unify advanced video generation workflows behind a backend-first contract so `video-gen` can support Tongyi/Wan, HappyHorse, and Google/Veo capabilities without duplicated frontend logic.

The target UX must make these workflows explicit:

- Text to video.
- First-frame image to video.
- First and last frame to video.
- Continue from a previous video clip.
- Continue from a previous video clip plus a target last frame.
- Use the final frame of a generated video as the first frame of the next clip.
- Reference/video imitation.
- Prompt-driven video edit for background, scene, style, subject, and object changes.

## Official Evidence

### Alibaba Model Studio / DashScope

Source links:

- https://help.aliyun.com/zh/model-studio/video-generate-edit-model/
- https://help.aliyun.com/zh/model-studio/text-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/image-to-video-general-api-reference
- https://help.aliyun.com/zh/model-studio/wan-video-editing-api-reference
- https://help.aliyun.com/zh/model-studio/image-video-reference-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/video-reference-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/happyhorse-text-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/happyhorse-image-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/happyhorse-reference-to-video-api-reference
- https://help.aliyun.com/zh/model-studio/happyhorse-video-edit-api-reference

Findings:

- `wan2.7-t2v` is text-to-video and supports `prompt`, `negative_prompt`, `duration`, `resolution`, `ratio`, `seed`, `prompt_extend`, and `watermark`.
- `wan2.7-i2v` is the main advanced image/video-to-video entry. Officially documented media combinations include:
  - first frame only: `first_frame`
  - first and last frame: `first_frame` + `last_frame`
  - video continuation: `first_clip`
  - video continuation with target ending: `first_clip` + `last_frame`
  - optional driving audio in media where supported.
- Alibaba's model-selection page explicitly recommends using the previous video's final frame as the next segment's first frame for long-video continuity.
- `wan2.7-r2v` is reference-to-video. It supports reference image/video style imitation; the current backend model family is correct, but UI needs a clear "reference/imitation" strategy and attachment role mapping.
- `wan2.7-videoedit` is video edit. Official payload is source `video` plus optional `reference_image`; this is not the same as Google mask-based editing.
- HappyHorse has separate `t2v`, `i2v`, `r2v`, and `video-edit` endpoints/models. It should share the same product contract but with model-specific limits and defaults.

### Google / Veo

Source links:

- https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos
- https://cloud.google.com/vertex-ai/generative-ai/docs/video/insert-objects-into-videos
- https://cloud.google.com/vertex-ai/generative-ai/docs/video/remove-objects-from-videos

Findings:

- Veo supports text-to-video, image-to-video, first/last frame generation, reference/ingredient images, video extension, and mask-guided object insertion/removal depending on model and runtime.
- This confirms the project should keep a generic video contract, but provider-specific slots must differ. Tongyi video edit reference images must not be normalized as Google-style mask images.

### Official GitHub

Source links:

- https://github.com/Wan-Video/Wan2.1
- https://github.com/Wan-Video/Wan2.2

Findings:

- Wan open-source examples expose model tasks such as text-to-video, image-to-video, first-last-frame generation, text-image-to-video, animate/move/mix, and replacement/background/mask style workflows.
- These GitHub workflows are not necessarily identical to DashScope hosted APIs, but they validate the product taxonomy: text generation, frame-conditioned generation, reference/motion imitation, and edit/replacement are separate workflow families.

## Current Project State

Relevant files:

- `backend/app/services/tongyi/video_generation.py`
- `backend/app/services/common/video_mode_contract.py`
- `backend/app/config/mode_controls_catalog.json`
- `backend/app/services/common/tongyi_model_catalog.py`
- `frontend/controls/modes/google/VideoGenControls.tsx`
- `frontend/controls/modes/registry.ts`
- `frontend/services/providers/unifiedProviderHelpers.ts`
- `frontend/hooks/useControlsState.ts`
- `frontend/hooks/handlers/AllHandlerClasses.ts`

What is already correct:

- `TongyiVideoGenerationService` already recognizes `*-t2v`, `*-i2v`, `*-r2v`, and `*-videoedit` / `*-video-edit`.
- The Tongyi service already emits `first_frame`, `last_frame`, `first_clip`, `driving_audio`, `reference_video`, `reference_image`, and `video` media types in the right broad model families.
- Static Tongyi media models are present in `tongyi_model_catalog.py`, so the UI can list Wan/HappyHorse video models even when provider model listing omits them.
- Google video services already have a last-frame bridge helper in `backend/app/services/gemini/base/video_frame_bridge.py`.

Current gaps:

- `build_video_mode_contract` only returns a contract for Google `video-gen`; Tongyi receives no provider-specific video contract.
- Tongyi uses the common Google `VideoGenControls`; this is good for reuse, but the component currently has no schema-driven input strategy UI.
- `extract_video_mode_attachment_params` is Google-oriented for `source_video + loose image`, mapping loose image to `video_mask_image`. That is wrong for Tongyi video edit, where loose images are usually `reference_image`.
- There is no frontend control for assigning attachment roles such as first frame, last frame, source clip, reference image, reference video, driving audio, or edit reference image.
- There is no persisted "derived final frame" attachment for Tongyi output videos, so users cannot reliably chain generated clips by selecting a previous final frame.
- `MODE_OPTION_KEYS` / `MODE_EXTRA_KEYS` do not include explicit video strategy fields yet.
- Tongyi schema options are partly generic. HappyHorse and Wan variants need provider/model-specific limits for media count, durations, ratios, and audio/edit parameters.

## Target Architecture

Backend remains the source of truth:

```text
mode_controls_catalog.json
  -> resolve_mode_controls()
  -> build_video_mode_contract(provider, mode, model_id)
  -> frontend shared video controls
  -> POST /api/modes/{provider}/video-gen
  -> normalize_video_generation_request_params()
  -> provider video service payload builder
```

Do not add separate Tongyi-only UI panels unless the schema cannot express the behavior. The correct design is a shared video control surface driven by provider/model contracts.

## Contract Additions

Add provider-aware video contract fields:

- `input_strategies`
  - `text_to_video`
  - `first_frame_to_video`
  - `first_last_frame_to_video`
  - `video_continuation`
  - `video_continuation_to_last_frame`
  - `reference_to_video`
  - `video_edit`
  - `masked_video_edit`
- `attachment_slots`
  - `source_image`
  - `last_frame_image`
  - `source_video`
  - `reference_images`
  - `reference_video`
  - `video_edit_reference_images`
  - `driving_audio`
  - `video_mask_image`
- `provider_payload_media_types`
  - Tongyi: `first_frame`, `last_frame`, `first_clip`, `driving_audio`, `reference_image`, `reference_video`, `video`
  - Google: SDK image/video/mask/reference config names
- `field_policies`
  - prompt enhancement availability/default/mandatory
  - negative prompt support
  - ratio availability
  - duration options
  - resolution options
  - audio/driving audio availability
  - video edit audio settings
- `media_limits`
  - max reference images
  - max reference videos
  - required media by strategy
  - mutually exclusive media by strategy

## Implementation Plan

### Phase 1: Backend Contract

- Refactor `build_video_mode_contract` into provider-specific builders while keeping one public entry.
- Add `build_tongyi_video_mode_contract(schema)` for Wan/HappyHorse model families.
- Add Tongyi-specific attachment normalization:
  - `source_video + loose image` should become `reference_images` for `videoedit`, not `video_mask_image`.
  - `source_video` should map to `first_clip` for `i2v`.
  - `source_video` should map to `reference_video` for `r2v`.
  - explicit roles must always win over positional inference.
- Validate required media before provider calls and return actionable errors.

### Phase 2: Shared Frontend Controls

- Extend the existing shared `VideoGenControls` instead of duplicating provider panels.
- Add reusable schema-driven components:
  - `VideoInputStrategyControl`
  - `VideoAttachmentRolePicker`
  - `VideoMediaSlotStatus`
- Add `videoInputStrategy` state in `useControlsState`.
- Add allowed option keys in `unifiedProviderHelpers.ts`.
- Show only strategies allowed by the selected model.

### Phase 3: Last-Frame Chaining

- Reuse the existing frame extraction pattern, but make it provider-neutral.
- After a generated video is stored, optionally extract the last frame.
- Persist the derived image attachment with metadata:
  - `derived_from_attachment_id`
  - `derived_role: last_frame`
  - `source_mode: video-gen`
  - `source_provider`
  - `source_model`
- Frontend should expose "use as next first frame" from the video result/media card.

### Phase 4: Provider Payload Tightening

- Update `TongyiVideoGenerationService` to consume explicit strategy metadata instead of guessing only from model ID and available attachments.
- Cap reference media counts per official model family.
- Add missing Tongyi video edit parameters only if supported by docs and schema.
- Keep Google mask-based video edit separate from Tongyi prompt/reference-based video edit.

### Phase 5: Workflow Templates

- Update video workflow templates to use the same strategies:
  - text-to-video
  - first-frame image-to-video
  - first-last-frame video
  - long continuation via last-frame chaining
  - reference imitation
  - background/scene edit
- Templates must reference agent/task types consistently as `video-gen`, not generic `chat`.

### Phase 6: Tests

Backend:

- Contract generation for every Tongyi model family.
- Attachment role normalization for every strategy.
- Tongyi payload media arrays for `t2v`, `i2v`, `r2v`, `videoedit`.
- Last-frame derived attachment creation.

Frontend:

- Strategy options change when selecting `wan2.7-t2v`, `wan2.7-i2v`, `wan2.7-r2v`, `wan2.7-videoedit`, and HappyHorse variants.
- Role picker sends explicit roles.
- No strategy-specific duplicate panels.

E2E:

- Login, select Tongyi, generate text-to-video.
- Upload first frame, generate image-to-video.
- Upload first and last frames, generate constrained video.
- Select a prior result, use final frame as next first frame.
- Upload reference media, run reference-to-video.
- Upload source video plus reference image, run video edit.

## Acceptance Criteria

- Switching models changes visible video strategies and parameters without stale controls.
- Tongyi `videoedit` never treats ordinary reference images as Google masks.
- Users can chain generated videos by using the previous final frame as the next first frame.
- Backend rejects invalid media combinations before creating provider tasks.
- All new UI is shared and schema-driven.
- Existing Google/Veo video behavior remains green.
- Existing Tongyi image/video model listing remains green.

## Implementation Status

Completed on 2026-05-27:

- Backend provider contracts now support Tongyi video families with schema-driven input strategies and attachment slots.
- Video request normalization validates explicit and derived strategies before provider calls.
- Google first/last-frame and mask-edit strategy derivation was corrected to match the Google contract IDs.
- Shared frontend video controls now include schema-driven input strategy selection.
- Chat video attachments now expose schema-driven role selection and pass first-frame, last-frame, source-video, reference, mask, and driving-audio roles to the backend.
- Workflow agent video nodes now expose input strategy and driving audio URL fields, and execution forwards them to provider runtimes.
- Video templates were updated for text-to-video, Google first/last-frame, Google masked background edit, and long-continuation mutual exclusion.
- Video generation now persists provider-neutral derived final-frame image attachments through the shared attachment pipeline.
- Workflow video result persistence now attaches `lastFrameImageUrl`, `lastFrameAttachmentId`, and `derivedAssets` metadata for generated video outputs.
- The frontend video handler now renders returned video last-frame derivatives as normal message attachments with `role=last_frame`.
- Added `e2e:tongyi-video:ui`, a real-browser UI test that captures Tongyi `video-gen` payloads through the Vite app and verifies first-frame, first/last-frame, continuation, reference-to-video, and video-edit strategy plus attachment-role submission.

Remaining:

- Run a paid/provider-backed Tongyi smoke only when explicitly needed; the committed E2E intentionally uses a fake backend to validate browser behavior without creating provider jobs.
