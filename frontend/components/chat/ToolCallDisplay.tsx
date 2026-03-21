import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/solid';

interface ToolCall {
  type: string;
  name: string;
  arguments: any;
  id: string;
}

interface ToolResult {
  name: string;
  callId: string;
  result: any;
  error?: string;
  screenshot?: string;
  screenshotUrl?: string;
}

interface ToolCallDisplayProps {
  toolCall: ToolCall;
  toolResult?: ToolResult;
  isExecuting?: boolean;
}

const ToolCallDisplay: React.FC<ToolCallDisplayProps> = ({ toolCall, toolResult, isExecuting }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const renderToolIcon = () => {
    switch (toolCall.type) {
      case 'function_call':
        return 'FC';
      case 'google_search':
        return 'GS';
      case 'code_execution':
        return 'CE';
      case 'url_context':
        return 'UC';
      case 'mcp_server':
        return 'MS';
      default:
        return 'TL';
    }
  };

  const safeStringify = (obj: any): string => {
    try {
      return JSON.stringify(obj, null, 2);
    } catch (error) {
      return `[Unable to display: ${error instanceof Error ? error.message : 'Unknown error'}]`;
    }
  };

  const renderResult = () => {
    if (isExecuting) {
      return <div className="text-gray-400">Executing...</div>;
    }

    if (toolResult?.error) {
      return <div className="text-red-500">Error: {toolResult.error}</div>;
    }

    if (toolResult) {
      const screenshotSrc = toolResult.screenshotUrl
        ? toolResult.screenshotUrl
        : (toolResult.screenshot
            ? (toolResult.screenshot.startsWith('data:')
                ? toolResult.screenshot
                : `data:image/png;base64,${toolResult.screenshot}`)
            : null);

      return (
        <div className="space-y-2">
          <pre className="bg-gray-800 p-2 rounded overflow-x-auto text-sm">
            {safeStringify(toolResult.result)}
          </pre>
          {screenshotSrc && (
            <div className="rounded border border-gray-700 overflow-hidden">
              <img
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
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center min-w-0">
          <div className="bg-indigo-600 text-white rounded-full w-6 h-6 flex-shrink-0 flex items-center justify-center text-xs font-bold mr-2">
            {renderToolIcon()}
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
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-3">
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
