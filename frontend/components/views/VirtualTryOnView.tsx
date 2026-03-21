/**
 * Virtual Try-On 视图组件
 *
 * 布局：
 * - 侧边栏：显示所有消息历史（USER 的人物图+服装图，MODEL 的试衣结果）
 * - 主区域左侧：显示 AI 生成的结果（支持多图网格布局）
 * - 主区域右侧：上传控制面板（人物图、服装图、参数、试穿按钮）
 * 
 * ✅ 与 GEN/Edit 模式保持一致：
 * - 使用 onSend → useChat.sendMessage → VirtualTryOnHandler 流程
 * - 自动传递 sessionId、message_id 到后端
 * - 结果通过 AttachmentService 写入数据库
 * - 支持会话持久化
 */
import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { AppMode, ModelConfig, ChatOptions, Message, Role, Attachment } from '../../types/types';
import { Shirt, User, Layers, Download, Maximize2, Bot, AlertCircle, Upload, SlidersHorizontal, Sparkles, X } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';
import { GenViewLayout } from '../common/GenViewLayout';
import { useToastContext } from '../../contexts/ToastContext';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { useModeControlsSchema } from '../../hooks/useModeControlsSchema';
import { downloadSourceUrlInBrowser } from '../../services/downloadService';

interface VirtualTryOnViewProps {
  messages: Message[];
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
  providerId?: string;
  sessionId?: string | null;
  apiKey?: string;
}

const getAttachmentStableKey = (attachment: Attachment): string => {
  const parts = [
    attachment.id,
    attachment.url,
    attachment.fileUri,
    attachment.name,
    attachment.mimeType,
  ].filter((part): part is string => Boolean(part && part.length > 0));

  return parts.join('|');
};

export const VirtualTryOnView: React.FC<VirtualTryOnViewProps> = ({
  messages,
  loadingState,
  setAppMode,
  onImageClick,
  onSend,
  onStop,
  activeModelConfig,
  visibleModels = [],
  allVisibleModels = [],
  initialAttachments,
  providerId,
  sessionId,
}) => {
  const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
  const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { showError } = useToastContext();
  
  // ✅ 右侧面板：人物图和服装图状态
  const [personImageUrl, setPersonImageUrl] = useState<string | null>(null);
  const [garmentImageUrl, setGarmentImageUrl] = useState<string | null>(null);
  const personInputRef = useRef<HTMLInputElement>(null);
  const garmentInputRef = useRef<HTMLInputElement>(null);
  const resolvedProviderId = providerId || 'google';
  const { schema: tryOnSchema } = useModeControlsSchema(
    resolvedProviderId,
    'virtual-try-on',
    activeModelConfig?.id
  );
  const tryOnDefaults = tryOnSchema?.defaults ?? {};
  const baseStepsRange = tryOnSchema?.numericRanges?.base_steps;
  const numberOfImageOptions = useMemo(() => {
    return (tryOnSchema?.paramOptions?.number_of_images ?? [])
      .map((option) => option.value)
      .filter((value): value is number => typeof value === 'number');
  }, [tryOnSchema]);
  const minBaseSteps = baseStepsRange?.min ?? 8;
  const maxBaseSteps = baseStepsRange?.max ?? 48;
  const stepBaseSteps = baseStepsRange?.step ?? 8;
  const defaultBaseSteps =
    (typeof tryOnDefaults.base_steps === 'number' ? tryOnDefaults.base_steps : undefined) ??
    minBaseSteps;
  const defaultNumberOfImages =
    (typeof tryOnDefaults.number_of_images === 'number' ? tryOnDefaults.number_of_images : undefined) ??
    numberOfImageOptions[0] ??
    1;
  
  // ✅ 参数状态
  const [baseSteps, setBaseSteps] = useState<number>(32);
  const [numberOfImages, setNumberOfImages] = useState<number>(1);
  
  const isLoading = loadingState !== 'idle';
  
  // ✅ 历史批次（MODEL 消息）
  const historyBatches = useMemo(() => {
    return messages
      .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
      .reverse();
  }, [messages]);
  
  // ✅ 当前激活的批次
  const activeBatchMessage = useMemo(() => {
    if (selectedMsgId) {
      return historyBatches.find(m => m.id === selectedMsgId);
    }
    return historyBatches[0];
  }, [selectedMsgId, historyBatches]);
  
  // ✅ 当前批次的所有图片（支持多张）
  const displayImages = useMemo(() => {
    return (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
  }, [activeBatchMessage?.attachments]);
  
  const isBatchError = activeBatchMessage?.isError;
  
  // ✅ 新生成开始时，自动切换到最新批次
  useEffect(() => {
    if (loadingState === 'loading') {
      setSelectedMsgId(null);
    }
  }, [loadingState]);
  
  // ✅ 新生成完成时，自动更新
  useEffect(() => {
    if (loadingState === 'idle' && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.id !== lastProcessedMsgId) {
        if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0) {
          setSelectedMsgId(null);
          setLastProcessedMsgId(lastMsg.id);
        } else if (lastMsg.isError) {
          setLastProcessedMsgId(lastMsg.id);
        }
      }
    }
  }, [messages, loadingState, lastProcessedMsgId]);

  // ✅ 自动滚动历史
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    requestAnimationFrame(() => {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
  }, [messages]);

  useEffect(() => {
    if (baseSteps < minBaseSteps || baseSteps > maxBaseSteps) {
      setBaseSteps(defaultBaseSteps);
      return;
    }
    const offset = (baseSteps - minBaseSteps) / stepBaseSteps;
    if (Math.abs(offset - Math.round(offset)) > 1e-6) {
      setBaseSteps(defaultBaseSteps);
    }
  }, [baseSteps, defaultBaseSteps, minBaseSteps, maxBaseSteps, stepBaseSteps]);

  useEffect(() => {
    if (numberOfImageOptions.length > 0 && !numberOfImageOptions.includes(numberOfImages)) {
      setNumberOfImages(defaultNumberOfImages);
    }
  }, [numberOfImages, numberOfImageOptions, defaultNumberOfImages]);

  // ✅ 文件转 DataURL
  const toDataUrl = useCallback((file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }, []);

  // ✅ 人物图上传处理
  const handlePersonUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const url = await toDataUrl(file);
      setPersonImageUrl(url);
    } catch (err) {
      showError('人物图上传失败');
    }
    e.target.value = '';
  }, [toDataUrl, showError]);

  // ✅ 服装图上传处理
  const handleGarmentUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const url = await toDataUrl(file);
      setGarmentImageUrl(url);
    } catch (err) {
      showError('服装图上传失败');
    }
    e.target.value = '';
  }, [toDataUrl, showError]);

  // ✅ 右侧面板试穿按钮处理
  const handleTryOn = useCallback(async () => {
    if (!personImageUrl || !garmentImageUrl) {
      showError('请先上传人物图和服装图');
      return;
    }

    // 构建附件
    const tryOnAttachments: Attachment[] = [
      { id: uuidv4(), url: personImageUrl, mimeType: 'image/png', name: 'person.png' },
      { id: uuidv4(), url: garmentImageUrl, mimeType: 'image/png', name: 'garment.png' }
    ];

    try {
      const finalAttachments = await processUserAttachments(
        tryOnAttachments,
        null,
        messages,
        sessionId,
        'canvas'
      );


      // 使用实际的参数
      const options: ChatOptions = {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1024x1024',
        numberOfImages: numberOfImages,
        baseSteps: baseSteps,
      };

      onSend('', options, finalAttachments, 'virtual-try-on');

      // 发送后清空上传槽
      setPersonImageUrl(null);
      setGarmentImageUrl(null);
    } catch (error) {
      showError('处理附件失败，请重试');
    }
  }, [personImageUrl, garmentImageUrl, messages, sessionId, onSend, showError, baseSteps, numberOfImages]);

  // ✅ 侧边栏：显示所有消息
  const sidebarContent = useMemo(() => (
    <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
      {messages.map((msg) => {
        // 过滤空占位消息
        const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
        if (isPlaceholder) return null;

        const isSelected = msg.role === Role.MODEL && activeBatchMessage?.id === msg.id;

        return (
          <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
            <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
              {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
              <span>{msg.role === Role.USER ? '输入' : (activeModelConfig?.name || 'AI')}</span>
            </div>
            <div 
              className={`p-3 rounded-2xl max-w-full text-sm shadow-sm cursor-pointer transition-all ${
                msg.role === Role.USER
                  ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                  : `bg-slate-800/50 text-slate-300 border rounded-tl-sm ${
                      isSelected ? 'ring-2 ring-rose-500 border-transparent' : 'border-slate-700/50 hover:border-slate-600'
                    }`
              }`}
              onClick={() => {
                if (msg.role === Role.MODEL && msg.attachments?.length) {
                  setSelectedMsgId(msg.id);
                }
              }}
            >
              {msg.content && <p className="mb-2">{msg.content}</p>}
              
              {/* 附件显示 */}
              {msg.attachments?.filter(att => att.url && att.url.length > 0).map((att, idx) => (
                <div
                  key={`${msg.id}:${getAttachmentStableKey(att)}`}
                  className="relative group mt-1 rounded-lg overflow-hidden border border-slate-700 hover:border-slate-500"
                >
                  <img 
                    src={att.url} 
                    className="w-full h-24 object-cover bg-slate-900" 
                    alt={msg.role === Role.USER 
                      ? (idx === 0 ? '人物图' : '服装图') 
                      : `试衣结果 ${idx + 1}`
                    } 
                  />
                  {/* 标签 */}
                  <div className="absolute bottom-1 left-1 bg-black/60 text-[10px] text-slate-300 px-1.5 py-0.5 rounded">
                    {msg.role === Role.USER 
                      ? (idx === 0 ? '👤 人物' : '👕 服装')
                      : `结果 ${idx + 1}`
                    }
                  </div>
                </div>
              ))}
              
              {/* 多图标识 */}
              {msg.role === Role.MODEL && (msg.attachments?.length || 0) > 1 && (
                <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1">
                  <Layers size={10} />
                  {msg.attachments?.length} 张图片
                </div>
              )}
              
              {msg.isError && (
                <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                  <AlertCircle size={12} /> 生成失败
                </div>
              )}
            </div>
            <div className="text-[10px] text-slate-500 px-1">
              {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        );
      })}
      
      {/* 加载状态 */}
      {isLoading && (
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
            <Shirt size={16} className="text-rose-400" />
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
            <div className="font-medium mb-1 animate-pulse">
              {loadingState === 'uploading' ? '上传图片中...' : 'AI 正在生成试衣结果...'}
            </div>
          </div>
        </div>
      )}
      
      {/* 空状态提示 */}
      {messages.length === 0 && !isLoading && (
        <div className="text-center py-10 text-slate-500 text-xs">
          <p>上传人物图和服装图开始试衣</p>
          <p className="mt-1 opacity-60">第一张图为人物，第二张图为服装</p>
        </div>
      )}
    </div>
  ), [messages, activeBatchMessage?.id, activeModelConfig?.name, isLoading, loadingState]);

  // ✅ 主区域：左侧结果显示 + 右侧上传控制面板
  const mainContent = useMemo(() => (
    <div className="flex-1 flex flex-row h-full overflow-hidden">
      {/* ========== 左侧：结果显示区 ========== */}
      <div className="flex-1 w-full h-full select-none flex flex-col relative overflow-hidden">
        {/* 棋盘格背景 */}
        <div
          className="absolute inset-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage: `
              linear-gradient(45deg, #334155 25%, transparent 25%), 
              linear-gradient(-45deg, #334155 25%, transparent 25%), 
              linear-gradient(45deg, transparent 75%, #334155 75%), 
              linear-gradient(-45deg, transparent 75%, #334155 75%)
            `,
            backgroundSize: '20px 20px',
            backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          }}
        />

        {/* 主图片显示区域 */}
        <div className="flex-1 flex items-center justify-center p-6 w-full h-full overflow-y-auto">
          {isLoading ? (
            <div className="flex flex-col items-center gap-4 pointer-events-none">
              <div className="relative">
                <div className="w-20 h-20 border-4 border-rose-500/30 border-t-rose-500 rounded-full animate-spin"></div>
              </div>
              <p className="text-slate-400 animate-pulse">
                {loadingState === 'uploading' ? '上传图片中...' : 'AI 正在生成试衣结果...'}
              </p>
            </div>
          ) : isBatchError ? (
            <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
              <AlertCircle size={48} className="text-red-500 opacity-80" />
              <div>
                <h3 className="text-lg font-bold text-slate-200">生成失败</h3>
                <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || "未知错误"}</p>
              </div>
            </div>
          ) : displayImages.length > 0 ? (
            // ✅ 多张图片网格布局
            <div className={`w-full max-w-5xl grid gap-6 transition-all duration-300 ${
              displayImages.length === 1 ? 'grid-cols-1 place-items-center' :
              displayImages.length === 2 ? 'grid-cols-1 md:grid-cols-2 place-items-start' :
              displayImages.length === 3 ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start' :
              'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 place-items-start'
            }`}>
              {displayImages.map((att, idx) => (
                <div
                  key={`${activeBatchMessage?.id ?? 'active'}:${getAttachmentStableKey(att)}`}
                  className={`relative rounded-2xl overflow-hidden shadow-2xl group border border-slate-800/50 bg-slate-900 animate-[fadeIn_0.5s_ease-out] mx-auto ${
                    displayImages.length === 1 ? 'max-w-full' : 'w-full'
                  }`}
                  style={{ animationDelay: `${idx * 100}ms` }}
                >
                  {att.url ? (
                    <img
                      src={att.url}
                      className={`block cursor-pointer ${
                        displayImages.length === 1
                          ? 'max-h-[70vh] w-auto object-contain'
                          : 'w-full h-auto object-cover'
                      }`}
                      onClick={() => onImageClick(att.url!)}
                      alt={`试衣结果 ${idx + 1}`}
                    />
                  ) : (
                    <div className="w-full h-64 flex items-center justify-center text-slate-600 bg-slate-900">
                      <Shirt size={48} className="opacity-50" />
                    </div>
                  )}
                  {/* 悬浮操作按钮 */}
                  <div className="absolute top-4 right-4 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all translate-x-4 group-hover:translate-x-0">
                    <button 
                      onClick={() => onImageClick(att.url!)} 
                      className="p-2.5 bg-black/60 hover:bg-black/80 text-white rounded-xl backdrop-blur border border-white/10 shadow-lg" 
                      title="全屏"
                    >
                      <Maximize2 size={18} />
                    </button>
                    <button 
                      onClick={async () => {
                        await downloadSourceUrlInBrowser({
                          sourceUrl: att.url!,
                          fileName: `tryon-${Date.now()}-${idx + 1}.jpg`,
                        });
                      }} 
                      className="p-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl shadow-lg" 
                      title="下载"
                    >
                      <Download size={18} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            // 空状态
            <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
              <Shirt size={48} className="opacity-20" />
              <div>
                <h3 className="text-xl font-bold text-slate-500 mb-2">Virtual Try-On</h3>
                <p className="text-sm opacity-60 mb-4">
                  在右侧上传人物图和服装图，设置参数后点击试穿
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 批次信息提示 */}
        {displayImages.length > 1 && (
          <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
            <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
              <Layers size={14} className="text-rose-400" />
              批次结果 ({displayImages.length})
            </div>
          </div>
        )}
      </div>

      {/* ========== 中间：上传控制面板 ========== */}
      <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
          {/* 人物图上传区域 */}
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-2">
                <User size={14} className="text-blue-400" />
                人物图
              </span>
              {personImageUrl && (
                <button
                  onClick={() => setPersonImageUrl(null)}
                  className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                  title="清除"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <div 
              className="h-40 flex items-center justify-center bg-slate-900/30 cursor-pointer hover:bg-slate-900/50 transition-colors relative"
              onClick={() => personInputRef.current?.click()}
            >
              <input
                ref={personInputRef}
                type="file"
                accept="image/*"
                onChange={handlePersonUpload}
                className="hidden"
              />
              {personImageUrl ? (
                <img 
                  src={personImageUrl} 
                  alt="人物图" 
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-slate-500">
                  <Upload size={24} />
                  <span className="text-xs">点击上传人物图</span>
                </div>
              )}
            </div>
          </div>

          {/* 服装图上传区域 */}
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-2">
                <Shirt size={14} className="text-rose-400" />
                服装图
              </span>
              {garmentImageUrl && (
                <button
                  onClick={() => setGarmentImageUrl(null)}
                  className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                  title="清除"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <div 
              className="h-40 flex items-center justify-center bg-slate-900/30 cursor-pointer hover:bg-slate-900/50 transition-colors relative"
              onClick={() => garmentInputRef.current?.click()}
            >
              <input
                ref={garmentInputRef}
                type="file"
                accept="image/*"
                onChange={handleGarmentUpload}
                className="hidden"
              />
              {garmentImageUrl ? (
                <img 
                  src={garmentImageUrl} 
                  alt="服装图" 
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-slate-500">
                  <Upload size={24} />
                  <span className="text-xs">点击上传服装图</span>
                </div>
              )}
            </div>
          </div>

          {/* 参数区域 */}
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-2">
                <SlidersHorizontal size={14} className="text-amber-400" />
                参数设置
              </span>
            </div>
            <div className="p-3 space-y-4">
              {/* 质量步数 - 滑块 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">质量步数</span>
                  <span className="text-xs text-slate-300 bg-slate-700 px-2 py-0.5 rounded">{baseSteps} 步</span>
                </div>
                <input
                  type="range"
                  min={minBaseSteps}
                  max={maxBaseSteps}
                  step={stepBaseSteps}
                  value={baseSteps}
                  onChange={(e) => setBaseSteps(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-rose-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>快速</span>
                  <span>高质量</span>
                </div>
              </div>
              
              {/* 生成数量 - 选择按钮 */}
              <div className="space-y-2">
                <span className="text-xs text-slate-400">生成数量</span>
                <div className="flex gap-2">
                  {numberOfImageOptions.map((num) => (
                    <button
                      key={num}
                      onClick={() => setNumberOfImages(num)}
                      className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                        numberOfImages === num
                          ? 'bg-rose-600 text-white'
                          : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                      }`}
                    >
                      {num}
                    </button>
                  ))}
                </div>
              </div>
              {numberOfImageOptions.length === 0 && (
                <p className="text-[10px] text-rose-400">
                  试衣参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
                </p>
              )}
            </div>
          </div>
        </div>

        {/* 试穿按钮 */}
        <div className="p-4 border-t border-slate-800">
          <button
            onClick={handleTryOn}
            disabled={!personImageUrl || !garmentImageUrl || isLoading}
            className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                试穿中...
              </>
            ) : (
              <>
                <Sparkles size={18} />
                开始试穿
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  ), [
    isLoading,
    loadingState,
    displayImages,
    isBatchError,
    activeBatchMessage,
    onImageClick,
    personImageUrl,
    garmentImageUrl,
    handlePersonUpload,
    handleGarmentUpload,
    handleTryOn,
    baseSteps,
    numberOfImages,
    minBaseSteps,
    maxBaseSteps,
    stepBaseSteps,
    numberOfImageOptions,
  ]);

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="试衣历史"
      sidebarHeaderIcon={<Layers size={14} />}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};

export default VirtualTryOnView;
