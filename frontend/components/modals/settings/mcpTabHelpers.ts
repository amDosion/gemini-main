/**
 * MCP Tab 内部辅助类型 + 工具函数集合。
 *
 * 1:1 抽离自 `McpTab.tsx` L29-217（< 800 行合规拆分）。
 */

export type JsonObject = Record<string, any>;
export type TransportType = 'stdio' | 'sse' | 'http' | 'streamable-http' | 'unknown';
export type ServerMapSource = 'mcpServers' | 'root' | 'none';

export interface ServerCard {
  key: string;
  config: JsonObject;
  transport: TransportType;
  enabled: boolean;
  valid: boolean;
  summary: string;
}

export interface ServerToolsState {
  loading: boolean;
  loaded: boolean;
  tools: Array<{ name: string; description?: string }>;
  fetchedAt?: number;
  cacheHit?: boolean;
  error?: string;
}

export interface ServerInvokeState {
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

export const TOOL_PREVIEW_COUNT = 8;
export const TOOL_CACHE_TTL_MS = 60 * 1000;

export const DEFAULT_CONFIG_TEMPLATE = {
  mcpServers: {},
};

export const NEW_SERVER_TEMPLATE = {
  name: '',
  serverType: 'stdio',
  command: '',
  args: [],
};

export const KNOWN_SERVER_FIELDS = new Set([
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

export const isPlainObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export const formatTime = (iso?: string | null): string => {
  if (!iso) return '-';
  const time = new Date(iso);
  if (Number.isNaN(time.getTime())) return '-';
  return time.toLocaleString();
};

export const parseRootObject = (jsonText: string): JsonObject => {
  const parsed = JSON.parse((jsonText || '').trim() || '{}');
  if (!isPlainObject(parsed)) {
    throw new Error('MCP config root must be a JSON object');
  }
  return parsed;
};

export const isRootServerMap = (root: JsonObject): boolean => {
  const entries = Object.entries(root);
  if (entries.length === 0) return false;
  if (entries.some(([key]) => KNOWN_SERVER_FIELDS.has(key))) return false;
  return entries.every(([, value]) => isPlainObject(value));
};

export const extractServerMap = (
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

export const detectTransport = (config: JsonObject): TransportType => {
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

export const buildSummary = (transport: TransportType, config: JsonObject): string => {
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

export const validateServer = (transport: TransportType, config: JsonObject): boolean => {
  if (transport === 'stdio') return !!String(config.command || '').trim();
  if (transport === 'sse' || transport === 'http' || transport === 'streamable-http') {
    return !!String(config.url || '').trim();
  }
  return false;
};

export const extractServersFromDialogJson = (payload: JsonObject): Record<string, JsonObject> => {
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

export const buildPersistedRoot = (
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
