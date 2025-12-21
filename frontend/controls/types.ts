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
  onOpenDocuments?: () => void;
  googleCacheMode?: 'none' | 'exact' | 'semantic';
  setGoogleCacheMode?: (v: 'none' | 'exact' | 'semantic') => void;
}

export interface ImageGenControlsProps {
  providerId: string;
  style: string;
  setStyle: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}

export interface ImageEditControlsProps {
  providerId: string;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}


export interface OffsetPixels {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface ImageOutpaintControlsProps {
  outPaintingMode: 'scale' | 'offset';
  setOutPaintingMode: (v: 'scale' | 'offset') => void;
  scaleFactor: number;
  setScaleFactor: (v: number) => void;
  offsetPixels: OffsetPixels;
  setOffsetPixels: (v: React.SetStateAction<OffsetPixels>) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}

export interface VideoGenControlsProps {
  providerId: string;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
}

export interface AudioGenControlsProps {
  voice: string;
  setVoice: (v: string) => void;
}

export interface PdfExtractControlsProps {
  selectedTemplate: string;
  setSelectedTemplate: (v: string) => void;
  templates?: PdfExtractionTemplate[];
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}

export interface VirtualTryOnControlsProps {
  tryOnTarget: string;
  setTryOnTarget: (v: string) => void;
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
  tryOnTarget: string;
  setTryOnTarget: (v: string) => void;
}
