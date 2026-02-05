/**
 * useAuth Hook - 管理用户认证状态
 */
import { useState, useEffect, useCallback } from 'react';
import { authService, User, RegisterData, LoginData } from '../services/auth';

export interface UseAuthReturn {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  allowRegistration: boolean;
  hasActiveProfile: boolean | null;  // ✅ 新增：是否有活跃的配置文件
  register: (data: RegisterData) => Promise<void>;
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  refreshUser: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allowRegistration, setAllowRegistration] = useState(false);
  const [hasActiveProfile, setHasActiveProfile] = useState<boolean | null>(null);  // ✅ 新增状态

  // 初始化：尝试刷新 token 而不是直接清除
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        const token = localStorage.getItem('access_token');
        const refreshToken = localStorage.getItem('refresh_token');

        // ✅ 先从 localStorage 读取缓存的配置状态（立即可用）
        const cachedStatus = localStorage.getItem('has_active_profile');
        if (cachedStatus !== null) {
          setHasActiveProfile(cachedStatus === 'true');
        }

        if (token) {
          try {
            // 尝试获取用户信息
            const [currentUser, config] = await Promise.all([
              authService.getCurrentUser(),
              authService.getConfig().catch(() => ({ allowRegistration: false }))
            ]);
            setUser(currentUser);
            setAllowRegistration(config.allowRegistration);

            // ✅ 更新配置状态（从用户信息中获取）
            if (currentUser?.hasActiveProfile !== undefined) {
              setHasActiveProfile(currentUser.hasActiveProfile);
            }
          } catch {
            // ✅ 新增：如果有 refresh_token，尝试刷新
            if (refreshToken) {
              try {
                const refreshed = await authService.refreshToken();
                if (refreshed) {
                  // 刷新成功，重新获取用户信息
                  const [currentUser, config] = await Promise.all([
                    authService.getCurrentUser(),
                    authService.getConfig().catch(() => ({ allowRegistration: false }))
                  ]);
                  setUser(currentUser);
                  setAllowRegistration(config.allowRegistration);

                  // ✅ 更新配置状态
                  if (currentUser?.hasActiveProfile !== undefined) {
                    setHasActiveProfile(currentUser.hasActiveProfile);
                  }
                  return; // 成功，退出
                }
              } catch {
                // Refresh failed
              }
            }

            // 刷新失败或没有 refresh_token，清除所有 tokens
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('has_active_profile');  // ✅ 同时清除配置状态
            setUser(null);
            setHasActiveProfile(null);
            const config = await authService.getConfig().catch(() => ({ allowRegistration: false }));
            setAllowRegistration(config.allowRegistration);
          }
        } else {
          // 没有 token，设置为未登录状态
          const config = await authService.getConfig().catch(() => ({ allowRegistration: false }));
          setAllowRegistration(config.allowRegistration);
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

  // ✅ 新增：自动刷新 Token（静默刷新）
  useEffect(() => {
    if (!user) return;

    // ✅ 使用服务端返回的 expires_in，提前 2 小时刷新（更安全）
    // 24 小时 - 2 小时 = 22 小时后刷新
    const refreshInterval = 22 * 60 * 60 * 1000; // 22 小时（毫秒）
    
    const timer = setInterval(async () => {
      try {
        const success = await authService.refreshToken();
        if (!success) {
          setUser(null);
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      } catch {
        setUser(null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    }, refreshInterval);

    return () => {
      clearInterval(timer);
    };
  }, [user]);


  // 注册
  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true);
    setError(null);
    try {
      const newUser = await authService.register(data);
      setUser(newUser);

      // ✅ 更新配置状态（注册后通常没有配置）
      const cachedStatus = localStorage.getItem('has_active_profile');
      if (cachedStatus !== null) {
        setHasActiveProfile(cachedStatus === 'true');
      }
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
      // ✅ 登录成功，设置用户信息（token 已自动存储到 localStorage）
      setUser(result.user);

      // ✅ 设置配置状态（优化：减少前端初始化请求）
      if (result.hasActiveProfile !== undefined) {
        setHasActiveProfile(result.hasActiveProfile);
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
      setHasActiveProfile(null);  // ✅ 清除配置状态
      localStorage.removeItem('has_active_profile');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Logout failed';
      setError(message);
      // 即使出错也清除用户状态
      setUser(null);
      setHasActiveProfile(null);
      localStorage.removeItem('has_active_profile');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 刷新用户信息
  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);

      // ✅ 更新配置状态
      if (currentUser?.hasActiveProfile !== undefined) {
        setHasActiveProfile(currentUser.hasActiveProfile);
      }
    } catch {
      // Failed to refresh user
    }
  }, []);

  // 清除错误
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    allowRegistration,
    hasActiveProfile,  // ✅ 新增：返回配置状态
    register,
    login,
    logout,
    clearError,
    refreshUser,
  };
}

export default useAuth;
