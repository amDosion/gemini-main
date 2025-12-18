
import React, { useState } from 'react';
import { Plus, MessageSquare, X, Settings, Wand2, Crop, Expand, Video, Mic, Trash2, Edit2, Check, UserCircle2 } from 'lucide-react';
import { ChatSession, AppMode } from '../../../types';
import { CacheIndicator } from '../common/CacheIndicator';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  sessions: ChatSession[];
  currentSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession?: (id: string) => void;
  onUpdateSessionTitle?: (id: string, newTitle: string) => void;
  onOpenSettings: () => void;
  isRightSidebarOpen: boolean;
  setIsRightSidebarOpen: (v: boolean) => void;
  // 缓存相关（可选）
  cacheStatus?: CacheStatusInfo;
  onRefreshSessions?: () => void;
}

const getModeIcon = (mode?: AppMode) => {
  switch (mode) {
    case 'image-gen': return Wand2;
    case 'image-edit': return Crop;
    case 'image-outpainting': return Expand;
    case 'video-gen': return Video;
    case 'audio-gen': return Mic;
    case 'chat':
    default: return MessageSquare;
  }
};

const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  setIsOpen,
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onUpdateSessionTitle,
  onOpenSettings,
  isRightSidebarOpen,
  setIsRightSidebarOpen,
  cacheStatus,
  onRefreshSessions,
}) => {
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Prevent session selection
    if (onDeleteSession && window.confirm('Are you sure you want to delete this session?')) {
      onDeleteSession(sessionId);
    }
  };

  const handleStartEdit = (e: React.MouseEvent, sessionId: string, currentTitle: string) => {
    e.stopPropagation(); // Prevent session selection
    setEditingSessionId(sessionId);
    setEditingTitle(currentTitle);
  };

  const handleSaveEdit = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Prevent session selection
    if (onUpdateSessionTitle && editingTitle.trim()) {
      onUpdateSessionTitle(sessionId, editingTitle.trim());
    }
    setEditingSessionId(null);
    setEditingTitle('');
  };

  const handleCancelEdit = () => {
    setEditingSessionId(null);
    setEditingTitle('');
  };
  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar Content */}
      <div className={`fixed inset-y-0 left-0 z-50 w-72 bg-slate-900 border-r border-slate-800 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}>
        <div className="flex flex-col h-full">

          {/* Header */}
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-2 font-bold text-xl tracking-tight text-white">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-500">Flux</span>
              <span>Chat</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="md:hidden text-slate-400 hover:text-white">
              <X size={24} />
            </button>
          </div>

          {/* New Chat Button */}
          <div className="px-4 mb-4">
            <button
              onClick={() => {
                onNewChat();
                if (window.innerWidth < 768) setIsOpen(false);
              }}
              className="w-full flex items-center gap-3 px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-lg shadow-indigo-900/20 group"
            >
              <Plus size={20} className="group-hover:rotate-90 transition-transform" />
              <span className="font-medium">New Chat</span>
            </button>
          </div>

          {/* Session List */}
          <div className="flex-1 overflow-y-auto px-3 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
            <div className="flex items-center justify-between px-4 mb-2">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">History</h3>
              {cacheStatus && (
                <CacheIndicator 
                  status={cacheStatus} 
                  onRefresh={onRefreshSessions}
                  showTimestamp={false}
                />
              )}
            </div>
            {sessions.map((session) => {
              const ModeIcon = getModeIcon(session.mode);
              const isHovered = hoveredSessionId === session.id;
              const isEditing = editingSessionId === session.id;
              return (
                <div
                  key={session.id}
                  className="group relative"
                  onMouseEnter={() => editingSessionId === null && setHoveredSessionId(session.id)}
                  onMouseLeave={() => setHoveredSessionId(null)}
                >
                  {isEditing ? (
                    // 编辑模式
                    <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 rounded-lg border border-indigo-500">
                      <ModeIcon size={16} className="text-indigo-400 flex-shrink-0" />
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleSaveEdit(e as any, session.id);
                          } else if (e.key === 'Escape') {
                            handleCancelEdit();
                          }
                        }}
                        className="flex-1 bg-slate-700 text-white text-sm px-2 py-1 rounded outline-none focus:ring-2 focus:ring-indigo-500"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                      <button
                        onClick={(e) => handleSaveEdit(e, session.id)}
                        className="p-1 rounded hover:bg-green-600/20 text-green-400 transition-colors flex-shrink-0"
                        title="Save"
                      >
                        <Check size={14} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancelEdit();
                        }}
                        className="p-1 rounded hover:bg-slate-600 text-slate-400 transition-colors flex-shrink-0"
                        title="Cancel"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    // 正常显示模式
                    <>
                      <button
                        onClick={() => {
                          onSelectSession(session.id);
                          if (window.innerWidth < 768) setIsOpen(false);
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors text-left ${currentSessionId === session.id
                          ? 'bg-slate-800 text-white border border-slate-700'
                          : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                          }`}
                      >
                        <ModeIcon size={16} className={currentSessionId === session.id ? 'text-indigo-400' : 'text-slate-500'} />
                        <span className="truncate flex-1">{session.title}</span>
                      </button>
                      {isHovered && (
                        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                          {onUpdateSessionTitle && (
                            <button
                              onClick={(e) => handleStartEdit(e, session.id, session.title)}
                              className="p-1.5 rounded hover:bg-indigo-600/20 text-slate-500 hover:text-indigo-400 transition-colors"
                              title="Edit title"
                            >
                              <Edit2 size={14} />
                            </button>
                          )}
                          {onDeleteSession && (
                            <button
                              onClick={(e) => handleDeleteSession(e, session.id)}
                              className="p-1.5 rounded hover:bg-red-600/20 text-slate-500 hover:text-red-400 transition-colors"
                              title="Delete session"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}

            {sessions.length === 0 && (
              <div className="text-center text-slate-600 text-sm py-10 italic">
                No history yet.
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-800 bg-slate-900 flex items-center gap-2">
            <button
              onClick={() => {
                onOpenSettings();
                if (window.innerWidth < 768) setIsOpen(false);
              }}
              className="flex-1 flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-sm"
            >
              <Settings size={18} />
              <span>Settings</span>
            </button>
            <button
              type="button"
              onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
              className={`p-3 rounded-lg transition-colors shrink-0 ${isRightSidebarOpen ? 'bg-indigo-500/20 text-indigo-400' : 'hover:bg-slate-800 text-slate-400 hover:text-white'}`}
              title="AI Persona & Roles"
            >
              <UserCircle2 size={20} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
