/**
 * 模式控制协调者（仅 Panel 模式）
 * 
 * 根据当前 mode 和 providerId 分发渲染对应的控制组件
 * 用于 View 组件右侧的参数面板
 * 
 * 架构说明：
 * - 控件注册表维护“通用实现 + provider 差异覆盖”
 * - 协调者按 providerId + mode 分发渲染
 * 
 * 使用方式：
 * <ModeControlsCoordinator 
 *   mode={mode} 
 *   providerId={providerId}
 *   controls={controls}
 *   currentModel={activeModelConfig}
 *   maxImageCount={4}
 * />
 */
import React from 'react';
import { AppMode, ModelConfig } from '../types/types';
import { ControlsState } from '../controls/types';
import { getProviderControls } from '../controls/modes/registry';
import {
  ChatControlsProps,
  ImageGenControlsProps,
  ImageEditControlsProps,
  ImageMaskEditControlsProps,
  ImageOutpaintControlsProps,
  VideoGenControlsProps,
  AudioGenControlsProps,
  VirtualTryOnControlsProps,
  PdfExtractControlsProps,
  MultiAgentControlsProps
} from '../controls/types';

type ModeControlsCoordinatorProps = {
  mode: AppMode;
  providerId: string;
  currentModel?: ModelConfig;
  availableModels?: ModelConfig[];
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  /** 最大图片数量（image-gen 模式） */
  maxImageCount?: number;
} & Partial<ChatControlsProps>
  & Partial<ImageGenControlsProps>
  & Partial<ImageEditControlsProps>
  & Partial<ImageMaskEditControlsProps>
  & Partial<ImageOutpaintControlsProps>
  & Partial<VideoGenControlsProps>
  & Partial<AudioGenControlsProps>
  & Partial<VirtualTryOnControlsProps>
  & Partial<PdfExtractControlsProps>
  & Partial<MultiAgentControlsProps>;

export const ModeControlsCoordinator: React.FC<ModeControlsCoordinatorProps> = (props) => {
  const { mode, providerId, currentModel, availableModels, controls, maxImageCount, ...controlProps } = props;

  // 获取当前提供商的控件集
  const Controls = getProviderControls(providerId);

  switch (mode) {
    case 'chat':
      return <Controls.ChatControls currentModel={currentModel} {...(controlProps as ChatControlsProps)} />;
    
    case 'image-gen':
      return (
        <Controls.ImageGenControls 
          providerId={providerId} 
          currentModel={currentModel} 
          controls={controls}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageGenControlsProps)} 
        />
      );
    
    // 图片编辑模式
    case 'image-chat-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
      return (
        <Controls.ImageEditControls
          providerId={providerId}
          controls={controls}
          availableModels={availableModels}
          maxImageCount={maxImageCount}
          {...(controlProps as ImageEditControlsProps)}
        />
      );
    
    // 掩码编辑模式（使用专门的 ImageMaskEditControls）
    case 'image-mask-edit':
      return (
        <Controls.ImageMaskEditControls 
          providerId={providerId} 
          controls={controls}
          {...(controlProps as ImageMaskEditControlsProps)} 
        />
      );
    
    case 'image-outpainting':
      return (
        <Controls.ImageOutpaintControls 
          providerId={providerId} 
          controls={controls}
          {...(controlProps as ImageOutpaintControlsProps)} 
        />
      );
    
    case 'video-gen':
      return (
        <Controls.VideoGenControls 
          providerId={providerId} 
          currentModel={currentModel}
          controls={controls}
          {...(controlProps as VideoGenControlsProps)} 
        />
      );
    
    case 'audio-gen':
      return (
        <Controls.AudioGenControls 
          providerId={providerId}
          controls={controls}
          {...(controlProps as AudioGenControlsProps)} 
        />
      );
    
    case 'pdf-extract':
      return <Controls.PdfExtractControls {...(controlProps as PdfExtractControlsProps)} />;
    
    case 'virtual-try-on':
      return (
        <Controls.VirtualTryOnControls 
          providerId={providerId}
          controls={controls}
          {...(controlProps as VirtualTryOnControlsProps)} 
        />
      );
    
    case 'multi-agent':
      return <Controls.MultiAgentControls currentModel={currentModel} {...(controlProps as MultiAgentControlsProps)} />;
    
    default:
      return null;
  }
};

export default ModeControlsCoordinator;
