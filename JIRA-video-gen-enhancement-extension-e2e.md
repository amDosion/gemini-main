# Video Gen Prompt Enhancement and Extension E2E

## Summary

Validate Google video-gen in real UI with:

- selected prompt enhancement model
- uploaded model image
- storyboard prompt
- Veo 3.1 720p / 8s base video
- 4 official video extensions
- local storage landing
- database attachment persistence
- reload display from stored local path

## Test Input

- User: `gemini2026_hq129v4k`
- Provider profile: Google Gemini Config
- Video model: `veo-3.1-generate-preview`
- Enhancement model selected in UI: `gemini-3.1-flash-lite-preview`
- Input image: `/tmp/gemini-main-ui-e2e/random_model_input.png`
- Base settings: `720p`, `8s`, `16:9`
- Extension count: `4`
- Expected final duration: `36s`

## Real UI Result

- Backend received `google/video-gen`
- Backend injected uploaded attachment as `source_image`
- Runtime input strategy: `image_to_video`
- Prompt enhancement call succeeded with `gemini-3.1-flash-lite-preview`
- Veo chain executed as:
  - 1 base request with `has_image=True`
  - 4 continuation requests with `has_video=True`
- Backend total request time: about `333s`

## Persistence Evidence

- Message id: `084b107e-f758-4e41-bdcc-e748d7d5a5ab`
- Session id: `035c914f-fa48-408d-ab24-1a5c03803d4c`
- Attachment id: `c381ec06-9857-4062-ba2d-782b7c1d4773`
- Stored URL: `/api/storage/local-files/2026/05/08/1778213089256_veo-3.1-generate-preview-720p-16x9.mp4`
- Local file: `/mnt/user/appdata/gemini-main/backend/app/temp/local_storage/2026/05/08/1778213089256_veo-3.1-generate-preview-720p-16x9.mp4`
- Local size: `7078206` bytes
- Attachment status: `completed`

## Media Verification

`ffprobe` verified:

- container: MP4 / QuickTime
- video codec: H.264
- audio codec: AAC
- resolution: `1280x720`
- video duration: `36.041667s`
- format duration: `36.056000s`
- frames: `865`

## Reload Verification

Fresh browser session after reload found the same stored local URL in the video DOM:

- matched source: `http://127.0.0.1:21573/api/storage/local-files/2026/05/08/1778213089256_veo-3.1-generate-preview-720p-16x9.mp4`
- UI text restored: `延长 4 次`
- UI text restored: `总时长 36s`
- rendered video metadata: `1280x720`, `36.041666s`, `readyState=1`

## Notes

The first E2E metadata probe used an extra hidden video element immediately after generation and hit a transient Firefox headless media error. The generated file, HTTP range serving, UI-rendered video element, and fresh reload all verified correctly. The E2E script now retries metadata probing and falls back to the actual rendered DOM video element metadata.

## 4K Extension Follow-up

### Implementation Decision

4K/1080p extension now uses a last-frame bridge chain:

- Generate the base 4K segment from the input image.
- Download the provider segment.
- Extract the segment's final frame.
- Use that final frame as the next segment's first-frame image input.
- Repeat for the requested extension count.
- Use one structured storyboard prompt per extension segment when provided by the UI.
- Trim `1s` from each continuation segment to preserve the existing `+7s` extension semantics.
- Concatenate all segments with `ffmpeg`.
- Return the joined MP4 as the final video payload so the existing attachment persistence writes one local file and database attachment path.

720p remains on the direct provider video-extension path by default.

Official support check:

- Gemini API Veo 3.1 docs list `720p`, `1080p`, and `4k` video generation support: https://ai.google.dev/gemini-api/docs/video
- Vertex AI Veo 3.1 docs list supported input and output resolutions as `720p`, `1080p`, and `4k`: https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate

### Automated Verification

- Backend unit tests: `26 passed`
- Targeted coordinator test verifies 4K + 2 extensions creates 3 image-to-video segment requests, strips source-video continuation fields, joins the segments, and returns `continuation_strategy=last_frame_bridge_chain`.
- Local ffmpeg join verification produced a valid joined MP4 and confirmed continuation trimming behavior.
- Frontend targeted tests passed for Video view/control changes.
- Production build passed.

### Real UI 4K Attempt

Input:

- User: `gemini2026_hq129v4k`
- Resolution: `4K UHD 3840x2160`
- Duration: `8s`
- Extension count: `4`
- Enhancement model: `gemini-3.1-flash-lite-preview`
- Storyboard prompt: present

UI control dry-run result:

- selected resolution label: `4K UHD 3840x2160`
- `延长次数`: `4`
- `延长后总时长`: `4`
- selected enhancement model: `gemini-3.1-flash-lite-preview`
- segmented storyboard fields: base `0-8s` plus 4 extension prompts for `8-15s`, `15-22s`, `22-29s`, `29-36s`

Real short submit result:

- Backend received `google/video-gen`.
- Backend logged Veo request as `resolution=4k`, `duration=8s`, `has_image=True`.
- Google API returned `429 RESOURCE_EXHAUSTED`: prepayment credits are depleted.
- Because the provider rejected the base segment, a real 4K joined MP4 could not be produced in this run.
