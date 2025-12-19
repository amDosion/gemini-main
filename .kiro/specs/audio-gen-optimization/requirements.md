# Audio Generation Mode 优化需求文档

## 概述

本文档记录 `audio-gen` 模式的优化需求，用于后期开发参考。

## 当前状态

`audio-gen` 模式目前存在以下问题：

1. **UI 控制不匹配**：当前使用通用的 `GenerationControls` 组件，显示了不相关的图片生成参数（分辨率、尺寸、风格等）
2. **缺少专用控制**：音频生成需要特定的控制选项，如语音选择、音频时长、语速等

## 需求列表

### Requirement 1: 移除不相关的 UI 控制

**User Story:** 作为用户，我希望在 `audio-gen` 模式下不看到图片生成相关的控制选项，以避免混淆。

#### Acceptance Criteria

1. WHEN 用户切换到 `audio-gen` 模式 THEN 系统 SHALL 隐藏 `GenerationControls` 组件
2. WHEN 用户在 `audio-gen` 模式下 THEN 系统 SHALL 不显示分辨率、尺寸、风格等图片参数

### Requirement 2: 添加音频专用控制组件

**User Story:** 作为用户，我希望在 `audio-gen` 模式下看到音频相关的控制选项，以便自定义生成的音频。

#### Acceptance Criteria

1. WHEN 用户在 `audio-gen` 模式下 THEN 系统 SHALL 显示语音选择器（Voice Selector）
2. WHEN 用户选择语音 THEN 系统 SHALL 使用选定的语音生成音频
3. WHERE 支持多种语音选项 THEN 系统 SHALL 提供至少以下语音：Puck, Charon, Kore, Fenrir, Aoede

### Requirement 3: 音频生成参数配置

**User Story:** 作为用户，我希望能够配置音频生成的参数，以获得更符合需求的输出。

#### Acceptance Criteria

1. WHERE 用户需要调整音频参数 THEN 系统 SHALL 提供高级设置面板
2. WHEN 用户打开高级设置 THEN 系统 SHALL 显示可配置的音频参数
3. WHEN 用户修改参数 THEN 系统 SHALL 在下次生成时应用新参数

## 技术实现建议

### 1. 创建 `AudioControls.tsx` 组件

```typescript
// frontend/components/chat/input/AudioControls.tsx
interface AudioControlsProps {
  voice: string;
  setVoice: (v: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}
```

### 2. 修改 `InputArea.tsx` 条件渲染

```typescript
// 在条件渲染中添加 audio-gen 模式的处理
{mode === 'chat' ? (
    <ChatControls ... />
) : mode === 'audio-gen' ? (
    <AudioControls ... />
) : isGenMode ? (
    <GenerationControls ... />
) : null}
```

### 3. 语音选项配置

```typescript
const VOICE_OPTIONS = [
  { label: "Puck", value: "Puck", description: "Friendly and energetic" },
  { label: "Charon", value: "Charon", description: "Deep and authoritative" },
  { label: "Kore", value: "Kore", description: "Warm and professional" },
  { label: "Fenrir", value: "Fenrir", description: "Bold and confident" },
  { label: "Aoede", value: "Aoede", description: "Soft and melodic" }
];
```

## 优先级

- **P1**: 移除不相关的 UI 控制（已完成部分，需要进一步优化）
- **P2**: 添加语音选择器
- **P3**: 添加高级音频参数配置

## 相关文件

- `frontend/components/chat/InputArea.tsx` - 主输入区域组件
- `frontend/components/chat/input/GenerationControls.tsx` - 生成控制组件
- `frontend/hooks/handlers/audioGenHandler.ts` - 音频生成处理器（如存在）
- `frontend/services/audioService.ts` - 音频服务（如存在）

## 备注

当前修改已将 `audio-gen` 模式从 `GenerationControls` 中排除，但尚未添加专用的音频控制组件。后续开发时需要：

1. 创建 `AudioControls.tsx` 组件
2. 在 `InputArea.tsx` 中集成该组件
3. 确保语音参数正确传递到后端
