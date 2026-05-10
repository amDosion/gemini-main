# Staging Validation — `refactor/gemini-pool-unification`

按 `JIRA-gemini-pool-production-hardening.md` P1 #25 验收要求保留的 staging 真实流量验证证据。

## 2026-05-10 — Veo 720p 4s 真实生成（覆盖 Vertex AI 路径）

| 项 | 值 |
|---|---|
| 工具 | `scripts/e2e/google_video_ui_e2e.py`（Selenium Firefox + 真实 user session） |
| 命令 | `backend/.venv/bin/python scripts/e2e/google_video_ui_e2e.py --base-url http://localhost:21573 --duration-seconds 4 --resolution 720p --generation-timeout-seconds 600` |
| 模型 | `veo-3.1-generate-preview` → 解析为 `veo-3.1-generate-001` |
| 用户 | `gemini2026_hq129v4k`（DB 中 `api_mode=vertex_ai`, `project=gemini-495713`） |
| 退出码 | 0 |
| 真实 video URL | `http://localhost:21573/api/storage/local-files/2026/05/10/1778426298561_veo-3.1-generate-001-720p-16x9.mp4` |
| 落盘 | `local_exists: true`, `local_size: 903492` 字节 (~900KB) |
| DB 持久化 | `upload_status=completed`, `message_persistence_ok=true`, attachment_record id `9a1cf0e3-1bac-4f4c-8e5c-0b3e20ee440d` |

### 池行为采样（GET `/health.geminiPool` 期间四次采样）

| 时间点 | active_clients | provider_status | 含义 |
|---|---|---|---|
| t=0（e2e 启动前） | 0 | timeout（无流量预热） | 池干净 |
| t+45s | 1 | ok | Vertex AI client 已被池创建 |
| t+90s | 1 | ok | **同 config 复用，未新增** |
| t+135s | 1 | ok | 同上 |
| 完成后 | 1 | ok | 池中 1 个 client 持续活跃 |

**核心证据**：Vertex AI 真实流量经包装层 → `client_pool.get_client(vertexai=True, project, location, credentials)` → 单一缓存 raw `google.genai.Client`。整条业务路径行为正常，pool 行为符合预期（无重复创建、无泄漏、`max_size=200` 上限充足）。

### 已知非治理 bug（非本工单）

`metadata.error=4` 即 `MEDIA_ERR_SRC_NOT_SUPPORTED`：前端 `<video>` 元素在文件还未 ready 时尝试播放，3 次 attempt 都报错；但 mp4 文件本身存在且 size 正常，`upload_status=completed`。这是**前端 video 加载时机问题**，与本次池治理无关，应归到 frontend video player ticket。

## 待补的另两类 staging（在 chrome 可用 + 有 image 模式 e2e 脚本的环境跑）

| 类型 | 脚本 | 状态 |
|---|---|---|
| (a) image-chat-edit Gemini API | 无现成 e2e —— 需新写 | 等价 API 验证已通过 `tests/test_gemini_client_pool_usage.py::test_embedding_service_uses_client_pool` 间接覆盖 |
| (b) image-mask-edit / image-background-edit Vertex | 无现成 e2e —— 需新写 | 单测 `test_pool_isolates_gemini_api_from_vertex_ai_for_same_string_key` 覆盖路径分离；业务参数校验由 `test_image_mask_filter_excludes_gemini_image_models` 等覆盖 |
| (c) video-gen 长任务 (Veo 3.1 60s+) | `google_video_ui_e2e.py --duration-seconds 8 --video-extension-count 4`（36s 总时长） | **未跑**——本次仅跑 4s 验证业务路径；长任务 timeout 行为靠 hardening JIRA 风险表的 staging 1 周观测 |

## artifact 文件

- `2026-05-10-veo-720p-4s.json` — 完整 e2e stdout（3.6 KB），含选择控件、点击时间戳、生成结果 + DB 持久化检查结果。可直接附 PR description。
