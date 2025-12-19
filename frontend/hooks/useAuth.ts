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

  // 初始化：获取配置和当前用户
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        // 并行获取配置和当前用户
        const [config, currentUser] = await Promise.all([
          authService.getConfig().catch(() => ({ allowRegistration: false })),
          authService.getCurrentUser(),
        ]);
        setAllowRegistration(config.allowRegistration);
        setUser(currentUser);
      } catch (err) {
        console.error('Auth init error:', err);
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
      const loggedInUser = await authService.login(data);
      setUser(loggedInUser);
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
      setUser(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Logout failed';
      setError(message);
      throw err;
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
