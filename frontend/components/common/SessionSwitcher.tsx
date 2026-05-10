/**
 * SessionSwitcher - 紧凑的会话切换器
 * 用于 Gen 模式的 sidebar 顶部，提供会话切换和新建对话功能
 * 切换会话时不改变当前模式
 */
import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  ChevronDown,
  MessageSquare,
  Wand2,
  Crop,
  Expand,
  Video,
  Mic,
  FileText,
  Shirt,
  Network,
  Trash2,
  Edit2,
  Check,
  X,
} from 'lucide-react';
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
  const {
    sessions,
    currentSessionId,
    onNewChat,
    onSelectSessionKeepMode,
    onDeleteSession,
    onUpdateSessionTitle,
  } = useSessionContext();
  const [isOpen, setIsOpen] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentSession = sessions.find(s => s.id === currentSessionId);

  const handleStartEdit = (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    setDeleteConfirmationId(null);
    setEditingSessionId(id);
    setEditingTitle(title);
  };

  const handleSaveEdit = (e: React.SyntheticEvent, id: string) => {
    e.stopPropagation();
    const nextTitle = editingTitle.trim();
    if (onUpdateSessionTitle && nextTitle) {
      onUpdateSessionTitle(id, nextTitle);
    }
    setEditingSessionId(null);
    setEditingTitle('');
  };

  const handleCancelEdit = (e?: React.SyntheticEvent) => {
    e?.stopPropagation();
    setEditingSessionId(null);
    setEditingTitle('');
  };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setEditingSessionId(null);
    setDeleteConfirmationId(id);
  };

  const handleConfirmDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    onDeleteSession?.(id);
    setDeleteConfirmationId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmationId(null);
  };

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
          title="New Session"
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
                const isEditing = editingSessionId === s.id;
                const isConfirmingDelete = deleteConfirmationId === s.id;
                return (
                  <div
                    key={s.id}
                    className={`group flex items-center gap-1.5 rounded-lg transition-colors ${
                      isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                    }`}
                  >
                    {isEditing ? (
                      <>
                        <Icon size={14} className="ml-3 text-indigo-400 shrink-0" />
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveEdit(e, s.id);
                            if (e.key === 'Escape') handleCancelEdit(e);
                          }}
                          className="min-w-0 flex-1 bg-slate-700 text-white text-xs px-2 py-1 rounded outline-none focus:ring-2 focus:ring-indigo-500"
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                        <button
                          onClick={(e) => handleSaveEdit(e, s.id)}
                          className="p-1 rounded hover:bg-green-600/20 text-green-400 transition-colors shrink-0"
                          title="Save"
                        >
                          <Check size={13} />
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="mr-1.5 p-1 rounded hover:bg-slate-600 text-slate-400 transition-colors shrink-0"
                          title="Cancel"
                        >
                          <X size={13} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => { onSelectSessionKeepMode(s.id); setIsOpen(false); }}
                          className="min-w-0 flex-1 flex items-center gap-2.5 px-3 py-2 rounded-lg text-left"
                        >
                          <Icon size={14} className={isActive ? 'text-indigo-400 shrink-0' : 'text-slate-500 shrink-0'} />
                          <span className="text-xs truncate flex-1">{s.title}</span>
                        </button>
                        {isConfirmingDelete ? (
                          <div className="mr-1.5 flex items-center bg-slate-950 border border-red-700/60 rounded-lg px-1.5 py-0.5 gap-1 shadow-lg shadow-red-900/30">
                            <Trash2 size={13} className="text-red-400 shrink-0" />
                            <span className="text-[11px] text-red-300 font-medium whitespace-nowrap">Delete?</span>
                            <button
                              onClick={(e) => handleConfirmDelete(e, s.id)}
                              className="px-1.5 py-0.5 bg-red-600 hover:bg-red-500 text-white rounded text-[11px] font-medium transition-colors"
                            >
                              Yes
                            </button>
                            <button
                              onClick={handleCancelDelete}
                              className="px-1.5 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-[11px] font-medium transition-colors"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <div className="mr-1.5 flex items-center gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity shrink-0">
                            {onUpdateSessionTitle && (
                              <button
                                onClick={(e) => handleStartEdit(e, s.id, s.title)}
                                className="p-1 rounded bg-slate-800 hover:bg-indigo-600 text-indigo-400 hover:text-white transition-colors border border-slate-700"
                                title="编辑标题"
                              >
                                <Edit2 size={13} />
                              </button>
                            )}
                            {onDeleteSession && (
                              <button
                                onClick={(e) => handleDeleteSession(e, s.id)}
                                className="p-1 rounded bg-slate-800 hover:bg-red-600 text-red-400 hover:text-white transition-colors border border-slate-700"
                                title="删除会话"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
