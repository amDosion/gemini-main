import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileJson,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  RefreshCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import mcpConfigService from '../../../services/mcpConfigService';
import {
  callSkybridgeTool,
  getSkybridgeHostType,
  isSkybridgeHostAvailable,
} from '../../../services/skybridgeToolService';
import { useEscapeClose } from '../../../hooks/useEscapeClose';

type JsonObject = Record<string, any>;
type TransportType = 'stdio' | 'sse' | 'http' | 'streamable-http' | 'unknown';
type ServerMapSource = 'mcpServers' | 'root' | 'none';

interface ServerCard {
  key: string;
  config: JsonObject;
  transport: TransportType;
  enabled: boolean;
  valid: boolean;
  summary: string;
}

interface ServerToolsState {
  loading: boolean;
  loaded: boolean;
  tools: Array<{ name: string; description?: string }>;
  fetchedAt?: number;
  cacheHit?: boolean;
  error?: string;
}

interface ServerInvokeState {
  open: boolean;
  toolName: string;
  argsText: string;
  running: boolean;
  result?: unknown;
  latencyMs?: number;
  error?: string;
  mode?: 'backend' | 'skybridge';
  notice?: string;
}

const TOOL_PREVIEW_COUNT = 8;
const TOOL_CACHE_TTL_MS = 60 * 1000;

const DEFAULT_CONFIG_TEMPLATE = {
  mcpServers: {},
};

const NEW_SERVER_TEMPLATE = {
  name: '',
  serverType: 'stdio',
  command: '',
  args: [],
};

const KNOWN_SERVER_FIELDS = new Set([
  'command',
  'args',
  'env',
  'url',
  'introUrl',
  'timeout',
  'type',
  'serverType',
  'server_type',
  'enabled',
  'disabled',
  'headers',
]);

const isPlainObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const formatTime = (iso?: string | null): string => {
  if (!iso) return '-';
  const time = new Date(iso);
  if (Number.isNaN(time.getTime())) return '-';
  return time.toLocaleString();
};

const parseRootObject = (jsonText: string): JsonObject => {
  const parsed = JSON.parse((jsonText || '').trim() || '{}');
  if (!isPlainObject(parsed)) {
    throw new Error('MCP config root must be a JSON object');
  }
  return parsed;
};

const isRootServerMap = (root: JsonObject): boolean => {
  const entries = Object.entries(root);
  if (entries.length === 0) return false;
  if (entries.some(([key]) => KNOWN_SERVER_FIELDS.has(key))) return false;
  return entries.every(([, value]) => isPlainObject(value));
};

const extractServerMap = (
  root: JsonObject
): { map: Record<string, JsonObject>; source: ServerMapSource } => {
  if (isPlainObject(root.mcpServers)) {
    const map: Record<string, JsonObject> = {};
    Object.entries(root.mcpServers).forEach(([key, value]) => {
      if (isPlainObject(value)) map[key] = value;
    });
    return { map, source: 'mcpServers' };
  }

  if (isRootServerMap(root)) {
    const map: Record<string, JsonObject> = {};
    Object.entries(root).forEach(([key, value]) => {
      if (isPlainObject(value)) map[key] = value;
    });
    return { map, source: 'root' };
  }

  return { map: {}, source: 'none' };
};

const detectTransport = (config: JsonObject): TransportType => {
  const explicit = String(
    config.serverType ?? config.server_type ?? config.type ?? ''
  ).trim().toLowerCase();

  if (explicit === 'stdio' || explicit === 'sse' || explicit === 'http') {
    return explicit;
  }
  if (explicit === 'streamablehttp' || explicit === 'streamable_http' || explicit === 'streamable-http') {
    return 'streamable-http';
  }
  if (config.command) return 'stdio';
  if (config.url) return 'http';
  return 'unknown';
};

const buildSummary = (transport: TransportType, config: JsonObject): string => {
  if (transport === 'stdio') {
    const command = String(config.command || '').trim();
    const args = Array.isArray(config.args) ? config.args.join(' ') : '';
    if (!command) return 'Missing command';
    return args ? `${command} ${args}` : command;
  }
  if (transport === 'sse' || transport === 'http' || transport === 'streamable-http') {
    const url = String(config.url || '').trim();
    return url || 'Missing URL';
  }
  return 'Unknown transport';
};

const validateServer = (transport: TransportType, config: JsonObject): boolean => {
  if (transport === 'stdio') return !!String(config.command || '').trim();
  if (transport === 'sse' || transport === 'http' || transport === 'streamable-http') {
    return !!String(config.url || '').trim();
  }
  return false;
};

const extractServersFromDialogJson = (payload: JsonObject): Record<string, JsonObject> => {
  if (isPlainObject(payload.mcpServers)) {
    const map: Record<string, JsonObject> = {};
    Object.entries(payload.mcpServers).forEach(([key, value]) => {
      if (isPlainObject(value)) map[key] = value;
    });
    if (Object.keys(map).length > 0) return map;
  }

  if (isRootServerMap(payload)) {
    const map: Record<string, JsonObject> = {};
    Object.entries(payload).forEach(([key, value]) => {
      if (isPlainObject(value)) map[key] = value;
    });
    if (Object.keys(map).length > 0) return map;
  }

  const serverKey = String(payload.name ?? payload.key ?? payload.id ?? '').trim();
  if (!serverKey) {
    throw new Error('JSON must contain `mcpServers` or a `name` field');
  }

  const nextConfig: JsonObject = { ...payload };
  delete nextConfig.name;
  delete nextConfig.key;
  delete nextConfig.id;

  return {
    [serverKey]: nextConfig,
  };
};

const buildPersistedRoot = (
  previousRoot: JsonObject,
  source: ServerMapSource,
  servers: Record<string, JsonObject>
): JsonObject => {
  if (source === 'mcpServers') {
    return { ...previousRoot, mcpServers: servers };
  }
  if (source === 'none' && Object.keys(previousRoot).length > 0) {
    return { ...previousRoot, mcpServers: servers };
  }
  return { mcpServers: servers };
};

export const McpTab: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [rootConfig, setRootConfig] = useState<JsonObject>(DEFAULT_CONFIG_TEMPLATE);
  const [sourceType, setSourceType] = useState<ServerMapSource>('none');
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

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
  const toolsCacheRef = useRef<Record<string, { expiresAt: number; tools: Array<{ name: string; description?: string }> }>>({});
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
    } catch (e: any) {
      setError(e?.message || 'Failed to load MCP configuration');
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
    } catch (e: any) {
      setServerToolsMap((prev) => ({
        ...prev,
        [serverKey]: {
          loading: false,
          loaded: true,
          tools: prev[serverKey]?.tools || [],
          error: e?.message || 'Failed to load tools',
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
    } catch (e: any) {
      setError(e?.message || 'Failed to save MCP configuration');
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
    } catch (e: any) {
      setDialogError(e?.message || 'Invalid JSON');
      return;
    }

    let incomingServers: Record<string, JsonObject>;
    try {
      incomingServers = extractServersFromDialogJson(parsedDialog);
    } catch (e: any) {
      setDialogError(e?.message || 'Invalid MCP server JSON');
      return;
    }

    let normalizedIntroUrl = '';
    try {
      normalizedIntroUrl = normalizeIntroUrl(dialogIntroUrl);
    } catch (e: any) {
      setDialogIntroUrlError(e?.message || 'Invalid URL');
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

  const handleDelete = async (key: string) => {
    if (deletingKey !== key) {
      setDeletingKey(key);
      window.setTimeout(() => setDeletingKey((prev) => (prev === key ? null : prev)), 3000);
      return;
    }

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
    setDeletingKey(null);
    try {
      await persistServerMap(nextServers);
    } catch {
      // Error already handled in persistServerMap
    }
  };

  const openToolInvoke = async (serverKey: string, availableTools: Array<{ name: string; description?: string }>) => {
    const currentToolsState = serverToolsMap[serverKey];
    if (!currentToolsState?.loaded && !currentToolsState?.loading) {
      await loadServerTools(serverKey);
    }

    const latestTools = (
      serverToolsMap[serverKey]?.tools
      || availableTools
      || toolsCacheRef.current[serverKey]?.tools
      || []
    );
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
      } catch (error: any) {
        updateInvokeState(serverKey, { error: `Invalid JSON arguments: ${error?.message || 'parse error'}` });
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
        error: response.isError ? (response.error || 'Tool returned error') : undefined,
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
          error: response.isError ? (typeof response.result === 'string' ? response.result : 'Tool returned error') : undefined,
          mode: 'skybridge',
          notice: `Executed via skybridge host (${getSkybridgeHostType() || 'unknown'})`,
        });
        return;
      } catch (skybridgeError: any) {
        const reason = skybridgeError?.message || 'Skybridge call failed';
        try {
          await invokeWithBackend(`Skybridge failed (${reason}); fell back to backend bridge.`);
          return;
        } catch (backendFallbackError: any) {
          updateInvokeState(serverKey, {
            running: false,
            error: backendFallbackError?.message || 'Failed to invoke MCP tool',
            mode: 'backend',
            notice: `Skybridge failed (${reason}); backend fallback failed too.`,
          });
          return;
        }
      }
    }

    try {
      await invokeWithBackend('Executed via backend MCP bridge.');
    } catch (error: any) {
      updateInvokeState(serverKey, {
        running: false,
        error: error?.message || 'Failed to invoke MCP tool',
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
          <p className="text-xs text-slate-500">
            Last updated: {formatTime(updatedAt)}
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            Tools are loaded on-demand and invokable per server (MCP bridge mode).
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            Invocation route: {skybridgeHostType ? `skybridge host (${skybridgeHostType}) with backend fallback` : 'backend bridge only (no skybridge host detected)'}.
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
            {cards.map((card) => {
              const isDeleting = deletingKey === card.key;
              const isMenuOpen = openMenuKey === card.key;
              const toolsState = serverToolsMap[card.key];
              const tools = toolsState?.tools || [];
              const invokeState = serverInvokeMap[card.key];
              const isToolsExpanded = !!expandedToolsMap[card.key];
              const visibleTools = isToolsExpanded ? tools : tools.slice(0, TOOL_PREVIEW_COUNT);
              const hiddenToolsCount = Math.max(0, tools.length - TOOL_PREVIEW_COUNT);
              const isToolsLoaded = !!toolsState?.loaded;
              const isToolsLoading = !!toolsState?.loading;
              const statusLabel = !card.enabled
                ? 'Disabled'
                : card.valid
                  ? 'Ready'
                  : 'Invalid';
              const statusClass = !card.enabled
                ? 'bg-slate-500/10 text-slate-400 border-slate-500/30'
                : card.valid
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

              return (
                <div
                  key={card.key}
                  className="group rounded-xl border bg-slate-900/50 border-slate-800 hover:border-slate-700 transition-all p-4 md:p-5 h-full flex flex-col"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="text-sm md:text-base font-medium text-slate-200 truncate">
                        {card.key}
                      </h3>
                      <div className="relative shrink-0" data-mcp-card-actions>
                        <button
                          type="button"
                          onClick={() => setOpenMenuKey((prev) => (prev === card.key ? null : card.key))}
                          className={`p-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-all ${isMenuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
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
                                <span>{isToolsExpanded ? 'Show less tools' : `Show all tools (+${hiddenToolsCount})`}</span>
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
                              onClick={() => {
                                void handleDelete(card.key);
                                if (isDeleting) {
                                  setOpenMenuKey(null);
                                }
                              }}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30 rounded"
                            >
                              <Trash2 size={13} />
                              <span>{isDeleting ? 'Confirm Delete' : 'Delete'}</span>
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

                  <div className="text-xs text-slate-500 font-mono break-all">
                    {card.summary}
                  </div>

                  {typeof card.config.introUrl === 'string' && card.config.introUrl.trim() && (
                    <button
                      type="button"
                      onClick={() => window.open(card.config.introUrl, '_blank', 'noopener,noreferrer')}
                      className="mt-2 inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 transition-colors text-left break-all"
                      title={card.config.introUrl}
                    >
                      <ExternalLink size={12} />
                      <span>{card.config.introUrl}</span>
                    </button>
                  )}

                  <div className="mt-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[11px] uppercase tracking-wide text-slate-500">
                        Tools
                      </div>
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
                    {isToolsLoading && (
                      <div className="text-xs text-slate-500">Loading tools...</div>
                    )}
                    {!isToolsLoading && !isToolsLoaded && (
                      <div className="text-xs text-slate-500">Tools are loaded on demand to reduce startup overhead.</div>
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
                            onChange={(event) => updateInvokeState(card.key, { toolName: event.target.value, error: undefined })}
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
                          onChange={(event) => updateInvokeState(card.key, { argsText: event.target.value, error: undefined })}
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
            })}
          </div>
        )}
      </div>

      {isDialogOpen && (
        <div className="fixed inset-0 z-[160] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-3xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
              <h3 className="text-base md:text-lg font-semibold text-white">
                {dialogMode === 'edit' ? 'Edit MCP Server' : 'New MCP Server'}
              </h3>
              <button
                type="button"
                onClick={() => setIsDialogOpen(false)}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-3">
              <p className="text-xs text-slate-500">
                Paste server JSON. Supported formats: <code className="font-mono">{"{ name, ...config }"}</code> or <code className="font-mono">{"{ mcpServers: { ... } }"}</code>.
              </p>
              <div className="space-y-1.5">
                <label className="block text-xs text-slate-400">
                  MCP Intro Website URL (optional)
                </label>
                <input
                  type="text"
                  value={dialogIntroUrl}
                  onChange={(e) => setDialogIntroUrl(e.target.value)}
                  placeholder="https://example.com/mcp-intro"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                  disabled={isSaving}
                />
                {dialogIntroUrlError && (
                  <div className="rounded-lg border border-red-800/60 bg-red-900/20 px-3 py-2 text-xs text-red-200 flex items-center gap-2">
                    <AlertTriangle size={14} />
                    <span>{dialogIntroUrlError}</span>
                  </div>
                )}
              </div>

              <textarea
                value={dialogJsonText}
                onChange={(e) => setDialogJsonText(e.target.value)}
                spellCheck={false}
                className="w-full h-72 md:h-80 resize-y rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-xs md:text-sm font-mono text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                disabled={isSaving}
              />

              {dialogError && (
                <div className="rounded-lg border border-red-800/60 bg-red-900/20 px-3 py-2 text-xs text-red-200 flex items-center gap-2">
                  <AlertTriangle size={14} />
                  <span>{dialogError}</span>
                </div>
              )}
            </div>

            <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsDialogOpen(false)}
                className="px-4 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors text-sm"
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveDialog}
                disabled={isSaving}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium inline-flex items-center gap-2 transition-colors"
              >
                <Save size={14} />
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
