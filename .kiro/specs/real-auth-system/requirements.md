# Requirements Document

## Introduction

本文档定义了将现有 Mock 登录系统升级为真实认证系统的需求。系统采用**可控注册模式**（后端可配置是否开放注册，默认关闭），所有用户共享同一套数据，但需要通过认证才能访问公网部署的应用。

## Glossary

| 术语 | 定义 |
|------|------|
| **JWT** | JSON Web Token，用于安全传输用户身份信息的令牌格式 |
| **Access Token** | 短期有效的令牌（15分钟），用于 API 请求认证 |
| **Refresh Token** | 长期有效的令牌（7天），用于获取新的 Access Token |
| **httpOnly Cookie** | 仅服务端可读的 Cookie，防止 XSS 攻击窃取令牌 |
| **CSRF Token** | 跨站请求伪造防护令牌 |
| **注册开关** | 后端环境变量 `ALLOW_REGISTRATION`，控制是否允许新用户注册 |

## Requirements

### Requirement 1: 用户注册（可控）

**User Story:** As a new user, I want to register an account when registration is enabled, so that I can access the application.

#### Acceptance Criteria

1. WHEN registration is enabled AND a user submits valid registration data THEN the System SHALL create a new user account
2. WHEN registration is disabled THEN the System SHALL reject registration requests with 403 status
3. WHEN a user submits an email that already exists THEN the System SHALL reject the registration
4. WHEN a user submits a password shorter than 8 characters THEN the System SHALL reject the registration
5. WHEN a user submits mismatched password and confirm password THEN the System SHALL reject the registration

### Requirement 2: 注册状态查询

**User Story:** As a frontend application, I want to know if registration is enabled, so that I can show or hide the registration button.

#### Acceptance Criteria

1. THE System SHALL provide a `/api/auth/config` endpoint returning registration status
2. WHEN registration is disabled THEN the frontend SHALL hide the registration button
3. WHEN registration is enabled THEN the frontend SHALL show the registration button

### Requirement 3: 用户登录

**User Story:** As a user, I want to log in with my email and password, so that I can access the application.

#### Acceptance Criteria

1. WHEN a user submits valid credentials THEN the System SHALL authenticate the user and set httpOnly cookies containing tokens
2. WHEN a user submits invalid credentials THEN the System SHALL reject the login and display a generic error message (不透露具体哪个字段错误)
3. WHEN a user submits empty email or password THEN the System SHALL prevent submission and indicate required fields
4. WHILE the login request is processing THEN the System SHALL display a loading indicator and disable the submit button
5. WHEN login succeeds THEN the System SHALL redirect to the main application

### Requirement 2: 会话持久化

**User Story:** As a user, I want my session to persist across browser refreshes, so that I do not need to log in repeatedly.

#### Acceptance Criteria

1. WHEN a user has valid cookies THEN the System SHALL automatically restore the session on page load
2. WHEN the access token expires THEN the System SHALL automatically refresh it using the refresh token cookie
3. WHEN the refresh token expires THEN the System SHALL redirect the user to the login page
4. WHEN a user closes and reopens the browser THEN the System SHALL restore the session if cookies remain valid

### Requirement 3: 用户登出

**User Story:** As a user, I want to log out of my account, so that I can secure my session on shared devices.

#### Acceptance Criteria

1. WHEN a user clicks the logout button THEN the System SHALL clear all cookies and session data
2. WHEN a user logs out THEN the System SHALL redirect to the login page
3. WHEN a user logs out THEN the System SHALL invalidate the refresh token on the server

### Requirement 4: API 错误处理

**User Story:** As a developer, I want the authentication system to handle API errors gracefully, so that users receive meaningful feedback.

#### Acceptance Criteria

1. WHEN the backend returns a 401 Unauthorized error THEN the System SHALL attempt token refresh before showing login page
2. WHEN the backend returns a 500 Server Error THEN the System SHALL display a user-friendly error message
3. WHEN a network error occurs THEN the System SHALL display a connectivity error message and allow retry
4. WHEN rate limiting is triggered THEN the System SHALL display the remaining wait time

### Requirement 5: 安全性

**User Story:** As a security-conscious user, I want my credentials to be handled securely, so that my account remains protected.

#### Acceptance Criteria

1. THE System SHALL transmit credentials only over HTTPS
2. THE System SHALL store tokens in httpOnly cookies with Secure and SameSite=Strict flags
3. THE System SHALL implement CSRF protection for all state-changing endpoints
4. THE System SHALL clear all authentication data when tokens are invalidated
5. THE System SHALL configure CORS to only allow specific origins (not `*`)

### Requirement 8: 账号管理

**User Story:** As an administrator, I want to manage user accounts, so that I can control who has access to the system.

#### Acceptance Criteria

1. THE System SHALL provide a CLI script to create new user accounts
2. THE System SHALL support setting initial password for new accounts
3. THE System SHALL generate unique user IDs in `gemini2026_xxxxxxxx` format
4. THE System SHALL allow administrators to disable/enable accounts
5. THE System SHALL provide environment variable `ALLOW_REGISTRATION` to control registration (default: false)

### Requirement 9: 开发模式降级（可选）

**User Story:** As a developer, I want to use the application without backend during development, so that I can work on frontend independently.

#### Acceptance Criteria

1. WHEN `VITE_DEV_MODE=true` AND backend is unavailable THEN the System MAY allow local mock authentication
2. WHEN in production mode THEN the System SHALL NOT allow any mock authentication
3. WHEN using mock mode THEN the System SHALL display a clear warning indicator
