/**
 * API 客户端 - 带有自动 token 刷新和错误处理
 */
import { authService } from './auth';
import {
  getAccessToken as getStoredAccessToken,
  getAuthorizationHeader,
} from './authTokenStore';
import { fetchWithTimeout, parseHttpError, readJsonResponse } from './http';

// ============================================
// 类型定义
// ============================================

interface ApiClientOptions {
  baseUrl?: string;
  onUnauthorized?: () => void;
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  timeoutMs?: number;
}

// ============================================
// Token 工具函数
// ============================================

export function getAccessToken(): string | null {
  return getStoredAccessToken();
}

export function getAuthHeaders(options: { includeBearer?: boolean } = {}): Record<string, string> {
  return options.includeBearer ? getAuthorizationHeader() : {};
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
    const { skipAuth, timeoutMs, ...fetchOptions } = options;

    // 发送请求。认证请求统一同时支持内存 Authorization 与 httpOnly Cookie。
    const response = await fetchWithTimeout(`${this.baseUrl}${url}`, {
      ...fetchOptions,
      withAuth: !skipAuth,
      timeoutMs,
    });

    // 处理 401 错误 - 尝试刷新 token
    if (response.status === 401 && !skipAuth) {
      const refreshed = await this.tryRefreshToken();
      if (refreshed) {
        const retryHeaders = new Headers(fetchOptions.headers);
        retryHeaders.delete('Authorization');
        
        // 重试原请求，仍然走 httpOnly Cookie，避免 stale bearer 覆盖新 Cookie。
        const retryResponse = await fetchWithTimeout(`${this.baseUrl}${url}`, {
          ...fetchOptions,
          headers: retryHeaders,
          withAuth: true,
          timeoutMs,
        });
        
        if (!retryResponse.ok) {
          const parsedError = await parseHttpError(
            retryResponse,
            `Request failed: ${retryResponse.status}`
          );
          throw new Error(parsedError.message);
        }

        return readJsonResponse<T>(retryResponse);
      } else {
        // 刷新失败，触发未授权回调
        this.onUnauthorized?.();
        throw new Error('Unauthorized');
      }
    }

    // 处理其他错误
    if (!response.ok) {
      const parsedError = await parseHttpError(response, `Request failed: ${response.status}`);
      throw new Error(parsedError.message);
    }

    // 返回响应数据
    return readJsonResponse<T>(response);
  }

  /**
   * 尝试刷新 token
   *
   * 使用 .finally() 链接在共享 promise 上重置状态，确保所有并发调用者
   * 都能观察到相同的 promise 生命周期，而不会因 finally 块过早清空状态
   * 导致新进入的调用者拿到已重置的引用。
   */
  private tryRefreshToken(): Promise<boolean> {
    // 如果已经在刷新中，直接返回同一个 promise，所有等待方共享结果
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    // 将 .finally() 挂在共享 promise 上，确保状态在所有消费者 settle 后重置
    this.refreshPromise = authService.refreshToken().finally(() => {
      this.isRefreshing = false;
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }

  // 便捷方法
  get<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  post<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    // 如果 data 是 FormData，不设置 Content-Type，让浏览器自动设置
    const isFormData = data instanceof FormData;
    const headers: HeadersInit = isFormData 
      ? { ...options?.headers }  // FormData 时不设置 Content-Type
      : { 'Content-Type': 'application/json', ...options?.headers };
    
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      headers,
      body: isFormData ? data : (data ? JSON.stringify(data) : undefined),
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
