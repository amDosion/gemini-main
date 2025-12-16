
import React from 'react';
import { Message, AppMode, Attachment, ChatOptions, ModelConfig } from '../../../types';
import { ImageGenView } from './ImageGenView';
import { ImageEditView } from './ImageEditView';
import { ImageExpandView } from './ImageExpandView';
import { VideoGenView } from './VideoGenView';
import { AudioGenView } from './AudioGenView';
import { PdfExtractView } from './PdfExtractView';

interface StudioViewProps {
  messages: Message[];
  mode: AppMode; // 'image-gen' | 'image-edit' | 'video-gen' | 'image-outpainting'
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  onEditImage?: (url: string) => void;
  onExpandImage?: (url: string) => void; // Added prop
  providerId?: string;
  sessionId?: string | null;  // ✅ 会话 ID，用于查询附件
}

export const StudioView: React.FC<StudioViewProps> = (props) => {
  // Delegate to specific views based on mode
  switch (props.mode) {
      case 'image-gen':
          return <ImageGenView {...props} />;
      case 'image-edit':
          return <ImageEditView {...props} />;
      case 'image-outpainting':
          return <ImageExpandView {...props} />;
      case 'video-gen':
          return <VideoGenView {...props} />;
      case 'audio-gen':
          return <AudioGenView {...props} />;
      case 'pdf-extract':
          return <PdfExtractView {...props} />;
      default:
          return <ImageGenView {...props} />;
  }
};
