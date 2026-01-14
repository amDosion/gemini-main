# Google Provider 目录 - 已废弃

## ⚠️ 此目录已废弃

根据新架构，所有 Provider 都应该通过后端统一处理，前端不应该直接调用任何 SDK。

## 迁移指南

### 旧方式（已废弃）
```typescript
import { createGoogleClient } from './utils';
import { generateTextToImage } from './media/image-gen';
const ai = createGoogleClient(apiKey, baseUrl);
const result = await generateTextToImage(ai, modelId, prompt, options);
```

### 新方式（推荐）
```typescript
import { UnifiedProviderClient } from '../UnifiedProviderClient';
const client = new UnifiedProviderClient('google');
const result = await client.executeMode('image-gen', modelId, prompt, attachments, options);
```

## 文件状态

- ✅ `utils.ts` - 已废弃，使用 `UnifiedProviderClient` 代替
- ✅ `fileService.ts` - 已废弃，文件上传通过后端统一处理
- ✅ `parser.ts` - 已废弃，响应解析由后端统一处理
- ✅ `media/image-gen.ts` - 已废弃，使用 `UnifiedProviderClient.executeMode('image-gen', ...)` 代替
- ✅ `media/image-edit.ts` - 已废弃，使用 `UnifiedProviderClient.executeMode('image-edit', ...)` 代替
- ✅ `media/video.ts` - 已废弃，使用 `UnifiedProviderClient.executeMode('video-gen', ...)` 代替
- ✅ `media/audio.ts` - 已废弃，使用 `UnifiedProviderClient.executeMode('audio-gen', ...)` 代替
- ✅ `media/virtual-tryon.ts` - 已废弃，使用 `UnifiedProviderClient.executeMode('virtual-try-on', ...)` 代替
- ✅ `media/index.ts` - 已废弃，`MediaFactory` 应使用 `UnifiedProviderClient` 代替

## 特殊说明

### generateMaskPreview 函数
`generateMaskPreview` 函数用于生成掩码预览，目前仍在使用。此功能应该：
1. 通过后端 API 实现（推荐）
2. 或者重构为纯前端功能（不依赖 Google SDK）

如果后端已支持分割功能，应使用 `UnifiedProviderClient.executeMode()` 调用后端 API。
