import React, { useState, useEffect, useRef } from 'react';
import { ChatOptions, ModelConfig, Attachment, AppMode, OutPaintingOptions, PdfExtractionTemplate } from '../../types/types';
import { v4 as uuidv4 } from 'uuid';

// Sub-components
import { ModeSelector } from './input/ModeSelector';
import { AdvancedSettings } from './input/AdvancedSettings';
import { PdfAdvancedSettings } from './input/PdfAdvancedSettings';
import { AttachmentPreview } from './input/AttachmentPreview';
import { PromptInput } from './input/PromptInput';

// New refactored components
import { ModeControlsCoordinator } from '../../coordinators';
import { useControlsState } from '../../hooks/useControlsState';

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
  pdfTemplates?: PdfExtractionTemplate[];
  selectedPdfTemplate?: string;
  onPdfTemplateChange?: (template: string) => void;
}

const InputArea: React.FC<InputAreaProps> = ({ 
    onSend, isLoading, onStop, currentModel, 
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
        alert("Out-Painting mode supports only one reference image at a time.");
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
    updateAttachments(attachments.filter(att => att.id !== id));
  };


  const handleSend = () => {
    if (isLoading && !onStop) return;
    
    if (mode === 'image-outpainting') {
        if (attachments.length === 0 && !hasActiveContext) {
            alert("Please attach an image to expand (Out-Painting).");
            return;
        }
    } else {
        if (!input.trim() && attachments.length === 0 && !hasActiveContext) return;
    }

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

    onSend(input, {
        enableSearch: controls.enableSearch,
        enableThinking: controls.enableThinking,
        enableCodeExecution: controls.enableCodeExecution,
        enableUrlContext: controls.enableUrlContext, 
        enableBrowser: controls.enableBrowser, 
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
        pdfAdditionalInstructions: mode === 'pdf-extract' ? controls.pdfAdditionalInstructions.trim() : undefined
    }, attachments, mode);
    
    setInput('');
    updateAttachments([]);
  };

  const isGenMode = mode === 'image-gen' || mode === 'image-edit' || mode === 'video-gen' || mode === 'image-outpainting';
  const isMissingImage = (mode === 'image-edit' || mode === 'image-outpainting') && attachments.length === 0 && !hasActiveContext;
  const showLoraSettings = providerId === 'tongyi' && mode === 'image-edit';


  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-6 pt-2 transition-all duration-300">
      
      {/* 1. Toolbar Row */}
      <div className="flex flex-wrap items-center gap-3 mb-2 px-1">
          <ModeSelector 
              mode={mode} 
              setMode={setMode} 
              currentModel={currentModel} 
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
                  googleCacheMode={controls.googleCacheMode}
                  setGoogleCacheMode={controls.setGoogleCacheMode}
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


      {isGenMode && controls.showAdvanced && (
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
      />
    </div>
  );
};

export default InputArea;
