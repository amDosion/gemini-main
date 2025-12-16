
import React from 'react';
import { PdfExtractionResult as PdfExtractionResultType } from '../../../types';
import { FileText, CheckCircle, XCircle, ChevronDown, ChevronRight, Copy, Check, Download } from 'lucide-react';

interface PdfExtractionResultProps {
  result: PdfExtractionResultType;
  onClose?: () => void;
}

export const PdfExtractionResult: React.FC<PdfExtractionResultProps> = ({ result, onClose }) => {
  const [expandedSections, setExpandedSections] = React.useState<Set<string>>(new Set(['main']));
  const [copiedFields, setCopiedFields] = React.useState<Set<string>>(new Set());

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
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

  const renderValue = (value: any, key: string, depth: number = 0): React.ReactNode => {
    const fieldId = `${key}-${depth}`;
    const isCopied = copiedFields.has(fieldId);

    // Handle arrays
    if (Array.isArray(value)) {
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''}`}>
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => toggleSection(fieldId)}
              className="flex items-center gap-1 text-sm font-medium text-slate-300 hover:text-white"
            >
              {expandedSections.has(fieldId) ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
              {key} ({value.length} items)
            </button>
          </div>
          {expandedSections.has(fieldId) && (
            <div className="space-y-3">
              {value.map((item, index) => (
                <div
                  key={index}
                  className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3"
                >
                  <div className="text-xs font-medium text-slate-400 mb-2">
                    Item {index + 1}
                  </div>
                  {typeof item === 'object' && item !== null ? (
                    <div className="space-y-1">
                      {Object.entries(item).map(([itemKey, itemValue]) => (
                        <div key={itemKey} className="flex justify-between items-start">
                          <span className="text-sm text-slate-400">{itemKey}:</span>
                          <span className="text-sm text-white ml-2 text-right">
                            {String(itemValue)}
                          </span>
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

    // Handle objects
    if (typeof value === 'object' && value !== null) {
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''}`}>
          <div className="space-y-2">
            {Object.entries(value).map(([objKey, objValue]) => (
              <div key={objKey}>
                {renderValue(objValue, objKey, depth + 1)}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Handle primitive values
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
            {isCopied ? (
              <Check size={14} className="text-green-400" />
            ) : (
              <Copy size={14} className="text-slate-400" />
            )}
          </button>
        </div>
      </div>
    );
  };

  if (!result.success) {
    return (
      <div className="bg-gradient-to-br from-red-900/20 to-red-800/10 border border-red-500/30 rounded-xl p-6 shadow-xl animate-[fadeIn_0.3s_ease-out]">
        <div className="flex items-start gap-3">
          <XCircle className="text-red-400 flex-shrink-0 mt-1" size={24} />
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-red-200 mb-2">
              Extraction Failed
            </h3>
            <p className="text-sm text-red-300 mb-3">
              {result.error || 'Could not extract structured data from the PDF'}
            </p>
            {result.model_response && (
              <div className="bg-red-950/30 border border-red-500/20 rounded-lg p-3">
                <div className="text-xs font-medium text-red-400 mb-1">Model Response:</div>
                <div className="text-sm text-red-200">{result.model_response}</div>
              </div>
            )}
            {result.raw_text && (
              <div className="mt-3">
                <button
                  onClick={() => toggleSection('raw-text')}
                  className="flex items-center gap-1 text-sm text-red-300 hover:text-red-200"
                >
                  {expandedSections.has('raw-text') ? (
                    <ChevronDown size={16} />
                  ) : (
                    <ChevronRight size={16} />
                  )}
                  Show extracted text
                </button>
                {expandedSections.has('raw-text') && (
                  <div className="mt-2 bg-red-950/30 border border-red-500/20 rounded-lg p-3">
                    <pre className="text-xs text-red-200 whitespace-pre-wrap">
                      {result.raw_text}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-slate-800/80 to-slate-700/50 border border-slate-600/50 rounded-xl p-6 shadow-xl backdrop-blur-sm animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-start gap-3 mb-4">
        <CheckCircle className="text-green-400 flex-shrink-0 mt-1" size={24} />
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-lg font-semibold text-white">
              Extraction Successful
            </h3>
            {onClose && (
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <XCircle size={20} />
              </button>
            )}
          </div>
          <p className="text-sm text-slate-300">
            Template: <span className="font-medium text-indigo-400">{result.template_name}</span>
          </p>
        </div>
      </div>

      {/* Extracted Data */}
      <div className="bg-slate-900/40 border border-slate-600/30 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileText size={18} className="text-indigo-400" />
          <h4 className="text-sm font-semibold text-white">Extracted Data</h4>
        </div>

        <div className="space-y-2">
          {Object.entries(result.data).map(([key, value]) => (
            <div key={key}>
              {renderValue(value, key)}
            </div>
          ))}
        </div>
      </div>

      {/* Raw Text Preview (Optional) */}
      {result.raw_text && (
        <div className="mt-4">
          <button
            onClick={() => toggleSection('raw-preview')}
            className="flex items-center gap-1 text-sm text-slate-400 hover:text-white transition-colors"
          >
            {expandedSections.has('raw-preview') ? (
              <ChevronDown size={16} />
            ) : (
              <ChevronRight size={16} />
            )}
            Show original text preview
          </button>
          {expandedSections.has('raw-preview') && (
            <div className="mt-2 bg-slate-900/40 border border-slate-600/30 rounded-lg p-3 max-h-48 overflow-y-auto">
              <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
                {result.raw_text}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex justify-end gap-2">
        <button
          onClick={downloadAsJson}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-200 transition-all"
        >
          <Download size={14} />
          Download JSON
        </button>
        <button
          onClick={() => copyToClipboard(JSON.stringify(result.data, null, 2), 'json-all')}
          className="flex items-center gap-2 px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 rounded-lg text-sm text-indigo-300 hover:text-indigo-200 transition-all"
        >
          {copiedFields.has('json-all') ? (
            <>
              <Check size={14} />
              Copied!
            </>
          ) : (
            <>
              <Copy size={14} />
              Copy JSON
            </>
          )}
        </button>
      </div>
    </div>
  );
};
