
import React, { lazy, Suspense } from 'react';
import { Message, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { LoadingSpinner } from '../common/LoadingSpinner';

// ✅ 懒加载所有 Studio 子视图
const ImageGenView = lazy(() => import('./ImageGenView').then(m => ({ default: m.ImageGenView })));
const ImageEditView = lazy(() => import('./ImageEditView').then(m => ({ default: m.ImageEditView })));
const ImageMaskEditView = lazy(() => import('./ImageMaskEditView').then(m => ({ default: m.ImageMaskEditView })));
const ImageInpaintingView = lazy(() => import('./ImageInpaintingView').then(m => ({ default: m.ImageInpaintingView })));
const ImageBackgroundEditView = lazy(() => import('./ImageBackgroundEditView').then(m => ({ default: m.ImageBackgroundEditView })));
const ImageRecontextView = lazy(() => import('./ImageRecontextView').then(m => ({ default: m.ImageRecontextView })));
const ImageExpandView = lazy(() => import('./ImageExpandView').then(m => ({ default: m.ImageExpandView })));
const VideoGenView = lazy(() => import('./VideoGenView').then(m => ({ default: m.VideoGenView })));
const AudioGenView = lazy(() => import('./AudioGenView').then(m => ({ default: m.AudioGenView })));
const PdfExtractView = lazy(() => import('./PdfExtractView').then(m => ({ default: m.PdfExtractView })));
const VirtualTryOnView = lazy(() => import('./VirtualTryOnView').then(m => ({ default: m.VirtualTryOnView })));

interface StudioViewProps {
  messages: Message[];
  mode: AppMode; // 'image-gen' | 'image-edit' | 'video-gen' | 'image-outpainting'
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[];  // 当前模式下可见的模型列表
  allVisibleModels?: ModelConfig[];  // ✅ 新增：完整模型列表（不按模式过滤），用于 ModeSelector 判断模式可用性
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  onEditImage?: (url: string) => void;
  onExpandImage?: (url: string) => void; // Added prop
  providerId?: string;
  sessionId?: string | null;  // ✅ 会话 ID，用于查询附件
  onDeleteMessage?: (messageId: string) => void;  // ✅ 删除消息回调
  apiKey?: string;  // ✅ API Key，用于调用 API
}

export const StudioView: React.FC<StudioViewProps> = React.memo((props) => {
  // Delegate to specific views based on mode
  const renderView = () => {
    switch (props.mode) {
        case 'image-gen':
            return <ImageGenView {...props} />;
        // 图片编辑模式（已拆分为多个独立模式，每个模式有独立的视图组件）
        case 'image-chat-edit':
            return <ImageEditView {...props} />;
        case 'image-mask-edit':
            return <ImageMaskEditView {...props} />;
        case 'image-inpainting':
            return <ImageInpaintingView {...props} />;
        case 'image-background-edit':
            return <ImageBackgroundEditView {...props} />;
        case 'image-recontext':
            return <ImageRecontextView {...props} />;
        case 'image-outpainting':
            return <ImageExpandView {...props} />;
        case 'video-gen':
            return <VideoGenView {...props} />;
        case 'audio-gen':
            return <AudioGenView {...props} />;
        case 'pdf-extract':
            return <PdfExtractView {...props} />;
        case 'virtual-try-on':
            return <VirtualTryOnView {...props} />;
        default:
            return <ImageGenView {...props} />;
    }
  };

  return (
    <Suspense fallback={<LoadingSpinner />}>
      {renderView()}
    </Suspense>
  );
});
