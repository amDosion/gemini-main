
import React, { useState, useMemo } from 'react';
import { Plus, MessageSquare, X, Settings, Wand2, Crop, Expand, Video, Mic, Trash2, Edit2, Check, ChevronRight, FileText, Shirt, Search, Network } from 'lucide-react';
import { ChatSession, AppMode } from '../../types/types';
import { CacheIndicator } from '../common/CacheIndicator';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';
import { SearchInput } from '../common/SearchInput';

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
  // 缓存相关（可选）
  cacheStatus?: CacheStatusInfo;
  onRefreshSessions?: () => void;
}

const getModeIcon = (mode?: AppMode) => {
  switch (mode) {
    case 'chat':
      return MessageSquare;
    case 'image-gen':
      return Wand2;
    case 'image-chat-edit':
    case 'image-mask-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
      return Crop;
    case 'image-outpainting':
      return Expand;
    case 'video-gen':
      return Video;
    case 'audio-gen':
      return Mic;
    case 'pdf-extract':
      return FileText;
    case 'virtual-try-on':
      return Shirt;
    case 'deep-research':
      return Search;
    case 'multi-agent':
      return Network;
    default:
      return MessageSquare;
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
  cacheStatus,
  onRefreshSessions,
}) => {
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchInput, setSearchInput] = useState<string>('');

  // Filter sessions based on search query (only after search button clicked)
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const query = searchQuery.toLowerCase();
    return sessions.filter(session => 
      session.title.toLowerCase().includes(query)
    );
  }, [sessions, searchQuery]);

  const handleSearchInputChange = (value: string) => {
    setSearchInput(value);
  };

  const handleSearch = () => {
    setSearchQuery(searchInput);
  };

  const handleClearSearch = () => {
    setSearchInput('');
    setSearchQuery('');
  };

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeleteConfirmationId(sessionId);
  };

  const handleConfirmDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (onDeleteSession) {
      onDeleteSession(sessionId);
    }
    setDeleteConfirmationId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmationId(null);
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

      {/* Floating Expand Button - Only visible when sidebar is collapsed */}
      {!isOpen && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsOpen(true);
          }}
          className="fixed left-0 top-1/2 -translate-y-1/2 z-[100] p-3 bg-slate-900 hover:bg-indigo-600 border-r border-y border-slate-800 rounded-r-lg text-slate-400 hover:text-white transition-all shadow-lg hover:shadow-indigo-500/50 pointer-events-auto"
          title="Expand Sidebar"
        >
          <ChevronRight size={20} className="text-white" />
        </button>
      )}

      {/* Sidebar Content */}
      <div className={`fixed inset-y-0 left-0 z-50 w-72 bg-slate-900 border-r border-slate-800 transform transition-transform duration-300 ease-in-out md:relative ${isOpen ? 'translate-x-0' : '-translate-x-full md:hidden'
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

          {/* New Chat Button & Search Input */}
          <div className="px-4 mb-4 flex items-center gap-2">
            {/* New Chat Button - Icon Only */}
            <button
              onClick={() => {
                setSearchInput('');
                setSearchQuery('');
                onNewChat();
                if (window.innerWidth < 768) setIsOpen(false);
              }}
              className="flex-shrink-0 p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all shadow-lg shadow-indigo-900/20 group"
              title="New Chat"
            >
              <Plus size={20} className="group-hover:rotate-90 transition-transform" />
            </button>

            {/* Search Input */}
            <SearchInput
              value={searchInput}
              onChange={handleSearchInputChange}
              onSearch={handleSearch}
              onClear={handleClearSearch}
              placeholder="Search conversations..."
              className="flex-1"
            />
          </div>

          {/* Session List */}
          <div className="flex-1 overflow-y-auto px-3 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
            <div className="flex items-center justify-between px-4 mb-2">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                History{searchQuery ? ` (${filteredSessions.length})` : ''}
              </h3>
              {cacheStatus && (
                <CacheIndicator
                  status={cacheStatus}
                  onRefresh={onRefreshSessions}
                  showTimestamp={false}
                />
              )}
            </div>
            {filteredSessions.map((session) => {
              const ModeIcon = getModeIcon(session.mode);
              const isHovered = hoveredSessionId === session.id || deleteConfirmationId === session.id;
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
                        id={`edit-session-title-${session.id}`}
                        name={`edit-session-title-${session.id}`}
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
                          {deleteConfirmationId === session.id ? (
                            // 删除确认模式 - 带背景的内联确认
                            <div className="flex items-center bg-slate-950 border border-red-700/60 rounded-lg px-2 py-1 gap-1.5 shadow-lg shadow-red-900/30 animate-[fadeIn_0.15s_ease-out]">
                              <Trash2 size={14} className="text-red-400" />
                              <span className="text-xs text-red-300 font-medium whitespace-nowrap">Delete?</span>
                              <button
                                onClick={(e) => handleConfirmDelete(e, session.id)}
                                className="px-2 py-0.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium transition-colors"
                              >
                                Yes
                              </button>
                              <button
                                onClick={handleCancelDelete}
                                className="px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs font-medium transition-colors"
                              >
                                No
                              </button>
                            </div>
                          ) : (
                            // 正常操作按钮
                            <>
                              {onUpdateSessionTitle && (
                                <button
                                  onClick={(e) => handleStartEdit(e, session.id, session.title)}
                                  className="p-1.5 rounded bg-slate-800 hover:bg-indigo-600 text-indigo-400 hover:text-white transition-colors border border-slate-700"
                                  title="编辑标题"
                                >
                                  <Edit2 size={14} />
                                </button>
                              )}
                              {onDeleteSession && (
                                <button
                                  onClick={(e) => handleDeleteSession(e, session.id)}
                                  className="p-1.5 rounded bg-slate-800 hover:bg-red-600 text-red-400 hover:text-white transition-colors border border-slate-700"
                                  title="删除会话"
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}

            {sessions.length === 0 ? (
              <div className="text-center text-slate-600 text-sm py-10 italic">
                No history yet.
              </div>
            ) : filteredSessions.length === 0 && (
              <div className="text-center text-slate-600 text-sm py-10 italic">
                No matching conversations.
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-800 bg-slate-900">
            <button
              onClick={() => {
                onOpenSettings();
                if (window.innerWidth < 768) setIsOpen(false);
              }}
              className="w-full flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-sm"
            >
              <Settings size={18} />
              <span>Setting</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
