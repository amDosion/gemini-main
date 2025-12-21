# Image Outpainting 功能需求文档

## 1. 简介

本文档定义了 Image Outpainting（画布扩展）功能的需求规格。该功能允许用户扩展图像边界，在图像边界外生成新内容，将半身照补全为全身照，或扩展背景区域。

## 2. 术语表

| 术语 | 定义 |
|------|------|
| **Outpainting** | 画布扩展，在图像边界外生成新内容 |
| **Expansion Mask** | 扩展掩码，标识需要生成内容的扩展区域（白色=扩展区域，黑色=原图区域） |
| **Expansion Direction** | 扩展方向，包括上（top）、下（bottom）、左（left）、右（right）、全部（all） |
| **Expansion Pixels** | 扩展像素数，指定每个方向扩展的像素数量 |
| **Imagen 3** | Google 的图像生成/编辑模型，用于画布扩展 |
| **Vertex AI** | Google Cloud 的 AI 平台，提供 Imagen 3 API |
| **AppMode** | 应用模式，定义当前功能视图（如 `'chat'`, `'image-gen'`, `'image-outpainting'`） |
| **Handler** | 处理器，负责处理特定模式的业务逻辑 |

## 3. 需求列表

### 需求 3.1：图片上传与验证

**用户故事**：作为用户，我希望系统能验证上传的图片格式和大小，确保功能正常运行。

#### 验收标准

1. **AC-3.1.1**：WHEN 用户上传图片 THEN 系统 SHALL 支持 JPG 和 PNG 格式
2. **AC-3.1.2**：WHEN 用户上传图片 THEN 系统 SHALL 限制文件大小不超过 10MB
3. **AC-3.1.3**：IF 用户上传不支持的格式 THEN 系统 SHALL 提示用户并拒绝上传
4. **AC-3.1.4**：IF 用户上传超过大小限制的文件 THEN 系统 SHALL 提示用户并拒绝上传
5. **AC-3.1.5**：WHEN 图片上传成功 THEN 系统 SHALL 在画布中显示预览

---

### 需求 3.2：扩展方向选择

**用户故事**：作为用户，我希望能选择图像扩展的方向，以便根据需要补全不同区域。

#### 验收标准

1. **AC-3.2.1**：WHEN 用户选择向下扩展 THEN 系统 SHALL 在图像底部生成新内容
2. **AC-3.2.2**：WHEN 用户选择向上扩展 THEN 系统 SHALL 在图像顶部生成新内容
3. **AC-3.2.3**：WHEN 用户选择向左扩展 THEN 系统 SHALL 在图像左侧生成新内容
4. **AC-3.2.4**：WHEN 用户选择向右扩展 THEN 系统 SHALL 在图像右侧生成新内容
5. **AC-3.2.5**：WHERE 用户选择四个方向同时扩展 THEN 系统 SHALL 同时处理所有方向

---

### 需求 3.3：扩展参数设置

**用户故事**：作为用户，我希望能精确控制扩展的大小，以便获得理想的结果。

#### 验收标准

1. **AC-3.3.1**：WHEN 用户指定扩展像素数 THEN 系统 SHALL 按指定像素数扩展画布
2. **AC-3.3.2**：WHEN 用户指定扩展比例 THEN 系统 SHALL 按原图尺寸的比例扩展画布
3. **AC-3.3.3**：WHEN 扩展参数超过合理范围 THEN 系统 SHALL 提示用户并拒绝处理
4. **AC-3.3.4**：WHEN 用户未指定扩展参数 THEN 系统 SHALL 使用默认值（如 256 像素）

---

### 需求 3.4：扩展内容生成

**用户故事**：作为用户，我希望系统能在扩展区域生成与原图风格一致的内容。

#### 验收标准

1. **AC-3.4.1**：WHEN 扩展完成 THEN 系统 SHALL 自动生成扩展区域的掩码
2. **AC-3.4.2**：WHEN 扩展完成 THEN 系统 SHALL 确保扩展内容与原图风格、光照保持一致
3. **AC-3.4.3**：WHEN 扩展完成 THEN 系统 SHALL 确保扩展内容与原图边缘自然融合
4. **AC-3.4.4**：WHERE 用户提供内容描述 THEN 系统 SHALL 根据描述生成扩展内容
5. **AC-3.4.5**：WHERE 用户未提供内容描述 THEN 系统 SHALL 自动推断并生成合适的扩展内容

---

### 需求 3.5：用户界面集成

**用户故事**：作为用户，我希望能通过独立的模式入口使用画布扩展功能，并与现有的模式切换机制无缝集成。

#### 验收标准

1. **AC-3.5.1**：WHEN 系统启动 THEN `AppMode` 类型 SHALL 包含 `'image-outpainting'` 模式
2. **AC-3.5.2**：WHEN 用户选择 `image-outpainting` 模式 THEN 系统 SHALL 显示专用的 `ImageExpandView` 界面
3. **AC-3.5.3**：WHEN 用户进入 Image Outpainting 界面 THEN 系统 SHALL 提供方向选择控件（上/下/左/右/全部）
4. **AC-3.5.4**：WHEN 用户进入 Image Outpainting 界面 THEN 系统 SHALL 提供扩展像素数输入控件
5. **AC-3.5.5**：WHEN 用户输入内容描述 THEN 系统 SHALL 将描述传递给扩展 API
6. **AC-3.5.6**：WHEN 用户点击生成按钮 THEN 系统 SHALL 调用 `handleImageExpand` Handler 处理请求
7. **AC-3.5.7**：WHEN 生成完成 THEN 系统 SHALL 在界面中显示结果图片
8. **AC-3.5.8**：WHEN 用户查看结果 THEN 系统 SHALL 提供原图与结果图的对比功能
9. **AC-3.5.9**：WHEN 用户需要下载 THEN 系统 SHALL 支持下载原图和结果图

---

### 需求 3.6：认证与配置

**用户故事**：作为系统管理员，我希望能配置 Vertex AI 认证信息，以便系统能调用 Imagen 3 API。

#### 验收标准

1. **AC-3.6.1**：WHEN 系统启动 THEN 系统 SHALL 从环境变量读取 `GCP_PROJECT_ID` 配置
2. **AC-3.6.2**：WHEN 调用 Imagen 3 API THEN 系统 SHALL 通过后端代理调用 Vertex AI API（避免前端暴露凭证）
3. **AC-3.6.3**：IF Vertex AI 未配置 THEN 系统 SHALL 显示友好的错误提示，指导用户配置

---

### 需求 3.7：错误处理

**用户故事**：作为用户，我希望在操作失败时能看到清晰的错误信息，以便了解问题原因。

#### 验收标准

1. **AC-3.7.1**：IF 画布扩展失败 THEN 系统 SHALL 提示具体原因（如安全过滤、API 限制等）
2. **AC-3.7.2**：IF 扩展比例过大 THEN 系统 SHALL 提示用户减小扩展像素数
3. **AC-3.7.3**：IF 掩码生成失败 THEN 系统 SHALL 记录错误并提示用户
4. **AC-3.7.4**：IF 画布创建失败 THEN 系统 SHALL 提示用户检查图像格式
5. **AC-3.7.5**：WHEN 任何错误发生 THEN 系统 SHALL 记录详细的错误日志以便调试

---

## 4. 技术约束

### 4.1 API 依赖

| API | 用途 | 认证方式 |
|-----|------|---------|
| **Vertex AI** | 图像扩展（Imagen 3） | GCP 项目 + OAuth |

### 4.2 模型版本

- **扩展模型**：`imagen-3.0-capability-001`

### 4.3 图像限制

- 建议图像尺寸：1024×1024 或更小
- 支持格式：PNG、JPEG
- 最大文件大小：10MB
- 扩展后最大尺寸：建议不超过 2048×2048

### 4.4 数据流集成点

| 组件 | 文件 | 集成方式 |
|------|------|---------|
| 类型定义 | `types.ts` | 扩展 `AppMode` 和 `ChatOptions` |
| 数据处理 | `useChat.ts` | 添加 `image-outpainting` 模式分支 |
| Handler | `handlers/imageExpandHandler.ts` | 新增或更新 Handler 文件 |
| 服务 | `google/media/image-expand.ts` | 新增服务文件 |
| UI 组件 | `views/ImageExpandView.tsx` | 新增或更新视图组件 |
| 路由 | `StudioView.tsx` | 添加 case 分支 |

---

## 5. 非功能性需求

1. **性能**：画布扩展的总处理时间应控制在 30 秒以内
2. **安全**：Vertex AI 凭证不应暴露在前端代码中
3. **可用性**：界面操作应直观，无需用户了解底层技术细节
4. **一致性**：与现有模式（如 `image-edit`、`virtual-try-on`）保持一致的交互模式和数据流
5. **可扩展性**：支持未来添加更多扩展选项（如智能裁剪、自动补全等）
