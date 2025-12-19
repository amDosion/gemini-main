# Implementation Plan

## 1. 后端基础设施

- [x] 1.1 创建用户数据模型
  - 在 `backend/app/models/db_models.py` 中添加 `User`、`RefreshToken` 模型
  - 实现 `gemini2026_xxxxxxxx` 格式的用户 ID 生成函数
  - 类型：backend
  - _Requirements: 8.3_

- [x] 1.2 实现 JWT 工具类
  - 在 `backend/app/core/jwt_utils.py` 中实现 `JWTUtils` 类
  - 实现 `create_access_token`（15分钟）、`create_refresh_token`（7天）
  - 实现 `generate_csrf_token`
  - 类型：backend
  - _Requirements: 6.2_

- [x] 1.3 实现密码哈希工具
  - 使用 `passlib[bcrypt]` 实现密码哈希和验证
  - 类型：backend
  - _Requirements: 6.1_

- [x] 1.4 添加环境变量配置
  - 在 `backend/app/core/config.py` 中添加 `ALLOW_REGISTRATION` 配置
  - 默认值为 `false`
  - 类型：backend
  - _Requirements: 8.5_

## 2. 后端认证服务

- [x] 2.1 实现 AuthService
  - 在 `backend/app/services/auth_service.py` 中实现
  - 方法：`is_registration_enabled`、`register`、`login`、`validate_token`、`get_user_by_id`、`invalidate_refresh_token`
  - 注册方法需检查 `ALLOW_REGISTRATION` 开关
  - 类型：backend
  - _Requirements: 1.1, 1.2, 3.1, 3.2, 5.3_

- [x] 2.2 实现 Auth Middleware
  - 在 `backend/app/middleware/auth.py` 中实现
  - 从 cookie 读取并验证 `access_token`
  - 验证 CSRF token（POST/PUT/DELETE）
  - 注入 `request.state.user`
  - 类型：backend
  - _Requirements: 6.2, 6.3_

## 3. 后端 API 路由

- [x] 3.1 实现认证路由
  - 在 `backend/app/routers/auth.py` 中实现
  - `GET /api/auth/config` - 返回注册开关状态
  - `POST /api/auth/register` - 用户注册（受开关控制）
  - `POST /api/auth/login` - 设置 httpOnly cookies
  - `POST /api/auth/logout` - 清除 cookies
  - `POST /api/auth/refresh` - 刷新 access_token
  - `GET /api/auth/me` - 获取当前用户
  - 类型：backend
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.2, 5.1, 5.3_

- [x] 3.2 配置 CORS
  - 修改 `backend/app/main.py` 中的 CORS 配置
  - 设置具体的 `allow_origins`（不使用 `*`）
  - 启用 `allow_credentials=True`
  - 类型：backend
  - _Requirements: 6.5_

- [x] 3.3 注册 Auth Router 和 Middleware
  - 在 `backend/app/main.py` 中注册路由和中间件
  - 类型：backend

## 4. 账号管理脚本

- [x] 4.1 创建账号管理 CLI 脚本
  - 在 `backend/scripts/create_user.py` 中实现
  - 支持创建用户、设置密码
  - 类型：backend
  - _Requirements: 8.1, 8.2_

- [x] 4.2 创建账号管理脚本
  - 在 `backend/scripts/manage_user.py` 中实现
  - 支持禁用/启用账号、重置密码
  - 类型：backend
  - _Requirements: 8.4_

## 5. 前端认证服务

- [x] 5.1 实现 AuthService
  - 在 `frontend/services/auth.ts` 中实现
  - 实现 `getConfig()` 获取注册开关状态
  - 实现 `register()`、`login()`、`logout()`、`getCurrentUser()`、`refreshToken()`
  - 所有请求使用 `credentials: 'include'`
  - 实现 CSRF token 读取和发送
  - 类型：frontend
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 6.3_

- [x] 5.2 实现 useAuth Hook
  - 在 `frontend/hooks/useAuth.ts` 中实现
  - 初始化时调用 `/api/auth/config` 获取注册开关状态
  - 实现自动会话恢复（页面加载时调用 `/api/auth/me`）
  - 实现自动 token 刷新（401 时重试）
  - 暴露 `allowRegistration` 状态
  - 类型：frontend
  - _Requirements: 2.1, 2.2, 4.1, 4.2, 4.3, 4.4_

## 6. 前端组件

- [x] 6.1 更新 LoginPage 组件
  - 修改 `frontend/components/auth/LoginPage.tsx`
  - 使用 `useAuth` Hook
  - 根据 `allowRegistration` 显示/隐藏注册按钮
  - 移除 Mock 数据和测试凭证显示
  - 添加 loading 状态和错误提示
  - 类型：frontend
  - _Requirements: 2.2, 3.3, 3.4, 3.5_

- [x] 6.2 创建 RegisterPage 组件
  - 创建 `frontend/components/auth/RegisterPage.tsx`
  - 实现注册表单（邮箱、密码、确认密码、昵称）
  - 实现表单验证
  - 类型：frontend
  - _Requirements: 1.1, 1.3, 1.4, 1.5_

- [x] 6.3 实现 ProtectedRoute 组件
  - 创建 `frontend/components/auth/ProtectedRoute.tsx`
  - 未认证时重定向到登录页
  - 类型：frontend
  - _Requirements: 4.3_

- [x] 6.4 实现 API 拦截器
  - 创建 `frontend/services/apiClient.ts`
  - 实现 401 自动刷新 token 并重试
  - 实现错误消息友好化
  - 类型：frontend
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

## 7. 集成和清理

- [x] 7.1 集成认证到应用
  - 在 `App.tsx` 中使用 `useAuth` Hook
  - 添加 `/register` 路由（条件渲染）
  - 更新路由配置
  - 类型：frontend

- [x] 7.2 清理 Mock 代码
  - 移除 `frontend/hooks/useLogin.ts` 中的 `MOCK_USERS`
  - 标记为废弃，引导使用 `useAuth`
  - 类型：frontend

- [x] 7.3 创建初始管理员账号
  - 使用脚本创建第一个管理员账号
  - 已创建用户：xcgrmini@example.com, xlhgemini@example.com
  - 类型：backend
  - _Requirements: 8.1, 8.2_

## 8. 测试验证

- [ ]* 8.1 后端单元测试
  - 测试 AuthService 的所有方法
  - 测试注册开关逻辑
  - 测试 JWT 生成和验证
  - 测试密码哈希
  - 类型：backend

- [ ]* 8.2 前端单元测试
  - 测试 useAuth Hook
  - 测试 AuthService
  - 测试注册按钮显示/隐藏逻辑
  - 类型：frontend

- [ ]* 8.3 集成测试
  - 测试完整登录流程
  - 测试注册流程（开关开启时）
  - 测试 token 刷新流程
  - 测试 CSRF 保护
  - 类型：fullstack

## 9. 可选：开发模式降级

- [ ] 9.1 实现开发模式 Mock 认证
  - 仅当 `VITE_DEV_MODE=true` 且后端不可用时启用
  - 显示明显的警告标识
  - 类型：frontend
  - _Requirements: 9.1, 9.2, 9.3_
