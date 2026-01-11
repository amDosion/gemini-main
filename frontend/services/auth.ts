/**
 * 认证服务 - 处理用户认证相关的 API 调用
 */

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

function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

function setAccessToken(token: string): void {
  localStorage.setItem('access_token', token);
}

function removeAccessToken(): void {
  localStorage.removeItem('access_token');
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

  /**
   * 获取认证配置（注册开关状态）- 公开端点，不需要 token
   */
  async getConfig(): Promise<AuthConfig> {
    const response = await fetch(`${this.baseUrl}/config`, {
      method: 'GET',
      signal: AbortSignal.timeout(10000), // 10秒超时
    });
    if (!response.ok) {
      throw new Error('Failed to fetch auth config');
    }
    const data = await response.json();
    return {
      allowRegistration: data.allow_registration,
    };
  }

  /**
   * 用户注册
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
    return response.json();
  }

  /**
   * 用户登录 - 返回用户信息和 token
   */
  async login(data: LoginData): Promise<{ user: User; access_token: string; expires_in: number }> {
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
    // ✅ 将 token 存储到 localStorage
    if (result.access_token) {
      setAccessToken(result.access_token);
    }
    return result;
  }

  /**
   * 用户登出
   */
  async logout(): Promise<void> {
    try {
    const response = await fetch(`${this.baseUrl}/logout`, {
      method: 'POST',
      headers: getHeaders(),
      signal: AbortSignal.timeout(10000), // 10秒超时
    });
      // 即使后端请求失败，也清除本地 token
    if (!response.ok) {
        console.warn('Logout request failed, but clearing local token');
      }
    } catch (error) {
      console.warn('Logout request error, but clearing local token:', error);
    } finally {
      // ✅ 清除本地 token
      removeAccessToken();
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
   * 刷新令牌
   */
  async refreshToken(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/refresh`, {
        method: 'POST',
        headers: getHeaders(),
        signal: AbortSignal.timeout(10000), // 10秒超时
      });
      if (response.ok) {
        const result = await response.json();
        if (result.access_token) {
          setAccessToken(result.access_token);
          return true;
        }
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
