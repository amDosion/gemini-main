
import React, { useState, useEffect } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig, PdfExtractionTemplate, PdfExtractionResult as PdfExtractionResultType } from '../../../types';
import { FileText, Upload, Server, AlertCircle, RefreshCw } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { PdfExtractionService } from '../../services/pdfExtractionService';
import { PdfExtractionResult } from '../pdf/PdfExtractionResult';

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
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);
  const [isCheckingBackend, setIsCheckingBackend] = useState(false);

  // Wrap onSend to include PDF extraction options
  const handlePdfSend = (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
    // Add PDF extraction template to options
    const pdfOptions = {
      ...options,
      pdfExtractTemplate: selectedTemplate
    };
    onSend(text, pdfOptions, attachments, mode);
  };

  // Check backend availability and fetch templates on mount
  useEffect(() => {
    checkBackendAndFetchTemplates();
  }, []);

  const checkBackendAndFetchTemplates = async (force = false) => {
    setIsCheckingBackend(true);
    try {
      if (force) {
          PdfExtractionService.resetAvailabilityCheck();
      }
      // Check if backend is available
      const isAvailable = await PdfExtractionService.checkAvailability(force);
      setBackendAvailable(isAvailable);
      
      // Fetch templates (will use defaults if backend unavailable)
      const templates = await PdfExtractionService.getTemplates();
      setTemplates(templates);
    } catch (error) {
      console.error('Error checking backend or fetching templates:', error);
      setBackendAvailable(false);
    } finally {
        setIsCheckingBackend(false);
    }
  };

  // Process messages to extract PDF results
  useEffect(() => {
    // Look for the latest model message
    const latestMessage = [...messages].reverse().find(m => m.role === Role.MODEL);
    
    if (latestMessage && latestMessage.content) {
      try {
        // Try to parse JSON from message content to see if it's a valid extraction result
        const parsed = JSON.parse(latestMessage.content);
        if (parsed.success !== undefined && (parsed.data || parsed.error)) {
          setExtractedData(parsed);
        } else {
            // New extraction starting or simple text
            if (loadingState === 'loading') setExtractedData(null);
        }
      } catch (e) {
        // Not JSON, likely streaming text or error text, ignore for structure view
      }
    } else if (loadingState === 'loading') {
        // Reset when new generation starts
        setExtractedData(null);
    }
  }, [messages, loadingState]);

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950">

      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-xl p-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 rounded-lg">
                <FileText className="text-indigo-400" size={24} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">PDF Structured Data Extraction</h1>
                <p className="text-sm text-slate-400">Extract fields automatically using Gemini Function Calling</p>
              </div>
            </div>
            
            {/* Backend Status Indicator */}
            {backendAvailable !== null && (
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
                backendAvailable 
                  ? 'bg-green-500/10 border-green-500/30 text-green-400' 
                  : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
              }`}>
                {backendAvailable ? (
                  <>
                    <Server size={16} />
                    <span className="text-xs font-medium">Backend Connected</span>
                  </>
                ) : (
                  <>
                    <AlertCircle size={16} />
                    <span className="text-xs font-medium">Local Mode</span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Template Selector */}
          <div className="mt-4">
            <label className="block text-sm font-medium text-slate-300 mb-2">Select Template</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => setSelectedTemplate(template.id)}
                  className={`p-4 rounded-xl border-2 transition-all ${
                    selectedTemplate === template.id
                      ? 'border-indigo-500 bg-indigo-500/10 shadow-lg shadow-indigo-500/20'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                >
                  <div className="text-3xl mb-2">{template.icon}</div>
                  <div className="text-sm font-medium text-white">{template.name}</div>
                  <div className="text-xs text-slate-400 mt-1">{template.description}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto p-6 custom-scrollbar">
        <div className="max-w-6xl mx-auto">

          {/* Backend Unavailable Warning */}
          {backendAvailable === false && (
            <div className="mb-6 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-start justify-between">
              <div className="flex items-start gap-3">
                <AlertCircle className="text-yellow-400 flex-shrink-0 mt-0.5" size={20} />
                <div>
                  <h4 className="text-sm font-semibold text-yellow-300 mb-1">
                    Backend Server Not Available
                  </h4>
                  <p className="text-xs text-yellow-200/80 mb-2">
                    The PDF extraction backend is not running. You can still use the chat interface, 
                    but PDF extraction features require the backend server.
                  </p>
                  <p className="text-xs text-yellow-200/60">
                    To enable PDF extraction, start the backend with: <code className="bg-yellow-900/30 px-1.5 py-0.5 rounded">pnpm run dev</code>
                  </p>
                </div>
              </div>
              <button 
                onClick={() => checkBackendAndFetchTemplates(true)}
                disabled={isCheckingBackend}
                className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600/20 hover:bg-yellow-600/30 text-yellow-200 rounded-lg text-xs font-medium transition-colors"
              >
                <RefreshCw size={14} className={isCheckingBackend ? "animate-spin" : ""} />
                Retry
              </button>
            </div>
          )}

          {/* Results Display */}
          {extractedData ? (
            <div className="space-y-4 mb-6">
               <PdfExtractionResult result={extractedData} />
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="inline-block p-4 bg-slate-900 rounded-full mb-4">
                <Upload className="text-slate-400" size={32} />
              </div>
              <h3 className="text-white font-semibold mb-2">Upload PDF to Extract</h3>
              <p className="text-slate-400 text-sm">
                {backendAvailable 
                  ? 'Select a template above, then attach a PDF file below.'
                  : 'Backend required for PDF extraction. Start the server to use this feature.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-800 bg-slate-900/50 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto p-4">
          <InputArea
            onSend={handlePdfSend}
            onStop={onStop}
            mode="pdf-extract"
            setMode={setAppMode}
            isLoading={loadingState === 'loading'}
            currentModel={activeModelConfig}
            hasActiveContext={false}
            providerId={providerId}
            initialPrompt="Extract details from this document."
          />
        </div>
      </div>
    </div>
  );
};
