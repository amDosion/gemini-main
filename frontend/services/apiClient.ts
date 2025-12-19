/**
 * API 客户端 - 带有自动 token 刷新和错误处理
 */
import { authService } from './auth';

// ============================================
// 类型定义
// ============================================

interface ApiClientOptions {
  baseUrl?: string;
  onUnauthorized?: () => void;
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

// ============================================
// CSRF Token 工具函数
// ============================================

function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

// ============================================
// ApiClient 类
// ============================================

class ApiClient {
  private baseUrl: string;
  private onUnauthorized?: () => void;
  private isRefreshing = false;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl || '';
    this.onUnauthorized = options.onUnauthorized;
  }

  /**
   * 设置未授权回调
   */
  setOnUnauthorized(callback: () => void) {
    this.onUnauthorized = callback;
  }

  /**
   * 发送请求
   */
  async request<T>(url: string, options: RequestOptions = {}): Promise<T> {
    const { skipAuth, ...fetchOptions } = options;

    // 构建请求头
    const headers: HeadersInit = {
      ...fetchOptions.headers,
    };

    // 添加 CSRF token（对于状态变更请求）
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(fetchOptions.method?.toUpperCase() || '')) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        (headers as Record<string, string>)['X-CSRF-Token'] = csrfToken;
      }
    }

    // 发送请求
    const response = await fetch(`${this.baseUrl}${url}`, {
      ...fetchOptions,
      headers,
      credentials: 'include',
    });

    // 处理 401 错误 - 尝试刷新 token
    if (response.status === 401 && !skipAuth) {
      const refreshed = await this.tryRefreshToken();
      if (refreshed) {
        // 重试原请求
        return this.request<T>(url, { ...options, skipAuth: true });
      } else {
        // 刷新失败，触发未授权回调
        this.onUnauthorized?.();
        throw new Error('Unauthorized');
      }
    }

    // 处理其他错误
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed: ${response.status}`);
    }

    // 返回响应数据
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  }

  /**
   * 尝试刷新 token
   */
  private async tryRefreshToken(): Promise<boolean> {
    // 如果已经在刷新中，等待结果
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    this.refreshPromise = authService.refreshToken();

    try {
      const result = await this.refreshPromise;
      return result;
    } finally {
      this.isRefreshing = false;
      this.refreshPromise = null;
    }
  }

  // 便捷方法
  get<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  post<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  delete<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: 'DELETE' });
  }
}

// 导出单例
export const apiClient = new ApiClient();
export default apiClient;
