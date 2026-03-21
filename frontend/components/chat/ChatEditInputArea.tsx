/**
 * Chat Edit 专用输入区域组件
 * 
 * 功能：
 * - 用于图片编辑、扩图、修复、视频生成、音频生成等模式的输入区域
 * - 处理附件上传、预览、删除
 * - 处理提示词输入和发送逻辑
 * - 支持画布图片的连续性逻辑（activeImageUrl）
 * - 使用 AttachmentPreview 组件显示附件
 * - 根据模式显示不同的按钮文本和图标
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ChatOptions, Attachment, AppMode, Message } from '../../types/types';
import { Wand2, Image as ImageIcon, Paperclip, X, Expand, Crop, Sparkles, Send, Mic } from 'lucide-react';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { AttachmentPreview } from './input/AttachmentPreview';
import { ControlsState } from '../../controls/types';
import { useToastContext } from '../../contexts/ToastContext';

interface ChatEditInputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  mode: AppMode; // 支持多种模式：image-chat-edit, image-outpainting, image-inpainting, video-gen, audio-gen 等
  // 附件相关（必需，由父组件统一管理）
  activeAttachments: Attachment[];
  onAttachmentsChange: (attachments: Attachment[]) => void;
  activeImageUrl: string | null; // 画布中的图片 URL（用于连续性逻辑）
  onActiveImageUrlChange: (url: string | null) => void;
  // ✅ 新增：画布图片对应的完整附件对象（包含元数据）
  activeCanvasAttachment?: Attachment | null;
  // 消息和会话相关（用于 processUserAttachments）
  messages: Message[];
  sessionId: string | null;
  // 初始值
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  providerId?: string;
  /** controls 状态（由父 View 通过 useControlsState 创建，与参数面板共享同一实例） */
  controls: ControlsState;
  // 可选：自定义按钮文本和图标（如果不提供，会根据 mode 自动选择）
  buttonText?: string;
  buttonIcon?: React.ReactNode;
  loadingText?: string;
  placeholder?: string;
  // ✅ 多附件支持
  maxAttachments?: number; // 最大附件数量，默认 10
  externalDisabled?: boolean;
  externalDisabledReason?: string | null;
}

// 根据模式获取按钮文本和图标
const getModeButtonConfig = (mode: AppMode, hasAttachmentsOrImage: boolean) => {
  const configs: Partial<Record<AppMode, { 
    text: string; 
    loadingText: string; 
    icon: React.ReactNode;
    placeholder: string;
  }>> = {
    'image-chat-edit': {
      text: hasAttachmentsOrImage ? '开始编辑' : '请先上传图片',
      loadingText: '编辑中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述你要对图片做的编辑...' : '请先上传图片...',
    },
    'image-outpainting': {
      text: hasAttachmentsOrImage ? '开始扩图' : '请先上传图片',
      loadingText: '扩图中...',
      icon: <Expand size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述扩展内容...' : '请先上传图片...',
    },
    'image-inpainting': {
      text: hasAttachmentsOrImage ? '开始修复' : '请先上传图片',
      loadingText: '修复中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述需要修复的区域...' : '请先上传图片...',
    },
    'image-mask-edit': {
      text: hasAttachmentsOrImage ? '开始 Mask 编辑' : '请先上传图片',
      loadingText: '编辑中...',
      icon: <Crop size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述遮罩区域的编辑...' : '请先上传图片...',
    },
    'image-recontext': {
      text: hasAttachmentsOrImage ? '重新上下文' : '请先上传图片',
      loadingText: '处理中...',
      icon: <Sparkles size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述新的上下文环境...' : '请先上传图片...',
    },
    'image-background-edit': {
      text: hasAttachmentsOrImage ? '替换背景' : '请先上传图片',
      loadingText: '处理中...',
      icon: <Wand2 size={18} />,
      placeholder: hasAttachmentsOrImage ? '描述新的背景...' : '请先上传图片...',
    },
    'video-gen': {
      text: '生成视频',
      loadingText: '生成中...',
      icon: <Send size={18} />,
      placeholder: '描述你想生成的视频；可上传一张或多张图片，或上传视频作为参考...',
    },
    'audio-gen': {
      text: '生成语音',
      loadingText: '生成中...',
      icon: <Mic size={18} />,
      placeholder: '输入要转换为语音的文本...',
    },
  };

  return configs[mode] || configs['image-chat-edit'] || {
    text: hasAttachmentsOrImage ? '开始操作' : '请先上传图片',
    loadingText: '处理中...',
    icon: <Wand2 size={18} />,
    placeholder: hasAttachmentsOrImage ? '描述操作内容...' : '请先上传图片...',
  };
};

const ChatEditInputArea: React.FC<ChatEditInputAreaProps> = ({
  onSend,
  isLoading,
  onStop,
  mode = 'image-chat-edit',
  activeAttachments,
  onAttachmentsChange,
  activeImageUrl,
  onActiveImageUrlChange,
  activeCanvasAttachment, // ✅ 新增：画布图片对应的完整附件对象
  messages,
  sessionId,
  initialPrompt,
  initialAttachments,
  providerId = 'google',
  controls,
  buttonText,
  buttonIcon,
  loadingText,
  placeholder,
  maxAttachments = 10, // ✅ 默认最多 10 张图片
  externalDisabled = false,
  externalDisabledReason = null,
}) => {
  const { showError } = useToastContext();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const attachmentLimit = maxAttachments;
  const requiresAttachmentForMode = !['video-gen', 'audio-gen'].includes(mode);
  const requiresPromptForMode = mode !== 'image-outpainting';

  // 提示词状态（仅此组件内部管理）
  const [prompt, setPrompt] = useState(initialPrompt || '');

  // 同步初始值
  useEffect(() => {
    if (initialPrompt) setPrompt(initialPrompt);
  }, [initialPrompt]);

  // 同步初始附件（仅在组件挂载时执行一次）
  useEffect(() => {
    if (initialAttachments !== undefined && initialAttachments.length > 0) {
      onAttachmentsChange(initialAttachments);
      const firstUrl = initialAttachments[0].url || initialAttachments[0].tempUrl || null;
      onActiveImageUrlChange(firstUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在挂载时执行一次

  // 文件上传处理（✅ 支持多文件选择）
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    // 计算还能添加多少个附件
    const remainingSlots = attachmentLimit - activeAttachments.length;
    if (remainingSlots <= 0) {
      showError(`最多只能上传 ${attachmentLimit} 个参考文件`);
      if (e.target) e.target.value = '';
      return;
    }

    // 只取允许数量的文件
    const filesToAdd = Array.from(files).slice(0, remainingSlots);

    // 创建新附件数组
    const newAttachments: Attachment[] = filesToAdd.map((file, index) => {
      const url = URL.createObjectURL(file);
      return {
        id: `att-${Date.now()}-${index}`,
        name: file.name,
        mimeType: file.type,
        url: url,
        tempUrl: url,
        file: file,
      };
    });

    // ✅ 追加到现有附件（而不是替换）
    onAttachmentsChange([...activeAttachments, ...newAttachments]);

    // 提示用户如果有文件被忽略
    if (files.length > remainingSlots) {
      showError(`已添加 ${remainingSlots} 个参考文件，超出部分已忽略（最多 ${attachmentLimit} 个）`);
    }

    if (e.target) e.target.value = '';
  }, [activeAttachments, attachmentLimit, onAttachmentsChange, showError]);

  // 删除附件
  const removeAttachment = useCallback((id: string) => {
    const attachmentToRemove = activeAttachments.find(att => att.id === id);
    // ✅ 注意：不在这里 revoke Blob URL
    // 原因：如果附件已经发送到消息中，消息可能仍在使用这个 Blob URL
    // 只有在确认附件不再被使用时才 revoke（例如消息被删除时）

    const newAtts = activeAttachments.filter(att => att.id !== id);
    onAttachmentsChange(newAtts);

    // 如果删除后没有附件了，清空 activeImageUrl（由父组件管理）
    if (newAtts.length === 0) {
      onActiveImageUrlChange(null);
    }
  }, [activeAttachments, onAttachmentsChange, onActiveImageUrlChange]);

  // ✅ 注意：不在这里清理 Blob URLs
  // 原因：用户消息中的附件可能仍在使用这些 Blob URL
  // Blob URL 的清理应该由消息生命周期管理，而不是组件卸载时清理

  // 发送逻辑
  const handleGenerate = useCallback(async () => {
    const missingRequiredPrompt = requiresPromptForMode && !prompt.trim();
    const missingRequiredAttachment = requiresAttachmentForMode && activeAttachments.length === 0 && !activeImageUrl;
    if (externalDisabled) {
      if (externalDisabledReason) {
        showError(externalDisabledReason);
      }
      return;
    }
    if (missingRequiredPrompt || isLoading || missingRequiredAttachment) return;

    try {
      // 逻辑：
      // 1. 如果用户上传了附件，使用上传的附件（优先，不传递 activeImageUrl）
      // 2. 如果没有上传附件，使用画布中的图片（CONTINUITY LOGIC，传递 activeImageUrl）
      // 3. processUserAttachments 会自动处理这个逻辑
      
      // 根据模式选择 filePrefix
      const getFilePrefix = (mode: AppMode): string => {
        const prefixMap: Partial<Record<AppMode, string>> = {
          'image-chat-edit': 'canvas',
          'image-outpainting': 'expand',
          'image-inpainting': 'inpaint',
          'image-mask-edit': 'mask',
          'image-recontext': 'recontext',
          'image-background-edit': 'background',
          'video-gen': 'video',
          'audio-gen': 'audio',
        };
        return prefixMap[mode] || 'file';
      };
      
      // ✅ 调试日志：确认发送前的附件数量
      activeAttachments.forEach((att, idx) => {
      });
      
      // ✅ 新增：记录画布图片的完整元数据（如果有）
      if (activeCanvasAttachment) {
        const formatUrlForLog = (url: string | undefined): string => {
          if (!url) return 'N/A';
          if (url.startsWith('data:')) return `Base64 (${url.length} 字符)`;
          return url.length > 80 ? url.substring(0, 80) + '...' : url;
        };
      } else {
      }

      // ✅ 互斥逻辑：有附件用附件，没附件用画布图片
      const finalAttachments = await processUserAttachments(
        activeAttachments, // 用户上传的附件
        activeAttachments.length > 0 ? null : activeImageUrl, // 有附件时不用画布图片
        messages,
        sessionId,
        getFilePrefix(mode)
      );


      // 构建 ChatOptions
      const options: ChatOptions = {
        enableSearch: false,
        enableThinking: controls.enableThinking,
        enableCodeExecution: false,
        ...(mode === 'video-gen'
          ? {
              aspectRatio: controls.aspectRatio,
              resolution: controls.resolution,
              seconds: controls.videoSeconds,
              videoExtensionCount: controls.videoExtensionCount > 0 ? controls.videoExtensionCount : undefined,
              storyboardShotSeconds: controls.storyboardShotSeconds,
              generateAudio: controls.generateAudio,
              personGeneration: controls.personGeneration || undefined,
              subtitleMode: controls.subtitleMode || undefined,
              subtitleLanguage: controls.subtitleLanguage || undefined,
              subtitleScript: controls.subtitleScript.trim() || undefined,
              storyboardPrompt: controls.storyboardPrompt.trim() || undefined,
            }
          : {
              imageAspectRatio: controls.aspectRatio,
              imageResolution: controls.resolution,
            }),
        numberOfImages: controls.numberOfImages,
        negativePrompt: controls.negativePrompt || undefined,
        seed: controls.seed !== -1 ? controls.seed : undefined,
        outputMimeType: controls.outputMimeType,
        // PNG 是无损格式，不需要压缩质量参数，仅 JPEG 时传递
        ...(controls.outputMimeType === 'image/jpeg' ? { outputCompressionQuality: controls.outputCompressionQuality } : {}),
        enhancePrompt: controls.enhancePrompt,
        enhancePromptModel: controls.enhancePromptModel || undefined,
      };

      // ✅ Mask 编辑模式特有参数
      if (mode === 'image-mask-edit') {
        options.editMode = controls.editMode;
        options.maskDilation = controls.maskDilation;
        options.guidanceScale = controls.guidanceScale;
        options.maskMode = controls.maskMode; // Vertex AI MaskReferenceConfig.mask_mode
      }

      // ✅ Outpainting 模式特有参数（传递给 ExpandService）
      if (mode === 'image-outpainting') {
        // 扩图模式：ratio | scale | offset | upscale
        (options as any).outpaintMode = controls.outpaintMode;

        // 根据扩图模式传递不同的参数
        if (controls.outpaintMode === 'scale') {
          // 缩放模式：x_scale, y_scale
          (options as any).xScale = controls.xScale;
          (options as any).yScale = controls.yScale;
        } else if (controls.outpaintMode === 'offset') {
          // 偏移模式：left_offset, right_offset, top_offset, bottom_offset
          (options as any).leftOffset = controls.offsetPixels.left;
          (options as any).rightOffset = controls.offsetPixels.right;
          (options as any).topOffset = controls.offsetPixels.top;
          (options as any).bottomOffset = controls.offsetPixels.bottom;
        } else if (controls.outpaintMode === 'ratio') {
          // 比例模式：使用 aspectRatio
          (options as any).outputRatio = controls.aspectRatio;
        } else if (controls.outpaintMode === 'upscale') {
          // 放大模式：upscale_factor
          (options as any).upscaleFactor = controls.upscaleFactor;
        }

      }

      onSend(prompt, options, finalAttachments, mode);
      setPrompt(''); // 发送后清空提示词
      
      // 发送后清空附件预览
      if (activeAttachments.length > 0) {
        onAttachmentsChange([]);
      }
    } catch (error) {
      showError('处理附件失败，请重试');
    }
  }, [
    prompt,
    isLoading,
    activeAttachments,
    activeImageUrl,
    messages,
    sessionId,
    controls,
    onSend,
    showError,
    onAttachmentsChange,
    requiresAttachmentForMode,
    requiresPromptForMode,
    externalDisabled,
    externalDisabledReason,
  ]);

  // 键盘快捷键
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  }, [handleGenerate]);

  // 根据模式获取按钮配置
  const hasAttachmentsOrImage = activeAttachments.length > 0 || !!activeImageUrl;
  const modeConfig = useMemo(() => getModeButtonConfig(mode, hasAttachmentsOrImage), [mode, hasAttachmentsOrImage]);
  
  // 使用自定义文本或模式默认文本
  const finalButtonText = buttonText || modeConfig.text;
  const finalLoadingText = loadingText || modeConfig.loadingText;
  const finalButtonIcon = buttonIcon || modeConfig.icon;
  const finalPlaceholder = placeholder || modeConfig.placeholder;

  // 判断是否支持附件（audio-gen 不支持，video-gen 支持可选参考图）
  const supportsAttachments = mode !== 'audio-gen';
  // 判断是否必须有附件（video-gen 参考图可选）
  const isDisabled =
    (requiresPromptForMode && !prompt.trim()) ||
    isLoading ||
    externalDisabled ||
    (requiresAttachmentForMode && activeAttachments.length === 0 && !activeImageUrl);
  const attachmentAccept = mode === 'video-gen' ? 'image/*,video/*' : 'image/*';
  const attachmentTitle = mode === 'video-gen'
    ? (activeAttachments.length >= attachmentLimit ? `已达到最大数量 (${attachmentLimit})` : '点击上传图片或视频（支持多选，作为视频参考）')
    : (activeAttachments.length >= attachmentLimit ? `已达到最大数量 (${attachmentLimit})` : '点击上传图片（支持多选）');

  return (
    <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
      {/* 附件预览 - 使用 AttachmentPreview 组件（仅在需要附件的模式显示） */}
      {supportsAttachments && (
        <AttachmentPreview
          attachments={activeAttachments}
          removeAttachment={removeAttachment}
        />
      )}

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
        placeholder={finalPlaceholder}
        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
      />

      {/* 上传按钮 + 操作按钮 */}
      <div className="flex gap-2 items-center">
        {/* 上传按钮（仅在需要附件的模式显示，✅ 支持多文件选择） */}
        {supportsAttachments && (
          <label
            className={`p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg relative ${
              activeAttachments.length >= attachmentLimit ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            title={attachmentTitle}
          >
            <input
              type="file"
              accept={attachmentAccept}
              multiple={attachmentLimit > 1}
              className="hidden"
              onChange={handleFileSelect}
              disabled={activeAttachments.length >= attachmentLimit}
            />
            {activeAttachments.length === 0 ? (
              <ImageIcon size={18} className="text-white" />
            ) : (
              <div className="relative">
                <Paperclip size={18} className="text-white" />
                {/* ✅ 显示附件计数 */}
                <span className="absolute -top-2 -right-2 bg-pink-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  {activeAttachments.length}
                </span>
              </div>
            )}
          </label>
        )}

        {/* 操作按钮（编辑/生成/扩图等） */}
        <button
          onClick={handleGenerate}
          disabled={isDisabled}
          className={`${supportsAttachments ? 'flex-1' : 'w-full'} py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              {finalLoadingText}
            </>
          ) : (
            <>
              {finalButtonIcon}
              {finalButtonText}
            </>
          )}
        </button>
      </div>

      {externalDisabledReason && (
        <div className="text-[11px] text-amber-400">
          {externalDisabledReason}
        </div>
      )}
    </div>
  );
};

export default ChatEditInputArea;
