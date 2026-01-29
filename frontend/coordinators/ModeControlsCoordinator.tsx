/**
 * 模式控制协调者（仅 Panel 模式）
 * 
 * 根据当前 mode 和 providerId 分发渲染对应的控制组件
 * 用于 View 组件右侧的参数面板
 * 
 * 架构说明：
 * - 按提供商加载对应的控件集（Google、TongYi、OpenAI）
 * - 每个提供商有完整的控件导出（专有实现 + 占位）
 * - 占位文件 re-export Google 主实现
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
import * as GoogleControls from '../controls/modes/google';
import * as TongYiControls from '../controls/modes/tongyi';
import * as OpenAIControls from '../controls/modes/openai';
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
  DeepResearchControlsProps,
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
  & Partial<DeepResearchControlsProps>
  & Partial<MultiAgentControlsProps>;

/**
 * 获取对应提供商的控件集
 */
const getProviderControls = (providerId: string) => {
  switch (providerId) {
    case 'tongyi':
      return TongYiControls;
    case 'openai':
      return OpenAIControls;
    case 'google':
    case 'google-custom':
    default:
      return GoogleControls;
  }
};

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
      // 类型断言：所有提供商都通过占位导出提供了 ImageMaskEditControls
      if ('ImageMaskEditControls' in Controls) {
        const MaskEditControls = (Controls as any).ImageMaskEditControls as React.ComponentType<ImageMaskEditControlsProps>;
        return (
          <MaskEditControls 
            providerId={providerId} 
            controls={controls}
            {...(controlProps as ImageMaskEditControlsProps)} 
          />
        );
      }
      // Fallback（不应该到达这里）
      {
        const FallbackEditControls = (Controls as any).ImageEditControls as React.ComponentType<ImageEditControlsProps>;
        return (
          <FallbackEditControls
            providerId={providerId}
            controls={controls}
            {...(controlProps as ImageEditControlsProps)}
          />
        );
      }
    
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
          controls={controls}
          {...(controlProps as VideoGenControlsProps)} 
        />
      );
    
    case 'audio-gen':
      return (
        <Controls.AudioGenControls 
          controls={controls}
          {...(controlProps as AudioGenControlsProps)} 
        />
      );
    
    case 'pdf-extract':
      return <Controls.PdfExtractControls {...(controlProps as PdfExtractControlsProps)} />;
    
    case 'virtual-try-on':
      return (
        <Controls.VirtualTryOnControls 
          controls={controls}
          {...(controlProps as VirtualTryOnControlsProps)} 
        />
      );
    
    case 'deep-research':
      return <Controls.DeepResearchControls currentModel={currentModel} {...(controlProps as DeepResearchControlsProps)} />;
    
    case 'multi-agent':
      return <Controls.MultiAgentControls currentModel={currentModel} {...(controlProps as MultiAgentControlsProps)} />;
    
    default:
      return null;
  }
};

export default ModeControlsCoordinator;
