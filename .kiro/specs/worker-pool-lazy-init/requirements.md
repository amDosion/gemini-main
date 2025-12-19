# Requirements Document

## Introduction

本功能旨在优化上传 Worker 池的启动策略，将其从"应用启动时立即激活"改为"按需激活"模式。当前实现中，Worker 池在应用启动时自动启动 5 个 Worker 并连接 Redis，即使没有上传任务也会持续占用资源。通过按需激活，可以节省系统资源、减少日志噪音，并加快应用启动速度。

## Glossary

- **Worker 池（Worker Pool）**：管理多个并发 Worker 的组件，用于异步处理上传任务
- **Worker**：单个异步任务处理单元，从 Redis 队列获取任务并执行上传
- **Redis 队列**：基于 Redis 的任务队列，用于存储待处理的上传任务
- **懒加载（Lazy Initialization）**：延迟初始化模式，在首次需要时才进行初始化
- **Reconciler**：周期性补偿任务，检查并恢复未入队的 pending 任务
- **崩溃恢复（Crash Recovery）**：应用重启后恢复中断任务的机制

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the Worker pool to start only when needed, so that system resources are not wasted when upload functionality is not in use.

#### Acceptance Criteria

1. WHEN the application starts THEN the Worker_Pool SHALL NOT start Workers automatically
2. WHEN the application starts THEN the Worker_Pool SHALL only establish Redis connection for health checking
3. WHEN the first upload task is enqueued THEN the Worker_Pool SHALL start all Workers within 2 seconds
4. WHILE the Worker_Pool is not started THEN the system SHALL report "idle" status in health checks

### Requirement 2

**User Story:** As a developer, I want interrupted upload tasks to be recovered after application restart, so that no upload tasks are lost.

#### Acceptance Criteria

1. WHEN the application starts AND there are pending or uploading tasks in the database THEN the Worker_Pool SHALL start automatically
2. WHEN the Worker_Pool starts due to pending tasks THEN the system SHALL recover all interrupted tasks
3. WHEN no pending tasks exist at startup THEN the Worker_Pool SHALL remain in idle state

### Requirement 3

**User Story:** As a developer, I want the Worker pool initialization to be thread-safe, so that concurrent upload requests do not cause race conditions.

#### Acceptance Criteria

1. WHEN multiple upload requests arrive simultaneously THEN the Worker_Pool SHALL start only once
2. WHEN the Worker_Pool is starting THEN subsequent requests SHALL wait for initialization to complete
3. IF the Worker_Pool initialization fails THEN the system SHALL allow retry on next request

### Requirement 4

**User Story:** As a system administrator, I want to monitor the Worker pool status, so that I can understand the current state of the upload system.

#### Acceptance Criteria

1. WHEN querying the health endpoint THEN the system SHALL return Worker_Pool status including: idle, starting, running, or error
2. WHEN the Worker_Pool is running THEN the health endpoint SHALL return the number of active Workers
3. WHEN the Worker_Pool is idle THEN the health endpoint SHALL indicate that it will start on demand

### Requirement 5

**User Story:** As a developer, I want the Worker pool to handle edge cases gracefully, so that the system remains stable under abnormal conditions.

#### Acceptance Criteria

1. IF Redis connection fails during lazy initialization THEN the system SHALL log the error and allow retry
2. IF Worker startup fails THEN the system SHALL mark the pool as error state and allow manual restart
3. WHEN the Worker_Pool is in error state THEN new upload requests SHALL trigger a restart attempt
