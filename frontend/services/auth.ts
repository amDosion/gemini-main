/**
 * 认证服务 - 处理用户认证相关的 API 调用
 */
import {
  broadcastTokenRefresh,
  broadcastLogout,
  listenTokenRefresh,
  listenLogout,
} from './authSync';
import {
  getAccessToken,
  getRefreshToken,
  removeAccessToken,
  removeRefreshToken,
  setAccessToken,
  setRefreshToken,
  withAuthorization,
} from './authTokenStore';
import { fetchWithTimeout, parseHttpError, readJsonResponse } from './http';
import { cacheManager } from './CacheManager';

export { getAccessToken } from './authTokenStore';

const AUTH_CONFIG_SYNC_KEY = 'gemini_auth_config_updated';
const AUTH_CONFIG_UPDATED_EVENT = 'auth-config-updated';

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
  isAdmin?: boolean;
  createdAt?: string;
  updatedAt?: string;
  lastLoginAt?: string;
  hasActiveProfile?: boolean; // ✅ 新增：是否有活跃的配置文件
}

export interface LoginResponse {
  user: User;
  accessToken: string;
  refreshToken?: string;
  tokenType?: string;
  expiresIn: number;
  hasActiveProfile?: boolean; // ✅ 新增：是否有活跃的配置文件
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

export interface ChangePasswordData {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export interface AuthError {
  detail: string;
  code?: string;
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
  return withAuthorization(includeJson ? { 'Content-Type': 'application/json' } : {});
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

  // ✅ Wave 2 perf: in-flight + result cache for current user
  // 避免 useAuth init/refresh 等同 mount tick 内多次串行调用 /auth/me
  // logout / login / refreshToken 需调 clearUserCache() 失效
  private userPromise: Promise<User | null> | null = null;

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

    if (typeof window !== 'undefined') {
      window.addEventListener('storage', (event) => {
        if (event.key === AUTH_CONFIG_SYNC_KEY) {
          this.invalidateConfigCache();
          window.dispatchEvent(new Event(AUTH_CONFIG_UPDATED_EVENT));
        }
      });
    }
  }

  /**
   * 清理认证配置缓存（例如管理员修改注册开关后）。
   */
  invalidateConfigCache(): void {
    this.configCache = null;
    this.configPromise = null;
  }

  /**
   * 广播认证配置变更（用于跨页面静默刷新注册开关等配置）。
   */
  notifyConfigUpdated(): void {
    this.invalidateConfigCache();
    if (typeof window === 'undefined') return;

    try {
      localStorage.setItem(AUTH_CONFIG_SYNC_KEY, String(Date.now()));
    } catch {
      // ignore storage errors
    }

    window.dispatchEvent(new Event(AUTH_CONFIG_UPDATED_EVENT));
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
        const response = await fetchWithTimeout(`${this.baseUrl}/config`, {
          method: 'GET',
        });
        if (!response.ok) {
          throw new Error('Failed to fetch auth config');
        }
        const data = await readJsonResponse<any>(response);
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
    const response = await fetchWithTimeout(`${this.baseUrl}/register`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        email: data.email,
        password: data.password,
        confirmPassword: data.confirmPassword,
        name: data.name,
      }),
    });
    if (!response.ok) {
      const error = await parseHttpError(response, 'Registration failed');
      throw new Error(error.message);
    }
    const result = await readJsonResponse<any>(response);
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
    const response = await fetchWithTimeout(`${this.baseUrl}/login`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await parseHttpError(response, 'Login failed');
      throw new Error(error.message);
    }
    const result = await readJsonResponse<any>(response);
    // ✅ 保存 access_token 到 localStorage
    if (result.accessToken) {
      setAccessToken(result.accessToken);
      // ✅ 同时设置 Cookie（用于 EventSource 等场景）
      // 注意：后端也会设置 Cookie，这里作为双重保障
    }
    // ✅ 保存 refresh_token
    if (result.refreshToken) {
      setRefreshToken(result.refreshToken);
    }
    // ✅ 保存配置状态（优化：减少前端初始化请求）
    if (result.hasActiveProfile !== undefined) {
      localStorage.setItem('has_active_profile', String(result.hasActiveProfile));
    }
    // ✅ Wave 2 perf: 清除可能存在的上一用户缓存（新用户登录场景）
    this.clearUserCache();
    return result;
  }

  /**
   * 用户登出
   * ✅ C-9: 删除空 try/catch 死代码;cookie 清除由后端 clear_auth_cookies 处理
   */
  async logout(): Promise<void> {
    try {
      const response = await fetchWithTimeout(`${this.baseUrl}/logout`, {
        method: 'POST',
        headers: getHeaders(),
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
      // ✅ Wave 2 perf: 清除用户缓存防跨用户脏读
      this.clearUserCache();
      // ✅ 广播登出事件给其他标签页
      broadcastLogout();
    }
  }

  /**
   * 清除当前用户缓存（logout / token 刷新失败 / login 切换用户 时调用）。
   * Wave 2 perf: 避免跨用户脏读 + 配合 Promise 单例去重。
   */
  clearUserCache(): void {
    this.userPromise = null;
  }

  /**
   * 获取当前用户
   *
   * ✅ Wave 2 perf: Promise 单例去重 —— 同 tick 内多次调用（init + refresh + login）
   * 复用同一个 /auth/me in-flight Promise；resolve 后保留结果便于其它 consumer 复用。
   * force=true 时绕过缓存（refreshUser 主动刷新场景）。
   * 注意：仅缓存成功结果；错误/无 token 时不缓存，让下次调用重新尝试。
   */
  async getCurrentUser(force = false): Promise<User | null> {
    if (force) {
      this.userPromise = null;
    }
    if (this.userPromise) {
      return this.userPromise;
    }

    const promise = (async (): Promise<User | null> => {
      try {
        const token = getAccessToken();
        if (!token) {
          return null;
        }
        const response = await fetchWithTimeout(`${this.baseUrl}/me`, {
          method: 'GET',
          headers: getHeaders(),
        });
        if (!response.ok) {
          if (response.status === 401) {
            // Token 无效，清除本地 token
            removeAccessToken();
            return null;
          }
          throw new Error('Failed to get current user');
        }
        const result = await readJsonResponse<any>(response);

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
    })();

    // 仅在成功（user 非空）时保留缓存；null/失败 不缓存以允许后续重试
    this.userPromise = promise.then((result) => {
      if (result === null) {
        this.userPromise = null;
      }
      return result;
    });

    return this.userPromise;
  }

  /**
   * 刷新令牌（改进版 - 支持 Token 轮换和有效性检查）
   * ✅ C-4: 区分语义
   *   - return true  → 刷新成功
   *   - return false → 服务器明确拒绝(401/403/422),refresh_token 已失效,caller 应清 token
   *   - throw error  → 网络错误/超时/其它,caller 不清 token,允许后续重试
   */
  async refreshToken(): Promise<boolean> {
    const accessToken = getAccessToken();
    const refreshToken = getRefreshToken();

    if (!refreshToken) {
      return false;
    }

    // ✅ 检查 access_token 是否真的需要刷新
    if (accessToken && !isTokenExpired(accessToken)) {
      return true;
    }

    // 发送 refresh_token —— 网络错误向上抛,由 caller 决定是否清 token
    const response = await fetchWithTimeout(`${this.baseUrl}/refresh`, {
      method: 'POST',
      headers: withAuthorization(
        {
          'Content-Type': 'application/json',
        },
        { token: refreshToken }
      ),
    });

    if (response.ok) {
      const result = await readJsonResponse<any>(response);

      // ✅ 更新 access_token
      if (result.accessToken) {
        setAccessToken(result.accessToken);
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

    // 仅在服务器明确拒绝(401/403/422)时返回 false,其它状态码视为异常
    if (response.status === 401 || response.status === 403 || response.status === 422) {
      return false;
    }

    // 5xx 等错误抛出,允许 caller 重试而不清 token
    throw new Error(`Refresh token request failed with status ${response.status}`);
  }

  /**
   * 修改当前用户密码
   */
  async changePassword(data: ChangePasswordData): Promise<void> {
    const response = await fetchWithTimeout(`${this.baseUrl}/change-password`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        currentPassword: data.currentPassword,
        newPassword: data.newPassword,
        confirmPassword: data.confirmPassword,
      }),
    });

    if (!response.ok) {
      const error = await parseHttpError(response, 'Failed to change password');
      throw new Error(error.message);
    }
  }
}

// 导出单例
export const authService = new AuthService();
export default authService;
