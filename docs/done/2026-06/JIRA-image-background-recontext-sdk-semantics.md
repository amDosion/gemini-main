# JIRA: Align Background Edit and Recontext With Official Google SDK Semantics

## Type
Bug / Integration correctness

## Priority
High

## Summary
`image-background-edit` and `image-recontext` currently overlap in model exposure and backend routing. This makes a strict background replacement workflow capable of falling through to Gemini native image editing, while Recontext messaging contains background-swap semantics. The modes must map to the official Google SDK behavior precisely.

## Official Semantics
- **Background Edit**: product/background editing. Use Vertex Imagen edit with `EDIT_MODE_BGSWAP` and an automatic background mask (`MASK_MODE_BACKGROUND`) so the foreground product is preserved while the background is replaced.
- **Recontext**: product recontextualization. Use Gemini image editing (`gemini-2.5-flash-image`) with the source image and scene prompt to place the subject/product into a new context. This is not a mask-based background swap and must not promise foreground-pixel preservation.

## Problem
- `gemini-2.5-flash-image` is exposed for `image-background-edit`, which lets Background mode route to Gemini chat image editing instead of the official Vertex Imagen background-edit path.
- `image-background-edit` backend routing checks generic Gemini image models before the mode-specific Background route.
- `BackgroundEditService` sets `EDIT_MODE_BGSWAP`, but does not default an automatic background mask.
- Recontext wording and tests made it easy to confuse recontextualization with background replacement.

## Scope
- Restrict `image-background-edit` to Imagen edit models.
- Keep `image-recontext` and `product-recontext` on Gemini image models.
- Route `image-background-edit` before generic Gemini image handling and reject incompatible Gemini image models.
- Default Background Edit to `EDIT_MODE_BGSWAP + MASK_MODE_BACKGROUND`.
- Keep Gemini Recontext as official Gemini native image editing with the source image as context.

## Out Of Scope
- No provider credential changes.
- No destructive database changes.
- No UI redesign.
- No application-level parallelization for Gemini Recontext batch generation.

## Acceptance Criteria
- Model lists:
  - `image-background-edit` includes `imagen-3.0-capability-001`.
  - `image-background-edit` excludes `gemini-2.5-flash-image`.
  - `image-recontext` includes `gemini-2.5-flash-image`.
  - `image-recontext` excludes `imagen-3.0-capability-001`.
- Backend routing:
  - `image-background-edit + gemini-2.5-flash-image` is rejected before Gemini chat routing.
  - `image-background-edit + imagen-3.0-capability-001` routes to `BackgroundEditService`.
  - `image-recontext + gemini-2.5-flash-image` routes to `GeminiRecontextImageService`.
- SDK config:
  - Background edit sends `EDIT_MODE_BGSWAP`.
  - Background edit adds `MASK_MODE_BACKGROUND` when the user does not provide a mask.
- Tests:
  - Backend pytest covers model filtering, routing, and default mask behavior.
  - Frontend vitest covers model filtering for Background and Recontext.
