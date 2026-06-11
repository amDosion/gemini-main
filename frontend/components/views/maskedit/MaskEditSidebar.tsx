/**
 * ImageMaskEditView 侧边栏（消息列表 + thinking 状态）。
 *
 * 1:1 抽离自 `ImageMaskEditView.tsx` L861-986 sidebarContent useMemo body。
 */

import React from 'react';
import { AlertCircle, Bot, Crop, Layers, Sparkles, User } from 'lucide-react';
import { Attachment, Message, Role, ModelConfig } from '../../../types/types';
import { ThinkingBlock } from '../../message/ThinkingBlock';
import { CachedImage } from '../../common/CachedImage';
import { getPreferredImageAttachmentUrl } from '../../../utils/attachmentUrl';
import { getImageHistoryAttachmentPreviewUrl } from '../../common/imageHistorySidebarHelpers';

export interface MaskEditSidebarProps {
  scrollRef: React.RefObject<HTMLDivElement | null>;
  messages: Message[];
  activeModelConfig?: ModelConfig;
  loadingState: string;
  activeImageUrl: string | null;
  setActiveImageUrl: React.Dispatch<React.SetStateAction<string | null>>;
  setActiveAttachments: React.Dispatch<React.SetStateAction<Attachment[]>>;
  displayedThinkingContent: string;
  isThinkingOpen: boolean;
  setIsThinkingOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

export const MaskEditSidebar: React.FC<MaskEditSidebarProps> = ({
  scrollRef,
  messages,
  activeModelConfig,
  loadingState,
  activeImageUrl,
  setActiveImageUrl,
  setActiveAttachments,
  displayedThinkingContent,
  isThinkingOpen,
  setIsThinkingOpen,
}) => {
  return (
    <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
      {messages.map((msg) => {
        const isPlaceholder =
          !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
        if (isPlaceholder) return null;

        return (
          <div
            key={msg.id}
            className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
              {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
              <span>{msg.role === Role.USER ? 'You' : activeModelConfig?.name || 'AI'}</span>
            </div>
            <div
              className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${
                msg.role === Role.USER
                  ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                  : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
              }`}
            >
              {msg.content && <p className="mb-2">{msg.content}</p>}
              {msg.attachments?.map((att, idx) => {
                const previewId = att.id || `${msg.id}-${idx}`;
                const sourceAttachment = att.id ? att : { ...att, id: previewId };
                const imageUrl = getImageHistoryAttachmentPreviewUrl(
                  sourceAttachment,
                  previewId,
                  getPreferredImageAttachmentUrl(sourceAttachment)
                );
                if (!imageUrl) return null;
                return (
                  <div
                    key={idx}
                    onClick={() => {
                      setActiveAttachments([sourceAttachment]);
                      setActiveImageUrl(imageUrl);
                    }}
                    className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${
                      activeImageUrl === imageUrl
                        ? 'ring-2 ring-purple-500 border-transparent'
                        : 'border-slate-700 hover:border-slate-500'
                    }`}
                  >
                    <CachedImage
                      source={{
                        ...sourceAttachment,
                        attachmentId: previewId,
                        url: imageUrl,
                      }}
                      src={imageUrl}
                      className="w-full h-32 object-cover bg-slate-900"
                      alt="thumbnail"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                      {activeImageUrl === imageUrl && (
                        <div className="bg-purple-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />
                      )}
                    </div>
                  </div>
                );
              })}
              {msg.isError && (
                <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                  <AlertCircle size={12} /> Error generating
                </div>
              )}
            </div>
          </div>
        );
      })}
      {loadingState !== 'idle' &&
        (() => {
          let statusText = 'Processing request...';
          let statusIcon = <Bot size={16} className="text-slate-500" />;

          if (loadingState === 'uploading') {
            statusText = '上传图片中...';
            statusIcon = <Layers size={16} className="text-blue-400" />;
          } else if (loadingState === 'loading') {
            statusText = 'Mask 编辑中，正在处理遮罩区域...';
            statusIcon = <Crop size={16} className="text-purple-400" />;
          } else if (loadingState === 'streaming') {
            statusText = '流式处理中...';
            statusIcon = <Sparkles size={16} className="text-purple-400 animate-pulse" />;
          }

          const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
          const thoughts = lastMessage?.thoughts || [];
          const textResponse = lastMessage?.textResponse;
          const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;

          return (
            <div className="flex items-start gap-2">
              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                {statusIcon}
              </div>
              <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
                <div className="font-medium mb-1 animate-pulse">{statusText}</div>

                {displayedThinkingContent && (
                  <div className="mt-2">
                    {/* 该块仅在 loadingState !== 'idle' 时渲染，thinking 必然未完成 */}
                    <ThinkingBlock
                      content={displayedThinkingContent}
                      isOpen={isThinkingOpen}
                      onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                      isComplete={false}
                    />
                  </div>
                )}

                {hasTextContent && !thoughts.length && !textResponse && (
                  <div className="mt-2 pt-2 border-t border-slate-700/50 text-slate-500 italic">
                    {lastMessage.content.substring(0, 100)}
                    {lastMessage.content.length > 100 ? '...' : ''}
                  </div>
                )}
              </div>
            </div>
          );
        })()}
      <div />
    </div>
  );
};
