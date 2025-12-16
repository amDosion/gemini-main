import React, { useState, useEffect, useRef } from 'react';
import { ChatOptions, ModelConfig, Attachment, AppMode, OutPaintingOptions, LoraConfig } from '../../../types';
import { v4 as uuidv4 } from 'uuid';

// Sub-components
import { ModeSelector } from './input/ModeSelector';
import { ChatControls } from './input/ChatControls';
import { GenerationControls } from './input/GenerationControls';
import { AdvancedSettings } from './input/AdvancedSettings';
import { AttachmentPreview } from './input/AttachmentPreview';
import { PromptInput } from './input/PromptInput';

interface InputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  currentModel?: ModelConfig;
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  activeAttachments?: Attachment[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
  hasActiveContext?: boolean;
  providerId?: string; 
}

const InputArea: React.FC<InputAreaProps> = ({ 
    onSend, isLoading, onStop, currentModel, 
    mode, setMode, initialPrompt, initialAttachments,
    activeAttachments, onAttachmentsChange, hasActiveContext,
    providerId = 'google'
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

  // --- Quick Settings State ---
  const [enableSearch, setEnableSearch] = useState(false);
  const [enableThinking, setEnableThinking] = useState(false);
  const [enableCodeExecution, setEnableCodeExecution] = useState(false);
  const [enableUrlContext, setEnableUrlContext] = useState(false);
  const [enableBrowser, setEnableBrowser] = useState(false); 
  const [googleCacheMode, setGoogleCacheMode] = useState<'none' | 'exact' | 'semantic'>('none');
  
  // --- Generation Settings ---
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [resolution, setResolution] = useState("1K");
  const [numberOfImages, setNumberOfImages] = useState(1);
  const [style, setStyle] = useState("None");
  const [voice, setVoice] = useState("Puck");

  // --- Virtual Try-On Settings ---
  const [showTryOn, setShowTryOn] = useState(false);

  // --- Advanced Settings ---
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [negativePrompt, setNegativePrompt] = useState("");
  const [seed, setSeed] = useState<number>(-1);
  const [loraConfig, setLoraConfig] = useState<LoraConfig>({ alpha: 0.6 });

  // --- Out-Painting Settings ---
  const [outPaintingMode, setOutPaintingMode] = useState<'scale' | 'offset'>('scale');
  const [scaleFactor, setScaleFactor] = useState(2.0);
  const [offsetPixels, setOffsetPixels] = useState({ left: 0, right: 0, top: 0, bottom: 0 });

  // --- Refs & Effects ---
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // ✅ 使用 ref 保存最新的 attachments 值，避免闭包问题
  const attachmentsRef = useRef<Attachment[]>(attachments);
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => {
      if (initialPrompt) setInput(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
      // 只有当 initialAttachments 明确传入时才更新
      // 避免在用户手动上传图片时被覆盖
      if (initialAttachments !== undefined) {
          updateAttachments(initialAttachments);
      }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAttachments]); // ✅ 只依赖 initialAttachments，避免循环更新

  useEffect(() => {
    if (currentModel) {
        if (!currentModel.capabilities.search && enableSearch) setEnableSearch(false);
        if (!currentModel.capabilities.reasoning && enableThinking) setEnableThinking(false);
    }
  }, [currentModel, enableSearch, enableThinking]);

  useEffect(() => {
      // ❌ 移除自动清空 attachments 的逻辑
      // 用户上传的图片不应该在切换模式时被清除
      
      if (mode === 'video-gen') {
          if (aspectRatio !== '16:9' && aspectRatio !== '9:16') setAspectRatio('16:9');
      } else if (mode === 'image-gen') {
          if (providerId === 'openai') {
             setNumberOfImages(1);
          }
      }

      setShowAdvanced(false); 
      setShowTryOn(false);
  }, [mode, providerId, aspectRatio]);

  // --- Handlers ---
  /**
   * 处理文件选择
   * 
   * 只创建 Blob URL 用于 UI 预览，不触发任何上传
   * 上传逻辑在点击发送后由 useChat.ts 统一处理：
   * - DashScope 上传：用于扩图 API 调用
   * - 云存储上传：用于持久化保存
   */
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    if (mode === 'image-outpainting' && (attachments.length > 0 || files.length > 1)) {
        alert("Out-Painting mode supports only one reference image at a time.");
        if (e.target) e.target.value = '';
        return;
    }

    const newAttachments: Attachment[] = [];
    
    // 处理每个文件：只创建 Blob URL 用于预览，保留 File 对象用于后续上传
    for (const file of Array.from(files)) {
        const blobUrl = URL.createObjectURL(file);
        const attachmentId = uuidv4();
        
        // 创建附件（使用 Blob URL 预览，保留 File 对象）
        const attachment: Attachment = {
            id: attachmentId,
            file: file,  // 保留 File 对象，发送时上传
            mimeType: file.type,
            name: file.name,
            url: blobUrl,  // Blob URL 用于 UI 预览
            tempUrl: blobUrl,
            uploadStatus: 'pending'  // 等待发送时上传
        };
        
        newAttachments.push(attachment);
        // ✅ 不再自动上传，等待用户点击发送
    }
    
    updateAttachments([...attachments, ...newAttachments]);
    if (e.target) e.target.value = '';
  };

  const handleAddLink = (url: string) => {
    if (url) {
        // Validation for YouTube or other links
        const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
        
        // Treat as a special attachment
        const newAttachment: Attachment = {
            id: uuidv4(),
            mimeType: isYouTube ? 'video/external' : 'text/link',
            fileUri: url,          
            name: isYouTube ? 'YouTube Video' : 'Link',
            url: url               
        };
        updateAttachments([...attachments, newAttachment]);
        
        // Auto-enable URL context if it's a generic link
        if (!isYouTube && !enableUrlContext && mode === 'chat') {
            setEnableUrlContext(true);
        }
    }
  };

  const removeAttachment = (id: string) => {
    updateAttachments(attachments.filter(att => att.id !== id));
  };

  const handleSend = () => {
    // 如果正在加载且没有停止按钮，直接返回
    if (isLoading && !onStop) return;
    
    // 对于 image-outpainting 模式，只需要有附件即可发送
    if (mode === 'image-outpainting') {
        if (attachments.length === 0 && !hasActiveContext) {
            alert("Please attach an image to expand (Out-Painting).");
            return;
        }
        // ✅ 有附件就可以发送，不需要输入文本
    } else {
        // 其他模式需要有输入文本或附件或活动上下文
        if (!input.trim() && attachments.length === 0 && !hasActiveContext) return;
    }

    const outPaintingOptions: OutPaintingOptions = {
        mode: outPaintingMode,
        xScale: scaleFactor,
        yScale: scaleFactor,
        leftOffset: offsetPixels.left,
        rightOffset: offsetPixels.right,
        topOffset: offsetPixels.top,
        bottomOffset: offsetPixels.bottom,
        bestQuality: true,
        limitImageSize: false
    };

    onSend(input, {
        enableSearch,
        enableThinking,
        enableCodeExecution,
        enableUrlContext, 
        enableBrowser, 
        googleCacheMode, 
        imageAspectRatio: aspectRatio,
        imageResolution: resolution,
        numberOfImages: numberOfImages, 
        imageStyle: style,
        voiceName: voice,
        outPainting: outPaintingOptions,
        virtualTryOnTarget: undefined, 
        negativePrompt: negativePrompt.trim(),
        seed: seed > -1 ? seed : undefined,
        loraConfig: loraConfig.image ? loraConfig : undefined // Only pass if image is set
    }, attachments, mode);
    
    if (mode !== 'chat') {
        setInput('');
        updateAttachments([]);
    } else {
        setInput('');
        updateAttachments([]);
    }
  };

  const isGenMode = mode === 'image-gen' || mode === 'image-edit' || mode === 'video-gen' || mode === 'image-outpainting';
  const isMissingImage = (mode === 'image-edit' || mode === 'image-outpainting') && attachments.length === 0 && !hasActiveContext;
  
  // Only show LoRA settings if provider is TongYi and mode is Edit
  const showLoraSettings = providerId === 'tongyi' && mode === 'image-edit';

  return (
    <div className="w-full max-w-[98%] 2xl:max-w-[1800px] mx-auto px-4 pb-6 pt-2 transition-all duration-300">
      
      {/* 1. Toolbar Row */}
      <div className="flex flex-wrap items-center gap-3 mb-2 px-1">
          <ModeSelector 
              mode={mode} 
              setMode={setMode} 
              currentModel={currentModel} 
          />

          <div className="flex items-center gap-2 flex-wrap justify-end">
              {mode === 'chat' ? (
                  <ChatControls 
                      currentModel={currentModel}
                      enableSearch={enableSearch} setEnableSearch={setEnableSearch}
                      enableThinking={enableThinking} setEnableThinking={setEnableThinking}
                      enableCodeExecution={enableCodeExecution} setEnableCodeExecution={setEnableCodeExecution}
                      enableUrlContext={enableUrlContext} setEnableUrlContext={setEnableUrlContext}
                      enableBrowser={enableBrowser} setEnableBrowser={setEnableBrowser}
                      googleCacheMode={googleCacheMode} setGoogleCacheMode={setGoogleCacheMode}
                  />
              ) : (
                  <GenerationControls 
                      mode={mode}
                      showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced}
                      style={style} setStyle={setStyle}
                      numberOfImages={numberOfImages} setNumberOfImages={setNumberOfImages}
                      aspectRatio={aspectRatio} setAspectRatio={setAspectRatio}
                      resolution={resolution} setResolution={setResolution}
                      outPaintingMode={outPaintingMode} setOutPaintingMode={setOutPaintingMode}
                      scaleFactor={scaleFactor} setScaleFactor={setScaleFactor}
                      offsetPixels={offsetPixels} setOffsetPixels={setOffsetPixels}
                      showTryOn={showTryOn} setShowTryOn={setShowTryOn}
                      providerId={providerId}
                  />
              )}
          </div>
      </div>

      {isGenMode && showAdvanced && (
          <AdvancedSettings 
              negativePrompt={negativePrompt} setNegativePrompt={setNegativePrompt}
              seed={seed} setSeed={setSeed}
              // Only pass LoRA setters if applicable
              loraConfig={showLoraSettings ? loraConfig : undefined}
              setLoraConfig={showLoraSettings ? setLoraConfig : undefined}
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
      />
    </div>
  );
};

export default InputArea;