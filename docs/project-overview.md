# Project Overview

## Product and Business Context

- Product goal: 提供统一 provider/mode 架构下的多模态 AI 产品能力，当前重点之一是 Gemini/Google 视频生成模式。
- Target users: 内部产品、运营和内容生产用户。
- Core business flows:
  - 选择 provider 与 model
  - 读取 mode controls schema
  - 生成图片/视频/音频
  - 写入 session/history/attachments
  - 在历史列表和结果区回看媒体

## Architecture Summary

- Frontend stack and entry points:
  - React + TypeScript
  - 视频模式核心入口：`frontend/components/views/VideoGenView.tsx`
- Backend/services and APIs:
  - FastAPI 风格路由
  - 核心视频路由：`backend/app/routers/core/modes.py`
  - Gemini 视频协调器：`backend/app/services/gemini/coordinators/video_generation_coordinator.py`
- Data storage and external dependencies:
  - session / message / attachment DB 表
  - Google Gemini / Veo provider
- CI/CD and runtime environments:
  - 本地前后端分离开发环境

## Critical Modules

| Module | Responsibility | Key Dependencies | Risk Notes |
| --- | --- | --- | --- |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/components/views/VideoGenView.tsx` | 视频模式页面、历史列表、结果播放器 | `useControlsState`, `useModeControlsSchema`, `ChatEditInputArea` | 当前承载的业务语义偏多，容易越界 |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/controls/modes/google/VideoGenControls.tsx` | Google 视频参数面板 | backend controls schema | 若前端自行推导能力，会与后端漂移 |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/config/mode_controls_catalog.json` | 视频 controls 单一源 | `resolve_mode_controls` | 是 contract 核心，改动需谨慎 |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/routers/core/modes.py` | mode request 校验、附件注入、结果桥接 | provider service, attachment service | 责任大，容易堆逻辑 |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/services/gemini/coordinators/video_generation_coordinator.py` | prompt/storyboard/延长/fallback 核心协调 | Gemini API / Vertex video services | 是视频域真正业务核心 |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/services/gemini/base/video_storyboard.py` | storyboard 与字幕 sidecar 辅助 | coordinator | 直接影响 prompt 质量与元数据语义 |

## Current Capability Baseline

- Existing feature set:
  - text-to-video
  - reference-image driven video
  - Veo 3.1 extension chain
  - session/history persistence
- Known limitations:
  - 视频模式前端仍然带有较多能力语义与默认行为
  - `person_generation` 与 extension 的实际 provider 能力存在边界差异
  - 参考目录中的能力还未系统吸收
- Quality/security debt:
  - contract 与 UI 之间仍有耦合
  - live 上游错误对用户侧表达仍需继续收敛

## Upgrade Opportunities

1. backend-first video capability contract
2. schema-driven video UI mode split
3. identity-lock / styling storyboard quality hardening
