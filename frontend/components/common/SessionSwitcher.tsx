/**
 * SessionSwitcher - 紧凑的会话切换器
 * 用于 Gen 模式的 sidebar 顶部，提供会话切换和新建对话功能
 * 切换会话时不改变当前模式
 */
import React, { useState, useRef, useEffect } from 'react';
import { Plus, ChevronDown, MessageSquare, Wand2, Crop, Expand, Video, Mic, FileText, Shirt, Network } from 'lucide-react';
import { AppMode } from '../../types/types';
import { useSessionContext } from '../../contexts/SessionContext';

const getModeIcon = (mode?: AppMode) => {
  switch (mode) {
    case 'chat': return MessageSquare;
    case 'image-gen': return Wand2;
    case 'image-chat-edit':
    case 'image-mask-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext': return Crop;
    case 'image-outpainting': return Expand;
    case 'video-gen': return Video;
    case 'audio-gen': return Mic;
    case 'pdf-extract': return FileText;
    case 'virtual-try-on': return Shirt;
    case 'multi-agent': return Network;
    default: return MessageSquare;
  }
};

export const SessionSwitcher: React.FC = () => {
  const { sessions, currentSessionId, onNewChat, onSelectSessionKeepMode } = useSessionContext();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentSession = sessions.find(s => s.id === currentSessionId);

  // 点击外部关闭
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  return (
    <div ref={dropdownRef} className="relative px-3 py-2 border-b border-slate-800/50 shrink-0">
      {/* Label */}
      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Session</div>

      <div className="flex items-center gap-1.5">
        {/* 当前会话按钮 */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex-1 flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 text-left transition-colors min-w-0"
        >
          {currentSession ? (
            <>
              {React.createElement(getModeIcon(currentSession.mode), { size: 14, className: 'text-slate-500 shrink-0' })}
              <span className="text-xs text-slate-300 truncate flex-1">{currentSession.title}</span>
            </>
          ) : (
            <span className="text-xs text-slate-500 italic">No session</span>
          )}
          <ChevronDown size={12} className={`text-slate-500 shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {/* 新建对话按钮 */}
        <button
          onClick={() => { onNewChat(); setIsOpen(false); }}
          className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors shrink-0"
          title="New Chat"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* 下拉会话列表 */}
      {isOpen && (
        <div className="absolute left-2 right-2 top-full mt-1 z-50 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden ring-1 ring-black/50">
          <div className="max-h-[300px] overflow-y-auto custom-scrollbar p-1">
            {sessions.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500 italic">No sessions</div>
            ) : (
              sessions.slice(0, 20).map((s) => {
                const Icon = getModeIcon(s.mode);
                const isActive = s.id === currentSessionId;
                return (
                  <button
                    key={s.id}
                    onClick={() => { onSelectSessionKeepMode(s.id); setIsOpen(false); }}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors ${
                      isActive
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                    }`}
                  >
                    <Icon size={14} className={isActive ? 'text-indigo-400' : 'text-slate-500'} />
                    <span className="text-xs truncate flex-1">{s.title}</span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
