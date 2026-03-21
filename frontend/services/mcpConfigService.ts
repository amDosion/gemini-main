import apiClient from './apiClient';

export interface McpConfigPayload {
  configJson: string;
  updatedAt?: string | null;
}

export interface McpServerToolItem {
  name: string;
  description?: string;
}

export interface McpServerToolsPayload {
  serverKey: string;
  toolCount: number;
  tools: McpServerToolItem[];
}

export interface StopMcpSessionPayload {
  success: boolean;
  closedCount: number;
  closedSessions: string[];
  errors: string[];
}

export interface McpToolInvokeResult {
  serverKey: string;
  toolName: string;
  sessionId: string;
  latencyMs: number;
  timestamp: number;
  success: boolean;
  isError?: boolean;
  error?: string | null;
  result?: unknown;
}

type AnyObject = Record<string, any>;

const toStringOrEmpty = (value: unknown): string => (typeof value === 'string' ? value : '');

const toNumberOrZero = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const mapConfigPayload = (raw: AnyObject): McpConfigPayload => ({
  configJson: toStringOrEmpty(raw.configJson ?? raw.config_json ?? '{}') || '{}',
  updatedAt: (raw.updatedAt ?? raw.updated_at ?? null) as string | null,
});

const mapServerToolsPayload = (raw: AnyObject): McpServerToolsPayload => ({
  serverKey: toStringOrEmpty(raw.serverKey ?? raw.server_key),
  toolCount: toNumberOrZero(raw.toolCount ?? raw.tool_count),
  tools: Array.isArray(raw.tools)
    ? raw.tools.map((item: AnyObject) => ({
      name: toStringOrEmpty(item?.name),
      description: typeof item?.description === 'string' ? item.description : undefined,
    }))
    : [],
});

const mapStopSessionPayload = (raw: AnyObject): StopMcpSessionPayload => ({
  success: Boolean(raw.success),
  closedCount: toNumberOrZero(raw.closedCount ?? raw.closed_count),
  closedSessions: Array.isArray(raw.closedSessions ?? raw.closed_sessions)
    ? (raw.closedSessions ?? raw.closed_sessions).map((item: unknown) => String(item))
    : [],
  errors: Array.isArray(raw.errors) ? raw.errors.map((item: unknown) => String(item)) : [],
});

const mapInvokePayload = (raw: AnyObject): McpToolInvokeResult => {
  const isError = raw.isError ?? raw.is_error;
  return {
    serverKey: toStringOrEmpty(raw.serverKey ?? raw.server_key),
    toolName: toStringOrEmpty(raw.toolName ?? raw.tool_name),
    sessionId: toStringOrEmpty(raw.sessionId ?? raw.session_id),
    latencyMs: toNumberOrZero(raw.latencyMs ?? raw.latency_ms),
    timestamp: toNumberOrZero(raw.timestamp),
    success: raw.success === undefined ? !Boolean(isError) : Boolean(raw.success),
    isError: isError === undefined ? undefined : Boolean(isError),
    error: (raw.error ?? null) as string | null,
    result: raw.result,
  };
};

class McpConfigService {
  private readonly baseUrl = '/api/mcp/config';

  async getConfig(): Promise<McpConfigPayload> {
    const raw = await apiClient.get<AnyObject>(this.baseUrl);
    return mapConfigPayload(raw || {});
  }

  async saveConfig(configJson: string): Promise<McpConfigPayload> {
    const raw = await apiClient.put<AnyObject>(this.baseUrl, {
      config_json: configJson,
      configJson,
    });
    return mapConfigPayload(raw || {});
  }

  async getServerTools(serverKey: string): Promise<McpServerToolsPayload> {
    const raw = await apiClient.get<AnyObject>(`${this.baseUrl}/tools/${encodeURIComponent(serverKey)}`);
    return mapServerToolsPayload(raw || {});
  }

  async stopSessions(mcpServerKey?: string): Promise<StopMcpSessionPayload> {
    const raw = await apiClient.post<AnyObject>('/api/mcp/session/stop', {
      mcp_server_key: mcpServerKey || null,
      mcpServerKey: mcpServerKey || null,
    });
    return mapStopSessionPayload(raw || {});
  }

  async invokeServerTool(serverKey: string, toolName: string, argumentsPayload: Record<string, any>): Promise<McpToolInvokeResult> {
    const raw = await apiClient.post<AnyObject>(`${this.baseUrl}/tools/${encodeURIComponent(serverKey)}/invoke`, {
      tool_name: toolName,
      toolName,
      arguments: argumentsPayload,
    });
    return mapInvokePayload(raw || {});
  }
}

export const mcpConfigService = new McpConfigService();
export default mcpConfigService;
