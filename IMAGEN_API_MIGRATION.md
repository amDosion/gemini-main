# Google Image Generation API - Migration Guide

## Overview

This document describes the changes made to the Google image generation flow and provides guidance for migrating existing code.

**Version**: 2026-01-09  
**Status**: Completed

---

## What Changed?

### Security Improvements

1. **API Key No Longer Exposed in Frontend**
   - **Before**: API keys were passed from frontend to backend in request body
   - **After**: API keys are retrieved from database on the backend
   - **Impact**: Frontend code is more secure, API keys never exposed in network requests

2. **Session-Based Authentication**
   - **Before**: API key authentication
   - **After**: Session cookie authentication (`credentials: 'include'`)
   - **Impact**: Better security, consistent with other endpoints

### Architecture Improvements

3. **Vertex AI Configuration Support**
   - **Before**: Only Gemini API supported
   - **After**: Supports both Gemini API and Vertex AI
   - **Impact**: Users can configure Vertex AI for better performance/features

4. **User-Scoped Configuration**
   - **Before**: Global configuration only
   - **After**: Per-user configuration with fallback to environment variables
   - **Impact**: Multi-tenant support, better isolation

---

## API Changes

### Image Generation Endpoint

**Endpoint**: `POST /api/generate/{provider}/image`

#### Request Body Changes

**Removed Parameters**:
- ❌ `apiKey` - No longer accepted in request body

**Request Body (Before)**:
```json
{
  "modelId": "imagen-3.0-generate-001",
  "prompt": "A beautiful sunset",
  "apiKey": "your-api-key-here",  // ❌ REMOVED
  "options": {
    "numberOfImages": 1,
    "aspectRatio": "1:1"
  }
}
```

**Request Body (After)**:
```json
{
  "modelId": "imagen-3.0-generate-001",
  "prompt": "A beautiful sunset",
  // ✅ apiKey removed - retrieved from database
  "options": {
    "numberOfImages": 1,
    "aspectRatio": "1:1"
  }
}
```

#### Authentication Changes

**Before**:
```typescript
// Frontend code (OLD - DO NOT USE)
const response = await fetch('/api/generate/google/image', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    modelId: 'imagen-3.0-generate-001',
    prompt: 'A sunset',
    apiKey: userApiKey  // ❌ Exposed in network request
  })
});
```

**After**:
```typescript
// Frontend code (NEW - RECOMMENDED)
const response = await fetch('/api/generate/google/image', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',  // ✅ Send session cookie
  body: JSON.stringify({
    modelId: 'imagen-3.0-generate-001',
    prompt: 'A sunset'
    // ✅ No apiKey - backend retrieves from database
  })
});
```

#### Response Format

**No changes** - Response format remains the same:

```json
{
  "images": [
    {
      "url": "data:image/jpeg;base64,...",
      "revised_prompt": "Enhanced prompt..."
    }
  ]
}
```

---

## Migration Steps

### For Frontend Developers

#### Step 1: Remove API Key Parameters

**File**: `frontend/services/providers/UnifiedProviderClient.ts`

```typescript
// Before
async generateImage(
  prompt: string,
  model: string,
  apiKey: string,  // ❌ Remove this parameter
  options?: any
): Promise<ImageGenerationResult[]>

// After
async generateImage(
  prompt: string,
  model: string,
  // ✅ apiKey parameter removed
  options?: any
): Promise<ImageGenerationResult[]>
```

#### Step 2: Update API Calls

**File**: `frontend/services/llmService.ts`

```typescript
// Before
const results = await this.currentProvider.generateImage(
  prompt,
  model,
  this.apiKey,  // ❌ Remove this argument
  options
);

// After
const results = await this.currentProvider.generateImage(
  prompt,
  model,
  // ✅ apiKey argument removed
  options
);
```

#### Step 3: Ensure Credentials Are Included

```typescript
// Ensure all fetch calls include credentials
fetch(url, {
  method: 'POST',
  credentials: 'include',  // ✅ Required for session authentication
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(requestBody)
});
```

### For Backend Developers

#### Step 1: Update Provider Factory Calls

**File**: `backend/app/routers/generate.py`

```python
# Before
service = ProviderFactory.create(
    provider=provider,
    api_key=api_key,
    api_url=base_url,
    timeout=120.0
    # ❌ Missing user_id and db
)

# After
service = ProviderFactory.create(
    provider=provider,
    api_key=api_key,
    api_url=base_url,
    timeout=120.0,
    user_id=user_id,  # ✅ Added
    db=db             # ✅ Added
)
```

#### Step 2: Pass User Context Through Chain

Ensure all components in the chain receive `user_id` and `db`:

```
Router → ProviderFactory → GoogleService → ImageGenerator → ImagenCoordinator
```

---

## Configuration Guide

### Vertex AI Configuration

Users can now configure Vertex AI for image generation:

#### Database Configuration (Recommended)

1. Navigate to Settings → Imagen Configuration
2. Select "Vertex AI" as API mode
3. Enter configuration:
   - Project ID: Your Google Cloud project ID
   - Location: Region (e.g., `us-central1`)
   - Credentials JSON: Service account credentials

#### Environment Variable Configuration (Fallback)

```bash
# Enable Vertex AI
export GOOGLE_GENAI_USE_VERTEXAI=true

# Vertex AI configuration
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
```

### Configuration Priority

The system uses the following priority order:

1. **Database Configuration** (per-user)
   - Highest priority
   - Stored in `ImagenConfig` table
   - Encrypted credentials

2. **Environment Variables** (global)
   - Fallback when no database config
   - Shared across all users
   - Useful for testing/development

---

## Error Handling

### New Error Messages

#### 401 Authentication Failed

**Cause**: User session expired or not logged in

**Message**: "Authentication failed. Please log in again to generate images."

**Solution**: User needs to log in again

#### 401 API Key Not Found

**Cause**: No API key configured for the user

**Message**: "API Key not found for provider: google. User: {user_id}. Please configure it in provider settings or environment variables."

**Solution**: Configure API key in settings or environment variables

---

## Monitoring

### Usage Statistics

A new monitoring endpoint is available:

**Endpoint**: `GET /api/generate/monitoring/stats`

**Response**:
```json
{
  "status": "success",
  "stats": {
    "vertex_ai_usage": 150,
    "gemini_api_usage": 50,
    "fallback_count": 5
  },
  "description": {
    "vertex_ai_usage": "Number of times Vertex AI was used for image generation",
    "gemini_api_usage": "Number of times Gemini API was used for image generation",
    "fallback_count": "Number of times fallback from Vertex AI to Gemini API occurred"
  }
}
```

### Logging

Enhanced logging is now available:

```python
# Configuration source logging
logger.info(f"[ImagenCoordinator] Using Vertex AI config from database for user={user_id}")
logger.info(f"[ImagenCoordinator] Using Vertex AI config from environment variables")

# Request logging
logger.info(f"[Generate] Image generation: provider={provider}, user={user_id}, model={model}")

# Fallback logging
logger.warning(f"[ImagenCoordinator] Falling back to Gemini API due to Vertex AI failure")
```

---

## Backward Compatibility

### Breaking Changes

1. **Frontend API Signature**
   - `generateImage()` method no longer accepts `apiKey` parameter
   - **Impact**: All calling code must be updated

2. **Authentication Method**
   - Session-based authentication required
   - **Impact**: Users must be logged in

### Non-Breaking Changes

1. **Backend API**
   - `user_id` and `db` parameters are optional in ProviderFactory
   - **Impact**: Backward compatible with existing code

2. **Response Format**
   - No changes to response structure
   - **Impact**: No changes needed in response handling code

---

## Testing

### Manual Testing Checklist

- [ ] User with Vertex AI config can generate images
- [ ] User without config falls back to Gemini API
- [ ] User with incomplete config falls back correctly
- [ ] 401 error shows friendly message when not logged in
- [ ] API key not exposed in network requests (check DevTools)
- [ ] Monitoring endpoint returns correct statistics

### Automated Testing

Optional test tasks are available in the spec:
- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- Property tests: `backend/tests/property/`

---

## Rollback Plan

If issues occur, follow this rollback procedure:

### Step 1: Revert Frontend Changes

```bash
git revert <commit-hash-phase-2>
```

### Step 2: Keep Backend Changes

Backend changes are non-breaking and can remain:
- `user_id` and `db` parameters are optional
- Existing functionality continues to work

### Step 3: Estimated Rollback Time

- **Frontend rollback**: < 15 minutes
- **Backend rollback**: Not required (backward compatible)
- **Total rollback time**: < 30 minutes

---

## Support

### Documentation

- **Spec Document**: `.kiro/specs/google-image-gen-flow-analysis/`
- **Design Document**: `.kiro/specs/google-image-gen-flow-analysis/design.md`
- **Requirements**: `.kiro/specs/google-image-gen-flow-analysis/requirements.md`

### Contact

For questions or issues, please contact the development team.

---

**Last Updated**: 2026-01-09  
**Version**: 1.0.0  
**Status**: Production Ready
