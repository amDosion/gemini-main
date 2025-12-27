
export interface ToolCall {
  type: string;
  name: string;
  arguments: any;
  id: string;
}

export interface ToolResult {
  name: string;
  call_id: string;
  result: any;
  error?: string;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
  systemPrompt: string;
  icon: string; // Component string identifier
  category: string; // New field for categorization
}

export enum Role {
  USER = 'user',
  MODEL = 'model',
  SYSTEM = 'system', // Added SYSTEM role
}

export type ApiProtocol = 'google' | 'openai';

export type AppMode = 'chat' | 'image-gen' | 'image-edit' | 'video-gen' | 'audio-gen' | 'image-outpainting' | 'pdf-extract' | 'virtual-try-on' | 'deep-research';

export interface GroundingChunk {
  web?: {
    uri: string;
    title: string;
  };
}

export interface GroundingMetadata {
  webSearchQueries?: string[];
  groundingChunks?: GroundingChunk[];
  searchEntryPoint?: {
    renderedContent: string;
  };
}

export interface UrlContextMetadata {
  urlMetadata: {
    retrievedUrl: string;
    urlRetrievalStatus: string;
  }[];
}

export interface Attachment {
  id: string;
  fileUri?: string; 
  mimeType: string;
  name: string;
  url?: string; 
  file?: File;
  // 云存储上传相关字段
  tempUrl?: string; // 临时 URL（DashScope/Blob）
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed'; // 上传状态
  uploadTaskId?: string; // 后端上传任务 ID
  uploadError?: string; // 上传失败的错误信息
  // Google Files API 相关字段
  googleFileUri?: string; // Google Files API 返回的 file_uri（48小时有效）
  googleFileExpiry?: number; // Google 文件过期时间戳
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  attachments?: Attachment[]; 
  groundingMetadata?: GroundingMetadata;
  urlContextMetadata?: UrlContextMetadata; // Added URL Context Metadata
  browserOperationId?: string; // Added: Track browser tool execution ID
  timestamp: number;
  isError?: boolean;
  mode?: AppMode; // Track which mode this message belongs to
  toolCalls?: ToolCall[]; // Added toolCalls
  toolResults?: ToolResult[]; // Added toolResults
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  personaId?: string; // Store the persona used for this session
  mode?: AppMode; // Store the mode of the session
}

export type LoadingState = 'idle' | 'uploading' | 'loading' | 'streaming';

export interface ModelConfig {
  id: string;
  name: string;
  description: string;
  capabilities: {
    vision: boolean;
    search: boolean;
    reasoning: boolean; 
    coding: boolean;
  };
  baseModelId?: string;
  contextWindow?: number; // Optional context window info
}

export interface OutPaintingOptions {
    mode: 'scale' | 'offset' | 'ratio'; // Expanded to support 'ratio'
    xScale?: number;
    yScale?: number;
    leftOffset?: number;
    rightOffset?: number;
    topOffset?: number;
    bottomOffset?: number;
    angle?: number;        // For ratio mode
    outputRatio?: string;  // For ratio mode (e.g., "16:9")
    bestQuality: boolean;
    limitImageSize: boolean;
}

export interface LoraConfig {
    image?: string; // URL of the LoRA reference image
    alpha?: number; // Weight (0.0 to 1.0)
}

export interface ChatOptions {
  enableSearch: boolean;
  enableThinking: boolean;
  enableCodeExecution: boolean;
  enableUrlContext?: boolean; // Added URL Context option
  enableBrowser?: boolean; // Added Browser Tool option
  googleCacheMode?: 'none' | 'exact' | 'semantic'; // Added Google Cache Mode
  imageAspectRatio: string;
  imageResolution: string;
  numberOfImages?: number; // Added for Imagen
  imageStyle?: string;
  voiceName?: string;
  outPainting?: OutPaintingOptions;
  loraConfig?: LoraConfig; // Added for WanX 2.5
  virtualTryOnTarget?: string; // Added for Virtual Try-On
  enableUpscale?: boolean; // Added for Virtual Try-On Upscale
  upscaleFactor?: 2 | 4; // Added for Virtual Try-On Upscale
  addWatermark?: boolean; // Added for Virtual Try-On Upscale
  negativePrompt?: string; // Added for SD-like control
  seed?: number; // Added for reproducibility
  persona?: Persona; // Added for Persona context
  pdfExtractTemplate?: string; // Added for PDF extraction template selection
  pdfAdditionalInstructions?: string; // Added for PDF extraction additional instructions
  enableRAG?: boolean; // Added for RAG (Retrieval-Augmented Generation)
  useGoogleFilesApi?: boolean; // 使用 Google Files API 替代 Base64（减少数据传输）
}

// PDF Extraction Types
export interface PdfExtractionTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface PdfExtractionResult {
  success: boolean;
  template_type: string;
  template_name: string;
  data: Record<string, any>;
  raw_text?: string;
  error?: string;
  model_response?: string;
}

// RAG / Document Embedding Types
export interface DocumentMetadata {
  filename: string;
  document_id: string;
  chunk_count: number;
  added_at: string;
}

export interface SearchResult {
  text: string;
  source: string;
  filename: string;
  similarity: number;
  chunk_id: string;
}

export interface VectorStoreStats {
  total_chunks: number;
  total_documents: number;
  documents: string[];
}
