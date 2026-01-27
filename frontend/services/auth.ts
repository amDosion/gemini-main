/**
 * 认证服务 - 处理用户认证相关的 API 调用
 */
import { broadcastTokenRefresh, broadcastLogout, listenTokenRefresh, listenLogout } from './authSync';

// ============================================
// 类型定义
// ============================================

export interface AuthConfig {
  allowRegistration: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  status: string;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in: number;
}

export interface RegisterData {
  email: string;
  password: string;
  confirmPassword: string;
  name?: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface AuthError {
  detail: string;
  code?: string;
}

// ============================================
// Token 工具函数
// ============================================

export function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

function setAccessToken(token: string): void {
  localStorage.setItem('access_token', token);
}

function removeAccessToken(): void {
  localStorage.removeItem('access_token');
}

// ✅ 新增：Refresh Token 工具函数
function getRefreshToken(): string | null {
  return localStorage.getItem('refresh_token');
}

function setRefreshToken(token: string): void {
  localStorage.setItem('refresh_token', token);
}

function removeRefreshToken(): void {
  localStorage.removeItem('refresh_token');
}

/**
 * 检查 token 是否过期
 */
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    // 提前 5 分钟判断为过期（缓冲时间）
    return payload.exp * 1000 < Date.now() + 5 * 60 * 1000;
  } catch {
    return true;
  }
}

function getHeaders(includeJson = true): HeadersInit {
  const headers: HeadersInit = {};
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }
  // ✅ 使用 Authorization header 发送 token
  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}


// ============================================
// AuthService 类
// ============================================

class AuthService {
  private baseUrl = '/api/auth';

  // ✅ 配置缓存（避免多个组件同时请求）
  private configCache: { timestamp: number; data: AuthConfig } | null = null;
  private configCacheTTL = 30000; // 30秒缓存
  private configPromise: Promise<AuthConfig> | null = null; // 防止并发请求

  constructor() {
    // ✅ 监听其他标签页的 token 刷新
    listenTokenRefresh((accessToken, refreshToken) => {
      setAccessToken(accessToken);
      setRefreshToken(refreshToken);
    });

    // ✅ 监听其他标签页的登出
    listenLogout(() => {
      removeAccessToken();
      removeRefreshToken();
      // 触发页面刷新或重定向到登录页
      window.location.reload();
    });
  }

  /**
   * 获取认证配置（注册开关状态）- 公开端点，不需要 token
   * ✅ 使用缓存和请求去重，避免多个组件同时请求
   */
  async getConfig(): Promise<AuthConfig> {
    const now = Date.now();

    // ✅ 检查缓存是否有效
    if (this.configCache && now - this.configCache.timestamp < this.configCacheTTL) {
      console.log('[AuthService] Using cached config');
      return this.configCache.data;
    }

    // ✅ 如果已有进行中的请求，复用它（防止并发请求）
    if (this.configPromise) {
      console.log('[AuthService] Reusing pending config request');
      return this.configPromise;
    }

    // ✅ 发起新请求
    console.log('[AuthService] Fetching config...');
    this.configPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/config`, {
          method: 'GET',
          signal: AbortSignal.timeout(10000), // 10秒超时
        });
        if (!response.ok) {
          console.error('[AuthService] 获取配置失败:', response.status, response.statusText);
          throw new Error('Failed to fetch auth config');
        }
        const data = await response.json();
        const result: AuthConfig = {
          allowRegistration: data.allow_registration,
        };

        // ✅ 更新缓存
        this.configCache = { timestamp: Date.now(), data: result };
        console.log('[AuthService] Config fetched and cached:', result);
        return result;
      } finally {
        // ✅ 请求完成，清除 promise 引用
        this.configPromise = null;
      }
    })();

    return this.configPromise;
  }

  /**
   * 用户注册 - 支持注册即登录
   */
  async register(data: RegisterData): Promise<User> {
    const response = await fetch(`${this.baseUrl}/register`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        email: data.email,
        password: data.password,
        confirm_password: data.confirmPassword,
        name: data.name,
      }),
      signal: AbortSignal.timeout(10000), // 10秒超时
    });
    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }
    const result = await response.json();
    // ✅ 新增：如果注册返回了 tokens，保存它们（注册即登录）
    if (result.access_token) {
      setAccessToken(result.access_token);
      console.log('[AuthService] Saved access_token from registration');
    }
    if (result.refresh_token) {
      setRefreshToken(result.refresh_token);
      console.log('[AuthService] Saved refresh_token from registration');
    }
    // 返回用户对象
    return result.user || result;
  }

  /**
   * 用户登录 - 返回用户信息和 token
   */
  async login(data: LoginData): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/login`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
      signal: AbortSignal.timeout(10000), // 10秒超时
    });
    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    const result = await response.json();
    // ✅ 保存 access_token 到 localStorage
    if (result.access_token) {
      setAccessToken(result.access_token);
      // ✅ 同时设置 Cookie（用于 EventSource 等场景）
      // 注意：后端也会设置 Cookie，这里作为双重保障
      const expiresIn = result.expires_in || 3600; // 默认 1 小时
      const expiresDate = new Date(Date.now() + expiresIn * 1000);
      document.cookie = `access_token=${result.access_token}; expires=${expiresDate.toUTCString()}; path=/; SameSite=Lax`;
    }
    // ✅ 保存 refresh_token
    if (result.refresh_token) {
      setRefreshToken(result.refresh_token);
    }
    return result;
  }

  /**
   * 用户登出
   */
  async logout(): Promise<void> {
    try {
      // ✅ 清除 Cookie
      document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax';
    } catch (e) {
      // 忽略 Cookie 清除错误
    }
    try {
      const response = await fetch(`${this.baseUrl}/logout`, {
        method: 'POST',
        headers: getHeaders(),
        signal: AbortSignal.timeout(10000), // 10秒超时
      });
      // 即使后端请求失败，也清除本地 token
      if (!response.ok) {
        console.warn('Logout request failed, but clearing local tokens');
      }
    } catch (error) {
      console.warn('Logout request error, but clearing local tokens:', error);
    } finally {
      // ✅ 清除所有 token
      removeAccessToken();
      removeRefreshToken();
      // ✅ 广播登出事件给其他标签页
      broadcastLogout();
    }
  }

  /**
   * 获取当前用户
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      const token = getAccessToken();
      if (!token) {
        return null;
      }
      const response = await fetch(`${this.baseUrl}/me`, {
        method: 'GET',
        headers: getHeaders(),
        signal: AbortSignal.timeout(10000), // 10秒超时
      });
      if (!response.ok) {
        if (response.status === 401) {
          // Token 无效，清除本地 token
          removeAccessToken();
          return null;
        }
        throw new Error('Failed to get current user');
      }
      return response.json();
    } catch (error) {
      console.warn('[AuthService] getCurrentUser failed:', error);
      // 出错时清除 token
      removeAccessToken();
      return null;
    }
  }

  /**
   * 刷新令牌（改进版 - 支持 Token 轮换和有效性检查）
   */
  async refreshToken(): Promise<boolean> {
    try {
      const accessToken = getAccessToken();
      const refreshToken = getRefreshToken();
      
      if (!refreshToken) {
        console.warn('[AuthService] No refresh token available');
        return false;
      }
      
      // ✅ 检查 access_token 是否真的需要刷新
      if (accessToken && !isTokenExpired(accessToken)) {
        console.log('[AuthService] Access token still valid, skip refresh');
        return true;
      }

      // 发送 refresh_token
      const response = await fetch(`${this.baseUrl}/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${refreshToken}`,
        },
        signal: AbortSignal.timeout(10000),
      });
      
      if (response.ok) {
        const result = await response.json();
        
        // ✅ 更新 access_token
        if (result.access_token) {
          setAccessToken(result.access_token);
          // ✅ 同时更新 Cookie
          const expiresIn = result.expires_in || 3600;
          const expiresDate = new Date(Date.now() + expiresIn * 1000);
          document.cookie = `access_token=${result.access_token}; expires=${expiresDate.toUTCString()}; path=/; SameSite=Lax`;
        }
        
        // ✅ 更新 refresh_token（Token 轮换）
        if (result.refresh_token) {
          setRefreshToken(result.refresh_token);
          console.log('[AuthService] Refresh token rotated');
          // ✅ 广播给其他标签页
          broadcastTokenRefresh(result.access_token, result.refresh_token);
        }
        
        console.log('[AuthService] Token refreshed successfully');
        return true;
      }
      
      console.warn('[AuthService] Token refresh failed');
      return false;
    } catch (error) {
      console.error('[AuthService] Token refresh error:', error);
      return false;
    }
  }
}

// 导出单例
export const authService = new AuthService();
export default authService;
