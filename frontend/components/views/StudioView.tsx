import React, { lazy, Suspense, useRef, useMemo, useCallback } from 'react';
import { Message, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { useViewMessages } from '../../hooks/useViewMessages';

// Lazy load all Studio sub-views
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

// Mode to component mapping
const MODE_COMPONENTS: Record<string, React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>> = {
  'image-gen': ImageGenView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-chat-edit': ImageEditView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-mask-edit': ImageMaskEditView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-inpainting': ImageInpaintingView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-background-edit': ImageBackgroundEditView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-recontext': ImageRecontextView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'image-outpainting': ImageExpandView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'video-gen': VideoGenView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'audio-gen': AudioGenView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'pdf-extract': PdfExtractView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
  'virtual-try-on': VirtualTryOnView as React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>,
};

interface StudioViewProps {
  messages: Message[];
  mode: AppMode;
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[];
  allVisibleModels?: ModelConfig[];
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  onEditImage?: (url: string, attachment?: Attachment) => void;
  onExpandImage?: (url: string, attachment?: Attachment) => void;
  providerId?: string;
  sessionId?: string | null;
  onDeleteMessage?: (messageId: string) => void;
  apiKey?: string;
  onSubmitResearchAction?: (interactionId: string, action: Record<string, unknown>) => void;
  personas?: unknown[];
  activePersonaId?: string;
  onSelectPersona?: (id: string) => void;
}

/**
 * StudioView - Keep-Alive architecture
 * 
 * Instead of switch(mode) which destroys/recreates components on every mode change,
 * this renders all visited modes simultaneously and controls visibility via CSS.
 * 
 * Benefits:
 * - Zero re-requests on mode switch (hooks don't re-execute)
 * - State preserved (canvas zoom, scroll position, form inputs)
 * - Instant mode switching (CSS display toggle)
 * 
 * Memory optimization:
 * - Only visited modes are mounted (lazy mount on first visit)
 * - Unvisited modes cost zero memory
 */
export const StudioView: React.FC<StudioViewProps> = React.memo((props) => {
  const { mode: currentMode, messages, ...restProps } = props;

  // Track which modes have been visited (once mounted, stay alive)
  const mountedModesRef = useRef<Set<string>>(new Set());

  // Always add current mode
  mountedModesRef.current.add(currentMode);

  // Get the set of mounted modes for rendering
  const mountedModes = Array.from(mountedModesRef.current);

  return (
    <>
      {mountedModes.map((mode) => {
        const Component = MODE_COMPONENTS[mode];
        if (!Component) return null;

        const isActive = mode === currentMode;

        return (
          <div
            key={mode}
            style={{
              display: isActive ? 'contents' : 'none',
            }}
          >
            <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
              <KeepAliveViewWrapper
                Component={Component}
                mode={mode as AppMode}
                isActive={isActive}
                messages={messages}
                {...restProps}
              />
            </Suspense>
          </div>
        );
      })}
    </>
  );
});

/**
 * Wrapper that provides mode-specific messages and memoized props
 * to prevent unnecessary re-renders of hidden views
 */
const KeepAliveViewWrapper: React.FC<{
  Component: React.LazyExoticComponent<React.ComponentType<Record<string, unknown>>>;
  mode: AppMode;
  isActive: boolean;
  messages: Message[];
  [key: string]: unknown;
}> = React.memo(({ Component, mode, isActive, messages, ...props }) => {
  // Each view gets its own filtered messages
  const viewMessages = useViewMessages(messages, mode);

  return (
    <Component
      {...props}
      messages={viewMessages}
      mode={mode}
    />
  );
}, (prevProps, nextProps) => {
  // Custom comparison: skip re-render for hidden views unless messages changed
  if (!nextProps.isActive && !prevProps.isActive) {
    // Both hidden - skip re-render entirely
    return true;
  }
  // Active or becoming active - let React decide
  return false;
});
