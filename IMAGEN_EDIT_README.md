# Google Imagen Image Editing - User Guide

## Overview

This document provides a comprehensive guide to using Google Imagen's image editing capabilities in the application. Image editing allows you to modify existing images using AI-powered tools with natural language prompts.

**Key Features**:
- 🎨 **Inpainting**: Insert or remove content in specific areas
- 🖼️ **Outpainting**: Extend image boundaries
- 🛍️ **Product Image Editing**: Specialized editing for product photos
- 🎭 **Style Transfer**: Apply artistic styles to images
- 🎯 **Subject-based Editing**: Edit based on subject references

**Important**: Image editing is **only supported in Vertex AI mode**. Gemini API does not support image editing functionality.

---

## Prerequisites

### Vertex AI Configuration Required

To use image editing, you must configure Vertex AI credentials:

1. Go to **Settings → Profiles**
2. Select or create a Google provider profile
3. Configure the following:
   - **Project ID**: Your Google Cloud project ID
   - **Location**: Region (e.g., `us-central1`)
   - **Credentials**: Service account JSON key or Application Default Credentials

**Without Vertex AI configuration**, you will receive an error:
```
Image editing is only supported in Vertex AI mode. 
Please configure Vertex AI credentials in settings.
```

---

## Reference Image Types

Image editing supports **6 types of reference images**. At minimum, you must provide a **raw** (base) image.

### 1. Raw Reference Image (Required)

The base image that will be edited.

**Format**:
```typescript
{
  raw: {
    url: "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    mimeType: "image/jpeg"
  }
}
```

**Supported formats**: JPEG, PNG, WebP

---

### 2. Mask Reference Image (Optional)

Defines the area to be edited (for inpainting operations).

**Format**:
```typescript
{
  raw: { url: "...", mimeType: "image/jpeg" },
  mask: {
    url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    mimeType: "image/png",
    mode: "background",  // or "foreground", "semantic"
    dilation: 0.03       // Optional: 0.0-1.0
  }
}
```

**Mask Modes**:
- `background`: Edit the background (keep foreground)
- `foreground`: Edit the foreground (keep background)
- `semantic`: Semantic segmentation-based masking

**Dilation**: Expands the mask area (0.0 = no dilation, 1.0 = maximum)

---

### 3. Control Reference Image (Optional)

Provides structural guidance for the edit.

**Format**:
```typescript
{
  raw: { url: "...", mimeType: "image/jpeg" },
  control: {
    url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    mimeType: "image/png",
    type: "canny"  // or "depth", "pose", "scribble"
  }
}
```

**Control Types**:
- `canny`: Edge detection control
- `depth`: Depth map control
- `pose`: Human pose control
- `scribble`: Sketch/scribble control

---

### 4. Style Reference Image (Optional)

Applies the artistic style of a reference image.

**Format**:
```typescript
{
  raw: { url: "...", mimeType: "image/jpeg" },
  style: {
    url: "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    mimeType: "image/jpeg",
    description: "Impressionist painting style"  // Optional
  }
}
```

---

### 5. Subject Reference Image (Optional)

Provides a reference for the subject to be edited.

**Format**:
```typescript
{
  raw: { url: "...", mimeType: "image/jpeg" },
  subject: {
    url: "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    mimeType: "image/jpeg",
    type: "person",  // or "object", "animal"
    description: "A person wearing a red jacket"  // Optional
  }
}
```

---

### 6. Content Reference Image (Optional)

Provides content reference (supports GCS URIs).

**Format**:
```typescript
{
  raw: { url: "...", mimeType: "image/jpeg" },
  content: {
    url: "gs://my-bucket/reference.jpg",  // GCS URI or Base64
    mimeType: "image/jpeg"
  }
}
```

---

## Edit Modes

### 1. Inpainting - Insert (`inpainting-insert`)

Insert new content into a masked area.

**Use Case**: Add objects, change backgrounds, fill in missing parts

**Required Images**: `raw` + `mask`

**Example**:
```typescript
await llmService.editImage(
  "Add a sunset background",
  {
    raw: { url: baseImageBase64, mimeType: "image/jpeg" },
    mask: { url: maskImageBase64, mimeType: "image/png", mode: "background" }
  }
);
```

**Note**: `aspect_ratio` parameter is **not supported** for inpainting-insert mode.

---

### 2. Inpainting - Remove (`inpainting-remove`)

Remove content from a masked area.

**Use Case**: Remove unwanted objects, clean up images

**Required Images**: `raw` + `mask`

**Example**:
```typescript
await llmService.editImage(
  "Remove the person from the image",
  {
    raw: { url: baseImageBase64, mimeType: "image/jpeg" },
    mask: { url: maskImageBase64, mimeType: "image/png", mode: "foreground" }
  }
);
```

---

### 3. Outpainting (`outpainting`)

Extend the image beyond its original boundaries.

**Use Case**: Expand canvas, add more context around the image

**Required Images**: `raw` only

**Example**:
```typescript
await llmService.editImage(
  "Extend the landscape to the left and right",
  {
    raw: { url: baseImageBase64, mimeType: "image/jpeg" }
  }
);
```

**Supported Aspect Ratios**: `1:1`, `3:4`, `4:3`, `9:16`, `16:9`

---

### 4. Product Image (`product-image`)

Specialized editing for product photography.

**Use Case**: Product photo enhancement, background replacement

**Required Images**: `raw` only

**Example**:
```typescript
await llmService.editImage(
  "Place the product on a white studio background",
  {
    raw: { url: productImageBase64, mimeType: "image/jpeg" }
  }
);
```

---

## Advanced Options

### Edit Configuration

You can customize the editing process with additional options:

```typescript
const options: ChatOptions = {
  // Number of images to generate (1-8)
  numberOfImages: 1,
  
  // Aspect ratio (for outpainting and product-image modes)
  imageAspectRatio: "1:1",  // "1:1", "3:4", "4:3", "9:16", "16:9"
  
  // Guidance scale (1.0-20.0, higher = more adherence to prompt)
  guidanceScale: 10.0,
  
  // Negative prompt (what to avoid)
  negativePrompt: "blurry, low quality, distorted",
  
  // Random seed for reproducibility
  seed: 12345,
  
  // Output format
  outputMimeType: "image/jpeg",  // or "image/png"
  
  // JPEG compression quality (1-100)
  outputCompressionQuality: 90,
  
  // Person generation setting
  personGeneration: "allow_adult",  // "dont_allow", "allow_adult", "allow_all"
  
  // Safety filter level
  safetyFilterLevel: "block_some",  // "block_low_and_above", "block_medium_and_above", "block_only_high", "block_some"
  
  // Add watermark (cannot be used with seed)
  addWatermark: false
};

await llmService.editImage(prompt, referenceImages);
```

---

## Code Examples

### Example 1: Basic Inpainting

```typescript
import { llmService } from './services/llmService';

// Start a new chat session with a model
llmService.startNewChat([], modelConfig, options);

// Prepare reference images
const referenceImages = {
  raw: {
    url: "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    mimeType: "image/jpeg"
  },
  mask: {
    url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    mimeType: "image/png",
    mode: "background"
  }
};

// Edit the image
try {
  const results = await llmService.editImage(
    "Replace the background with a beach scene",
    referenceImages
  );
  
  console.log(`Generated ${results.length} edited images`);
  results.forEach((img, i) => {
    console.log(`Image ${i + 1}: ${img.url.substring(0, 50)}...`);
  });
} catch (error) {
  console.error("Image editing failed:", error.message);
}
```

---

### Example 2: Style Transfer

```typescript
const referenceImages = {
  raw: {
    url: photoBase64,
    mimeType: "image/jpeg"
  },
  style: {
    url: paintingBase64,
    mimeType: "image/jpeg",
    description: "Van Gogh's Starry Night style"
  }
};

const results = await llmService.editImage(
  "Apply the artistic style to the photo",
  referenceImages
);
```

---

### Example 3: Outpainting with Custom Aspect Ratio

```typescript
// Configure options
llmService.startNewChat([], modelConfig, {
  imageAspectRatio: "16:9",
  guidanceScale: 12.0
});

const referenceImages = {
  raw: {
    url: landscapeBase64,
    mimeType: "image/jpeg"
  }
};

const results = await llmService.editImage(
  "Extend the landscape to create a panoramic view",
  referenceImages
);
```

---

### Example 4: Product Image with Negative Prompt

```typescript
llmService.startNewChat([], modelConfig, {
  negativePrompt: "shadows, reflections, cluttered background",
  outputMimeType: "image/png",
  outputCompressionQuality: 100
});

const referenceImages = {
  raw: {
    url: productBase64,
    mimeType: "image/jpeg"
  }
};

const results = await llmService.editImage(
  "Place the product on a clean white background",
  referenceImages
);
```

---

## Error Handling

### Common Errors

#### 1. Vertex AI Not Configured

**Error**:
```
Image editing is only supported in Vertex AI mode. 
Please configure Vertex AI credentials in settings.
```

**Solution**: Configure Vertex AI in Settings → Profiles

---

#### 2. Missing Raw Reference Image

**Error**:
```
Raw reference image is required for image editing
```

**Solution**: Ensure `referenceImages.raw` is provided

---

#### 3. Invalid Edit Mode

**Error**:
```
Invalid parameters: edit_mode must be one of: inpainting-insert, 
inpainting-remove, outpainting, product-image
```

**Solution**: Check the edit mode in options

---

#### 4. Content Policy Violation

**Error**:
```
Content policy blocked: Your prompt was blocked by safety filters. 
Try rephrasing it.
```

**Solution**: Rephrase the prompt to avoid sensitive content

---

#### 5. Aspect Ratio Not Supported

**Error**:
```
Invalid parameters: aspect_ratio is not supported for inpainting-insert mode
```

**Solution**: Remove `imageAspectRatio` option for inpainting operations

---

## Best Practices

### 1. Prompt Engineering

- **Be specific**: "Add a red sports car" instead of "Add a car"
- **Describe style**: "Photorealistic sunset" vs "Cartoon sunset"
- **Use negative prompts**: Specify what to avoid

### 2. Mask Quality

- **Clean edges**: Use high-quality masks with smooth edges
- **Appropriate dilation**: Use 0.03-0.05 for natural blending
- **Correct mode**: Use `background` to edit background, `foreground` to edit subject

### 3. Reference Images

- **High resolution**: Use at least 512x512 images
- **Consistent style**: Match the style of reference images to desired output
- **Clear subjects**: Use clear, well-lit reference images

### 4. Performance

- **Start with 1 image**: Test with `numberOfImages: 1` first
- **Iterate**: Use `seed` parameter to reproduce good results
- **Batch generation**: Generate multiple variations with different seeds

---

## API Reference

### llmService.editImage()

```typescript
async editImage(
  prompt: string,
  referenceImages: Record<string, Attachment>
): Promise<ImageGenerationResult[]>
```

**Parameters**:
- `prompt`: Text description of the desired edit
- `referenceImages`: Dictionary of reference images (at least `raw` required)

**Returns**: Array of edited images with `url` and `mimeType`

**Throws**:
- `Error` if provider not configured
- `Error` if no model selected
- `Error` if `raw` reference image missing
- `Error` if backend API fails

---

### UnifiedProviderClient.editImage()

```typescript
async editImage(
  modelId: string,
  prompt: string,
  referenceImages: Record<string, any>,
  options: ChatOptions,
  baseUrl: string
): Promise<ImageGenerationResult[]>
```

**Parameters**:
- `modelId`: Model to use (e.g., `imagen-3.0-generate-001`)
- `prompt`: Edit description
- `referenceImages`: Dictionary of reference images
- `options`: Edit configuration options
- `baseUrl`: Custom API URL (optional)

**Returns**: Array of edited images

---

## Monitoring and Logging

### Backend Logging

The backend logs all image editing requests:

```python
logger.info(f"[Generate Router] Image edit request: user_id={user_id}, model={model_id}, api_mode={api_mode}")
```

### Usage Statistics

Track image editing usage:

```python
# In ImageEditCoordinator
self.vertex_ai_edit_count += 1
self.gemini_api_edit_count += 1
self.edit_fallback_count += 1
```

### Monitoring Endpoint (Optional)

```
GET /api/generate/monitoring/stats
```

Returns:
```json
{
  "vertex_ai_edit_count": 150,
  "gemini_api_edit_count": 0,
  "edit_fallback_count": 5
}
```

---

## Troubleshooting

### Issue: Slow Response

**Possible Causes**:
- Large image files
- Complex edits
- Network latency

**Solutions**:
- Resize images to 1024x1024 or smaller
- Simplify the prompt
- Check network connection

---

### Issue: Poor Edit Quality

**Possible Causes**:
- Vague prompt
- Low-quality reference images
- Incorrect mask

**Solutions**:
- Use more specific prompts
- Use high-resolution reference images
- Refine the mask with proper dilation

---

### Issue: Inconsistent Results

**Possible Causes**:
- Random seed not set
- High guidance scale

**Solutions**:
- Set a fixed `seed` value
- Adjust `guidanceScale` (try 8.0-12.0)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-09 | Initial release |

---

## Support

For issues or questions:
- Check the [API Documentation](./IMAGEN_README.md)
- Review [Migration Guide](./IMAGEN_API_MIGRATION.md)
- Contact support team

---

**Last Updated**: 2026-01-09  
**Maintained By**: Development Team
