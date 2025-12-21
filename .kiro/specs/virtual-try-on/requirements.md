# Virtual Try-On 功能需求文档

## 1. 简介

本文档定义了 Virtual Try-On（虚拟试衣）功能的需求规格。该功能允许用户上传人物照片，通过 AI 技术实现服装的虚拟替换、画布扩展和图像超分辨率处理。

## 2. 术语表

| 术语 | 定义 |
|------|------|
| **Virtual Try-On** | 虚拟试衣，通过 AI 技术在图像中替换服装 |
| **Segmentation Mask** | 分割掩码，用于标识图像中需要编辑的区域（白色=目标区域，黑色=保留区域） |
| **Inpainting** | 图像修复/填充，在掩码区域生成新内容 |
| **Outpainting** | 画布扩展，在图像边界外生成新内容 |
| **Upscale** | 图像超分辨率，提高图像分辨率和清晰度 |
| **Gemini 2.5** | Google 的多模态 AI 模型，用于图像理解和分割 |
| **Imagen 3** | Google 的图像生成/编辑模型，用于服装替换和画布扩展 |
| **Imagen 4** | Google 的图像超分辨率模型，用于提高图像分辨率 |
| **Vertex AI** | Google Cloud 的 AI 平台，提供 Imagen 3/4 API |
| **AppMode** | 应用模式，定义当前功能视图（如 `'chat'`, `'image-gen'`, `'virtual-try-on'`） |
| **Handler** | 处理器，负责处理特定模式的业务逻辑 |
| **HandlerContext** | 处理器上下文，包含会话 ID、消息 ID、API Key 等信息 |

## 3. 需求列表

### 需求 3.1：服装分割功能

**用户故事**：作为用户，我希望系统能自动识别并分割图像中的服装区域，以便进行后续的服装替换。

#### 验收标准

1. **AC-3.1.1**：WHEN 用户上传包含人物的图像 THEN 系统 SHALL 调用 Gemini API 识别指定的服装类型（如 `hoodie`、`jacket`、`shirt`、`pants` 等）
2. **AC-3.1.2**：WHEN 分割完成 THEN 系统 SHALL 生成精确的二值掩码（白色=服装区域，黑色=其他区域）
3. **AC-3.1.3**：WHEN 分割完成 THEN 系统 SHALL 返回边界框坐标（`box_2d`，归一化到 1000）和掩码数据（`mask`，Base64 编码）
4. **AC-3.1.4**：WHERE 用户选择不同的 Gemini 模型 THEN 系统 SHALL 支持 `gemini-2.5-flash`、`gemini-2.5-pro`、`gemini-3-flash-preview` 等模型

---

### 需求 3.2：服装替换功能（Inpainting）

**用户故事**：作为用户，我希望能通过文字描述来替换图像中的服装，生成逼真的虚拟试衣效果。

#### 验收标准

1. **AC-3.2.1**：WHEN 用户提供服装描述（如 "A dark green jacket, white shirt inside"）THEN 系统 SHALL 在掩码区域生成对应的服装
2. **AC-3.2.2**：WHEN 生成完成 THEN 系统 SHALL 确保生成的服装与原图的光照、风格保持一致
3. **AC-3.2.3**：WHERE 用户选择 `inpainting-insert` 编辑模式 THEN 系统 SHALL 在掩码区域插入新内容
4. **AC-3.2.4**：WHERE 用户选择 `inpainting-remove` 编辑模式 THEN 系统 SHALL 移除掩码区域的内容
5. **AC-3.2.5**：WHERE 用户调整掩码膨胀系数（`dilation`，范围 0.0-1.0）THEN 系统 SHALL 优化边缘融合效果

---

### 需求 3.3：图像超分辨率功能（Upscale）

**用户故事**：作为用户，我希望能提高生成图像的分辨率和清晰度，以便获得更高质量的结果。

#### 验收标准

1. **AC-3.4.1**：WHEN 用户选择超分辨率功能 THEN 系统 SHALL 使用 Imagen 4 模型进行处理
2. **AC-3.4.2**：WHERE 用户选择 2x 放大 THEN 系统 SHALL 将图像分辨率提高到原来的 2 倍
3. **AC-3.4.3**：WHERE 用户选择 4x 放大 THEN 系统 SHALL 将图像分辨率提高到原来的 4 倍
4. **AC-3.4.4**：WHEN 输出分辨率超过 17 megapixels THEN 系统 SHALL 提示用户并拒绝处理
5. **AC-3.4.5**：WHERE 用户选择不添加水印 THEN 系统 SHALL 生成无水印的高分辨率图像
6. **AC-3.4.6**：WHEN 超分辨率完成 THEN 系统 SHALL 保持图像质量和细节

---

### 需求 3.4：用户界面集成

**用户故事**：作为用户，我希望能通过独立的模式入口使用虚拟试衣功能，并与现有的模式切换机制无缝集成。

#### 验收标准

1. **AC-3.5.1**：WHEN 系统启动 THEN `AppMode` 类型 SHALL 包含 `'virtual-try-on'` 模式
2. **AC-3.5.2**：WHEN 用户选择 `virtual-try-on` 模式 THEN 系统 SHALL 显示专用的 `VirtualTryOnView` 界面
3. **AC-3.5.3**：WHEN 用户进入 Virtual Try-On 界面 THEN 系统 SHALL 提供服装类型选择控件（上衣、下装、全身、自定义）
4. **AC-3.5.4**：WHERE 用户启用掩码预览 THEN 系统 SHALL 显示分割掩码叠加在原图上的预览效果（半透明红色）
5. **AC-3.5.5**：WHEN 用户输入服装描述 THEN 系统 SHALL 将描述传递给编辑 API
6. **AC-3.5.6**：WHEN 用户点击生成按钮 THEN 系统 SHALL 调用 `handleVirtualTryOn` Handler 处理请求
7. **AC-3.5.7**：WHEN 生成完成 THEN 系统 SHALL 在界面中显示结果图片
8. **AC-3.5.8**：WHEN 用户查看结果 THEN 系统 SHALL 提供原图与结果图的对比功能
9. **AC-3.5.9**：WHEN 用户需要下载 THEN 系统 SHALL 支持下载原图、结果图和掩码

---

### 需求 3.5：图片上传与验证

**用户故事**：作为用户，我希望系统能验证上传的图片格式和大小，确保功能正常运行。

#### 验收标准

1. **AC-3.6.1**：WHEN 用户上传图片 THEN 系统 SHALL 支持 JPG 和 PNG 格式
2. **AC-3.6.2**：WHEN 用户上传图片 THEN 系统 SHALL 限制文件大小不超过 10MB
3. **AC-3.6.3**：IF 用户上传不支持的格式 THEN 系统 SHALL 提示用户并拒绝上传
4. **AC-3.6.4**：IF 用户上传超过大小限制的文件 THEN 系统 SHALL 提示用户并拒绝上传
5. **AC-3.6.5**：WHEN 图片上传成功 THEN 系统 SHALL 在画布中显示预览

---

### 需求 3.6：认证与配置

**用户故事**：作为系统管理员，我希望能配置 Vertex AI 认证信息，以便系统能调用 Imagen 3/4 API。

#### 验收标准

1. **AC-3.7.1**：WHEN 系统启动 THEN 系统 SHALL 从环境变量读取 `GCP_PROJECT_ID` 配置
2. **AC-3.7.2**：WHEN 调用 Imagen 3/4 API THEN 系统 SHALL 通过后端代理调用 Vertex AI API（避免前端暴露凭证）
3. **AC-3.7.3**：IF Vertex AI 未配置 THEN 系统 SHALL 显示友好的错误提示，指导用户配置

---

### 需求 3.7：掩码预览参数调整

**用户故事**：作为用户，我希望能够动态调整掩码预览的透明度和精准度，以便根据不同图片获得最佳的预览效果。

#### 验收标准

1. **AC-3.7.1**：WHEN 用户显示掩码预览 THEN 系统 SHALL 提供透明度滑块控件（范围 0.3-1.0）
2. **AC-3.7.2**：WHEN 用户显示掩码预览 THEN 系统 SHALL 提供阈值滑块控件（范围 10-200）
3. **AC-3.7.3**：WHEN 用户调整透明度滑块 THEN 系统 SHALL 实时更新掩码预览的红色叠加透明度
4. **AC-3.7.4**：WHEN 用户调整阈值滑块 THEN 系统 SHALL 实时更新掩码覆盖区域的精准度
5. **AC-3.7.5**：WHEN 滑块变化 THEN 系统 SHALL 显示当前参数值（如 "透明度: 70%"、"阈值: 50"）
6. **AC-3.7.6**：WHEN 用户调整参数 THEN 系统 SHALL 使用防抖机制（debounce）避免频繁重新生成预览
7. **AC-3.7.7**：WHEN 用户关闭掩码预览 THEN 系统 SHALL 保存用户的参数偏好设置

---

### 需求 3.8：错误处理

**用户故事**：作为用户，我希望在操作失败时能看到清晰的错误信息，以便了解问题原因。

#### 验收标准

1. **AC-3.8.1**：IF 分割失败 THEN 系统 SHALL 提示用户检查图像质量或调整分割目标
2. **AC-3.8.2**：IF 服装替换失败 THEN 系统 SHALL 提示具体原因（如安全过滤、API 限制等）
3. **AC-3.8.3**：IF Upscale 失败 THEN 系统 SHALL 提示分辨率是否超过限制
4. **AC-3.8.4**：WHEN 任何错误发生 THEN 系统 SHALL 记录详细的错误日志以便调试

---

## 4. 技术约束

### 4.1 API 依赖

| API | 用途 | 认证方式 |
|-----|------|---------|
| **Gemini API** | 图像分割 | API Key（`GOOGLE_API_KEY`） |
| **Vertex AI** | 图像编辑（Imagen 3）、超分辨率（Imagen 4） | GCP 项目 + OAuth |

### 4.2 模型版本

- **分割模型**：`gemini-3-flash-preview`（推荐）或 `gemini-2.5-flash`
- **编辑模型**：`imagen-3.0-capability-001`
- **超分辨率模型**：`imagen-4.0-upscale-preview`

### 4.3 图像限制

- 建议图像尺寸：1024×1024 或更小
- 支持格式：PNG、JPEG
- 最大文件大小：10MB
- 超分辨率输出限制：17 megapixels

### 4.4 数据流集成点

| 组件 | 文件 | 集成方式 |
|------|------|---------|
| 类型定义 | `types.ts` | 扩展 `AppMode` 和 `ChatOptions` |
| 数据处理 | `useChat.ts` | 添加 `virtual-try-on` 模式分支 |
| Handler | `handlers/virtualTryOnHandler.ts` | 新增 Handler 文件 |
| 服务 | `google/media/virtual-tryon.ts` | 新增服务文件 |
| UI 组件 | `views/VirtualTryOnView.tsx` | 新增视图组件 |
| 路由 | `StudioView.tsx` | 添加 case 分支 |

---

## 5. 非功能性需求

1. **性能**：分割 + 替换的总处理时间应控制在 30 秒以内
2. **安全**：Vertex AI 凭证不应暴露在前端代码中
3. **可用性**：界面操作应直观，无需用户了解底层技术细节
4. **一致性**：与现有模式（如 `image-outpainting`、`image-edit`）保持一致的交互模式和数据流
5. **可扩展性**：支持未来添加更多编辑功能（如发型变换、配饰添加等）
