export interface SkybridgeToolResult {
  content?: unknown;
  structuredContent?: unknown;
  isError?: boolean;
  result?: string;
  meta?: Record<string, unknown>;
  [key: string]: unknown;
}

type SkybridgeHostType = 'apps-sdk' | 'mcp-app';

interface JsonRpcErrorPayload {
  code?: number;
  message?: string;
  data?: unknown;
}

interface JsonRpcSuccessResponse<T = any> {
  jsonrpc?: string;
  id?: number;
  result?: T;
}

interface JsonRpcErrorResponse {
  jsonrpc?: string;
  id?: number;
  error?: JsonRpcErrorPayload;
}

const SUPPORTED_HOST_TYPES = new Set<SkybridgeHostType>(['apps-sdk', 'mcp-app']);
const MCP_REQUEST_TIMEOUT_MS = 10_000;
let mcpRequestId = 1;

const getSkybridgeHostTypeUnsafe = (): SkybridgeHostType | null => {
  if (typeof window === 'undefined') return null;
  const globalSkybridge = (window as Window & { skybridge?: { hostType?: unknown } }).skybridge;
  if (!globalSkybridge) return null;
  const hostType = typeof globalSkybridge.hostType === 'string' ? globalSkybridge.hostType : '';
  return SUPPORTED_HOST_TYPES.has(hostType as SkybridgeHostType)
    ? (hostType as SkybridgeHostType)
    : null;
};

export const getSkybridgeHostType = (): string | null => getSkybridgeHostTypeUnsafe();

export const isSkybridgeHostAvailable = (): boolean => getSkybridgeHostTypeUnsafe() !== null;

const normalizeArgs = (argsPayload: Record<string, unknown>): Record<string, unknown> | null =>
  argsPayload && Object.keys(argsPayload).length > 0 ? argsPayload : null;

const callAppsSdkTool = async (
  toolName: string,
  argsPayload: Record<string, unknown>
): Promise<SkybridgeToolResult> => {
  const openai = (window as Window & { openai?: { callTool?: (name: string, args: Record<string, unknown> | null) => Promise<SkybridgeToolResult> } }).openai;
  if (!openai || typeof openai.callTool !== 'function') {
    throw new Error('Skybridge Apps SDK host is unavailable');
  }
  return openai.callTool(toolName, normalizeArgs(argsPayload));
};

const callMcpAppTool = async (
  toolName: string,
  argsPayload: Record<string, unknown>
): Promise<SkybridgeToolResult> => {
  if (typeof window === 'undefined' || !window.parent || window.parent === window) {
    throw new Error('Skybridge MCP App host is unavailable');
  }

  const requestId = mcpRequestId++;
  const params = {
    name: toolName,
    arguments: normalizeArgs(argsPayload) ?? undefined,
  };

  return new Promise((resolve, reject) => {
    const cleanup = (listener: (event: MessageEvent) => void, timeoutId: number) => {
      window.removeEventListener('message', listener);
      window.clearTimeout(timeoutId);
    };

    const listener = (event: MessageEvent) => {
      const data = event.data as JsonRpcSuccessResponse<any> | JsonRpcErrorResponse | null;
      if (!data || data.jsonrpc !== '2.0' || data.id !== requestId) {
        return;
      }

      cleanup(listener, timeoutId);

      if ('error' in data && data.error) {
        reject(new Error(data.error.message || 'MCP tool call failed'));
        return;
      }

      const payload = ('result' in data ? data.result : null) || {};
      const content = Array.isArray(payload.content) ? payload.content : [];
      const resultText = content
        .filter((item: any) => item && item.type === 'text' && typeof item.text === 'string')
        .map((item: any) => item.text as string)
        .join('\n');

      resolve({
        content,
        structuredContent: payload.structuredContent ?? {},
        isError: Boolean(payload.isError),
        result: resultText,
        meta: payload._meta ?? {},
      });
    };

    const timeoutId = window.setTimeout(() => {
      cleanup(listener, timeoutId);
      reject(new Error('MCP tool call timed out'));
    }, MCP_REQUEST_TIMEOUT_MS);

    window.addEventListener('message', listener);
    window.parent.postMessage(
      {
        jsonrpc: '2.0',
        id: requestId,
        method: 'tools/call',
        params,
      },
      '*'
    );
  });
};

export const callSkybridgeTool = async (
  toolName: string,
  argsPayload: Record<string, unknown>
): Promise<SkybridgeToolResult> => {
  const hostType = getSkybridgeHostTypeUnsafe();
  if (!hostType) {
    throw new Error('Skybridge host is unavailable in current runtime');
  }

  if (hostType === 'apps-sdk') {
    return callAppsSdkTool(toolName, argsPayload);
  }

  return callMcpAppTool(toolName, argsPayload);
};
