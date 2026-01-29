/**
 * Controls 模式参数控制类型定义
 */
import { ReactNode } from 'react';
import { AppMode, ModelConfig, LoraConfig, PdfExtractionTemplate } from '../types/types';

// ============================================
// Shared Component Props
// ============================================

export interface ToggleButtonProps {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  activeColor?: string;
  title?: string;
}

export interface DropdownSelectorProps<T = string> {
  value: T;
  onChange: (v: T) => void;
  options: { label: string; value: T }[];
  icon?: ReactNode;
  iconColor?: string;
  placeholder?: string;
  className?: string;
}

export interface SliderControlProps {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
  formatValue?: (v: number) => string;
}

export interface AdvancedToggleProps {
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  title?: string;
}


// ============================================
// Mode Control Component Props
// ============================================

export interface ChatControlsProps {
  currentModel?: ModelConfig;
  enableSearch: boolean;
  setEnableSearch: (v: boolean) => void;
  enableThinking: boolean;
  setEnableThinking: (v: boolean) => void;
  enableCodeExecution: boolean;
  setEnableCodeExecution: (v: boolean) => void;
  enableUrlContext: boolean;
  setEnableUrlContext: (v: boolean) => void;
  enableBrowser?: boolean;
  setEnableBrowser?: (v: boolean) => void;
  enableRAG?: boolean;
  setEnableRAG?: (v: boolean) => void;
  enableResearch: boolean;
  setEnableResearch: (v: boolean) => void;
  onOpenDocuments?: () => void;
  googleCacheMode?: 'none' | 'exact' | 'semantic';
  setGoogleCacheMode?: (v: 'none' | 'exact' | 'semantic') => void;
}

export interface ImageGenControlsProps {
  providerId: string;
  currentModel?: ModelConfig;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  /** 最大图片生成数量 */
  maxImageCount?: number;
  // 单独 props（向后兼容）
  style?: string;
  setStyle?: (v: string) => void;
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  aspectRatio?: string;
  setAspectRatio?: (v: string) => void;
  resolution?: string;
  setResolution?: (v: string) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
  // Imagen advanced parameters
  negativePrompt?: string;
  setNegativePrompt?: (v: string) => void;
  seed?: number;
  setSeed?: (v: number) => void;
  outputMimeType?: string;
  setOutputMimeType?: (v: string) => void;
  outputCompressionQuality?: number;
  setOutputCompressionQuality?: (v: number) => void;
  enhancePrompt?: boolean;
  setEnhancePrompt?: (v: boolean) => void;
}

export interface ImageEditControlsProps {
  providerId: string;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  /** 可用模型列表（用于增强提示词模型选择） */
  availableModels?: ModelConfig[];
  /** 最大图片生成数量 */
  maxImageCount?: number;
  // 单独 props（向后兼容）
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  aspectRatio?: string;
  setAspectRatio?: (v: string) => void;
  resolution?: string;
  setResolution?: (v: string) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
}

export interface ImageMaskEditControlsProps {
  providerId: string;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  editMode?: string;
  setEditMode?: (v: string) => void;
  maskDilation?: number;
  setMaskDilation?: (v: number) => void;
  guidanceScale?: number;
  setGuidanceScale?: (v: number) => void;
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  negativePrompt?: string;
  setNegativePrompt?: (v: string) => void;
  outputMimeType?: string;
  setOutputMimeType?: (v: string) => void;
  outputCompressionQuality?: number;
  setOutputCompressionQuality?: (v: number) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
}


export interface OffsetPixels {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface ImageOutpaintControlsProps {
  providerId?: string;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  outPaintingMode?: 'scale' | 'offset';
  setOutPaintingMode?: (v: 'scale' | 'offset') => void;
  scaleFactor?: number;
  setScaleFactor?: (v: number) => void;
  offsetPixels?: OffsetPixels;
  setOffsetPixels?: (v: React.SetStateAction<OffsetPixels>) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
}

export interface VideoGenControlsProps {
  providerId: string;
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  aspectRatio?: string;
  setAspectRatio?: (v: string) => void;
  resolution?: string;
  setResolution?: (v: string) => void;
}

export interface AudioGenControlsProps {
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  voice?: string;
  setVoice?: (v: string) => void;
}

export interface PdfExtractControlsProps {
  selectedTemplate: string;
  setSelectedTemplate: (v: string) => void;
  templates?: PdfExtractionTemplate[];
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}

export interface VirtualTryOnControlsProps {
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  baseSteps?: number;
  setBaseSteps?: (v: number) => void;
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  // output_mime_type 和 output_compression_quality 使用固定默认值（image/jpeg, 100）
  // 不提供 UI 设置，但在 ChatOptions 中传递给后端
}

export interface DeepResearchControlsProps {
  currentModel?: ModelConfig;
  thinkingSummaries: 'auto' | 'none';
  setThinkingSummaries: (v: 'auto' | 'none') => void;
  researchMode?: 'vertex-ai' | 'gemini-api';
  setResearchMode?: (v: 'vertex-ai' | 'gemini-api') => void;
}

export interface MultiAgentControlsProps {
  // Multi-Agent 模式目前主要在工作流编辑器中配置
  // 这里可以添加一些全局设置，如默认节点配置等
  currentModel?: ModelConfig;
  enableMultiAgent?: boolean;
  setEnableMultiAgent?: (v: boolean) => void;
}


// ============================================
// Coordinator Props
// ============================================

export interface ModeControlsCoordinatorProps {
  mode: AppMode;
  providerId: string;
  currentModel?: ModelConfig;
  [key: string]: any;
}

// ============================================
// Controls State (for useControlsState hook)
// ============================================

export interface ControlsState {
  // Chat Controls
  enableSearch: boolean;
  setEnableSearch: (v: boolean) => void;
  enableThinking: boolean;
  setEnableThinking: (v: boolean) => void;
  enableCodeExecution: boolean;
  setEnableCodeExecution: (v: boolean) => void;
  enableUrlContext: boolean;
  setEnableUrlContext: (v: boolean) => void;
  enableBrowser: boolean;
  setEnableBrowser: (v: boolean) => void;
  enableRAG: boolean;
  setEnableRAG: (v: boolean) => void;
  enableResearch: boolean;
  setEnableResearch: (v: boolean) => void;
  googleCacheMode: 'none' | 'exact' | 'semantic';
  setGoogleCacheMode: (v: 'none' | 'exact' | 'semantic') => void;

  // Generation Controls
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  style: string;
  setStyle: (v: string) => void;

  // Advanced Settings
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  negativePrompt: string;
  setNegativePrompt: (v: string) => void;
  seed: number;
  setSeed: (v: number) => void;
  loraConfig: LoraConfig;
  setLoraConfig: (v: LoraConfig) => void;

  // Imagen advanced parameters
  // guidanceScale removed - not officially documented by Google Imagen
  // personGeneration removed - API uses default (allow_adult)
  outputMimeType: string;
  setOutputMimeType: (v: string) => void;
  outputCompressionQuality: number;
  setOutputCompressionQuality: (v: number) => void;
  enhancePrompt: boolean;
  setEnhancePrompt: (v: boolean) => void;
  enhancePromptModel: string;
  setEnhancePromptModel: (v: string) => void;

  // TongYi Specific Parameters
  promptExtend: boolean;
  setPromptExtend: (v: boolean) => void;
  addMagicSuffix: boolean;
  setAddMagicSuffix: (v: boolean) => void;

  // Out-Painting
  outPaintingMode: 'scale' | 'offset';
  setOutPaintingMode: (v: 'scale' | 'offset') => void;
  scaleFactor: number;
  setScaleFactor: (v: number) => void;
  offsetPixels: OffsetPixels;
  setOffsetPixels: (v: React.SetStateAction<OffsetPixels>) => void;

  // Audio
  voice: string;
  setVoice: (v: string) => void;

  // PDF
  pdfTemplate: string;
  setPdfTemplate: (v: string) => void;
  pdfAdditionalInstructions: string;
  setPdfAdditionalInstructions: (v: string) => void;

  // Virtual Try-On
  baseSteps: number;
  setBaseSteps: (v: number) => void;
  // output_mime_type 和 output_compression_quality 使用固定默认值（image/jpeg, 100）

  // Deep Research Controls
  thinkingSummaries: 'auto' | 'none';
  setThinkingSummaries: (v: 'auto' | 'none') => void;
  researchMode: 'vertex-ai' | 'gemini-api';
  setResearchMode: (v: 'vertex-ai' | 'gemini-api') => void;
  
  // Multi-Agent Controls (保留用于向后兼容，但主要在工作流编辑器中管理)
  enableMultiAgent: boolean;
  setEnableMultiAgent: (v: boolean) => void;

  // Mask Edit Controls (仅用于 image-mask-edit 模式)
  editMode: string;
  setEditMode: (v: string) => void;
  maskDilation: number;
  setMaskDilation: (v: number) => void;
  guidanceScale: number;
  setGuidanceScale: (v: number) => void;
}
