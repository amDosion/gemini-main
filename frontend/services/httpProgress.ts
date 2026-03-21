export interface TransferProgress {
  loaded: number;
  total: number | null;
  percent: number | null;
}

interface XhrRequestBase {
  url: string;
  method?: string;
  headers?: HeadersInit;
  withCredentials?: boolean;
  timeoutMs?: number;
}

interface UploadFormDataOptions extends XhrRequestBase {
  formData: FormData;
  onUploadProgress?: (progress: TransferProgress) => void;
}

interface DownloadBlobOptions extends XhrRequestBase {
  body?: Document | XMLHttpRequestBodyInit | null;
  onDownloadProgress?: (progress: TransferProgress) => void;
}

export interface DownloadBlobResult {
  blob: Blob;
  headers: Record<string, string>;
}

const normalizeProgress = (loaded: number, total: number): TransferProgress => {
  const safeLoaded = Number.isFinite(loaded) ? Math.max(0, loaded) : 0;
  const safeTotal = Number.isFinite(total) && total > 0 ? total : null;
  const percent = safeTotal ? Math.max(0, Math.min(100, Math.round((safeLoaded / safeTotal) * 100))) : null;
  return {
    loaded: safeLoaded,
    total: safeTotal,
    percent,
  };
};

const applyHeaders = (xhr: XMLHttpRequest, headers?: HeadersInit) => {
  if (!headers) return;
  if (headers instanceof Headers) {
    headers.forEach((value, key) => {
      xhr.setRequestHeader(key, value);
    });
    return;
  }
  if (Array.isArray(headers)) {
    headers.forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });
    return;
  }
  Object.entries(headers).forEach(([key, value]) => {
    if (value == null) return;
    xhr.setRequestHeader(key, String(value));
  });
};

const parseResponseHeaders = (rawHeaders: string): Record<string, string> => {
  const headers: Record<string, string> = {};
  rawHeaders
    .trim()
    .split(/[\r\n]+/)
    .forEach((line) => {
      const delimiterIndex = line.indexOf(':');
      if (delimiterIndex <= 0) return;
      const key = line.slice(0, delimiterIndex).trim().toLowerCase();
      const value = line.slice(delimiterIndex + 1).trim();
      if (!key) return;
      headers[key] = value;
    });
  return headers;
};

const buildHttpErrorMessage = (status: number, responseText: string): string => {
  const trimmed = String(responseText || '').trim();
  if (!trimmed) return `Request failed: HTTP ${status}`;
  try {
    const payload = JSON.parse(trimmed);
    if (typeof payload?.message === 'string' && payload.message.trim()) {
      return payload.message.trim();
    }
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      return payload.detail.trim();
    }
    if (typeof payload?.error === 'string' && payload.error.trim()) {
      return payload.error.trim();
    }
  } catch {
    // not json
  }
  return trimmed;
};

export const uploadFormDataWithXhr = async <T = any>({
  url,
  method = 'POST',
  headers,
  withCredentials = true,
  timeoutMs = 120_000,
  formData,
  onUploadProgress,
}: UploadFormDataOptions): Promise<T> => {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = withCredentials;
    xhr.timeout = timeoutMs;
    xhr.responseType = 'text';
    applyHeaders(xhr, headers);

    xhr.upload.onprogress = (event) => {
      if (!onUploadProgress) return;
      onUploadProgress(normalizeProgress(event.loaded, event.total));
    };

    xhr.onload = () => {
      const status = xhr.status;
      const responseText = xhr.responseText || '';
      if (status < 200 || status >= 300) {
        reject(new Error(buildHttpErrorMessage(status, responseText)));
        return;
      }
      try {
        resolve(responseText ? (JSON.parse(responseText) as T) : (undefined as T));
      } catch (error) {
        reject(new Error(`Invalid JSON response: ${error instanceof Error ? error.message : String(error)}`));
      }
    };

    xhr.onerror = () => reject(new Error('Network error while uploading'));
    xhr.ontimeout = () => reject(new Error(`Upload timeout after ${timeoutMs}ms`));
    xhr.onabort = () => reject(new Error('Upload cancelled'));
    xhr.send(formData);
  });
};

export const downloadBlobWithXhr = async ({
  url,
  method = 'GET',
  headers,
  withCredentials = true,
  timeoutMs = 120_000,
  body = null,
  onDownloadProgress,
}: DownloadBlobOptions): Promise<DownloadBlobResult> => {
  return new Promise<DownloadBlobResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = withCredentials;
    xhr.timeout = timeoutMs;
    xhr.responseType = 'blob';
    applyHeaders(xhr, headers);

    xhr.onprogress = (event) => {
      if (!onDownloadProgress) return;
      onDownloadProgress(normalizeProgress(event.loaded, event.total));
    };

    xhr.onload = () => {
      const status = xhr.status;
      if (status < 200 || status >= 300) {
        const reader = new FileReader();
        reader.onload = () => {
          reject(new Error(buildHttpErrorMessage(status, String(reader.result || ''))));
        };
        reader.onerror = () => reject(new Error(`Request failed: HTTP ${status}`));
        reader.readAsText(xhr.response);
        return;
      }
      resolve({
        blob: xhr.response,
        headers: parseResponseHeaders(xhr.getAllResponseHeaders() || ''),
      });
    };

    xhr.onerror = () => reject(new Error('Network error while downloading'));
    xhr.ontimeout = () => reject(new Error(`Download timeout after ${timeoutMs}ms`));
    xhr.onabort = () => reject(new Error('Download cancelled'));
    xhr.send(body);
  });
};

