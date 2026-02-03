
export interface ToolCall {
  type: string;
  name: string;
  arguments: any;
  id: string;
}

export interface ToolResult {
  name: string;
  callId: string;
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

export type AppMode = 'chat' | 'image-gen' | 'image-chat-edit' | 'image-mask-edit' | 'image-inpainting' | 'image-background-edit' | 'image-recontext' | 'video-gen' | 'audio-gen' | 'image-outpainting' | 'pdf-extract' | 'virtual-try-on' | 'deep-research' | 'multi-agent' | 'image-upscale' | 'image-segmentation' | 'product-recontext';

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
  cloudUrl?: string; // 云存储 URL（如果已上传完成）
  size?: number; // 文件大小（bytes）
  // ✅ 后端返回的元数据
  messageId?: string; // 消息 ID
  sessionId?: string; // 会话 ID
  userId?: string; // 用户 ID
  createdAt?: number; // 创建时间戳
  // Google Files API 相关字段
  googleFileUri?: string; // Google Files API 返回的 file_uri（48小时有效）
  googleFileExpiry?: number; // Google 文件过期时间戳
  // AI 增强提示词相关字段
  enhancedPrompt?: string; // 增强后的提示词（当启用 enhance_prompt 时返回）
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
  thoughts?: Array<{ type: 'text' | 'image'; content: string }>; // 思考过程（thoughts）
  textResponse?: string; // 文本响应
  enhancedPrompt?: string; // AI 增强后的提示词
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
    aspectRatio?: string;   // Aspect ratio for outpainting
    platform?: string;     // Platform identifier (e.g., 'gemini', 'vertex_ai')
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
  enableGrounding?: boolean; // Added for Google Grounding
  enableUrlContext?: boolean; // Added URL Context option
  enableBrowser?: boolean; // Added Browser Tool option
  enableResearch?: boolean; // Added Research option (basic research in Chat mode)
  googleCacheMode?: 'none' | 'exact' | 'semantic'; // Added Google Cache Mode
  imageAspectRatio: string;
  imageResolution: string;
  numberOfImages?: number; // Added for Imagen
  imageStyle?: string;
  voiceName?: string;
  outPainting?: OutPaintingOptions;
  loraConfig?: LoraConfig; // Added for WanX 2.5
  // Virtual Try-On 官方支持参数
  baseSteps?: number; // 质量步数（8/16/32/48）
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
  // Model generation parameters
  temperature?: number; // Model temperature parameter
  maxTokens?: number; // Maximum tokens to generate
  topP?: number; // Top-p sampling parameter
  topK?: number; // Top-k sampling parameter
  baseUrl?: string; // Custom base URL for API requests
  // Imagen-specific advanced parameters
  // guidanceScale removed - not officially documented by Google Imagen (但用于 mask 编辑)
  // personGeneration parameter removed - API uses default (allow_adult)
  outputMimeType?: string; // Output format (image/jpeg, image/png)
  outputCompressionQuality?: number; // JPEG compression quality (1-100)
  language?: string; // Prompt language

  enhancePrompt?: boolean; // Let AI improve the prompt (Google Imagen)
  enhancePromptModel?: string; // Model for prompt enhancement
  // Mask Edit 特有参数
  editMode?: string; // 编辑模式 (EDIT_MODE_INPAINT_INSERTION, EDIT_MODE_INPAINT_REMOVAL, etc.)
  maskDilation?: number; // 掩码膨胀系数 (0.0-1.0)
  guidanceScale?: number; // 引导比例 (1.0-20.0)，仅用于 mask 编辑
  maskMode?: 'MASK_MODE_USER_PROVIDED' | 'MASK_MODE_BACKGROUND' | 'MASK_MODE_FOREGROUND' | 'MASK_MODE_SEMANTIC'; // 掩码模式 (Vertex AI MaskReferenceConfig)
  // TongYi 专用参数
  promptExtend?: boolean; // AI 增强提示词 (TongYi)
  addMagicSuffix?: boolean; // 魔法词组 (TongYi)
  prompt?: string; // Prompt text for image generation/editing
  modelId?: string; // Model ID for specific operations
  platform?: string; // Platform identifier (e.g., 'gemini', 'vertex_ai')
  // Deep Research specific options
  deepResearchConfig?: {
    thinkingSummaries?: 'auto' | 'none'; // Thinking summaries mode for Deep Research
    researchMode?: 'vertex-ai' | 'gemini-api'; // Research mode: Vertex AI (interactions API) or Gemini API (genai SDK)
  };
  // Multi-Agent workflow configuration
  multiAgentConfig?: {
    nodes: Array<{
      id: string;
      type: 'agent' | 'condition' | 'merge';
      agentId?: string;
      label: string;
      position: { x: number; y: number };
    }>;
    edges: Array<{
      id: string;
      source: string;
      target: string;
    }>;
  };
  // Live API configuration
  liveAPIConfig?: {
    agentId?: string; // Optional agent ID for Live API
  };
  // Session/Message 上下文（Handler 传递给后端用于附件记录等）
  sessionId?: string;
  frontendSessionId?: string;
  messageId?: string;
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
  templateType: string;
  templateName: string;
  data: Record<string, any>;
  rawText?: string;
  error?: string;
  modelResponse?: string;
}

// RAG / Document Embedding Types
export interface DocumentMetadata {
  filename: string;
  documentId: string;
  chunkCount: number;
  addedAt: string;
}

export interface SearchResult {
  text: string;
  source: string;
  filename: string;
  similarity: number;
  chunkId: string;
}

export interface VectorStoreStats {
  totalChunks: number;
  totalDocuments: number;
  documents: string[];
}

// Unified Init API Types
export interface InitData {
  // Configuration related
  profiles: any[];  // ConfigProfile[] - imported from db.ts
  activeProfileId: string | null;
  activeProfile: any | null;  // ConfigProfile | null
  dashscopeKey: string;
  
  // Cloud storage related
  storageConfigs: any[];  // StorageConfig[] - imported from storage.ts
  activeStorageId: string | null;
  
  // Session related
  sessions: ChatSession[];
  sessionsTotal?: number;  // ✅ 总会话数量（用于分页）
  sessionsHasMore?: boolean;  // ✅ 是否还有更多会话（用于滚动加载）
  
  // Persona related
  personas: Persona[];
  
  // Imagen configuration
  imagenConfig?: {
    apiMode: string;
    vertexAiProjectId: string | null;
    vertexAiLocation: string;
    vertexAiCredentialsJson: string | null;
  } | null;
  
  // Optional: cached model list
  cachedModels?: ModelConfig[] | null;
  
  // Metadata
  _metadata?: {
    timestamp: number;
    partialFailures?: string[];
  };
}
