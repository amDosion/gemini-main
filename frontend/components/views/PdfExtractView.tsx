import React, { useState, useEffect } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig, PdfExtractionTemplate, PdfExtractionResult as PdfExtractionResultType } from '../../../types';
import { Upload, FileSearch, FileText, CheckCircle, XCircle, ChevronDown, ChevronRight, Copy, Check, Download, Eye, Code, Table } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { PdfExtractionService } from '../../services/pdfExtractionService';
import ReactMarkdown from 'react-markdown';

// --- Shared Types ---
type ViewMode = 'table' | 'json' | 'preview';

interface PdfExtractViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  providerId?: string;
}

export const PdfExtractView: React.FC<PdfExtractViewProps> = ({
  messages,
  setAppMode,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  providerId
}) => {
  const [selectedTemplate, setSelectedTemplate] = useState<string>('invoice');
  const [templates, setTemplates] = useState<PdfExtractionTemplate[]>([]);
  const [extractedData, setExtractedData] = useState<PdfExtractionResultType | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('table');

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const fetchedTemplates = await PdfExtractionService.getTemplates();
        setTemplates(fetchedTemplates);
      } catch (error) {
        console.error('Error fetching templates:', error);
      }
    };
    fetchTemplates();
  }, []);

  useEffect(() => {
    const latestMessage = [...messages].reverse().find(m => m.role === Role.MODEL);

    if (latestMessage && latestMessage.content) {
      try {
        const parsed = JSON.parse(latestMessage.content);
        if (parsed.success !== undefined && (parsed.data || parsed.error)) {
          setExtractedData(parsed);
        } else {
          if (loadingState === 'loading') setExtractedData(null);
        }
      } catch (e) {
        // Not JSON
      }
    } else if (loadingState === 'loading') {
      setExtractedData(null);
    }
  }, [messages, loadingState]);

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950">

      {/* 1. Header Section */}
      {extractedData && (
        <PdfResultHeader
          result={extractedData}
          onClose={() => setExtractedData(null)}
        />
      )}

      {/* 2. Mode/Action Buttons (Toolbar) */}
      {extractedData && (
        <PdfResultToolbar
          viewMode={viewMode}
          setViewMode={setViewMode}
          result={extractedData}
        />
      )}

      {/* 3. Main Content Area (Scrollable) */}
      <div className="flex-1 overflow-auto custom-scrollbar relative flex flex-col">
        {extractedData ? (
          <PdfResultBody
            viewMode={viewMode}
            result={extractedData}
          />
        ) : (
          <EmptyState />
        )}
      </div>

      {/* 4. Input Area */}
      <div className="border-t border-slate-800 bg-slate-900/50 backdrop-blur-xl z-10">
        <div className="max-w-6xl mx-auto py-4 px-2 md:px-4">
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
        </div>
      </div>
    </div>
  );
};

// --- Sub-components (Merged from PdfExtractionResult.tsx) ---

const EmptyState = () => (
  <div className="flex-1 flex flex-col items-center justify-center text-center opacity-0 animate-[fadeIn_0.5s_ease-out_forwards] p-6">
    <div className="relative mb-8 group">
      <div className="absolute inset-0 bg-indigo-500/20 blur-xl rounded-full group-hover:bg-indigo-500/30 transition-all duration-500"></div>
      <div className="relative w-24 h-24 bg-slate-800/80 backdrop-blur-sm border border-slate-700 rounded-2xl flex items-center justify-center shadow-2xl rotate-3 group-hover:rotate-6 transition-transform duration-300">
        <FileSearch className="text-indigo-400" size={40} strokeWidth={1.5} />
      </div>
      <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-slate-800/90 backdrop-blur-md border border-slate-600 rounded-xl flex items-center justify-center shadow-xl -rotate-6 group-hover:-rotate-3 transition-transform duration-300">
        <Upload className="text-emerald-400" size={24} strokeWidth={2} />
      </div>
    </div>

    <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
      Intelligent PDF Extraction
    </h2>
    <p className="text-slate-400 max-w-md mx-auto text-base md:text-lg leading-relaxed">
      Upload a PDF document to automatically extract structured data using AI.
      Choose a template below to get started.
    </p>
  </div>
);

interface ResultComponentProps {
  result: PdfExtractionResultType;
  onClose?: () => void;
}

const PdfResultHeader: React.FC<ResultComponentProps> = ({ result, onClose }) => {
  if (!result.success) {
    return (
      <div className="flex items-start gap-3 p-4 bg-red-900/10 border-b border-red-500/20">
        <XCircle className="text-red-400 flex-shrink-0 mt-1" size={24} />
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-red-200">Extraction Failed</h3>
          <p className="text-sm text-red-300">{result.error || 'Could not extract structured data'}</p>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <XCircle size={20} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 p-4 bg-slate-900/50 border-b border-slate-800">
      <CheckCircle className="text-green-400 flex-shrink-0" size={24} />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Extraction Successful</h3>
        </div>
        <p className="text-sm text-slate-300">
          Template: <span className="font-medium text-indigo-400">{result.template_name}</span>
        </p>
      </div>
      {onClose && (
        <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
          <XCircle size={20} />
        </button>
      )}
    </div>
  );
};

interface PdfResultToolbarProps {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  result: PdfExtractionResultType;
}

const PdfResultToolbar: React.FC<PdfResultToolbarProps> = ({ viewMode, setViewMode, result }) => {
  const [copied, setCopied] = useState(false);

  const downloadAsJson = () => {
    if (!result.data) return;
    const dataStr = JSON.stringify(result.data, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `extracted-${result.template_type || 'data'}-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const previewHtml = () => {
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(`
        <html>
          <head><title>Print JSON</title></head>
          <body><pre style="white-space: pre-wrap; word-wrap: break-word;">${JSON.stringify(result.data, null, 2)}</pre></body>
        </html>
      `);
      printWindow.document.close();
    }
  };

  const copyJson = () => {
    if (!result.data) return;
    navigator.clipboard.writeText(JSON.stringify(result.data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!result.success) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 p-2 px-4 border-b border-slate-800 bg-slate-900/30">
      {/* View Mode Tabs */}
      <div className="flex bg-slate-800/50 rounded-lg p-1">
        <button
          onClick={() => setViewMode('table')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'table' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
        >
          <Table size={14} />
          Table
        </button>
        <button
          onClick={() => setViewMode('json')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'json' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
        >
          <Code size={14} />
          JSON
        </button>
        <button
          onClick={() => setViewMode('preview')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'preview' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
        >
          <Eye size={14} />
          Preview
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <ActionIcon onClick={previewHtml} icon={Eye} tooltip="Open in New Tab" />
        <ActionIcon onClick={downloadAsJson} icon={Download} tooltip="Download JSON" label="JSON" />

        <button
          onClick={copyJson}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 rounded-lg text-sm text-indigo-300 hover:text-indigo-200 transition-all ml-2"
          title="Copy Full JSON"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span className="hidden sm:inline">Copy JSON</span>
        </button>
      </div>
    </div>
  );
};

interface PdfResultBodyProps {
  viewMode: ViewMode;
  result: PdfExtractionResultType;
}

const PdfResultBody: React.FC<PdfResultBodyProps> = ({ viewMode, result }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['main']));
  const [copiedFields, setCopiedFields] = useState<Set<string>>(new Set());

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) newExpanded.delete(section);
    else newExpanded.add(section);
    setExpandedSections(newExpanded);
  };

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFields(new Set(copiedFields).add(fieldName));
    setTimeout(() => {
      setCopiedFields((prev) => {
        const newSet = new Set(prev);
        newSet.delete(fieldName);
        return newSet;
      });
    }, 2000);
  };

  const renderValue = (value: any, key: string, depth: number = 0): React.ReactNode => {
    const fieldId = `${key}-${depth}`;
    const isCopied = copiedFields.has(fieldId);

    if (Array.isArray(value)) {
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''}`}>
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => toggleSection(fieldId)}
              className="flex items-center gap-1 text-sm font-medium text-slate-300 hover:text-white"
            >
              {expandedSections.has(fieldId) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              {key} ({value.length} items)
            </button>
          </div>
          {expandedSections.has(fieldId) && (
            <div className="space-y-3">
              {value.map((item, index) => (
                <div key={index} className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
                  <div className="text-xs font-medium text-slate-400 mb-2">Item {index + 1}</div>
                  {typeof item === 'object' && item !== null ? (
                    <div className="space-y-1">
                      {Object.entries(item).map(([itemKey, itemValue]) => (
                        <div key={itemKey} className="flex justify-between items-start">
                          <span className="text-sm text-slate-400">{itemKey}:</span>
                          <span className="text-sm text-white ml-2 text-right">{String(itemValue)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-white">{String(item)}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (typeof value === 'object' && value !== null) {
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''}`}>
          <div className="space-y-2">
            {Object.entries(value).map(([objKey, objValue]) => (
              <div key={objKey}>{renderValue(objValue, objKey, depth + 1)}</div>
            ))}
          </div>
        </div>
      );
    }

    const stringValue = String(value);
    return (
      <div className="flex justify-between items-center gap-2 group py-1">
        <span className="text-sm font-medium text-slate-400">{key}:</span>
        <div className="flex items-center gap-2">
          <span className="text-sm text-white">{stringValue}</span>
          <button
            onClick={() => copyToClipboard(stringValue, fieldId)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-slate-600/50 rounded"
            title="Copy to clipboard"
          >
            {isCopied ? <Check size={14} className="text-green-400" /> : <Copy size={14} className="text-slate-400" />}
          </button>
        </div>
      </div>
    );
  };

  if (!result.success) {
    return (
      <div className="p-4">
        {/* Error already shown in header, but display raw details here if needed */}
        {result.model_response && (
          <div className="bg-red-950/30 border border-red-500/20 rounded-lg p-3 mb-3">
            <div className="text-xs font-medium text-red-400 mb-1">Model Response:</div>
            <div className="text-sm text-red-200">{result.model_response}</div>
          </div>
        )}
        {result.raw_text && (
          <div className="bg-slate-900/50 p-3 rounded">
            <div className="text-xs text-slate-500 mb-2">Raw Text</div>
            <pre className="text-xs text-red-200 whitespace-pre-wrap">{result.raw_text}</pre>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="w-full">
      {viewMode === 'table' && (
        <div className="space-y-2">
          {Object.entries(result.data).map(([key, value]) => (
            <div key={key}>{renderValue(value, key)}</div>
          ))}
        </div>
      )}

      {viewMode === 'json' && (
        <pre className="bg-slate-950/50 border border-slate-700/50 rounded-lg p-4 text-sm text-slate-300 overflow-x-auto font-mono">
          {JSON.stringify(result.data, null, 2)}
        </pre>
      )}

      {viewMode === 'preview' && (


        <div className="space-y-6">
          {Object.entries(result.data).map(([key, value]) => (
            <div key={key} className="border-b border-slate-800/50 pb-4 last:border-0 last:pb-0">
              <h3 className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-3">{key}</h3>
              {key.toLowerCase() === 'markdown' && typeof value === 'string' ? (
                <div className="text-slate-300 leading-relaxed markdown-body">
                  <ReactMarkdown
                    components={{
                      h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 text-white" {...props} />,
                      h2: ({ node, ...props }) => <h2 className="text-xl font-bold mb-3 text-white" {...props} />,
                      h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mb-2 text-white" {...props} />,
                      p: ({ node, ...props }) => <p className="mb-4 last:mb-0" {...props} />,
                      ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4 space-y-1" {...props} />,
                      ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-4 space-y-1" {...props} />,
                      li: ({ node, ...props }) => <li className="pl-1" {...props} />,
                      strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                      code: ({ node, ...props }) => <code className="bg-slate-800 px-1.5 py-0.5 rounded text-sm font-mono text-indigo-300" {...props} />,
                      pre: ({ node, ...props }) => <pre className="bg-slate-900/50 p-4 rounded-lg overflow-x-auto my-4 text-sm font-mono border border-slate-800" {...props} />,
                      blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-slate-600 pl-4 py-1 my-4 text-slate-400 italic" {...props} />,
                      a: ({ node, ...props }) => <a className="text-indigo-400 hover:text-indigo-300 underline" target="_blank" rel="noopener noreferrer" {...props} />,
                    }}
                  >
                    {value}
                  </ReactMarkdown>
                </div>
              ) : (
                renderValue(value, key)
              )}
            </div>
          ))}
        </div>

      )}
    </div>
  );
};

// Helper component for small action buttons
const ActionIcon = ({ onClick, icon: Icon, tooltip, label }: { onClick: () => void, icon: any, tooltip: string, label?: string }) => (
  <button
    onClick={onClick}
    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs text-slate-200 transition-all"
    title={tooltip}
  >
    <Icon size={14} />
    {label && <span>{label}</span>}
  </button>
);
