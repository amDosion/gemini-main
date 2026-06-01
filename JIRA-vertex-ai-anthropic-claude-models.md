# Jira: Vertex AI Anthropic Claude Partner Models

## Issue Type
Feature / Integration

## Priority
High

## Summary
The app already has a user-scoped Vertex AI configuration flow, but the current model verification path only lists Google/Gemini models through `genai.Client(...).models.list()` plus the local Google Vertex static catalog. It does not explicitly discover or expose third-party Vertex AI partner models from Anthropic, including `claude-mythos-preview`.

We need to extend the Vertex AI model discovery and selection flow so Claude partner models can be detected, selected, saved, and later routed correctly.

## Current Evidence
Probe script added:

- `scripts/probe_vertex_claude_mythos.py`

Commands run:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/probe_vertex_claude_mythos.py --include-controls --model claude-mythos-preview --location global --timeout 30
```

Observed with the saved project Vertex AI config:

- Credentials decrypt successfully.
- OAuth token refresh succeeds.
- Anthropic `rawPredict` endpoint is reachable under `locations/global`.
- `claude-mythos-preview` is recognized by Vertex AI, but prediction is blocked by quota:

```text
HTTP 429 RESOURCE_EXHAUSTED
Quota exceeded for aiplatform.googleapis.com/global_online_prediction_requests_per_base_model
base model: anthropic-claude-mythos-preview
```

Control models behave similarly:

- `claude-sonnet-4-6` returns global quota exceeded.
- `claude-opus-4-7` returns global quota exceeded.

Regional probes such as `us-east5` return 404 for these IDs. Current usable location appears to be `global`.

## External Setup Still Required
Google Cloud project must have Vertex AI global online prediction quota for the desired Anthropic base model.

Console:

```text
https://console.cloud.google.com/iam-admin/quotas?service=aiplatform.googleapis.com
```

Request quota for:

- Service: `Vertex AI API`
- Location: `global`
- Metric: `global_online_prediction_requests_per_base_model`
- Base model: `anthropic-claude-mythos-preview`

Likely also needed:

- `global_online_prediction_tokens_per_minute_per_base_model`
- input/output token quotas if split by the console

Official reference:

- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude

## Existing Code Entry Points
Backend:

- `backend/app/routers/models/vertex_ai_config.py`
  - `POST /api/vertex-ai/verify-vertex-ai`
  - Currently lists models with `genai.Client(...).models.list()`.
  - Merges `get_static_google_vertex_models()`.

- `backend/app/routers/models/models.py`
  - `GET /api/models/{provider}`
  - Merges provider `saved_models`.
  - For provider `google`, also merges `VertexAIConfig.saved_models`.
  - Applies `filter_models_by_mode`.

- `backend/app/services/common/model_capabilities.py`
  - Infers capabilities, traits, descriptions.
  - Needs Claude/Anthropic model recognition.

- `backend/app/config/google_vertex_models.json`
  - Google/Vertex static catalog only.

Frontend:

- `frontend/components/modals/settings/VertexAIConfiguration.tsx`
  - Calls `/vertex-ai/verify-vertex-ai`.
  - Converts returned full model path to short ID.
  - Saves selected models into `VertexAIConfig.saved_models`.

- `frontend/components/modals/settings/ModelSelectionPanel.tsx`
  - Displays verified models.

## Target Behavior
1. In Vertex AI settings, Verify Connection should show Anthropic Claude partner models in addition to Google Vertex models.
2. `claude-mythos-preview` should be visible when the project can access the model or when the static partner catalog includes it.
3. If live probing returns quota errors for a recognized Claude model, the UI should still be able to show the model with a clear status/warning rather than silently omitting it.
4. Selected Claude models should be saved into `VertexAIConfig.saved_models`.
5. `GET /api/models/google?mode=chat` should include saved Claude models because they are chat-capable.
6. Media modes must not expose Claude models.
7. Existing Google Vertex image/video model behavior must remain unchanged.

## Recommended Design
### 1. Add Anthropic Vertex Partner Catalog
Create a separate static catalog rather than mixing Anthropic entries into `google_vertex_models.json`.

Suggested file:

- `backend/app/config/vertex_anthropic_models.json`

Initial entries:

```json
{
  "publisher": "anthropic",
  "models": [
    {
      "id": "claude-mythos-preview",
      "display_name": "Claude Mythos Preview",
      "location": "global",
      "families": ["anthropic_claude"],
      "modes": ["chat", "multi-agent", "pdf-extract"]
    },
    {
      "id": "claude-sonnet-4-6",
      "display_name": "Claude Sonnet 4.6",
      "location": "global",
      "families": ["anthropic_claude"],
      "modes": ["chat", "multi-agent", "pdf-extract"]
    },
    {
      "id": "claude-opus-4-7",
      "display_name": "Claude Opus 4.7",
      "location": "global",
      "families": ["anthropic_claude"],
      "modes": ["chat", "multi-agent", "pdf-extract"]
    }
  ]
}
```

Names may need updating if Google publishes canonical IDs differently. Keep the probe script as the local truth tool.

### 2. Add Catalog Loader
Suggested file:

- `backend/app/services/common/vertex_partner_model_catalog.py`

Responsibilities:

- Load Anthropic catalog.
- Return static Claude models.
- Return IDs by mode/family.
- Avoid changing Google static catalog semantics.

### 3. Extend Verify Endpoint
Modify:

- `backend/app/routers/models/vertex_ai_config.py`

Add helper functions:

- Build service-account credentials from request JSON.
- Probe Anthropic models by catalog using:

```text
POST https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/anthropic/models/{model}:rawPredict
```

Payload:

```json
{
  "anthropic_version": "vertex-2023-10-16",
  "messages": [{ "role": "user", "content": "Reply with exactly OK." }],
  "max_tokens": 1,
  "stream": false
}
```

Classification:

- `200`: available.
- `429 RESOURCE_EXHAUSTED` with matching base model: recognized but quota blocked. Include in results with status `quota_exhausted`.
- `403`: access denied. Include only if useful with status `access_denied`, or omit and show warning.
- `404`: not available in that location/project. Omit unless debugging mode.

Response model should be extended carefully:

```python
class VertexAIModel(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = Field(default=None, alias="displayName")
    description: Optional[str] = None
    capabilities: Optional[ModelCapabilities] = None
    publisher: Optional[str] = None
    location: Optional[str] = None
    availability_status: Optional[str] = Field(default=None, alias="availabilityStatus")
    availability_message: Optional[str] = Field(default=None, alias="availabilityMessage")
```

Keep existing fields backward-compatible.

### 4. Add Claude Capabilities
Modify:

- `backend/app/services/common/model_capabilities.py`

Expected Claude capabilities:

```text
vision: true or false depending on model; default true for modern Claude unless verified otherwise
search: false
reasoning: true
coding: true
```

Traits:

```text
multimodal_understanding: true for modern Claude
thinking: true only if model supports thinking and runtime supports it
deep_research: false unless separately implemented
```

Descriptions should not say `Google AI model`. Use `Anthropic Claude model on Vertex AI`.

### 5. Backend Mode Filtering
Modify:

- `backend/app/routers/models/models.py`

Ensure Claude models:

- Included in `chat`, `multi-agent`, `pdf-extract`.
- Excluded from image/video/audio generation/edit modes.

Current chat filter excludes media keywords. Claude IDs should naturally pass, but add tests to protect this.

### 6. Frontend Display
Modify:

- `frontend/components/modals/settings/VertexAIConfiguration.tsx`
- `frontend/components/modals/settings/ModelSelectionPanel.tsx` if needed.

Display `availabilityStatus`:

- `available`: normal selected/unselected card.
- `quota_exhausted`: visible card with warning badge; allow selection only if desired, or disable until quota is fixed.
- `access_denied`: show warning and disable selection.

Avoid hiding quota-blocked Claude Mythos; the user needs to know it exists and what to fix.

When saving selected models, preserve:

- `id`
- `name`
- `description`
- `capabilities`
- `publisher`
- `location`
- `availabilityStatus`

Old saved data without these fields must still load.

## Tests To Add
Backend:

- Unit test Anthropic probe classification:
  - `200` -> model included as available.
  - `429 RESOURCE_EXHAUSTED` -> model included as quota_exhausted.
  - `404` -> omitted from normal result.

- Unit test `verify_vertex_ai_connection` merges:
  - GenAI listed Google models.
  - Static Google Vertex models.
  - Anthropic partner catalog/probe results.

- Unit test mode filtering:
  - Claude appears for `chat`.
  - Claude appears for `multi-agent`.
  - Claude does not appear for `image-gen`, `image-chat-edit`, `video-gen`.

Frontend:

- `VertexAIConfiguration` renders Claude Mythos with quota warning.
- Saving preserves Claude metadata.
- Existing saved Claude model without metadata still renders.

Suggested test targets:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_vertex_anthropic_models.py -q
node_modules/.bin/vitest --root /mnt/user/appdata/gemini-main run frontend/components/modals/settings/VertexAIConfiguration.test.tsx --environment jsdom
node_modules/.bin/tsc --noEmit --pretty false --project tsconfig.json
```

## Acceptance Criteria
- Running Verify Connection with current Vertex AI config shows `Claude Mythos Preview` in the model list.
- If quota is still missing, UI clearly says quota is exhausted and references `anthropic-claude-mythos-preview`.
- Once quota is granted, the same model reports available.
- Saving Vertex AI config persists selected Claude models.
- `GET /api/models/google?mode=chat` can return selected Claude models.
- Existing Google Vertex image/video modes still show the same model set as before.

## Local Probe Command
Use this while implementing:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/probe_vertex_claude_mythos.py --include-controls --model claude-mythos-preview --location global --timeout 30
```

Expected current result before quota increase:

```text
POST global claude-mythos-preview:
HTTP 429 RESOURCE_EXHAUSTED ... base model: anthropic-claude-mythos-preview
```

Expected result after quota increase:

```text
POST global claude-mythos-preview: OK model=claude-mythos-preview text='OK'
```

## Notes For Claude
- Do not print or persist service account JSON outside existing encrypted config storage.
- Do not send long prompts in verification; use `max_tokens=1`.
- Keep verification read-only except for the user clicking Save.
- Avoid broad refactors in provider/model routing.
- Preserve old saved model records.
- Prefer a separate Anthropic catalog/helper over mixing all partner-model behavior into the Google image catalog.
