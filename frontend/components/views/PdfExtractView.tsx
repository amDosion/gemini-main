import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Message,
  Role,
  AppMode,
  Attachment,
  ChatOptions,
  ModelConfig,
  PdfExtractionTemplate,
  PdfExtractionResult as PdfExtractionResultType
} from '../../types/types';
import { CheckCircle, XCircle, Clock, AlertCircle, Trash2, SlidersHorizontal, RotateCcw, FileText, X, Paperclip, Send } from 'lucide-react';
import { apiClient } from '../../services/apiClient';
import { GenViewLayout } from '../common/GenViewLayout';
import {
  PdfEmptyState,
  PdfResultToolbar,
  ViewMode,
  PdfTableView,
  PdfJsonView,
  PdfMarkdownView,
  PdfHtmlView
} from './pdf';

interface PdfExtractViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[];  // 新增
  allVisibleModels?: ModelConfig[];  // 新增：完整模型列表
  providerId?: string;
  onDeleteMessage?: (messageId: string) => void;
}

export const PdfExtractView: React.FC<PdfExtractViewProps> = ({
  messages,
  setAppMode,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  visibleModels = [],
  allVisibleModels = [],
  providerId,
  onDeleteMessage
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 默认模板（后端不可用时使用）
  const DEFAULT_TEMPLATES: PdfExtractionTemplate[] = [
    { id: 'invoice', name: 'Invoice', description: 'Extract invoice details', icon: '🧾' },
    { id: 'form', name: 'Form', description: 'Extract form fields', icon: '📋' },
    { id: 'receipt', name: 'Receipt', description: 'Extract receipt data', icon: '🧾' },
    { id: 'contract', name: 'Contract', description: 'Extract contract terms', icon: '📄' }
  ];

  const [selectedTemplate, setSelectedTemplate] = useState<string>('invoice');
  const [templates, setTemplates] = useState<PdfExtractionTemplate[]>(DEFAULT_TEMPLATES);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
  
  // ✅ 参数面板状态
  const [prompt, setPrompt] = useState('Extract details from this document.');
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);

  useEffect(() => {
    let isMounted = true;
    // 直接使用 apiClient 获取模板
    apiClient.get<{ success: boolean; templates: PdfExtractionTemplate[] }>('/api/pdf/templates')
      .then(response => {
        if (isMounted && response.templates && response.templates.length > 0) {
          setTemplates(response.templates);
        }
      })
      .catch(() => {
        // 后端不可用时使用默认模板
        if (isMounted) {
          setTemplates(DEFAULT_TEMPLATES);
        }
      });
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    if (loadingState === 'loading') {
      setSelectedMsgId(null);
      setIsMobileHistoryOpen(false);
    }
  }, [loadingState]);

  const historyBatches = useMemo(() => {
    return messages
      .filter(m => m.role === Role.MODEL && (m.content || m.isError))
      .reverse();
  }, [messages]);

  const activeBatchMessage = useMemo(() => {
    if (selectedMsgId) {
      return historyBatches.find(m => m.id === selectedMsgId);
    }
    return historyBatches[0];
  }, [selectedMsgId, historyBatches]);

  const extractedData = useMemo((): PdfExtractionResultType | null => {
    if (!activeBatchMessage?.content) return null;
    try {
      const parsed = JSON.parse(activeBatchMessage.content);
      if (parsed.success !== undefined && (parsed.data || parsed.error)) {
        return parsed;
      }
    } catch {}
    return null;
  }, [activeBatchMessage]);

  const isBatchError = activeBatchMessage?.isError;

  const renderResultView = useCallback(() => {
    if (!extractedData?.success) return null;
    switch (viewMode) {
      case 'table':
        return <PdfTableView data={extractedData.data} />;
      case 'json':
        return <PdfJsonView data={extractedData.data} />;
      case 'markdown':
        return <PdfMarkdownView data={extractedData.data} />;
      case 'html':
        return <PdfHtmlView data={extractedData.data} />;
      default:
        return <PdfTableView data={extractedData.data} />;
    }
  }, [extractedData, viewMode]);

  // ✅ 重置参数
  const resetParams = useCallback(() => {
    setSelectedTemplate('invoice');
    setPrompt('Extract details from this document.');
  }, []);

  // ✅ 发送提取请求
  const handleGenerate = useCallback(() => {
    if (loadingState === 'loading' || activeAttachments.length === 0) return;
    
    const options: ChatOptions = {
      enableSearch: false,
      enableThinking: false,
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      imageResolution: '1024x1024',
      pdfExtractTemplate: selectedTemplate,
    };
    
    onSend(prompt, options, activeAttachments, 'pdf-extract');
    setPrompt(''); // 发送后清空提示词
    // 不清空附件，以便用户可以重复提取
  }, [loadingState, activeAttachments, prompt, selectedTemplate, onSend]);

  // ✅ 键盘快捷键
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  }, [handleGenerate]);

  // 缓存 sidebarExtraHeader
  const sidebarExtraHeader = useMemo(() => (
    <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
      {historyBatches.length}
    </span>
  ), [historyBatches.length]);

  // 缓存 sidebarContent
  const sidebarContent = useMemo(() => (
        <div className="p-3 space-y-3">
          {historyBatches.map((msg) => {
            const isSelected = activeBatchMessage?.id === msg.id;
            let result: PdfExtractionResultType | null = null;
            try {
              if (msg.content) {
                const parsed = JSON.parse(msg.content);
                if (parsed.success !== undefined) result = parsed;
              }
            } catch {}

            return (
              <div
                key={msg.id}
                className={`group relative rounded-xl overflow-hidden border cursor-pointer transition-all flex flex-col gap-2 bg-slate-800/40 p-3 ${
                  isSelected 
                    ? 'ring-1 ring-indigo-500 border-transparent bg-slate-800' 
                    : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
                }`}
                onClick={() => {
                  setSelectedMsgId(msg.id);
                  if (window.innerWidth < 768) setIsMobileHistoryOpen(false);
                }}
              >
                {onDeleteMessage && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isSelected) setSelectedMsgId(null);
                      onDeleteMessage(msg.id);
                    }}
                    className="absolute top-2 right-2 p-1.5 rounded-lg bg-slate-900/80 text-slate-500 hover:text-red-400 hover:bg-red-900/30 opacity-0 group-hover:opacity-100 transition-all z-10"
                    title="删除此记录"
                  >
                    <Trash2 size={14} />
                  </button>
                )}

                <div className="flex items-center gap-2 pr-6">
                  {msg.isError ? (
                    <AlertCircle size={16} className="text-red-400" />
                  ) : result?.success ? (
                    <CheckCircle size={16} className="text-green-400" />
                  ) : (
                    <XCircle size={16} className="text-red-400" />
                  )}
                  <span className="text-xs font-medium text-slate-300 truncate">
                    {result?.templateName || (msg.isError ? '提取失败' : '未知模板')}
                  </span>
                </div>

                <p className="text-[10px] text-slate-500">
                  {new Date(msg.timestamp).toLocaleString([], { 
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
                  })}
                </p>

                {result?.success && result.data && (
                  <p className="text-[11px] text-slate-400 line-clamp-2">
                    {Object.keys(result.data).slice(0, 3).join(', ')}...
                  </p>
                )}
              </div>
            );
          })}

          {historyBatches.length === 0 && (
            <div className="text-center py-10 text-slate-600 text-xs italic">暂无提取历史</div>
          )}
        </div>
  ), [historyBatches, activeBatchMessage?.id, onDeleteMessage]);

  // ✅ 主区域：两栏布局（结果显示 + 参数面板）
  const mainContent = useMemo(() => (
    <div className="flex-1 flex flex-row h-full">
      {/* ========== 左侧：结果显示区域 ========== */}
      <div className="flex-1 w-full h-full overflow-y-auto relative custom-scrollbar bg-slate-950">
        {extractedData?.success && (
          <div className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur-sm border-b border-slate-800">
            <PdfResultToolbar viewMode={viewMode} setViewMode={setViewMode} result={extractedData} />
          </div>
        )}

        <div className="p-4 md:p-6">
          {loadingState !== 'idle' ? (
            <div className="flex flex-col items-center justify-center min-h-[400px] gap-6">
              <div className="relative">
                <div className="w-20 h-20 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
                <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-indigo-400 font-bold">PDF</div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-slate-200 font-medium text-lg">正在提取文档数据...</p>
                <p className="text-slate-500 text-sm">AI 正在分析您的 PDF 文件</p>
              </div>
            </div>
          ) : isBatchError || (extractedData && !extractedData.success) ? (
            <div className="flex items-center gap-3 p-4 bg-red-900/20 border border-red-900/30 rounded-lg mb-4">
              <AlertCircle size={20} className="text-red-400 flex-shrink-0" />
              <p className="text-sm text-red-300">
                {extractedData?.error || activeBatchMessage?.content || "提取失败，请重试"}
              </p>
            </div>
          ) : extractedData?.success ? (
            renderResultView()
          ) : (
            <PdfEmptyState />
          )}
        </div>
      </div>

      {/* ========== 右侧：参数面板 ========== */}
      <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
        {/* 头部 */}
        <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} className="text-indigo-400" />
            <span className="text-xs font-bold text-white">提取参数</span>
          </div>
          <button
            onClick={resetParams}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            title="重置为默认值"
          >
            <RotateCcw size={12} />
          </button>
        </div>

        {/* 参数滚动区 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
          {/* 模板选择 */}
          <div className="space-y-2">
            <span className="text-xs text-slate-300 font-medium">提取模板</span>
            <div className="grid grid-cols-2 gap-2">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => setSelectedTemplate(template.id)}
                  className={`p-2 rounded-lg text-xs font-medium transition-all flex flex-col items-center gap-1 ${
                    selectedTemplate === template.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  <span className="text-lg">{template.icon}</span>
                  <span>{template.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 模板描述 */}
          <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
            <p className="text-xs text-slate-400">
              {templates.find(t => t.id === selectedTemplate)?.description || '提取文档数据'}
            </p>
          </div>
        </div>

        {/* 底部固定区：附件预览 + 提示词 + 提取按钮 */}
        <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
          {/* 附件预览区 */}
          {activeAttachments.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {activeAttachments.map((att, idx) => (
                <div key={idx} className="relative group flex items-center gap-2 bg-slate-800 rounded-lg px-2 py-1">
                  <FileText size={14} className="text-indigo-400" />
                  <span className="text-xs text-slate-300 max-w-[100px] truncate">{att.name}</span>
                  <button
                    onClick={() => {
                      setActiveAttachments(activeAttachments.filter((_, i) => i !== idx));
                    }}
                    className="p-0.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
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
            placeholder={activeAttachments.length === 0 ? "请先上传 PDF 文件..." : "提取指令..."}
            className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
          />

          {/* 上传按钮 + 提取按钮 */}
          <div className="flex gap-2 items-center">
            {/* 上传按钮 */}
            <label className="p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg">
              <input
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const newAtt: Attachment = {
                      id: `att-${Date.now()}`,
                      name: file.name,
                      mimeType: file.type,
                      file: file,
                    };
                    setActiveAttachments([newAtt]);
                  }
                  e.target.value = '';
                }}
              />
              {activeAttachments.length === 0 ? (
                <FileText size={18} className="text-white" />
              ) : (
                <Paperclip size={18} className="text-white" />
              )}
            </label>

            {/* 提取按钮 */}
            <button
              onClick={handleGenerate}
              disabled={loadingState === 'loading' || activeAttachments.length === 0}
              className="flex-1 py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingState === 'loading' ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  提取中...
                </>
              ) : (
                <>
                  <Send size={18} />
                  {activeAttachments.length === 0 ? '请先上传 PDF' : '开始提取'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  ), [loadingState, isBatchError, extractedData, activeBatchMessage?.content, viewMode, renderResultView, templates, selectedTemplate, activeAttachments, prompt, handleKeyDown, handleGenerate, resetParams]);

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="提取历史"
      sidebarHeaderIcon={<Clock size={14} />}
      sidebarExtraHeader={sidebarExtraHeader}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};
