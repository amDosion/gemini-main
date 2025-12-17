# 优化方案

以下内容整理了针对当前代码的优化建议，覆盖后端依赖管理、Celery 生命周期治理以及前端多提供商管线的可观测性与退避策略。

## 1. 后端依赖导入与启动自检
- 在 `backend/app/main.py` 提取通用的 `safe_import` / `require_dependency` 辅助函数，集中处理相对/绝对导入的回退与缺失提示，减少重复的 try/except。
- 为浏览器、PDF、Embedding 等可选模块增加启动期自检，并在 `/health` 提供详细状态，避免运行期才暴露缺依赖问题。
- 调整日志输出格式，清晰标记被禁用的功能以及需要额外安装的依赖，便于部署排障。

## 2. Celery Worker 生命周期与可配置性
- 在 `backend/app/main.py` 引入环境变量或配置开关，允许在生产多副本场景关闭自动拉起 worker，由独立进程负责。
- 将 `subprocess` 启动逻辑拆分为可复用的 `start_worker` / `stop_worker` 工具，确保异常时正确清理并记录 PID。
- 在 `/health` 或独立诊断端点增加 Celery 队列可用性检查，及时暴露 worker 健康状态。

## 3. 前端 LLM Provider 可观测性与退避策略
- 在 `frontend/services/LLMFactory.ts` 及各 Provider 的 `sendMessageStream` 中引入统一的链路 ID、耗时与错误指标打点（可先输出到 console/调试面板，后续接入监控）。
- 抽象共享的重试与指数退避模块，在网络错误或 429/5xx 时自动应用，并在 UI 层提示“已自动重试/已降级”。
- 为 HybridDB/后端调用路径添加超时与快速降级策略，确保某个 Provider 或后端不可用时可以平滑切换。
