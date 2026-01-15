/**
 * Execution Log Panel Component
 * 
 * Displays execution logs with filtering and export capabilities:
 * - Timestamp + Node ID + Message display
 * - Log level filtering (info/warn/error)
 * - Log export functionality
 * - Auto-scroll to latest logs
 */

import React, { useState, useRef, useEffect } from 'react';
import { Download, Filter, X, Info, AlertTriangle, XCircle } from 'lucide-react';

export type LogLevel = 'info' | 'warn' | 'error';

export interface LogEntry {
  id: string;
  timestamp: number;
  nodeId: string;
  nodeName: string;
  level: LogLevel;
  message: string;
}

interface ExecutionLogPanelProps {
  logs: LogEntry[];
  isOpen: boolean;
  onClose: () => void;
}

// Log level configuration
const logLevelConfig: Record<LogLevel, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  color: string;
  bgColor: string;
}> = {
  info: {
    icon: Info,
    label: '信息',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50'
  },
  warn: {
    icon: AlertTriangle,
    label: '警告',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50'
  },
  error: {
    icon: XCircle,
    label: '错误',
    color: 'text-red-600',
    bgColor: 'bg-red-50'
  }
};

export const ExecutionLogPanel: React.FC<ExecutionLogPanelProps> = ({
  logs,
  isOpen,
  onClose
}) => {
  const [selectedLevels, setSelectedLevels] = useState<Set<LogLevel>>(
    new Set(['info', 'warn', 'error'])
  );
  const [showFilter, setShowFilter] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const toggleLevel = (level: LogLevel) => {
    const newLevels = new Set(selectedLevels);
    if (newLevels.has(level)) {
      newLevels.delete(level);
    } else {
      newLevels.add(level);
    }
    setSelectedLevels(newLevels);
  };

  const filteredLogs = logs.filter(log => selectedLevels.has(log.level));

  const handleExport = () => {
    const logText = filteredLogs
      .map(log => {
        const timestamp = new Date(log.timestamp).toLocaleString();
        return `[${timestamp}] [${log.level.toUpperCase()}] [${log.nodeName}] ${log.message}`;
      })
      .join('\n');

    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-logs-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-10">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-800">执行日志</h3>
          <span className="text-xs text-gray-500">
            {filteredLogs.length} / {logs.length} 条
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Filter Button */}
          <button
            onClick={() => setShowFilter(!showFilter)}
            className={`p-1.5 rounded transition-colors ${
              showFilter ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-100 text-gray-600'
            }`}
            aria-label="过滤日志"
          >
            <Filter size={16} />
          </button>
          {/* Export Button */}
          <button
            onClick={handleExport}
            className="p-1.5 hover:bg-gray-100 rounded transition-colors text-gray-600"
            aria-label="导出日志"
            disabled={filteredLogs.length === 0}
          >
            <Download size={16} />
          </button>
          {/* Close Button */}
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-100 rounded transition-colors text-gray-600"
            aria-label="关闭日志面板"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilter && (
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-gray-600">日志级别:</span>
            {(Object.keys(logLevelConfig) as LogLevel[]).map(level => {
              const config = logLevelConfig[level];
              const LevelIcon = config.icon;
              const isSelected = selectedLevels.has(level);
              
              return (
                <button
                  key={level}
                  onClick={() => toggleLevel(level)}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                    isSelected
                      ? `${config.bgColor} ${config.color} font-medium`
                      : 'bg-white text-gray-400 hover:bg-gray-100'
                  }`}
                >
                  <LevelIcon size={12} />
                  {config.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Log Content */}
      <div
        ref={logContainerRef}
        className="h-[300px] overflow-y-auto p-4 space-y-2 font-mono text-xs"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            {logs.length === 0 ? '暂无日志' : '没有符合筛选条件的日志'}
          </div>
        ) : (
          filteredLogs.map(log => {
            const config = logLevelConfig[log.level];
            const LogIcon = config.icon;
            
            return (
              <div
                key={log.id}
                className={`flex items-start gap-2 p-2 rounded ${config.bgColor}`}
              >
                <LogIcon size={14} className={`${config.color} mt-0.5 flex-shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-gray-500">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span className={`font-medium ${config.color}`}>
                      [{log.nodeName}]
                    </span>
                  </div>
                  <div className="text-gray-700 break-words">
                    {log.message}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
