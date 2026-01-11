/**
 * Imagen API Configuration Types
 * 
 * Defines TypeScript interfaces for Imagen API configuration,
 * supporting both Gemini API and Vertex AI modes.
 */

/**
 * API mode for image generation
 */
export type ImagenAPIMode = 'gemini_api' | 'vertex_ai';

/**
 * Imagen API settings configuration
 */
export interface ImagenAPISettings {
  /** API mode to use for image generation */
  apiMode: ImagenAPIMode;
  
  /** Gemini API key (required for gemini_api mode) */
  geminiApiKey?: string;
  
  /** Vertex AI configuration (required for vertex_ai mode) */
  vertexAI?: {
    /** Google Cloud project ID */
    projectId: string;
    /** Vertex AI location/region */
    location: string;
    /** Service account credentials JSON content */
    credentialsJson: string;
  };
}

/**
 * Image generation capabilities for the selected API
 */
export interface ImageGenerationCapabilities {
  /** API type identifier */
  apiType: ImagenAPIMode;
  /** Maximum number of images that can be generated in one request */
  maxImages: number;
  /** Supported aspect ratios */
  aspectRatios: string[];
  /** Supported image sizes */
  imageSizes: string[];
  /** Deprecated: personGeneration parameter removed - API uses default (allow_adult) */
  // personGeneration: string[];
  /** Deprecated: supportsAllowAll removed with personGeneration parameter */
  // supportsAllowAll: boolean;
}

import { ModelConfig } from './types';

/**
 * Configuration response from backend
 */
export interface ImagenConfigResponse {
  /** Current API mode */
  apiMode: ImagenAPIMode;
  /** Capabilities of the current API */
  capabilities: ImageGenerationCapabilities;
  /** Whether Gemini API is configured */
  geminiApiConfigured: boolean;
  /** Whether Vertex AI is configured */
  vertexAiConfigured: boolean;
  /** Vertex AI project ID */
  vertexAiProjectId?: string;
  /** Vertex AI location */
  vertexAiLocation?: string;
  /** Vertex AI credentials JSON content */
  vertexAiCredentialsJson?: string;
  /** Hidden model IDs (for Vertex AI mode) */
  hiddenModels?: string[];
  /** Saved model configurations (ModelConfig[] for Vertex AI mode) */
  savedModels?: ModelConfig[];
}

/**
 * Configuration update request
 */
export interface ImagenConfigUpdateRequest {
  /** API mode to use */
  apiMode: ImagenAPIMode;
  /** Gemini API key (required for gemini_api mode) */
  geminiApiKey?: string;
  /** Vertex AI project ID (required for vertex_ai mode) */
  vertexAiProjectId?: string;
  /** Vertex AI location (required for vertex_ai mode) */
  vertexAiLocation?: string;
  /** Vertex AI credentials JSON content (required for vertex_ai mode) */
  vertexAiCredentialsJson?: string;
  /** Hidden model IDs */
  hiddenModels?: string[];
  /** Saved model configurations (ModelConfig[]) */
  savedModels?: ModelConfig[];
}

/**
 * Connection test request
 */
export interface TestConnectionRequest {
  /** API mode to test */
  apiMode: ImagenAPIMode;
  /** Gemini API key */
  geminiApiKey?: string;
  /** Vertex AI project ID */
  vertexAiProjectId?: string;
  /** Vertex AI location */
  vertexAiLocation?: string;
  /** Vertex AI credentials JSON content */
  vertexAiCredentialsJson?: string;
}

/**
 * Connection test response
 */
export interface TestConnectionResponse {
  /** Whether the connection test succeeded */
  success: boolean;
  /** API mode that was tested */
  apiMode: string;
  /** Result message */
  message: string;
  /** Additional details (models, capabilities, etc.) */
  details?: {
    supportedModels?: string[];
    capabilities?: ImageGenerationCapabilities;
    projectId?: string;
    location?: string;
  };
}
