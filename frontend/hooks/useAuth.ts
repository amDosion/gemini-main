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

  // 初始化：只在有 token 时才获取用户信息
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        // ✅ 修复：只在有 token 时才获取用户信息和配置
        const token = localStorage.getItem('access_token');
        if (token) {
          // 有 token，获取用户信息和配置
          try {
            const [currentUser, config] = await Promise.all([
              authService.getCurrentUser(),
              authService.getConfig().catch(() => ({ allowRegistration: false }))
            ]);
            setUser(currentUser);
            setAllowRegistration(config.allowRegistration);
          } catch (err) {
            // Token 可能已过期，清除 token
            console.warn('Auth token invalid, clearing:', err);
            localStorage.removeItem('access_token');
            setUser(null);
            // 获取配置（不需要认证）
        const config = await authService.getConfig().catch(() => ({ allowRegistration: false }));
        setAllowRegistration(config.allowRegistration);
          }
        } else {
          // 没有 token，设置为未登录状态
          // ✅ 修复：未登录时也获取配置（用于显示注册按钮）
          const config = await authService.getConfig().catch(() => ({ allowRegistration: false }));
          setAllowRegistration(config.allowRegistration);
          setUser(null);
        }
      } catch (err) {
        console.error('Auth init error:', err);
        // 即使出错也设置为未登录状态
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);


  // 注册
  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true);
    setError(null);
    try {
      const newUser = await authService.register(data);
      setUser(newUser);
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Logout failed';
      setError(message);
      // 即使出错也清除用户状态
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 刷新用户信息
  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error('Failed to refresh user:', err);
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
    register,
    login,
    logout,
    clearError,
    refreshUser,
  };
}

export default useAuth;
