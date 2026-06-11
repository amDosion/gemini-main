import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/solid';
import { CachedImage } from '../common/CachedImage';

interface ToolCall {
  type: string;
  name: string;
  arguments: Record<string, unknown>;
  id: string;
}

interface ToolResult {
  name: string;
  callId: string;
  result: unknown;
  error?: string;
  screenshot?: string;
  screenshotUrl?: string;
}

interface ToolCallDisplayProps {
  toolCall: ToolCall;
  toolResult?: ToolResult;
  isExecuting?: boolean;
}

const TOOL_ICON_LABELS: Record<string, string> = {
  function_call: 'FC',
  google_search: 'GS',
  code_execution: 'CE',
  url_context: 'UC',
  mcp_server: 'MS',
};

const safeStringify = (obj: unknown): string => {
  try {
    return JSON.stringify(obj, null, 2);
  } catch (error) {
    return `[Unable to display: ${error instanceof Error ? error.message : 'Unknown error'}]`;
  }
};

const ToolCallDisplay: React.FC<ToolCallDisplayProps> = ({ toolCall, toolResult, isExecuting }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const contentId = `tool-content-${toolCall.id}`;

  const renderResult = () => {
    if (isExecuting) {
      return <div className="text-gray-400">Executing...</div>;
    }

    if (toolResult?.error) {
      return <div className="text-red-500">Error: {toolResult.error}</div>;
    }

    if (toolResult) {
      const { screenshot } = toolResult;
      const screenshotSrc =
        toolResult.screenshotUrl ||
        (screenshot
          ? screenshot.startsWith('data:')
            ? screenshot
            : `data:image/png;base64,${screenshot}`
          : null);

      return (
        <div className="space-y-2">
          <pre className="bg-gray-800 p-2 rounded overflow-x-auto text-sm">
            {safeStringify(toolResult.result)}
          </pre>
          {screenshotSrc && (
            <div className="rounded border border-gray-700 overflow-hidden">
              <CachedImage
                source={{ url: screenshotSrc, name: `${toolResult.name} screenshot` }}
                src={screenshotSrc}
                alt={`${toolResult.name} screenshot`}
                className="w-full h-auto max-h-64 object-contain bg-black"
              />
            </div>
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 my-2">
      <button
        type="button"
        className="flex items-center justify-between w-full text-left"
        aria-expanded={isExpanded}
        aria-controls={contentId}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center min-w-0">
          <div className="bg-indigo-600 text-white rounded-full w-6 h-6 flex-shrink-0 flex items-center justify-center text-xs font-bold mr-2">
            {TOOL_ICON_LABELS[toolCall.type] ?? 'TL'}
          </div>
          <span className="font-semibold text-gray-300 truncate">{toolCall.name}</span>
        </div>
        <div className="flex items-center flex-shrink-0 ml-2">
          {isExecuting && (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-400 mr-2"></div>
          )}
          {isExpanded ? (
            <ChevronDownIcon className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronRightIcon className="h-5 w-5 text-gray-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div id={contentId} className="mt-3 space-y-3">
          <div>
            <h4 className="text-sm font-semibold text-gray-400 mb-1">Parameters</h4>
            <pre className="bg-gray-800 p-2 rounded overflow-x-auto text-sm">
              {safeStringify(toolCall.arguments)}
            </pre>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-400 mb-1">Result</h4>
            {renderResult()}
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolCallDisplay;
