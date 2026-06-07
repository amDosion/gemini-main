/**
 * UnifiedProviderClient 内部响应类型定义。
 *
 * 1:1 抽离自 `UnifiedProviderClient.ts`（< 800 行合规拆分），
 * 与 `unifiedProviderHelpers.ts` 遵循同一拆分模式。
 *
 * 这些接口描述后端 `/api/models/{provider}` 与
 * `/api/modes/{provider}/{mode}` 端点的响应形状。所有字段在 client
 * 内部按 provider 驱动的动态契约处理，narrowing 发生在映射点。
 */

/**
 * Raw model entry as returned by `GET /api/models/{provider}`.
 *
 * The backend emits complete ModelConfig-shaped objects, but every field is
 * treated as optional/dynamic here because the shape is provider-driven and
 * may evolve; narrowing happens at the mapping site.
 */
export interface RawModelEntry {
  id: string;
  name?: string;
  description?: string;
  capabilities?: Record<string, boolean>;
  contextWindow?: number;
}

/** Response envelope for `GET /api/models/{provider}`. */
export interface ModelsListResponse {
  models: RawModelEntry[];
}

/**
 * Unified backend response envelope: `{ success: boolean; data: T }`.
 * Used by every `/api/modes/{provider}/{mode}` endpoint.
 */
export interface UnifiedResponseEnvelope<T = unknown> {
  success: boolean;
  data: T;
}

/**
 * Image result item shape returned inside `data.images` for image modes.
 * Fields mirror the standardized backend payload (snake_case is converted to
 * camelCase by CaseConversionMiddleware before it reaches the client).
 */
export interface RawImageResultItem {
  url?: string;
  mimeType?: string;
  filename?: string;
  attachmentId?: string;
  uploadStatus?: 'pending' | 'completed' | 'failed';
  taskId?: string;
  thoughts?: Array<{ type: 'text' | 'image'; content: string }>;
  text?: string;
  enhancedPrompt?: string;
  openaiResponseId?: string;
  messageId?: string;
  sessionId?: string;
  userId?: string;
  size?: number;
  cloudUrl?: string;
  createdAt?: number;
}

/** `data` payload for image modes that return a list of generated images. */
export interface ImageModeData {
  images?: RawImageResultItem[];
}

/** Response payload for `POST /api/upload/{provider}`. */
export interface UploadFileResponse {
  fileId?: string;
  url?: string;
}
