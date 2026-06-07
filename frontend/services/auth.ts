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
  removeAccessToken,
  removeRefreshToken,
} from './authTokenStore';
import { fetchWithTimeout, parseHttpError, readJsonResponse } from './http';
import { clearPrivateClientCaches } from './privateClientCache';
import { getPrivateCacheUserScope, setPrivateCacheUserScope } from './privateCacheScope';

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

/** Raw shape returned by GET /auth/config (after camelCase middleware). */
interface AuthConfigRaw {
  allowRegistration: boolean;
}

/**
 * Raw shape returned by POST /auth/register.
 * Backend returns either a wrapped form { user, hasActiveProfile } or
 * the User object directly; both shapes are handled below.
 */
type RegisterResponseRaw =
  | { user: User; hasActiveProfile?: boolean }
  | (User & { user?: undefined });

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

function getTokenExpiresAt(token: string | null): number | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = Number(payload.exp);
    return Number.isFinite(exp) ? exp * 1000 : null;
  } catch {
    return null;
  }
}

function getJsonHeaders(): HeadersInit {
  return { 'Content-Type': 'application/json' };
}

function setAuthenticatedMediaScope(user: Pick<User, 'id'> | null | undefined): void {
  setPrivateCacheUserScope(user?.id || null);
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
  private userCacheGeneration = 0;

  private async clearPrivateBrowserCaches(): Promise<void> {
    await clearPrivateClientCaches();
  }

  private isUserCacheGenerationCurrent(generation: number | null | undefined): boolean {
    return generation === null || generation === undefined || generation === this.userCacheGeneration;
  }

  private async applyAuthenticatedUserScope(
    user: Pick<User, 'id'> | null | undefined,
    generationAtStart?: number
  ): Promise<boolean> {
    if (!this.isUserCacheGenerationCurrent(generationAtStart)) {
      return false;
    }

    const nextUserScope = user?.id || null;
    if (!nextUserScope) {
      setAuthenticatedMediaScope(null);
      return true;
    }

    const currentUserScope = getPrivateCacheUserScope();
    if (currentUserScope !== nextUserScope) {
      await this.clearPrivateBrowserCaches();
      if (!this.isUserCacheGenerationCurrent(generationAtStart)) {
        return false;
      }
    }

    setPrivateCacheUserScope(nextUserScope);
    return true;
  }

  constructor() {
    // 其他标签页刷新 Cookie 后，本标签页清掉可能过期的内存 token。
    // 后续请求优先走 httpOnly Cookie，避免 stale Authorization header 覆盖新 Cookie。
    listenTokenRefresh(() => {
      removeAccessToken();
      removeRefreshToken();
      this.clearUserCache();
    });

    // ✅ 监听其他标签页的登出
    listenLogout(async () => {
      await this.clearLocalPrivateSessionState();
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
        const data = await readJsonResponse<AuthConfigRaw>(response);
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
      headers: getJsonHeaders(),
      withAuth: true,
      skipAuth: true,
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
    const result = await readJsonResponse<RegisterResponseRaw>(response);
    removeAccessToken();
    this.clearUserCache();
    await this.clearPrivateBrowserCaches();
    setAuthenticatedMediaScope(result.user || result);
    // 返回用户对象
    const user = result.user || result;
    if (user?.hasActiveProfile === undefined && result.hasActiveProfile !== undefined) {
      return { ...user, hasActiveProfile: result.hasActiveProfile };
    }
    return user;
  }

  /**
   * 用户登录 - 返回用户信息；认证凭据由后端写入 httpOnly Cookie
   */
  async login(data: LoginData): Promise<LoginResponse> {
    const response = await fetchWithTimeout(`${this.baseUrl}/login`, {
      method: 'POST',
      headers: getJsonHeaders(),
      withAuth: true,
      skipAuth: true,
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await parseHttpError(response, 'Login failed');
      throw new Error(error.message);
    }
    const result = await readJsonResponse<LoginResponse>(response);
    removeAccessToken();
    // ✅ Wave 2 perf: 清除可能存在的上一用户缓存（新用户登录场景）
    this.clearUserCache();
    await this.clearPrivateBrowserCaches();
    setAuthenticatedMediaScope(result.user);
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
        withAuth: true,
        skipAuth: true,
      });
      // 即使后端请求失败，也清除本地 token
      if (!response.ok) {
        // Logout request failed, but clearing local tokens
      }
    } catch (error) {
      // Logout request error, clearing local tokens
    } finally {
      await this.clearLocalPrivateSessionState({ broadcast: true });
    }
  }

  async clearLocalPrivateSessionState(options: { broadcast?: boolean } = {}): Promise<void> {
    // ✅ 清除所有 token
    removeAccessToken();
    removeRefreshToken();
    try {
      localStorage.removeItem('has_active_profile');
    } catch {
      // ignore storage errors
    }
    // ✅ Wave 2 perf: 清除用户缓存防跨用户脏读
    this.clearUserCache();
    await this.clearPrivateBrowserCaches();
    setAuthenticatedMediaScope(null);
    if (options.broadcast) {
      // ✅ 广播登出事件给其他标签页
      broadcastLogout();
    }
  }

  /**
   * 清除当前用户缓存（logout / token 刷新失败 / login 切换用户 时调用）。
   * Wave 2 perf: 避免跨用户脏读 + 配合 Promise 单例去重。
   */
  clearUserCache(): void {
    this.userCacheGeneration += 1;
    this.userPromise = null;
  }

  getAccessTokenRefreshDelayMs(): number {
    const expiresAt = getTokenExpiresAt(getAccessToken());
    if (!expiresAt) {
      return 5 * 60 * 1000;
    }

    const refreshAt = expiresAt - 2 * 60 * 1000;
    return Math.max(30 * 1000, refreshAt - Date.now());
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
      this.clearUserCache();
    }
    if (this.userPromise) {
      return this.userPromise;
    }

    const generationAtStart = this.userCacheGeneration;
    const promise = (async (): Promise<User | null> => {
      const response = await fetchWithTimeout(`${this.baseUrl}/me`, {
        method: 'GET',
        withAuth: true,
        skipAuth: true,
      });
      if (!response.ok) {
        if (response.status === 401) {
          await this.clearLocalPrivateSessionState();
          return null;
        }
        throw new Error('Failed to get current user');
      }
      const result = await readJsonResponse<User>(response);

      if (!this.isUserCacheGenerationCurrent(generationAtStart)) {
        return null;
      }

      const scopeApplied = await this.applyAuthenticatedUserScope(result, generationAtStart);
      if (!scopeApplied) {
        return null;
      }
      return result;
    })();

    // 仅在成功（user 非空）时保留缓存；null/失败 不缓存以允许后续重试
    const trackedPromise = promise
      .then((result) => {
        if (result === null && this.userPromise === trackedPromise) {
          this.userPromise = null;
        }
        return result;
      })
      .catch((error) => {
        if (this.userPromise === trackedPromise) {
          this.userPromise = null;
        }
        throw error;
      });

    this.userPromise = trackedPromise;
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

    // ✅ 检查 access_token 是否真的需要刷新
    if (accessToken && !isTokenExpired(accessToken)) {
      return true;
    }

    const headers = new Headers({ 'Content-Type': 'application/json' });

    // refresh token 只走 httpOnly Cookie，不再进入 JS 内存或 Authorization header。
    const response = await fetchWithTimeout(`${this.baseUrl}/refresh`, {
      method: 'POST',
      headers,
      withAuth: true,
      skipAuth: true,
    });

    if (response.ok) {
      removeAccessToken();
      broadcastTokenRefresh();

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
      headers: getJsonHeaders(),
      withAuth: true,
      skipAuth: true,
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
