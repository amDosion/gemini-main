/**
 * useAuth Hook - 管理用户认证状态
 */
import { useState, useEffect, useCallback } from 'react';
import { authService, User, RegisterData, LoginData, ChangePasswordData } from '../services/auth';

export interface UseAuthReturn {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  allowRegistration: boolean;
  hasActiveProfile: boolean | null; // ✅ 新增：是否有活跃的配置文件
  register: (data: RegisterData) => Promise<void>;
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  refreshUser: () => Promise<void>;
  changePassword: (data: ChangePasswordData) => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allowRegistration, setAllowRegistration] = useState(false);
  const [hasActiveProfile, setHasActiveProfile] = useState<boolean | null>(null); // ✅ 新增状态

  // 初始化：Cookie 是主认证状态；内存 token 只作为当前标签页加速路径。
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        const configPromise = authService.getConfig().catch(() => ({ allowRegistration: false }));
        let currentUser = await authService.getCurrentUser();

        if (!currentUser) {
          try {
            const refreshed = await authService.refreshToken();
            if (refreshed) {
              currentUser = await authService.getCurrentUser(true);
            }
          } catch {
            // refresh 网络错误或服务端拒绝都进入未登录收敛路径
          }
        }

        const config = await configPromise;
        setAllowRegistration(config.allowRegistration);

        if (currentUser) {
          setUser(currentUser);
          if (currentUser.hasActiveProfile !== undefined) {
            setHasActiveProfile(currentUser.hasActiveProfile);
          }
        } else {
          await authService.clearLocalPrivateSessionState();
          setUser(null);
          setHasActiveProfile(null);
        }
      } catch {
        setUser(null);
        setHasActiveProfile(null);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  // 监听认证配置变更（例如管理员更新注册开关），静默刷新 allowRegistration
  useEffect(() => {
    const handleAuthConfigUpdated = async () => {
      const config = await authService.getConfig().catch(() => ({ allowRegistration: false }));
      setAllowRegistration(config.allowRegistration);
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('auth-config-updated', handleAuthConfigUpdated);
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('auth-config-updated', handleAuthConfigUpdated);
      }
    };
  }, []);

  // ✅ 新增：自动刷新 Token（静默刷新）
  // ✅ B-8: deps 改 [user?.id] 避免 user 对象引用变化重建定时器
  useEffect(() => {
    if (!user) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const scheduleNextRefresh = () => {
      if (cancelled) return;
      timer = setTimeout(async () => {
        try {
          const success = await authService.refreshToken();
          if (success === false) {
            await authService.clearLocalPrivateSessionState({ broadcast: true });
            setUser(null);
            setHasActiveProfile(null);
            return;
          }
        } catch {
          // 网络错误,保留状态
        }
        scheduleNextRefresh();
      }, authService.getAccessTokenRefreshDelayMs());
    };

    scheduleNextRefresh();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [user?.id]);

  const refreshAuthenticatedUser = useCallback(async () => {
    try {
      const success = await authService.refreshToken();
      if (success === false) {
        await authService.clearLocalPrivateSessionState({ broadcast: true });
        setUser(null);
        setHasActiveProfile(null);
        return null;
      }
      return await authService.getCurrentUser(true);
    } catch {
      return null;
    }
  }, []);

  // 注册
  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true);
    setError(null);
    try {
      const newUser = await authService.register(data);
      setUser(newUser);
      setHasActiveProfile(newUser.hasActiveProfile ?? null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 登录
  const login = useCallback(async (data: LoginData) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await authService.login(data);

      // ✅ B-1: 优先使用 login response 中的 user 字段(后端已返回),消除串行 /me 调用;
      // 兼容旧 schema —— 如果后端尚未返回 user,fall-through 到 /me
      let currentUser: typeof result.user | null = result.user ?? null;
      if (!currentUser) {
        currentUser = await authService.getCurrentUser();
      }
      if (!currentUser) {
        throw new Error('Failed to fetch current user after login');
      }
      setUser(currentUser);

      // ✅ 设置配置状态（优化：减少前端初始化请求）
      if (result.hasActiveProfile !== undefined) {
        setHasActiveProfile(result.hasActiveProfile);
      } else if (currentUser.hasActiveProfile !== undefined) {
        setHasActiveProfile(currentUser.hasActiveProfile);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 登出
  const logout = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.logout();
      // ✅ token 已在 authService.logout() 中清除
      setUser(null);
      setHasActiveProfile(null); // ✅ 清除配置状态
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Logout failed';
      setError(message);
      // 即使出错也清除用户状态
      setUser(null);
      setHasActiveProfile(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 刷新用户信息
  const refreshUser = useCallback(async () => {
    try {
      // ✅ Wave 2 perf: force=true 绕过缓存（用户主动刷新场景需要实时数据）
      const currentUser = await refreshAuthenticatedUser();
      setUser(currentUser);

      // ✅ 更新配置状态
      if (currentUser?.hasActiveProfile !== undefined) {
        setHasActiveProfile(currentUser.hasActiveProfile);
      }
    } catch {
      // Failed to refresh user
    }
  }, [refreshAuthenticatedUser]);

  // 清除错误
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const changePassword = useCallback(async (data: ChangePasswordData) => {
    setError(null);
    await authService.changePassword(data);
  }, []);

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    allowRegistration,
    hasActiveProfile, // ✅ 新增：返回配置状态
    register,
    login,
    logout,
    clearError,
    refreshUser,
    changePassword,
  };
}

export default useAuth;
