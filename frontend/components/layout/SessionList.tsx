/**
 * SessionList - 可复用的会话列表组件
 * 从 Sidebar 中抽取的核心逻辑，用于 GenViewLayout 的 sidebar slot
 */
import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  Plus, MessageSquare, X, Wand2, Crop, Expand, Video, Mic,
  Trash2, Edit2, Check, ChevronRight, FileText, Shirt, Network
} from 'lucide-react';
import { ChatSession, AppMode } from '../../types/types';
import { CacheIndicator } from '../common/CacheIndicator';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';
import { SearchInput } from '../common/SearchInput';
import { LoadingSpinner } from '../common/LoadingSpinner';

export interface SessionListProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession?: (id: string) => void;
  onUpdateSessionTitle?: (id: string, newTitle: string) => void;
  cacheStatus?: CacheStatusInfo;
  onRefreshSessions?: () => void;
  hasMoreSessions?: boolean;
  isLoadingMore?: boolean;
  loadMoreSessions?: () => void;
  /** 可选：选中会话后的额外回调（如移动端关闭侧边栏） */
  onSessionSelected?: () => void;
}

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

export const SessionList: React.FC<SessionListProps> = ({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onUpdateSessionTitle,
  cacheStatus,
  onRefreshSessions,
  hasMoreSessions = false,
  isLoadingMore = false,
  loadMoreSessions,
  onSessionSelected,
}) => {
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter(s => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  const handleSearch = () => setSearchQuery(searchInput);
  const handleClearSearch = () => { setSearchInput(''); setSearchQuery(''); };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
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
  const handleStartEdit = (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    setEditingSessionId(id);
    setEditingTitle(title);
  };
  const handleSaveEdit = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (onUpdateSessionTitle && editingTitle.trim()) {
      onUpdateSessionTitle(id, editingTitle.trim());
    }
    setEditingSessionId(null);
    setEditingTitle('');
  };
  const handleCancelEdit = () => {
    setEditingSessionId(null);
    setEditingTitle('');
  };

  // 滚动加载
  useEffect(() => {
    const el = listRef.current;
    if (!el || !hasMoreSessions || isLoadingMore || !loadMoreSessions) return;
    const handleScroll = () => {
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 100) {
        loadMoreSessions();
      }
    };
    el.addEventListener('scroll', handleScroll);
    return () => el.removeEventListener('scroll', handleScroll);
  }, [hasMoreSessions, isLoadingMore, loadMoreSessions]);

  return (
    <div className="flex flex-col h-full">
      {/* New Chat + Search */}
      <div className="px-3 py-2 flex items-center gap-2 shrink-0">
        <button
          onClick={() => {
            setSearchInput(''); setSearchQuery('');
            onNewChat();
            onSessionSelected?.();
          }}
          className="flex-shrink-0 p-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all shadow-lg shadow-indigo-900/20 group"
          title="New Chat"
        >
          <Plus size={18} className="group-hover:rotate-90 transition-transform" />
        </button>
        <SearchInput
          value={searchInput}
          onChange={setSearchInput}
          onSearch={handleSearch}
          onClear={handleClearSearch}
          placeholder="Search..."
          className="flex-1"
        />
      </div>

      {/* Session List */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-2 space-y-1 custom-scrollbar">
        <div className="flex items-center justify-between px-3 mb-1">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            History{searchQuery ? ` (${filteredSessions.length})` : ''}
          </h3>
          {cacheStatus && (
            <CacheIndicator status={cacheStatus} onRefresh={onRefreshSessions} showTimestamp={false} />
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
              onMouseEnter={() => !editingSessionId && setHoveredSessionId(session.id)}
              onMouseLeave={() => setHoveredSessionId(null)}
            >
              {isEditing ? (
                <div className="flex items-center gap-2 px-3 py-2.5 bg-slate-800 rounded-lg border border-indigo-500">
                  <ModeIcon size={16} className="text-indigo-400 flex-shrink-0" />
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveEdit(e as any, session.id);
                      else if (e.key === 'Escape') handleCancelEdit();
                    }}
                    className="flex-1 bg-slate-700 text-white text-sm px-2 py-1 rounded outline-none focus:ring-2 focus:ring-indigo-500"
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                  <button onClick={(e) => handleSaveEdit(e, session.id)} className="p-1 rounded hover:bg-green-600/20 text-green-400 transition-colors flex-shrink-0" title="Save">
                    <Check size={14} />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); handleCancelEdit(); }} className="p-1 rounded hover:bg-slate-600 text-slate-400 transition-colors flex-shrink-0" title="Cancel">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => {
                      onSelectSession(session.id);
                      onSessionSelected?.();
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left ${
                      currentSessionId === session.id
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
                        <div className="flex items-center bg-slate-950 border border-red-700/60 rounded-lg px-2 py-1 gap-1.5 shadow-lg shadow-red-900/30 animate-[fadeIn_0.15s_ease-out]">
                          <Trash2 size={14} className="text-red-400" />
                          <span className="text-xs text-red-300 font-medium whitespace-nowrap">Delete?</span>
                          <button onClick={(e) => handleConfirmDelete(e, session.id)} className="px-2 py-0.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium transition-colors">Yes</button>
                          <button onClick={handleCancelDelete} className="px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs font-medium transition-colors">No</button>
                        </div>
                      ) : (
                        <>
                          {onUpdateSessionTitle && (
                            <button onClick={(e) => handleStartEdit(e, session.id, session.title)} className="p-1.5 rounded bg-slate-800 hover:bg-indigo-600 text-indigo-400 hover:text-white transition-colors border border-slate-700" title="编辑标题">
                              <Edit2 size={14} />
                            </button>
                          )}
                          {onDeleteSession && (
                            <button onClick={(e) => handleDeleteSession(e, session.id)} className="p-1.5 rounded bg-slate-800 hover:bg-red-600 text-red-400 hover:text-white transition-colors border border-slate-700" title="删除会话">
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
          <div className="text-center text-slate-600 text-sm py-10 italic">No history yet.</div>
        ) : filteredSessions.length === 0 && (
          <div className="text-center text-slate-600 text-sm py-10 italic">No matching conversations.</div>
        )}

        {!searchQuery && hasMoreSessions && (
          <div className="py-4 text-center">
            {isLoadingMore ? <LoadingSpinner fullscreen={false} showMessage={false} className="min-h-0" /> : (
              <button onClick={loadMoreSessions} className="text-xs text-slate-500 hover:text-slate-400 transition-colors">加载更多会话...</button>
            )}
          </div>
        )}
        {!searchQuery && !hasMoreSessions && sessions.length > 0 && (
          <div className="py-4 text-center text-xs text-slate-600">已加载全部会话</div>
        )}
      </div>
    </div>
  );
};
