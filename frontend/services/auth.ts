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
// CSRF Token 工具函数
// ============================================

function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

function getHeaders(includeJson = true): HeadersInit {
  const headers: HeadersInit = {};
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken;
  }
  return headers;
}


// ============================================
// AuthService 类
// ============================================

class AuthService {
  private baseUrl = '/api/auth';

  /**
   * 获取认证配置（注册开关状态）
   */
  async getConfig(): Promise<AuthConfig> {
    const response = await fetch(`${this.baseUrl}/config`, {
      method: 'GET',
      credentials: 'include',
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
      credentials: 'include',
      headers: getHeaders(),
      body: JSON.stringify({
        email: data.email,
        password: data.password,
        confirm_password: data.confirmPassword,
        name: data.name,
      }),
    });
    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }
    return response.json();
  }

  /**
   * 用户登录
   */
  async login(data: LoginData): Promise<User> {
    const response = await fetch(`${this.baseUrl}/login`, {
      method: 'POST',
      credentials: 'include',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    return response.json();
  }

  /**
   * 用户登出
   */
  async logout(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: getHeaders(),
    });
    if (!response.ok) {
      throw new Error('Logout failed');
    }
  }

  /**
   * 获取当前用户
   */
  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await fetch(`${this.baseUrl}/me`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        if (response.status === 401) {
          return null;
        }
        throw new Error('Failed to get current user');
      }
      return response.json();
    } catch {
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
        credentials: 'include',
        headers: getHeaders(),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

// 导出单例
export const authService = new AuthService();
export default authService;
