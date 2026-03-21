# Repository Structure Map

## Directory Tree (Video-Domain Focus)

```text
.
├── frontend/
│   ├── components/views/VideoGenView.tsx
│   ├── controls/modes/google/VideoGenControls.tsx
│   ├── components/chat/ChatEditInputArea.tsx
│   ├── hooks/useControlsState.ts
│   ├── hooks/useModeControlsSchema.ts
│   └── services/providers/UnifiedProviderClient.ts
├── backend/
│   └── app/
│       ├── config/mode_controls_catalog.json
│       ├── routers/core/modes.py
│       ├── services/common/mode_controls_catalog.py
│       └── services/gemini/
│           ├── coordinators/video_generation_coordinator.py
│           └── base/
│               ├── video_common.py
│               └── video_storyboard.py
└── 参考/
    ├── veo-studio/
    ├── fit-check/
    ├── proactive-co-creator/
    └── versatile-execution-agent/
```

## File Responsibility Matrix

| Path | Layer | File Responsibility | Main Inputs/Outputs | Owner Role |
| --- | --- | --- | --- | --- |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/components/views/VideoGenView.tsx` | frontend | 视频模式页面、历史列表、播放器与参数面板挂载点 | session messages, controls state, mode send | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/controls/modes/google/VideoGenControls.tsx` | frontend | 读取 schema 并渲染 Google 视频控件 | controls schema in, selected values out | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/components/chat/ChatEditInputArea.tsx` | frontend | 把当前视频控件值打包成 mode request options | controls state in, request payload out | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/hooks/useControlsState.ts` | frontend | 视频控件 UI 状态容器 | schema defaults in, UI values out | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/hooks/useModeControlsSchema.ts` | frontend | 获取后端 mode controls schema | provider/mode/model in, schema out | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/frontend/services/providers/UnifiedProviderClient.ts` | frontend | 统一 provider mode 请求发送器 | mode request in, backend response out | frontend |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/config/mode_controls_catalog.json` | backend | 视频模式能力、默认值和模型变体单一源 | static config in, resolved schema out | backend |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/services/common/mode_controls_catalog.py` | backend | controls schema 解析、别名归一化、参数校验辅助 | catalog in, normalized schema/params out | backend |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/routers/core/modes.py` | backend | 统一 mode 路由，参数桥接与附件注入 | HTTP request in, provider result + persistence out | backend |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/services/gemini/coordinators/video_generation_coordinator.py` | backend | 视频 prompt/storyboard/延长/fallback 核心协调 | normalized params in, provider-ready request out | backend |
| `/Users/xuelihong/gemini-main/gemini-main/backend/app/services/gemini/base/video_storyboard.py` | backend | storyboard prompt 与字幕 sidecar 生成 | prompt + options in, storyboard artifacts out | backend |
| `/Users/xuelihong/gemini-main/gemini-main/参考/veo-studio/*` | reference | Veo 官方能力导向的前端演示 | direct SDK video generation | project_owner |
| `/Users/xuelihong/gemini-main/gemini-main/参考/fit-check/*` | reference | identity-lock / try-on / pose variation prompt 思路 | image editing prompts | project_owner |

## Hotspots and Coupling

- Cross-cutting files:
  - `modes.py`
  - `video_generation_coordinator.py`
  - `VideoGenView.tsx`
- High-churn files:
  - `VideoGenView.tsx`
  - `VideoGenControls.tsx`
  - `mode_controls_catalog.json`
- Tight-coupling risks:
  - 前端控件默认值与后端 schema 漂移
  - coordinator 业务语义与路由桥接重复
  - reference-project 能力直接搬进前端而绕开后端 contract
