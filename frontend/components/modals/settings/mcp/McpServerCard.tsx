/**
 * MCP Server 单个 Card（顶部菜单 + 工具列表 + 调用 Dialog）。
 *
 * 1:1 抽离自 `McpTab.tsx` L659-946 cards.map render
 * （JIRA-frontend-deep-architecture-split.md #7 Step 2）。
 */

import React from 'react';
import { MoreHorizontal, RefreshCcw, Pencil, Play, Trash2, ExternalLink } from 'lucide-react';
import type { ServerCard, ServerToolsState, ServerInvokeState } from '../mcpTabHelpers';
import { TOOL_PREVIEW_COUNT } from '../mcpTabHelpers';
import { openSafeUrlInNewTab } from '../../../../utils/safeOpen';

export interface McpServerCardProps {
  card: ServerCard;
  openMenuKey: string | null;
  setOpenMenuKey: React.Dispatch<React.SetStateAction<string | null>>;
  toolsState: ServerToolsState | undefined;
  invokeState: ServerInvokeState | undefined;
  expandedToolsMap: Record<string, boolean>;
  setExpandedToolsMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  loadServerTools: (serverKey: string, force?: boolean) => Promise<void>;
  openToolInvoke: (
    serverKey: string,
    tools: Array<{ name: string; description?: string }>
  ) => Promise<void>;
  closeToolInvoke: (serverKey: string) => void;
  openEditDialog: (card: ServerCard) => void;
  handleDeleteClick: (key: string) => void;
  updateInvokeState: (serverKey: string, patch: Partial<ServerInvokeState>) => void;
  runToolInvoke: (serverKey: string) => Promise<void>;
}

export const McpServerCard: React.FC<McpServerCardProps> = ({
  card,
  openMenuKey,
  setOpenMenuKey,
  toolsState,
  invokeState,
  expandedToolsMap,
  setExpandedToolsMap,
  loadServerTools,
  openToolInvoke,
  closeToolInvoke,
  openEditDialog,
  handleDeleteClick,
  updateInvokeState,
  runToolInvoke,
}) => {
  const isMenuOpen = openMenuKey === card.key;
  const tools = toolsState?.tools || [];
  const isToolsExpanded = !!expandedToolsMap[card.key];
  const visibleTools = isToolsExpanded ? tools : tools.slice(0, TOOL_PREVIEW_COUNT);
  const hiddenToolsCount = Math.max(0, tools.length - TOOL_PREVIEW_COUNT);
  const isToolsLoaded = !!toolsState?.loaded;
  const isToolsLoading = !!toolsState?.loading;
  const statusLabel = !card.enabled ? 'Disabled' : card.valid ? 'Ready' : 'Invalid';
  const statusClass = !card.enabled
    ? 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    : card.valid
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
      : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

  return (
    <div className="group rounded-xl border bg-slate-900/50 border-slate-800 hover:border-slate-700 transition-all p-4 md:p-5 h-full flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="text-sm md:text-base font-medium text-slate-200 truncate">{card.key}</h3>
          <div className="relative shrink-0" data-mcp-card-actions>
            <button
              type="button"
              onClick={() => setOpenMenuKey((prev) => (prev === card.key ? null : card.key))}
              className={`p-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-all ${
                isMenuOpen
                  ? 'opacity-100'
                  : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
              }`}
              title="Actions"
            >
              <MoreHorizontal size={14} />
            </button>

            {isMenuOpen && (
              <div className="absolute left-0 top-9 z-20 w-44 rounded-lg border border-slate-700 bg-slate-900 shadow-xl p-1">
                <button
                  type="button"
                  onClick={() => {
                    void loadServerTools(card.key, true);
                    setOpenMenuKey(null);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                >
                  <RefreshCcw size={13} />
                  <span>{isToolsLoaded ? 'Refresh tools' : 'Load tools'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    void openToolInvoke(card.key, tools);
                    setOpenMenuKey(null);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                >
                  <Play size={13} />
                  <span>Invoke tool</span>
                </button>

                {hiddenToolsCount > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setExpandedToolsMap((prev) => ({
                        ...prev,
                        [card.key]: !prev[card.key],
                      }));
                      setOpenMenuKey(null);
                    }}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                  >
                    <span>
                      {isToolsExpanded
                        ? 'Show less tools'
                        : `Show all tools (+${hiddenToolsCount})`}
                    </span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    openEditDialog(card);
                    setOpenMenuKey(null);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                >
                  <Pencil size={13} />
                  <span>Edit</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleDeleteClick(card.key)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30 rounded"
                >
                  <Trash2 size={13} />
                  <span>Delete</span>
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span className="px-1.5 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] font-medium rounded border border-indigo-500/20 uppercase">
            {card.transport}
          </span>
          <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${statusClass}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      <div className="text-xs text-slate-500 font-mono break-all">{card.summary}</div>

      {typeof card.config.introUrl === 'string' && card.config.introUrl.trim() && (
        <button
          type="button"
          onClick={() => openSafeUrlInNewTab(card.config.introUrl)}
          className="mt-2 inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 transition-colors text-left break-all"
          title={card.config.introUrl}
        >
          <ExternalLink size={12} />
          <span>{card.config.introUrl}</span>
        </button>
      )}

      <div className="mt-3 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Tools</div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => void loadServerTools(card.key, true)}
              disabled={isToolsLoading}
              className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800/70 px-2 py-1 text-[10px] text-slate-300 hover:text-white hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCcw size={10} className={isToolsLoading ? 'animate-spin' : ''} />
              <span>{isToolsLoaded ? 'Refresh' : 'Load'}</span>
            </button>
            <button
              type="button"
              onClick={() => void openToolInvoke(card.key, tools)}
              disabled={isToolsLoading}
              className="inline-flex items-center gap-1 rounded-md border border-indigo-500/40 bg-indigo-500/10 px-2 py-1 text-[10px] text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play size={10} />
              <span>Run</span>
            </button>
          </div>
        </div>
        {isToolsLoading && <div className="text-xs text-slate-500">Loading tools...</div>}
        {!isToolsLoading && !isToolsLoaded && (
          <div className="text-xs text-slate-500">
            Tools are loaded on demand to reduce startup overhead.
          </div>
        )}
        {!isToolsLoading && isToolsLoaded && toolsState?.cacheHit && (
          <div className="text-[10px] text-slate-500">Loaded from cache</div>
        )}
        {!isToolsLoading && isToolsLoaded && toolsState?.error && (
          <div className="text-xs text-amber-400">{toolsState.error}</div>
        )}
        {!isToolsLoading && isToolsLoaded && !toolsState?.error && tools.length === 0 && (
          <div className="text-xs text-slate-500">No tools exposed</div>
        )}
        {!isToolsLoading && isToolsLoaded && !toolsState?.error && tools.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {visibleTools.map((tool) => (
              <span
                key={tool.name}
                title={tool.description || tool.name}
                className="px-2 py-1 rounded-md border border-cyan-500/25 bg-cyan-500/10 text-cyan-200 text-[11px] font-mono"
              >
                {tool.name}
              </span>
            ))}
          </div>
        )}
        {invokeState?.open && (
          <div className="mt-2 rounded-lg border border-indigo-500/30 bg-indigo-950/20 p-2.5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] text-indigo-200 font-medium">Tool Invocation</div>
              <button
                type="button"
                onClick={() => closeToolInvoke(card.key)}
                className="text-[10px] text-slate-300 hover:text-white"
              >
                Close
              </button>
            </div>

            {tools.length > 0 ? (
              <select
                value={invokeState.toolName}
                onChange={(event) =>
                  updateInvokeState(card.key, {
                    toolName: event.target.value,
                    error: undefined,
                  })
                }
                className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {tools.map((tool) => (
                  <option key={tool.name} value={tool.name}>
                    {tool.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-[11px] text-slate-400">Load tools first to invoke.</div>
            )}

            <textarea
              value={invokeState.argsText}
              onChange={(event) =>
                updateInvokeState(card.key, {
                  argsText: event.target.value,
                  error: undefined,
                })
              }
              className="w-full h-24 resize-y rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-[11px] font-mono text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              spellCheck={false}
            />

            <button
              type="button"
              onClick={() => void runToolInvoke(card.key)}
              disabled={invokeState.running || !invokeState.toolName}
              className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1.5 text-[11px] text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play size={11} />
              <span>{invokeState.running ? 'Running...' : 'Run tool'}</span>
            </button>

            {invokeState.error && (
              <div className="text-[11px] text-red-300">{invokeState.error}</div>
            )}
            {invokeState.notice && (
              <div className="text-[10px] text-slate-400">{invokeState.notice}</div>
            )}
            {invokeState.mode && (
              <div className="text-[10px] text-slate-400">
                Mode: {invokeState.mode === 'skybridge' ? 'Skybridge Host' : 'Backend Bridge'}
              </div>
            )}
            {invokeState.latencyMs !== undefined && (
              <div className="text-[10px] text-slate-400">Latency: {invokeState.latencyMs} ms</div>
            )}
            {invokeState.result !== undefined && (
              <pre className="max-h-44 overflow-auto rounded-md border border-slate-700 bg-slate-950 p-2 text-[10px] text-slate-200 whitespace-pre-wrap break-all">
                {JSON.stringify(invokeState.result, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
