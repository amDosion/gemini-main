# Image Edit 404 Error - Root Cause Analysis

**Date**: 2026-01-10  
**Error**: 404 NOT_FOUND when using `nano-banana-pro-preview` in edit mode  
**Status**: ROOT CAUSE IDENTIFIED

---

## 🔍 Problem Summary

User is in **edit mode** (`mode="image-edit"`) with a reference image, but the backend receives a request to the **generation endpoint** instead of the **edit endpoint**.

---

## 📊 Evidence from Error Log

### 1. HTTP Request (Line 150 of log)
```
POST /api/generate/google/image HTTP/1.1
```
**❌ WRONG**: This is the generation endpoint  
**✅ CORRECT**: Should be `/api/generate/google/image/edit`

### 2. Backend Log Header (Line 1)
```
[Generate] ==================== Image Generation Request ====================
```
**Confirms**: Backend received a generation request, not an edit request

### 3. Service Call Chain
```
generate_image() → ImageGenerator → imagen_vertex_ai.generate_images()
```
**❌ WRONG**: Using generation flow  
**✅ CORRECT**: Should use `edit_image() → ImageEditCoordinator → image_edit_vertex_ai.edit_image()`

### 4. Reference Images
```
[Generate] Reference Images Count: 1
```
**Note**: User HAS a reference image, but it's being treated as generation context, not edit input

---

## 🐛 Root Cause

**Frontend is calling the wrong API endpoint.**

Despite `mode="image-edit"` being set correctly in the frontend:
- `ImageEditHandler` is selected ✅
- `llmService.editImage()` is called ✅
- `UnifiedProviderClient.editImage()` is invoked ✅
- **BUT**: The actual HTTP request goes to `/api/generate/google/image` ❌

---

## 🔧 Possible Causes

### Hypothesis 1: Frontend Routing Bug
The `UnifiedProviderClient.editImage()` method might have a bug where it constructs the wrong URL.

**Expected Code** (line 485 of UnifiedProviderClient.ts):
```typescript
const response = await fetch(`/api/generate/${this.id}/image/edit`, {
```

**Need to verify**: Is `this.id` correctly set to `'google'`?

### Hypothesis 2: Request Interception/Proxy
A middleware or proxy might be rewriting the URL from `/image/edit` to `/image`.

### Hypothesis 3: Frontend State Mismatch
The frontend might be in a mixed state where:
- UI shows edit mode
- But the actual request uses generation logic

---

## 🎯 Next Steps

### Step 1: Verify Frontend URL Construction
Check `UnifiedProviderClient.editImage()` at line 485:
```typescript
console.log('[DEBUG] Calling endpoint:', `/api/generate/${this.id}/image/edit`);
console.log('[DEBUG] Provider ID:', this.id);
```

### Step 2: Add Backend Logging
Add logging to both endpoints to see which one receives the request:
```python
# In /api/generate/{provider}/image
logger.info(f"[ENDPOINT] Generation endpoint hit: {provider}")

# In /api/generate/{provider}/image/edit
logger.info(f"[ENDPOINT] Edit endpoint hit: {provider}")
```

### Step 3: Check Network Tab
User should open browser DevTools → Network tab and verify:
- Request URL: Should be `/api/generate/google/image/edit`
- Request Method: POST
- Request Body: Should contain `referenceImages` object

---

## 💡 Temporary Workaround

Until the bug is fixed, user can:
1. Use a different model that supports generation (e.g., `imagen-3.0-generate-001`)
2. Or wait for the fix to use edit mode properly

---

## 📝 Model Compatibility Note

The 404 error for `nano-banana-pro-preview` is a **secondary issue**:
- This model doesn't exist in Vertex AI for **generation**
- But it DOES exist for **editing** (mapped to `imagen-3.0-capability-001`)
- Once the routing bug is fixed, the model will work correctly

**Model Mapping** (from `image_edit_vertex_ai.py`):
```python
MODEL_MAPPING = {
    'nano-banana-pro-preview': 'imagen-3.0-capability-001',  # ✅ Correct for EDIT
    # ...
}
```

---

## 🔍 Files to Investigate

1. **Frontend**:
   - `frontend/services/providers/UnifiedProviderClient.ts` (line 485)
   - `frontend/services/llmService.ts` (line 195-235)
   - `frontend/hooks/handlers/ImageEditHandlerClass.ts`

2. **Backend**:
   - `backend/app/routers/generate.py` (endpoints at line 200 and 417)
   - `backend/app/services/gemini/google_service.py` (routing logic)

---

## ✅ Verification Checklist

- [ ] Frontend calls `/api/generate/google/image/edit` (not `/image`)
- [ ] Backend receives request at edit endpoint
- [ ] `ImageEditCoordinator` is invoked (not `ImageGenerator`)
- [ ] `image_edit_vertex_ai.edit_image()` is called (not `imagen_vertex_ai.generate_image()`)
- [ ] Model mapping applies: `nano-banana-pro-preview` → `imagen-3.0-capability-001`
- [ ] Request succeeds with edited image

---

**Next Action**: Add debug logging to frontend and backend to trace the exact request path.
