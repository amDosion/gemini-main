import { withAuthorization } from './authTokenStore';

export const DEFAULT_REQUEST_TIMEOUT_MS = 10000;

type TimeoutMessage =
  | string
  | ((timeoutMs: number, requestUrl: string) => string);

export interface FetchWithTimeoutOptions extends RequestInit {
  timeoutMs?: number;
  /**
   * When true, sets `credentials: "include"` so browser cookies are sent with
   * the request. This is the primary auth mechanism for same-origin API calls.
   * It does NOT add a Bearer token header; use `includeBearer` for that.
   */
  withAuth?: boolean;
  /**
   * Suppresses the Bearer token Authorization header when `includeBearer` is
   * also true. Has no effect on cookie credentials (`withAuth`).
   */
  skipAuth?: boolean;
  /**
   * When true (and `withAuth` is also true), appends the in-memory access token
   * as a Bearer Authorization header. Intended for non-browser clients or
   * endpoints that require explicit token auth in addition to cookies.
   * `skipAuth` can be used to suppress the header on a per-request basis.
   */
  includeBearer?: boolean;
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

function isAbortError(error: unknown): boolean {
  return (
    !!error &&
    typeof error === 'object' &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  );
}

const REDACTED_ERROR_VALUE = 'REDACTED';
const SENSITIVE_ERROR_FIELD_PATTERN =
  /^(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|id[_-]?token|token|secret|password|signature|sig|credential|authorization)$/i;
const URL_IN_ERROR_PATTERN = /\bhttps?:\/\/[^\s"'<>]+/gi;
const BEARER_ERROR_PATTERN = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;
const SENSITIVE_ERROR_PAIR_PATTERN =
  /\b((?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|id[_-]?token|token|secret|password|signature|sig|credential|authorization)=)[^&\s"'<>]+/gi;
const SENSITIVE_JSON_FIELD_PATTERN =
  /("(?:(?:api[_-]?key)|(?:access[_-]?token)|(?:refresh[_-]?token)|(?:auth[_-]?token)|(?:id[_-]?token)|token|secret|password|signature|sig|credential|authorization)"\s*:\s*")[^"]*(")/gi;

function redactSensitiveUrlParams(rawUrl: string): string {
  const trailingPunctuation = rawUrl.match(/[),.;:!?]+$/)?.[0] ?? '';
  const urlText = trailingPunctuation
    ? rawUrl.slice(0, -trailingPunctuation.length)
    : rawUrl;

  try {
    const url = new URL(urlText);
    url.searchParams.forEach((_value, key) => {
      if (SENSITIVE_ERROR_FIELD_PATTERN.test(key)) {
        url.searchParams.set(key, REDACTED_ERROR_VALUE);
      }
    });
    return `${url.toString()}${trailingPunctuation}`;
  } catch {
    return rawUrl;
  }
}

function sanitizeErrorMessage(message: string): string {
  return message
    .replace(URL_IN_ERROR_PATTERN, redactSensitiveUrlParams)
    .replace(BEARER_ERROR_PATTERN, `Bearer ${REDACTED_ERROR_VALUE}`)
    .replace(SENSITIVE_JSON_FIELD_PATTERN, `$1${REDACTED_ERROR_VALUE}$2`)
    .replace(SENSITIVE_ERROR_PAIR_PATTERN, `$1${REDACTED_ERROR_VALUE}`);
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
    const message = parsedMessage || fallbackMessage || `Request failed: ${response.status}`;
    return {
      message: sanitizeErrorMessage(message),
      status: response.status,
      payload: payload ?? undefined,
    };
  }

  const text = (await response.text().catch(() => '')).trim();
  const message = text || fallbackMessage || `Request failed: ${response.status}`;
  return {
    message: sanitizeErrorMessage(message),
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

/**
 * Fetches a resource with an optional timeout, automatic signal merging, and
 * configurable auth behaviour.
 *
 * Auth model:
 * - `withAuth: true` — sets `credentials: "include"` (cookie auth, default for
 *   same-origin backend calls).
 * - `withAuth: true, includeBearer: true` — also appends the in-memory access
 *   token as a Bearer Authorization header (for non-cookie clients).
 * - `skipAuth: true` — suppresses the Bearer header even when `includeBearer`
 *   is true; has no effect on cookie credentials.
 *
 * These options are intentionally separate: cookie auth and Bearer token auth
 * serve different transport mechanisms and are opt-in independently.
 */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  options: FetchWithTimeoutOptions = {}
): Promise<Response> {
  const {
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    withAuth = false,
    skipAuth = false,
    includeBearer = false,
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
      headers: withAuth && includeBearer ? withAuthorization(headers, { skipAuth }) : headers,
      credentials: withAuth ? requestInit.credentials ?? 'include' : requestInit.credentials,
      signal: controller.signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
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
