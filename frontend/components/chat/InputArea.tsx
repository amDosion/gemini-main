import React, { useState, useEffect, useRef } from 'react';
import { ChatOptions, ModelConfig, Attachment, AppMode, OutPaintingOptions, PdfExtractionTemplate } from '../../types/types';
import { v4 as uuidv4 } from 'uuid';
import { fileToBase64, isBlobUrl } from '../../hooks/handlers/attachmentUtils';

// Sub-components
import { ModeSelector } from './input/ModeSelector';
import { AdvancedSettings } from './input/AdvancedSettings';
import { PdfAdvancedSettings } from './input/PdfAdvancedSettings';
import { AttachmentPreview } from './input/AttachmentPreview';
import { PromptInput } from './input/PromptInput';

// New refactored components
import { ModeControlsCoordinator } from '../../coordinators';
import { useControlsState } from '../../hooks/useControlsState';
import { useToastContext } from '../../contexts/ToastContext';

interface InputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  currentModel?: ModelConfig;
  visibleModels?: ModelConfig[];  // 新增：所有可见模型列表
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  activeAttachments?: Attachment[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
  hasActiveContext?: boolean;
  providerId?: string;
  pdfTemplates?: PdfExtractionTemplate[];
  selectedPdfTemplate?: string;
  onPdfTemplateChange?: (template: string) => void;
}

const InputArea: React.FC<InputAreaProps> = ({
  onSend, isLoading, onStop, currentModel, visibleModels = [],
  mode, setMode, initialPrompt, initialAttachments,
  activeAttachments, onAttachmentsChange, hasActiveContext,
  providerId = 'google',
  pdfTemplates = [],
  selectedPdfTemplate,
  onPdfTemplateChange
}) => {
  const [input, setInput] = useState('');
  const [localAttachments, setLocalAttachments] = useState<Attachment[]>([]);

  // Controlled vs Local State for Attachments
  const attachments = activeAttachments !== undefined ? activeAttachments : localAttachments;
  const updateAttachments = (newAtts: Attachment[]) => {
    if (onAttachmentsChange) {
      onAttachmentsChange(newAtts);
    } else {
      setLocalAttachments(newAtts);
    }
  };

  // Use centralized controls state hook
  const controls = useControlsState(mode, currentModel);


  // PDF template state (external or local)
  const [localPdfTemplate, setLocalPdfTemplate] = useState<string>('invoice');
  const currentPdfTemplate = selectedPdfTemplate ?? localPdfTemplate;
  const handlePdfTemplateChange = (template: string) => {
    if (onPdfTemplateChange) {
      onPdfTemplateChange(template);
    } else {
      setLocalPdfTemplate(template);
    }
  };

  // Refs & Effects
  const attachmentsRef = useRef<Attachment[]>(attachments);
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => {
    if (initialPrompt) setInput(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
    if (initialAttachments !== undefined) {
      updateAttachments(initialAttachments);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAttachments]);

  // Note: Mode-specific parameter adjustments are handled in useControlsState hook


  // File handling
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    if (mode === 'image-outpainting' && (attachments.length > 0 || files.length > 1)) {
      // Out-Painting mode supports only one reference image at a time.
      // This validation is handled by the backend, so we just prevent submission
      if (e.target) e.target.value = '';
      return;
    }

    const newAttachments: Attachment[] = [];
    for (const file of Array.from(files)) {
      const blobUrl = URL.createObjectURL(file);
      const attachmentId = uuidv4();
      const attachment: Attachment = {
        id: attachmentId,
        file: file,
        mimeType: file.type,
        name: file.name,
        url: blobUrl,
        tempUrl: blobUrl,
        uploadStatus: 'pending'
      };
      newAttachments.push(attachment);
    }

    updateAttachments([...attachments, ...newAttachments]);
    if (e.target) e.target.value = '';
  };

  const handleAddLink = (url: string) => {
    if (url) {
      const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
      const newAttachment: Attachment = {
        id: uuidv4(),
        mimeType: isYouTube ? 'video/external' : 'text/link',
        fileUri: url,
        name: isYouTube ? 'YouTube Video' : 'Link',
        url: url
      };
      updateAttachments([...attachments, newAttachment]);

      if (!isYouTube && !controls.enableUrlContext && mode === 'chat') {
        controls.setEnableUrlContext(true);
      }
    }
  };

  const removeAttachment = (id: string) => {
    const attachmentToRemove = attachments.find(att => att.id === id);
    if (attachmentToRemove?.tempUrl) {
      URL.revokeObjectURL(attachmentToRemove.tempUrl);
    }
    updateAttachments(attachments.filter(att => att.id !== id));
  };

  // Cleanup Blob URLs when component unmounts or attachments change
  useEffect(() => {
    return () => {
      attachments.forEach(att => {
        if (att.tempUrl) {
          URL.revokeObjectURL(att.tempUrl);
        }
      });
    };
  }, [attachments]);


  const handleSend = async () => {
    if (isLoading && !onStop) return;

    if (mode === 'image-outpainting') {
      if (attachments.length === 0 && !hasActiveContext) {
        // Please attach an image to expand (Out-Painting).
        // This validation is handled by the backend, so we just prevent submission
        return;
      }
    } else {
      if (!input.trim() && attachments.length === 0 && !hasActiveContext) return;
    }

    // ✅ 修复：在发送前将 Blob URL 转换为 Base64 Data URL（永久有效）
    const processedAttachments = await Promise.all(
      attachments.map(async (att) => {
        // 如果有 file 对象且 url 是 Blob URL，转换为 Base64
        if (att.file && isBlobUrl(att.url)) {
          try {
            const base64Url = await fileToBase64(att.file);
            return { ...att, url: base64Url, tempUrl: base64Url };
          } catch (e) {
            console.warn('[InputArea] File 转 Base64 失败:', e);
            return att;
          }
        }
        return att;
      })
    );

    const outPaintingOptions: OutPaintingOptions = {
      mode: controls.outPaintingMode,
      xScale: controls.scaleFactor,
      yScale: controls.scaleFactor,
      leftOffset: controls.offsetPixels.left,
      rightOffset: controls.offsetPixels.right,
      topOffset: controls.offsetPixels.top,
      bottomOffset: controls.offsetPixels.bottom,
      bestQuality: true,
      limitImageSize: false
    };

    // ✅ 构建 ChatOptions 对象
    const chatOptions: ChatOptions = {
      enableSearch: controls.enableSearch,
      enableThinking: controls.enableThinking,
      enableCodeExecution: controls.enableCodeExecution,
      enableUrlContext: controls.enableUrlContext,
      enableBrowser: controls.enableBrowser,
      enableResearch: controls.enableResearch,
      googleCacheMode: controls.googleCacheMode,
      imageAspectRatio: controls.aspectRatio,
      imageResolution: controls.resolution,
      numberOfImages: controls.numberOfImages,
      imageStyle: controls.style,
      voiceName: controls.voice,
      outPainting: outPaintingOptions,
      virtualTryOnTarget: mode === 'virtual-try-on' ? controls.tryOnTarget : undefined,
      negativePrompt: controls.negativePrompt.trim(),
      seed: controls.seed > -1 ? controls.seed : undefined,
      loraConfig: controls.loraConfig.image ? controls.loraConfig : undefined,
      pdfExtractTemplate: mode === 'pdf-extract' ? currentPdfTemplate : undefined,
      pdfAdditionalInstructions: mode === 'pdf-extract' ? controls.pdfAdditionalInstructions.trim() : undefined,
      // Google Imagen Advanced Parameters
      // guidanceScale removed - not officially documented by Google Imagen
      outputMimeType: controls.outputMimeType,
      outputCompressionQuality: controls.outputCompressionQuality,
      enhancePrompt: controls.enhancePrompt,
      // Deep Research specific options
      deepResearchConfig: mode === 'deep-research' ? {
        thinkingSummaries: controls.thinkingSummaries,
        researchMode: controls.researchMode  // ✅ 传递工作模式（vertex-ai 或 gemini-api）
      } : undefined,
    };
    
    // ✅ 详细日志：记录 image-gen 模式下用户选择的参数
    if (mode === 'image-gen') {
      console.log('========== [InputArea] image-gen 模式用户选择参数 ==========');
      console.log('[InputArea] 当前模式:', mode);
      console.log('[InputArea] 用户输入:', input.substring(0, 100) + (input.length > 100 ? '...' : ''));
      console.log('[InputArea] 用户选择的图片生成参数:', {
        numberOfImages: chatOptions.numberOfImages,
        imageAspectRatio: chatOptions.imageAspectRatio,
        imageResolution: chatOptions.imageResolution,
        imageStyle: chatOptions.imageStyle,
        negativePrompt: chatOptions.negativePrompt,
        seed: chatOptions.seed,
        // guidanceScale removed - not officially documented by Google Imagen
        outputMimeType: chatOptions.outputMimeType,
        outputCompressionQuality: chatOptions.outputCompressionQuality,
        enhancePrompt: chatOptions.enhancePrompt,
      });
      console.log('[InputArea] 其他选项:', {
        enableSearch: chatOptions.enableSearch,
        enableThinking: chatOptions.enableThinking,
        enableCodeExecution: chatOptions.enableCodeExecution,
        enableUrlContext: chatOptions.enableUrlContext,
        enableBrowser: chatOptions.enableBrowser,
        enableResearch: chatOptions.enableResearch,
        googleCacheMode: chatOptions.googleCacheMode,
      });
      console.log('[InputArea] 附件数量:', processedAttachments.length);
      console.log('[InputArea] 完整 ChatOptions:', JSON.stringify(chatOptions, null, 2));
      console.log('========== [InputArea] image-gen 模式参数记录结束 ==========');
    }
    
    onSend(input, chatOptions, processedAttachments, mode);

    setInput('');
    updateAttachments([]);
  };

  const isGenMode = mode === 'image-gen' || 
                    mode === 'image-chat-edit' || mode === 'image-mask-edit' || 
                    mode === 'image-inpainting' || mode === 'image-background-edit' || 
                    mode === 'image-recontext' ||
                    mode === 'video-gen' || mode === 'image-outpainting';
  const isMissingImage = (
    mode === 'image-chat-edit' || mode === 'image-mask-edit' || 
    mode === 'image-inpainting' || mode === 'image-background-edit' || 
    mode === 'image-recontext' ||
    mode === 'image-outpainting'
  ) && attachments.length === 0 && !hasActiveContext;
  const showLoraSettings = providerId === 'tongyi' && (
    mode === 'image-chat-edit' || mode === 'image-mask-edit' || 
    mode === 'image-inpainting' || mode === 'image-background-edit' || 
    mode === 'image-recontext'
  );


  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-6 pt-2 transition-all duration-300">

      {/* 1. Toolbar Row */}
      <div className="flex flex-wrap items-center gap-3 mb-2 px-1">
        <ModeSelector
          mode={mode}
          setMode={setMode}
          currentModel={currentModel}
          visibleModels={visibleModels}
        />

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <ModeControlsCoordinator
            mode={mode}
            providerId={providerId}
            currentModel={currentModel}
            // Chat controls
            enableSearch={controls.enableSearch}
            setEnableSearch={controls.setEnableSearch}
            enableThinking={controls.enableThinking}
            setEnableThinking={controls.setEnableThinking}
            enableCodeExecution={controls.enableCodeExecution}
            setEnableCodeExecution={controls.setEnableCodeExecution}
            enableUrlContext={controls.enableUrlContext}
            setEnableUrlContext={controls.setEnableUrlContext}
            enableBrowser={controls.enableBrowser}
            setEnableBrowser={controls.setEnableBrowser}
            enableRAG={controls.enableRAG}
            setEnableRAG={controls.setEnableRAG}
            enableResearch={controls.enableResearch}
            setEnableResearch={controls.setEnableResearch}
            googleCacheMode={controls.googleCacheMode}
            setGoogleCacheMode={controls.setGoogleCacheMode}
            // Deep Research controls（只在 deep-research 模式下传递）
            thinkingSummaries={mode === 'deep-research' ? controls.thinkingSummaries : 'none'}
            setThinkingSummaries={mode === 'deep-research' ? controls.setThinkingSummaries : () => {}}
            researchMode={mode === 'deep-research' ? controls.researchMode : 'vertex-ai'}
            setResearchMode={mode === 'deep-research' ? controls.setResearchMode : () => {}}
            // Multi-Agent controls（保留用于向后兼容，但 multi-agent 模式主要在工作流编辑器中管理）
            enableMultiAgent={mode === 'multi-agent' ? true : (mode === 'deep-research' ? controls.enableMultiAgent : false)}
            setEnableMultiAgent={mode === 'deep-research' ? controls.setEnableMultiAgent : () => {}}
            // Generation controls
            style={controls.style}
            setStyle={controls.setStyle}
            numberOfImages={controls.numberOfImages}
            setNumberOfImages={controls.setNumberOfImages}
            aspectRatio={controls.aspectRatio}
            setAspectRatio={controls.setAspectRatio}
            resolution={controls.resolution}
            setResolution={controls.setResolution}
            showAdvanced={controls.showAdvanced}
            setShowAdvanced={controls.setShowAdvanced}
            // Google Imagen advanced parameters
            negativePrompt={controls.negativePrompt}
            setNegativePrompt={controls.setNegativePrompt}
            seed={controls.seed}
            setSeed={controls.setSeed}
            // guidanceScale removed - not officially documented by Google Imagen
            outputMimeType={controls.outputMimeType}
            setOutputMimeType={controls.setOutputMimeType}
            outputCompressionQuality={controls.outputCompressionQuality}
            setOutputCompressionQuality={controls.setOutputCompressionQuality}
            enhancePrompt={controls.enhancePrompt}
            setEnhancePrompt={controls.setEnhancePrompt}
            // Out-painting controls
            outPaintingMode={controls.outPaintingMode}
            setOutPaintingMode={controls.setOutPaintingMode}
            scaleFactor={controls.scaleFactor}
            setScaleFactor={controls.setScaleFactor}
            offsetPixels={controls.offsetPixels}
            setOffsetPixels={controls.setOffsetPixels}
            // Try-on controls
            tryOnTarget={controls.tryOnTarget}
            setTryOnTarget={controls.setTryOnTarget}
            // Audio controls
            voice={controls.voice}
            setVoice={controls.setVoice}
            // PDF controls
            selectedTemplate={currentPdfTemplate}
            setSelectedTemplate={handlePdfTemplateChange}
            templates={pdfTemplates}
          />
        </div>
      </div>


      {/* AdvancedSettings: 排除 Google image-gen 模式（ImageGenControls 有自己的高级面板） */}
      {isGenMode && controls.showAdvanced && !(providerId === 'google' && mode === 'image-gen') && (
        <AdvancedSettings
          negativePrompt={controls.negativePrompt}
          setNegativePrompt={controls.setNegativePrompt}
          seed={controls.seed}
          setSeed={controls.setSeed}
          loraConfig={showLoraSettings ? controls.loraConfig : undefined}
          setLoraConfig={showLoraSettings ? controls.setLoraConfig : undefined}
        />
      )}

      {mode === 'pdf-extract' && controls.showAdvanced && (
        <PdfAdvancedSettings
          additionalInstructions={controls.pdfAdditionalInstructions}
          setAdditionalInstructions={controls.setPdfAdditionalInstructions}
        />
      )}

      <AttachmentPreview
        attachments={attachments}
        removeAttachment={removeAttachment}
      />

      <PromptInput
        input={input}
        setInput={setInput}
        handleSend={handleSend}
        isLoading={isLoading}
        onStop={onStop}
        mode={mode}
        hasActiveContext={hasActiveContext}
        hasAttachments={attachments.length > 0}
        isMissingImage={isMissingImage}
        onFileSelect={handleFileSelect}
        onAddLink={handleAddLink}
        attachmentCount={attachments.length}
      />
    </div>
  );
};

export default InputArea;
