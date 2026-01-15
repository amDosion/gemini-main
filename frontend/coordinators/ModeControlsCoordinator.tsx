import React from 'react';
import { AppMode, ModelConfig } from '../types/types';
import {
  ChatControls,
  ImageGenControls,
  ImageEditControls,
  ImageOutpaintControls,
  VideoGenControls,
  AudioGenControls,
  VirtualTryOnControls,
  PdfExtractControls,
  DeepResearchControls,
  MultiAgentControls
} from '../controls/modes';
import {
  ChatControlsProps,
  ImageGenControlsProps,
  ImageEditControlsProps,
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
} & Partial<ChatControlsProps>
  & Partial<ImageGenControlsProps>
  & Partial<ImageEditControlsProps>
  & Partial<ImageOutpaintControlsProps>
  & Partial<VideoGenControlsProps>
  & Partial<AudioGenControlsProps>
  & Partial<VirtualTryOnControlsProps>
  & Partial<PdfExtractControlsProps>
  & Partial<DeepResearchControlsProps>
  & Partial<MultiAgentControlsProps>;

/**
 * 模式控制协调者
 * 根据当前 mode 分发渲染对应的控制组件
 */
export const ModeControlsCoordinator: React.FC<ModeControlsCoordinatorProps> = (props) => {
  const { mode, providerId, currentModel, ...controlProps } = props;

  switch (mode) {
    case 'chat':
      return <ChatControls currentModel={currentModel} {...(controlProps as ChatControlsProps)} />;
    case 'image-gen':
      return <ImageGenControls providerId={providerId} currentModel={currentModel} {...(controlProps as ImageGenControlsProps)} />;
    // 图片编辑模式（已拆分为多个独立模式，都使用 ImageEditControls）
    case 'image-chat-edit':
    case 'image-mask-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
      return <ImageEditControls providerId={providerId} {...(controlProps as ImageEditControlsProps)} />;
    case 'image-outpainting':
      return <ImageOutpaintControls {...(controlProps as ImageOutpaintControlsProps)} />;
    case 'video-gen':
      return <VideoGenControls providerId={providerId} {...(controlProps as VideoGenControlsProps)} />;
    case 'audio-gen':
      return <AudioGenControls {...(controlProps as AudioGenControlsProps)} />;
    case 'pdf-extract':
      return <PdfExtractControls {...(controlProps as PdfExtractControlsProps)} />;
    case 'virtual-try-on':
      return <VirtualTryOnControls {...(controlProps as VirtualTryOnControlsProps)} />;
    case 'deep-research':
      return <DeepResearchControls currentModel={currentModel} {...(controlProps as DeepResearchControlsProps)} />;
    case 'multi-agent':
      return <MultiAgentControls currentModel={currentModel} {...(controlProps as MultiAgentControlsProps)} />;
    default:
      return null;
  }
};

export default ModeControlsCoordinator;
