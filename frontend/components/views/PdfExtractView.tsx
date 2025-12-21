import React, { useState, useEffect, useMemo } from 'react';
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
import { CheckCircle, XCircle, Clock, AlertCircle, Trash2 } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { PdfExtractionService } from '../../services/pdfExtractionService';
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
  providerId,
  onDeleteMessage
}) => {
  const [selectedTemplate, setSelectedTemplate] = useState<string>('invoice');
  const [templates, setTemplates] = useState<PdfExtractionTemplate[]>(
    () => PdfExtractionService.getCachedTemplates()
  );
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    PdfExtractionService.getTemplates().then(fetchedTemplates => {
      if (isMounted && fetchedTemplates.length > 0) {
        setTemplates(fetchedTemplates);
      }
    }).catch(() => {});
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

  const renderResultView = () => {
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
  };


  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="提取历史"
      sidebarHeaderIcon={<Clock size={14} />}
      sidebarExtraHeader={
        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
          {historyBatches.length}
        </span>
      }
      sidebarContent={
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
                    {result?.template_name || (msg.isError ? '提取失败' : '未知模板')}
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
      }
      mainContent={
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
      }
      bottomContent={
        <InputArea
          onSend={onSend}
          onStop={onStop}
          mode="pdf-extract"
          setMode={setAppMode}
          isLoading={loadingState === 'loading'}
          currentModel={activeModelConfig}
          hasActiveContext={false}
          providerId={providerId}
          initialPrompt="Extract details from this document."
          pdfTemplates={templates}
          selectedPdfTemplate={selectedTemplate}
          onPdfTemplateChange={setSelectedTemplate}
        />
      }
    />
  );
};
