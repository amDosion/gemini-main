import { withAuthorization } from './authTokenStore';

export const DEFAULT_REQUEST_TIMEOUT_MS = 10000;

type TimeoutMessage =
  | string
  | ((timeoutMs: number, requestUrl: string) => string);

export interface FetchWithTimeoutOptions extends RequestInit {
  timeoutMs?: number;
  withAuth?: boolean;
  skipAuth?: boolean;
  timeoutMessage?: TimeoutMessage;
  abortMessage?: string;
}

export interface JsonRequestOptions extends FetchWithTimeoutOptions {
  errorMessage?: string;
}

interface ParsedHttpError {
  message: string;
  status: number;
  payload?: unknown;
}

function toRequestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url || '';
}

function resolveTimeoutMessage(
  timeoutMessage: TimeoutMessage | undefined,
  timeoutMs: number,
  requestUrl: string
): string {
  if (typeof timeoutMessage === 'function') {
    return timeoutMessage(timeoutMs, requestUrl);
  }
  if (typeof timeoutMessage === 'string') {
    return timeoutMessage;
  }
  return `Request timeout after ${timeoutMs}ms`;
}

function extractErrorMessageFromPayload(payload: Record<string, unknown>): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  if (typeof payload.detail === 'string') {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    const normalized = payload.detail
      .map((item: Record<string, unknown>) => {
        if (item && typeof item === 'object' && typeof item.msg === 'string') {
          const location = Array.isArray(item.loc) ? item.loc.join('.') : 'unknown';
          return `${location}: ${item.msg}`;
        }
        if (typeof item === 'string') {
          return item;
        }
        return '';
      })
      .filter(Boolean);

    if (normalized.length > 0) {
      return normalized.join('; ');
    }
  }

  if (payload.detail && typeof payload.detail === 'object') {
    return JSON.stringify(payload.detail);
  }

  if (typeof payload.error === 'string') {
    return payload.error;
  }

  if (typeof payload.message === 'string') {
    return payload.message;
  }

  return null;
}

export async function parseHttpError(
  response: Response,
  fallbackMessage?: string
): Promise<ParsedHttpError> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => null);
    const parsedMessage = extractErrorMessageFromPayload(payload);
    return {
      message: parsedMessage || fallbackMessage || `Request failed: ${response.status}`,
      status: response.status,
      payload: payload ?? undefined,
    };
  }

  const text = (await response.text().catch(() => '')).trim();
  return {
    message: text || fallbackMessage || `Request failed: ${response.status}`,
    status: response.status,
    payload: text || undefined,
  };
}

export async function readJsonResponse<T>(response: Response): Promise<T> {
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  const contentLength = response.headers.get('content-length');
  if (contentLength === '0') {
    return undefined as T;
  }

  return response.json();
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  options: FetchWithTimeoutOptions = {}
): Promise<Response> {
  const {
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    withAuth = false,
    skipAuth = false,
    timeoutMessage,
    abortMessage = 'Request cancelled by user',
    signal: externalSignal,
    headers,
    ...requestInit
  } = options;

  const controller = new AbortController();
  const requestUrl = toRequestUrl(input);
  let timedOut = false;

  const onExternalAbort = () => {
    controller.abort((externalSignal as AbortSignal & { reason?: unknown }).reason);
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort((externalSignal as AbortSignal & { reason?: unknown }).reason);
    } else {
      externalSignal.addEventListener('abort', onExternalAbort, { once: true });
    }
  }

  const shouldSetTimeout = Number.isFinite(timeoutMs) && timeoutMs > 0;
  const timeoutId = shouldSetTimeout
    ? globalThis.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : null;

  try {
    return await fetch(input, {
      ...requestInit,
      headers: withAuth ? withAuthorization(headers, { skipAuth }) : headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      if (timedOut && shouldSetTimeout) {
        throw new Error(resolveTimeoutMessage(timeoutMessage, timeoutMs, requestUrl));
      }
      if (externalSignal?.aborted) {
        throw new Error(abortMessage);
      }
    }
    throw error;
  } finally {
    if (timeoutId !== null) {
      globalThis.clearTimeout(timeoutId);
    }
    if (externalSignal) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  }
}

export async function requestJson<T>(
  input: RequestInfo | URL,
  options: JsonRequestOptions = {}
): Promise<T> {
  const { errorMessage, ...fetchOptions } = options;
  const response = await fetchWithTimeout(input, fetchOptions);
  if (!response.ok) {
    const parsed = await parseHttpError(response, errorMessage);
    throw new Error(parsed.message);
  }
  return readJsonResponse<T>(response);
}
