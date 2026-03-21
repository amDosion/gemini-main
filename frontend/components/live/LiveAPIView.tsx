import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Loader2, MessageSquare, Bot, User } from 'lucide-react';
import MessageItem from '../chat/MessageItem';
import { Message, Role } from '../../types/types';

interface LiveAPIViewProps {
  onSend: (message: string, agentId?: string) => void;
  onStop: () => void;
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  agentId?: string;
  availableAgents?: Array<{ id: string; name: string }>;
  onAgentChange?: (agentId: string) => void;
}

export const LiveAPIView: React.FC<LiveAPIViewProps> = ({
  onSend,
  onStop,
  messages,
  isLoading,
  isStreaming,
  agentId,
  availableAgents = [],
  onAgentChange
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim(), agentId);
    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* 头部：Agent 选择 */}
      {availableAgents.length > 0 && (
        <div className="flex items-center gap-2 p-3 border-b border-slate-700 bg-slate-800/50">
          <span className="text-xs text-slate-400">Agent:</span>
          <select
            value={agentId || ''}
            onChange={(e) => onAgentChange?.(e.target.value)}
            className="px-2 py-1 text-xs bg-slate-700 border border-slate-600 rounded text-slate-200 focus:outline-none focus:border-teal-500"
          >
            <option value="">默认 Agent</option>
            {availableAgents.map(agent => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500">
            <div className="text-center">
              <MessageSquare size={48} className="mx-auto mb-4 opacity-50" />
              <p className="text-sm">开始双向对话</p>
              <p className="text-xs mt-2 text-slate-600">支持实时交互和确认</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => {
              const isStreamingMsg = isStreaming && idx === messages.length - 1 && msg.role === Role.MODEL;
              return (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  isStreaming={isStreamingMsg}
                />
              );
            })}
            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 bg-slate-800/50 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-700/50">
                  <Loader2 size={16} className="animate-spin text-teal-400" />
                  <span className="text-sm text-slate-400">正在处理...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 输入区域 */}
      <div className="border-t border-slate-700 bg-slate-800/50 p-3">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500 resize-none"
              rows={1}
              style={{ minHeight: '40px', maxHeight: '120px' }}
              disabled={isLoading}
            />
          </div>
          
          {isStreaming ? (
            <button
              onClick={onStop}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <Square size={16} />
              <span className="text-sm">停止</span>
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <Send size={16} />
              <span className="text-sm">发送</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default LiveAPIView;
