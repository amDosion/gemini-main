import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileJson, Plus, Save, X } from 'lucide-react';
import mcpConfigService from '../../../services/mcpConfigService';
import {
  callSkybridgeTool,
  getSkybridgeHostType,
  isSkybridgeHostAvailable,
} from '../../../services/skybridgeToolService';
import { useEscapeClose } from '../../../hooks/useEscapeClose';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import {
  type JsonObject,
  type TransportType,
  type ServerMapSource,
  type ServerCard,
  type ServerToolsState,
  type ServerInvokeState,
  TOOL_CACHE_TTL_MS,
  DEFAULT_CONFIG_TEMPLATE,
  NEW_SERVER_TEMPLATE,
  KNOWN_SERVER_FIELDS,
  isPlainObject,
  formatTime,
  parseRootObject,
  isRootServerMap,
  extractServerMap,
  detectTransport,
  buildSummary,
  validateServer,
  extractServersFromDialogJson,
  buildPersistedRoot,
} from './mcpTabHelpers';
import { McpServerDialog } from './mcp/McpServerDialog';
import { McpServerCard } from './mcp/McpServerCard';

export const McpTab: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [rootConfig, setRootConfig] = useState<JsonObject>(DEFAULT_CONFIG_TEMPLATE);
  const [sourceType, setSourceType] = useState<ServerMapSource>('none');
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [deleteTargetKey, setDeleteTargetKey] = useState<string | null>(null);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [dialogJsonText, setDialogJsonText] = useState<string>(
    JSON.stringify(NEW_SERVER_TEMPLATE, null, 2)
  );
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [dialogIntroUrl, setDialogIntroUrl] = useState('');
  const [dialogIntroUrlError, setDialogIntroUrlError] = useState<string | null>(null);
  const [serverToolsMap, setServerToolsMap] = useState<Record<string, ServerToolsState>>({});
  const [expandedToolsMap, setExpandedToolsMap] = useState<Record<string, boolean>>({});
  const [serverInvokeMap, setServerInvokeMap] = useState<Record<string, ServerInvokeState>>({});
  const [openMenuKey, setOpenMenuKey] = useState<string | null>(null);
  const toolsCacheRef = useRef<
    Record<string, { expiresAt: number; tools: Array<{ name: string; description?: string }> }>
  >({});
  const skybridgeHostType = useMemo(() => getSkybridgeHostType(), []);

  useEscapeClose(isDialogOpen, () => setIsDialogOpen(false));

  const serverMap = useMemo(() => extractServerMap(rootConfig).map, [rootConfig]);

  const cards = useMemo<ServerCard[]>(() => {
    return Object.entries(serverMap).map(([key, config]) => {
      const transport = detectTransport(config);
      const enabled = !(config.disabled === true || config.enabled === false);
      const valid = validateServer(transport, config);
      return {
        key,
        config,
        transport,
        enabled,
        valid,
        summary: buildSummary(transport, config),
      };
    });
  }, [serverMap]);

  const loadConfig = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await mcpConfigService.getConfig();
      const parsed = parseRootObject(data.configJson || '{}');
      const extracted = extractServerMap(parsed);
      setRootConfig(parsed);
      setSourceType(extracted.source);
      setUpdatedAt(data.updatedAt || null);
    } catch (e: unknown) {
      setError((e instanceof Error ? e.message : undefined) || 'Failed to load MCP configuration');
      setRootConfig(DEFAULT_CONFIG_TEMPLATE);
      setSourceType('none');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    if (!successMessage) return;
    const timer = window.setTimeout(() => setSuccessMessage(null), 2500);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('[data-mcp-card-actions]')) {
        return;
      }
      setOpenMenuKey(null);
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const loadServerTools = useCallback(async (serverKey: string, force = false) => {
    const now = Date.now();
    if (!force) {
      const cached = toolsCacheRef.current[serverKey];
      if (cached && cached.expiresAt > now) {
        setServerToolsMap((prev) => ({
          ...prev,
          [serverKey]: {
            loading: false,
            loaded: true,
            tools: cached.tools,
            fetchedAt: now,
            cacheHit: true,
            error: undefined,
          },
        }));
        return;
      }
    }

    setServerToolsMap((prev) => ({
      ...prev,
      [serverKey]: {
        loading: true,
        loaded: !!prev[serverKey]?.loaded,
        tools: prev[serverKey]?.tools || [],
      },
    }));

    try {
      const payload = await mcpConfigService.getServerTools(serverKey);
      const tools = payload.tools || [];
      toolsCacheRef.current[serverKey] = {
        tools,
        expiresAt: Date.now() + TOOL_CACHE_TTL_MS,
      };
      setServerToolsMap((prev) => ({
        ...prev,
        [serverKey]: {
          loading: false,
          loaded: true,
          tools,
          fetchedAt: Date.now(),
          cacheHit: false,
          error: undefined,
        },
      }));
    } catch (e: unknown) {
      setServerToolsMap((prev) => ({
        ...prev,
        [serverKey]: {
          loading: false,
          loaded: true,
          tools: prev[serverKey]?.tools || [],
          error: (e instanceof Error ? e.message : undefined) || 'Failed to load tools',
        },
      }));
    }
  }, []);

  useEffect(() => {
    if (isLoading) return;
    const cardKeys = new Set(cards.map((card) => card.key));

    setServerToolsMap((prev) => {
      const next: Record<string, ServerToolsState> = {};
      let removed = false;
      Object.entries(prev).forEach(([key, value]) => {
        if (cardKeys.has(key)) {
          next[key] = value;
        } else {
          removed = true;
        }
      });
      return removed ? next : prev;
    });

    setExpandedToolsMap((prev) => {
      const next: Record<string, boolean> = {};
      let removed = false;
      Object.entries(prev).forEach(([key, value]) => {
        if (cardKeys.has(key)) {
          next[key] = value;
        } else {
          removed = true;
        }
      });
      return removed ? next : prev;
    });

    setServerInvokeMap((prev) => {
      const next: Record<string, ServerInvokeState> = {};
      let removed = false;
      Object.entries(prev).forEach(([key, value]) => {
        if (cardKeys.has(key)) {
          next[key] = value;
        } else {
          removed = true;
        }
      });
      return removed ? next : prev;
    });

    Object.keys(toolsCacheRef.current).forEach((cacheKey) => {
      if (!cardKeys.has(cacheKey)) {
        delete toolsCacheRef.current[cacheKey];
      }
    });
  }, [cards, isLoading]);

  const persistServerMap = async (
    nextServers: Record<string, JsonObject>,
    previousSource?: ServerMapSource
  ) => {
    setIsSaving(true);
    setError(null);
    const source = previousSource || sourceType;
    try {
      const nextRoot = buildPersistedRoot(rootConfig, source, nextServers);
      const payload = JSON.stringify(nextRoot, null, 2);
      const result = await mcpConfigService.saveConfig(payload);
      const parsed = parseRootObject(result.configJson || '{}');
      const extracted = extractServerMap(parsed);
      setRootConfig(parsed);
      setSourceType(extracted.source);
      setUpdatedAt(result.updatedAt || null);
      setSuccessMessage('MCP configuration saved');
    } catch (e: unknown) {
      setError((e instanceof Error ? e.message : undefined) || 'Failed to save MCP configuration');
      throw e;
    } finally {
      setIsSaving(false);
    }
  };

  const openCreateDialog = () => {
    setDialogMode('create');
    setEditingKey(null);
    setDialogError(null);
    setDialogIntroUrlError(null);
    setDialogIntroUrl('');
    setDialogJsonText(JSON.stringify(NEW_SERVER_TEMPLATE, null, 2));
    setIsDialogOpen(true);
  };

  const openEditDialog = (card: ServerCard) => {
    setDialogMode('edit');
    setEditingKey(card.key);
    setDialogError(null);
    setDialogIntroUrlError(null);
    setDialogIntroUrl(
      typeof card.config.introUrl === 'string'
        ? card.config.introUrl
        : typeof card.config.website === 'string'
          ? card.config.website
          : ''
    );
    setDialogJsonText(
      JSON.stringify(
        {
          name: card.key,
          ...card.config,
        },
        null,
        2
      )
    );
    setIsDialogOpen(true);
  };

  const normalizeIntroUrl = (rawUrl: string): string => {
    const trimmed = rawUrl.trim();
    if (!trimmed) {
      return '';
    }

    const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    let parsed: URL;
    try {
      parsed = new URL(withProtocol);
    } catch {
      throw new Error('Invalid URL');
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error('URL must start with http:// or https://');
    }

    return parsed.toString();
  };

  const handleSaveDialog = async () => {
    setDialogError(null);
    setDialogIntroUrlError(null);
    let parsedDialog: JsonObject;
    try {
      parsedDialog = parseRootObject(dialogJsonText);
    } catch (e: unknown) {
      setDialogError((e instanceof Error ? e.message : undefined) || 'Invalid JSON');
      return;
    }

    let incomingServers: Record<string, JsonObject>;
    try {
      incomingServers = extractServersFromDialogJson(parsedDialog);
    } catch (e: unknown) {
      setDialogError((e instanceof Error ? e.message : undefined) || 'Invalid MCP server JSON');
      return;
    }

    let normalizedIntroUrl = '';
    try {
      normalizedIntroUrl = normalizeIntroUrl(dialogIntroUrl);
    } catch (e: unknown) {
      setDialogIntroUrlError((e instanceof Error ? e.message : undefined) || 'Invalid URL');
      return;
    }

    const nextServers = { ...serverMap };

    if (dialogMode === 'edit') {
      const entries = Object.entries(incomingServers);
      if (entries.length !== 1) {
        setDialogError('Edit expects exactly one MCP server entry');
        return;
      }

      const [nextKey, nextConfig] = entries[0];
      if (normalizedIntroUrl) {
        nextConfig.introUrl = normalizedIntroUrl;
      } else {
        delete nextConfig.introUrl;
      }
      if (editingKey && editingKey !== nextKey) {
        delete nextServers[editingKey];
      }
      nextServers[nextKey] = nextConfig;
    } else {
      Object.entries(incomingServers).forEach(([key, config]) => {
        if (normalizedIntroUrl) {
          config.introUrl = normalizedIntroUrl;
        } else {
          delete config.introUrl;
        }
        nextServers[key] = config;
      });
    }

    try {
      await persistServerMap(nextServers, sourceType === 'none' ? 'mcpServers' : sourceType);
      setIsDialogOpen(false);
    } catch {
      // Error already handled in persistServerMap
    }
  };

  const handleDeleteClick = (key: string) => {
    setDeleteTargetKey(key);
    setOpenMenuKey(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTargetKey) return;
    const key = deleteTargetKey;

    const nextServers = { ...serverMap };
    delete nextServers[key];
    delete toolsCacheRef.current[key];
    setServerToolsMap((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setServerInvokeMap((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setDeleteTargetKey(null);
    try {
      await persistServerMap(nextServers);
    } catch {
      // Error already handled in persistServerMap
    }
  };

  const handleDeleteCancel = () => {
    setDeleteTargetKey(null);
  };

  const openToolInvoke = async (
    serverKey: string,
    availableTools: Array<{ name: string; description?: string }>
  ) => {
    const currentToolsState = serverToolsMap[serverKey];
    if (!currentToolsState?.loaded && !currentToolsState?.loading) {
      await loadServerTools(serverKey);
    }

    const latestTools =
      serverToolsMap[serverKey]?.tools ||
      availableTools ||
      toolsCacheRef.current[serverKey]?.tools ||
      [];
    const defaultToolName = latestTools[0]?.name || '';
    setServerInvokeMap((prev) => {
      const existing = prev[serverKey];
      const existingToolInList = latestTools.some((tool) => tool.name === existing?.toolName);
      return {
        ...prev,
        [serverKey]: {
          open: true,
          toolName: existingToolInList ? String(existing?.toolName || '') : defaultToolName,
          argsText: existing?.argsText || '{}',
          running: false,
          result: existing?.result,
          latencyMs: existing?.latencyMs,
          error: existing?.error,
        },
      };
    });
  };

  const closeToolInvoke = (serverKey: string) => {
    setServerInvokeMap((prev) => {
      if (!prev[serverKey]) return prev;
      return {
        ...prev,
        [serverKey]: {
          ...prev[serverKey],
          open: false,
          running: false,
        },
      };
    });
  };

  const updateInvokeState = (serverKey: string, patch: Partial<ServerInvokeState>) => {
    setServerInvokeMap((prev) => {
      const current = prev[serverKey] || {
        open: true,
        toolName: '',
        argsText: '{}',
        running: false,
      };
      return {
        ...prev,
        [serverKey]: {
          ...current,
          ...patch,
        },
      };
    });
  };

  const runToolInvoke = async (serverKey: string) => {
    const invokeState = serverInvokeMap[serverKey];
    if (!invokeState) return;

    const toolName = String(invokeState.toolName || '').trim();
    if (!toolName) {
      updateInvokeState(serverKey, { error: 'Please choose a tool' });
      return;
    }

    let argsPayload: Record<string, any> = {};
    const argsText = String(invokeState.argsText || '{}').trim();
    if (argsText) {
      try {
        const parsed = JSON.parse(argsText);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          argsPayload = parsed;
        } else {
          updateInvokeState(serverKey, { error: 'Tool arguments must be a JSON object' });
          return;
        }
      } catch (error: unknown) {
        updateInvokeState(serverKey, {
          error: `Invalid JSON arguments: ${error instanceof Error ? error.message : 'parse error'}`,
        });
        return;
      }
    }

    updateInvokeState(serverKey, {
      running: true,
      error: undefined,
      notice: undefined,
      mode: undefined,
    });

    const invokeWithBackend = async (notice?: string) => {
      const response = await mcpConfigService.invokeServerTool(serverKey, toolName, argsPayload);
      updateInvokeState(serverKey, {
        running: false,
        result: response.result,
        latencyMs: response.latencyMs,
        error: response.isError ? response.error || 'Tool returned error' : undefined,
        mode: 'backend',
        notice,
      });
    };

    if (isSkybridgeHostAvailable()) {
      try {
        const start = performance.now();
        const response = await callSkybridgeTool(toolName, argsPayload);
        const latencyMs = Math.round((performance.now() - start) * 100) / 100;

        updateInvokeState(serverKey, {
          running: false,
          result: response.structuredContent ?? response.content ?? response.result ?? response,
          latencyMs,
          error: response.isError
            ? typeof response.result === 'string'
              ? response.result
              : 'Tool returned error'
            : undefined,
          mode: 'skybridge',
          notice: `Executed via skybridge host (${getSkybridgeHostType() || 'unknown'})`,
        });
        return;
      } catch (skybridgeError: unknown) {
        const reason =
          skybridgeError instanceof Error ? skybridgeError.message : 'Skybridge call failed';
        try {
          await invokeWithBackend(`Skybridge failed (${reason}); fell back to backend bridge.`);
          return;
        } catch (backendFallbackError: unknown) {
          updateInvokeState(serverKey, {
            running: false,
            error:
              (backendFallbackError instanceof Error ? backendFallbackError.message : undefined) ||
              'Failed to invoke MCP tool',
            mode: 'backend',
            notice: `Skybridge failed (${reason}); backend fallback failed too.`,
          });
          return;
        }
      }
    }

    try {
      await invokeWithBackend('Executed via backend MCP bridge.');
    } catch (error: unknown) {
      updateInvokeState(serverKey, {
        running: false,
        error: (error instanceof Error ? error.message : undefined) || 'Failed to invoke MCP tool',
        mode: 'backend',
      });
    }
  };

  return (
    <div className="absolute inset-0 flex flex-col p-3 md:p-6 space-y-4 md:space-y-6">
      <div className="shrink-0 flex items-center justify-between pb-3 md:pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileJson size={20} className="text-indigo-400" />
            <h2 className="text-base md:text-lg font-medium text-white">
              MCP Servers ({cards.length})
            </h2>
          </div>
          <p className="text-xs text-slate-500">Last updated: {formatTime(updatedAt)}</p>
          <p className="text-[11px] text-slate-500 mt-1">
            Tools are loaded on-demand and invokable per server (MCP bridge mode).
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            Invocation route:{' '}
            {skybridgeHostType
              ? `skybridge host (${skybridgeHostType}) with backend fallback`
              : 'backend bridge only (no skybridge host detected)'}
            .
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openCreateDialog}
            disabled={isLoading || isSaving}
            className="flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-xs md:text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
          >
            <Plus size={14} className="md:w-4 md:h-4" />
            <span className="hidden md:inline">New MCP</span>
            <span className="md:hidden">New</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/60 bg-red-900/20 px-4 py-3 text-sm text-red-200 flex items-center gap-2">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {successMessage && (
        <div className="rounded-xl border border-emerald-800/60 bg-emerald-900/20 px-4 py-3 text-sm text-emerald-200 flex items-center gap-2">
          <CheckCircle2 size={16} />
          <span>{successMessage}</span>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
        {isLoading ? (
          <div className="text-center py-16 bg-slate-900/30 rounded-xl border border-slate-800 text-slate-400 text-sm">
            Loading MCP servers...
          </div>
        ) : cards.length === 0 ? (
          <div className="text-center py-16 bg-slate-900/30 rounded-xl border border-slate-800 h-full flex flex-col items-center justify-center">
            <FileJson className="mx-auto mb-4 text-slate-600" size={40} />
            <p className="text-slate-400 mb-2 text-sm">No MCP servers configured</p>
            <p className="text-slate-500 text-xs">Click the button above to add one.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {cards.map((card) => (
              <McpServerCard
                key={card.key}
                card={card}
                openMenuKey={openMenuKey}
                setOpenMenuKey={setOpenMenuKey}
                toolsState={serverToolsMap[card.key]}
                invokeState={serverInvokeMap[card.key]}
                expandedToolsMap={expandedToolsMap}
                setExpandedToolsMap={setExpandedToolsMap}
                loadServerTools={loadServerTools}
                openToolInvoke={openToolInvoke}
                closeToolInvoke={closeToolInvoke}
                openEditDialog={openEditDialog}
                handleDeleteClick={handleDeleteClick}
                updateInvokeState={updateInvokeState}
                runToolInvoke={runToolInvoke}
              />
            ))}
          </div>
        )}
      </div>

      {/* Server 创建/编辑 Dialog 抽离至 ./mcp/McpServerDialog */}
      <McpServerDialog
        isOpen={isDialogOpen}
        mode={dialogMode}
        jsonText={dialogJsonText}
        onJsonTextChange={setDialogJsonText}
        introUrl={dialogIntroUrl}
        onIntroUrlChange={setDialogIntroUrl}
        introUrlError={dialogIntroUrlError}
        dialogError={dialogError}
        isSaving={isSaving}
        onSave={handleSaveDialog}
        onCancel={() => setIsDialogOpen(false)}
      />

      <ConfirmDialog
        isOpen={!!deleteTargetKey}
        title="Delete MCP Server"
        message="Are you sure you want to delete this MCP server configuration?"
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />
    </div>
  );
};
