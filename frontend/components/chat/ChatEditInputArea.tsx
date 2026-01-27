/**
 * Chat Edit 专用输入区域组件
 * 
 * 功能：
 * - 用于图片编辑模式（image-chat-edit）的输入区域
 * - 处理附件上传、预览、删除
 * - 处理提示词输入和发送逻辑
 * - 支持画布图片的连续性逻辑（activeImageUrl）
 * - 使用 AttachmentPreview 组件显示附件
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChatOptions, ModelConfig, Attachment, AppMode, Message } from '../../types/types';
import { Wand2, Image as ImageIcon, Paperclip, X } from 'lucide-react';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { AttachmentPreview } from './input/AttachmentPreview';
import { useControlsState } from '../../hooks/useControlsState';
import { useToastContext } from '../../contexts/ToastContext';

interface ChatEditInputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  currentModel?: ModelConfig;
  mode: AppMode; // 应该是 'image-chat-edit'
  // 附件相关
  activeAttachments?: Attachment[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
  activeImageUrl?: string | null; // 画布中的图片 URL（用于连续性逻辑）
  onActiveImageUrlChange?: (url: string | null) => void;
  // 消息和会话相关（用于 processUserAttachments）
  messages?: Message[];
  sessionId?: string | null;
  // 初始值
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  providerId?: string;
}

const ChatEditInputArea: React.FC<ChatEditInputAreaProps> = ({
  onSend,
  isLoading,
  onStop,
  currentModel,
  mode = 'image-chat-edit',
  activeAttachments: externalAttachments,
  onAttachmentsChange,
  activeImageUrl: externalActiveImageUrl,
  onActiveImageUrlChange,
  messages = [],
  sessionId = null,
  initialPrompt,
  initialAttachments,
  providerId = 'google',
}) => {
  const { showError } = useToastContext();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 本地状态
  const [localAttachments, setLocalAttachments] = useState<Attachment[]>([]);
  const [localActiveImageUrl, setLocalActiveImageUrl] = useState<string | null>(null);
  const [prompt, setPrompt] = useState(initialPrompt || '');

  // 受控/非受控模式处理
  const attachments = externalAttachments !== undefined ? externalAttachments : localAttachments;
  const activeImageUrl = externalActiveImageUrl !== undefined ? externalActiveImageUrl : localActiveImageUrl;

  const updateAttachments = useCallback((newAtts: Attachment[]) => {
    console.log('[ChatEditInputArea] updateAttachments 被调用:', {
      newAttachmentsCount: newAtts.length,
      hasCallback: !!onAttachmentsChange,
      attachments: newAtts.map(att => ({ id: att.id, name: att.name, hasFile: !!att.file })),
    });
    if (onAttachmentsChange) {
      console.log('[ChatEditInputArea] 调用 onAttachmentsChange 回调');
      onAttachmentsChange(newAtts);
    } else {
      console.log('[ChatEditInputArea] 使用本地状态 setLocalAttachments');
      setLocalAttachments(newAtts);
    }
  }, [onAttachmentsChange]);

  const updateActiveImageUrl = useCallback((url: string | null) => {
    if (onActiveImageUrlChange) {
      onActiveImageUrlChange(url);
    } else {
      setLocalActiveImageUrl(url);
    }
  }, [onActiveImageUrlChange]);

  // 使用统一的 controls 状态
  const controls = useControlsState(mode, currentModel);

  // 同步初始值
  useEffect(() => {
    if (initialPrompt) setPrompt(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
    if (initialAttachments !== undefined) {
      updateAttachments(initialAttachments);
      if (initialAttachments.length > 0) {
        const firstUrl = initialAttachments[0].url || initialAttachments[0].tempUrl || null;
        updateActiveImageUrl(firstUrl);
      }
    }
  }, [initialAttachments, updateAttachments, updateActiveImageUrl]);

  // 文件上传处理
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    const newAtt: Attachment = {
      id: `att-${Date.now()}`,
      name: file.name,
      mimeType: file.type,
      url: url,
      tempUrl: url,
      file: file,
    };

    console.log('[ChatEditInputArea] 文件上传:', {
      fileName: file.name,
      fileType: file.type,
      fileSize: file.size,
      attachmentId: newAtt.id,
      hasFile: !!newAtt.file,
      url: url.substring(0, 50) + '...',
    });

    // ✅ 只更新附件，让父组件的 useEffect 来处理 activeImageUrl
    // 这样可以利用 getStableCanvasUrlFromAttachment 创建稳定的 URL
    updateAttachments([newAtt]);
    console.log('[ChatEditInputArea] 已调用 updateAttachments，等待父组件同步');
    // 注意：不在这里直接设置 activeImageUrl，让 ImageEditView 的 useEffect 处理

    if (e.target) e.target.value = '';
  }, [updateAttachments]);

  // 删除附件
  const removeAttachment = useCallback((id: string) => {
    const attachmentToRemove = attachments.find(att => att.id === id);
    if (attachmentToRemove?.tempUrl) {
      URL.revokeObjectURL(attachmentToRemove.tempUrl);
    }

    const newAtts = attachments.filter(att => att.id !== id);
    updateAttachments(newAtts);

    // ✅ 如果删除后没有附件了，清空 activeImageUrl
    // 让父组件的 useEffect 来处理 activeImageUrl 的更新
    if (newAtts.length === 0) {
      updateActiveImageUrl(null);
    }
    // 注意：如果有剩余附件，父组件的 useEffect 会自动更新 activeImageUrl
  }, [attachments, updateAttachments, updateActiveImageUrl]);

  // 清理 Blob URLs
  useEffect(() => {
    return () => {
      attachments.forEach(att => {
        if (att.tempUrl && att.tempUrl.startsWith('blob:')) {
          URL.revokeObjectURL(att.tempUrl);
        }
      });
    };
  }, [attachments]);

  // 发送逻辑
  const handleGenerate = useCallback(async () => {
    // ✅ 逻辑：如果没有上传附件且画布也没有图片，则不允许发送
    if (!prompt.trim() || isLoading || (attachments.length === 0 && !activeImageUrl)) return;

    try {
      console.log('========== [ChatEditInputArea] handleGenerate 开始 ==========');
      console.log('[handleGenerate] 用户输入:', prompt);
      console.log('[handleGenerate] 当前附件数量:', attachments.length);
      console.log('[handleGenerate] 画布图片 URL:', activeImageUrl);

      // ✅ 逻辑修复：
      // 1. 如果用户上传了附件，使用上传的附件（优先，不传递 activeImageUrl）
      // 2. 如果没有上传附件，使用画布中的图片（CONTINUITY LOGIC，传递 activeImageUrl）
      // 3. processUserAttachments 会自动处理这个逻辑
      const finalAttachments = await processUserAttachments(
        attachments, // 如果有上传附件，这个数组不为空
        attachments.length > 0 ? null : activeImageUrl, // ✅ 有上传附件时不传递画布图片，没有上传时才传递
        messages,
        sessionId,
        'canvas'
      );

      // 构建 ChatOptions
      const options: ChatOptions = {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: controls.aspectRatio,
        imageResolution: controls.resolution,
        negativePrompt: controls.negativePrompt || undefined,
        seed: controls.seed !== -1 ? controls.seed : undefined,
        outputMimeType: controls.outputMimeType,
        outputCompressionQuality: controls.outputCompressionQuality,
      };

      console.log('[handleGenerate] 编辑参数:', options);
      console.log('[handleGenerate] 最终附件数量:', finalAttachments.length);
      console.log('========== [ChatEditInputArea] handleGenerate 结束 ==========');

      onSend(prompt, options, finalAttachments, mode);
      setPrompt(''); // 发送后清空提示词
      
      // ✅ 发送后清空附件预览
      if (attachments.length > 0) {
        console.log('[handleGenerate] 清空附件预览');
        updateAttachments([]);
      }
    } catch (error) {
      console.error('[ChatEditInputArea] handleGenerate 处理附件失败:', error);
      showError('处理附件失败，请重试');
    }
  }, [prompt, isLoading, attachments, activeImageUrl, messages, sessionId, controls, onSend, mode, showError, updateAttachments]);

  // 键盘快捷键
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  }, [handleGenerate]);

  const isDisabled = !prompt.trim() || isLoading || (attachments.length === 0 && !activeImageUrl);

  return (
    <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
      {/* 附件预览 - 使用 AttachmentPreview 组件 */}
      <AttachmentPreview
        attachments={attachments}
        removeAttachment={removeAttachment}
      />

      {/* 提示词输入 */}
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => {
          setPrompt(e.target.value);
          e.target.style.height = 'auto';
          e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
        }}
        onKeyDown={handleKeyDown}
        placeholder={(attachments.length === 0 && !activeImageUrl) ? "请先上传图片..." : "描述你要对图片做的编辑..."}
        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
      />

      {/* 上传按钮 + 编辑按钮 */}
      <div className="flex gap-2 items-center">
        {/* 上传按钮 */}
        <label className="p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg">
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileSelect}
          />
          {attachments.length === 0 ? (
            <ImageIcon size={18} className="text-white" />
          ) : (
            <Paperclip size={18} className="text-white" />
          )}
        </label>

        {/* 编辑按钮 */}
        <button
          onClick={handleGenerate}
          disabled={isDisabled}
          className="flex-1 py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              编辑中...
            </>
          ) : (
            <>
              <Wand2 size={18} />
              {(attachments.length === 0 && !activeImageUrl) ? '请先上传图片' : '开始编辑'}
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default ChatEditInputArea;
