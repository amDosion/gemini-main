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
  hasActiveProfile?: boolean;  // ✅ 新增：是否有活跃的配置文件
}

export interface LoginResponse {
  user: User;
  accessToken: string;
  refreshToken?: string;
  tokenType?: string;
  expiresIn: number;
  hasActiveProfile?: boolean;  // ✅ 新增：是否有活跃的配置文件
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
      return this.configCache.data;
    }

    // ✅ 如果已有进行中的请求，复用它（防止并发请求）
    if (this.configPromise) {
      return this.configPromise;
    }

    // ✅ 发起新请求
    this.configPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/config`, {
          method: 'GET',
          signal: AbortSignal.timeout(10000), // 10秒超时
        });
        if (!response.ok) {
          throw new Error('Failed to fetch auth config');
        }
        const data = await response.json();
        const result: AuthConfig = {
          // ✅ 后端统一返回 snake_case，中间件转换为 camelCase
          allowRegistration: data.allowRegistration ?? false,
        };

        // ✅ 更新缓存
        this.configCache = { timestamp: Date.now(), data: result };
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
        confirmPassword: data.confirmPassword,
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
    if (result.accessToken) {
      setAccessToken(result.accessToken);
    }
    if (result.refreshToken) {
      setRefreshToken(result.refreshToken);
    }
    // ✅ 保存配置状态（优化：减少前端初始化请求）
    if (result.hasActiveProfile !== undefined) {
      localStorage.setItem('has_active_profile', String(result.hasActiveProfile));
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
    if (result.accessToken) {
      setAccessToken(result.accessToken);
      // ✅ 同时设置 Cookie（用于 EventSource 等场景）
      // 注意：后端也会设置 Cookie，这里作为双重保障
      const expiresIn = result.expiresIn || 3600; // 默认 1 小时
      const expiresDate = new Date(Date.now() + expiresIn * 1000);
      document.cookie = `access_token=${result.accessToken}; expires=${expiresDate.toUTCString()}; path=/; SameSite=Lax`;
    }
    // ✅ 保存 refresh_token
    if (result.refreshToken) {
      setRefreshToken(result.refreshToken);
    }
    // ✅ 保存配置状态（优化：减少前端初始化请求）
    if (result.hasActiveProfile !== undefined) {
      localStorage.setItem('has_active_profile', String(result.hasActiveProfile));
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
        // Logout request failed, but clearing local tokens
      }
    } catch (error) {
      // Logout request error, clearing local tokens
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
      const result = await response.json();

      // ✅ 更新配置状态（优化：减少前端初始化请求）
      if (result.hasActiveProfile !== undefined) {
        localStorage.setItem('has_active_profile', String(result.hasActiveProfile));
      }

      return result;
    } catch {
      // getCurrentUser failed, clearing token
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
        return false;
      }
      
      // ✅ 检查 access_token 是否真的需要刷新
      if (accessToken && !isTokenExpired(accessToken)) {
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
        if (result.accessToken) {
          setAccessToken(result.accessToken);
          // ✅ 同时更新 Cookie
          const expiresIn = result.expiresIn || 3600;
          const expiresDate = new Date(Date.now() + expiresIn * 1000);
          document.cookie = `access_token=${result.accessToken}; expires=${expiresDate.toUTCString()}; path=/; SameSite=Lax`;
        }

        // ✅ 更新 refresh_token（Token 轮换）
        if (result.refreshToken) {
          setRefreshToken(result.refreshToken);
          // ✅ 广播给其他标签页
          broadcastTokenRefresh(result.accessToken, result.refreshToken);
        }

        // ✅ 更新配置状态（优化：减少前端初始化请求）
        if (result.hasActiveProfile !== undefined) {
          localStorage.setItem('has_active_profile', String(result.hasActiveProfile));
        }

        return true;
      }
      
      return false;
    } catch {
      return false;
    }
  }
}

// 导出单例
export const authService = new AuthService();
export default authService;
