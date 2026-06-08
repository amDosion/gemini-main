# JIRA: Gemini Provider Expand Mode Uses Vertex AI Imagen Official SDK

## Background

`image-outpainting` under the Gemini/Google provider must use Vertex AI Imagen APIs because Gemini API does not expose the mask-based outpaint and upscale surfaces required by Expand mode.

Official SDK paths:

- Outpaint: `client.models.edit_image(...)` with `imagen-3.0-capability-001`, `RawReferenceImage`, `MaskReferenceImage`, and `EditImageConfig(edit_mode="EDIT_MODE_OUTPAINT")`.
- Upscale: `client.models.upscale_image(...)` with `imagen-4.0-upscale-preview` and `upscale_factor` of `x2`, `x3`, or `x4`.

## User Story

As a user in Expand mode, I want the selected frontend model and expand controls to be passed to the backend unchanged, so that each expand operation runs through the correct Vertex AI Imagen SDK method without backend model substitution.

## Scope

Complete all four Google expand submodes:

- Ratio outpaint: expand to a target aspect ratio.
- Scale outpaint: expand by X/Y scale factors.
- Offset outpaint: expand by explicit pixel offsets.
- Upscale: increase image resolution by `x2`, `x3`, or `x4`.

## Requirements

- Frontend sends the selected model ID to backend.
- Backend validates whether the selected model supports the requested expand submode.
- Backend must not hardcode replacement model IDs when executing requests.
- Backend must remove person-generation and explicit safety-filter parameters from Expand mode requests.
- Outpaint uses Vertex AI `edit_image` with `EDIT_MODE_OUTPAINT`.
- Upscale uses Vertex AI `upscale_image`.
- Result MIME type must match the SDK response/request instead of being forced to PNG.
- Tests must cover all four submodes.

## Acceptance Criteria

- Ratio, scale, and offset modes call `edit_image` with the request model ID.
- Upscale mode calls `upscale_image` with the request model ID.
- Invalid model/submode combinations return clear validation errors.
- No `person_generation` or `safety_filter_level` is injected by Expand mode.
- `number_of_images` is supported for outpaint modes and remains unavailable for upscale.
- `output_mime_type`, JPEG compression quality, seed, negative prompt, base steps, and guidance scale are forwarded where supported by `EditImageConfig`.

## Test Plan

- Add unit tests for `ExpandService.expand_image()` covering:
  - `ratio` -> `edit_image`
  - `scale` -> `edit_image`
  - `offset` -> `edit_image`
  - `upscale` -> `upscale_image`
- Add model filtering coverage for `image-outpainting` so only outpaint-capable and upscale models appear.
- Run targeted backend tests.
- Run frontend/provider payload tests if frontend request shaping changes.
