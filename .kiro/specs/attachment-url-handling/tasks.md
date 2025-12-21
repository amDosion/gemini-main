# Implementation Plan

## 任务概览

本任务计划基于 `requirements.md` 和 `design.md` 文档，实现附件 URL 处理系统的重构。

## 任务列表

- [ ] 1. URL 类型检测与转换工具函数
  - [ ] 1.1 重构 URL 类型检测函数
    - 类型：frontend
    - Requirements: 3.1, 3.2, 3.3
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：确保 `isBase64Url`、`isBlobUrl`、`isHttpUrl` 函数正确检测 URL 类型
  
  - [ ] 1.2 添加 URL 类型日志工具
    - 类型：frontend
    - Requirements: 3.7
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：添加 `getUrlType` 函数返回 URL 类型枚举，用于日志记录

- [ ] 2. 附件字段职责重构
  - [ ] 2.1 更新 `url` 字段处理逻辑
    - 类型：frontend
    - Requirements: 1.1, 1.3, 1.4
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 用户上传时设置 `url` 为 Blob URL
      - 上传完成后更新 `url` 为云 URL（从后端 `target_url` 获取）
  
  - [ ] 2.2 更新 `tempUrl` 字段处理逻辑
    - 类型：frontend
    - Requirements: 1.2, 1.5
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - AI 返回临时图片时设置 `tempUrl` 为 AI 临时 URL
      - 跨模式传递时将原始 `url` 复制到 `tempUrl`

- [ ] 3. 附件来源识别
  - [ ] 3.1 添加附件来源检测逻辑
    - 类型：frontend
    - Requirements: 2.1, 2.2, 2.3
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 检测附件是手动上传还是跨模式传递
      - 添加日志记录附件来源

  - [ ] 3.2 更新跨模式传递处理
    - 类型：frontend
    - Requirements: 2.2, 2.4, 4.1, 4.2
    - 文件：`frontend/hooks/handlers/ImageEditHandlerClass.ts`
    - 描述：
      - 跨模式传递时保留原始 `id` 和 `uploadStatus`
      - 将原始 `url` 复制到 `tempUrl` 用于匹配

- [ ] 4. 后端云 URL 查询
  - [ ] 4.1 实现 `fetchAttachmentStatus` 函数
    - 类型：frontend
    - Requirements: 4.3, 4.4
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：从后端查询附件状态和 `target_url`

  - [ ] 4.2 实现上传完成后 URL 更新
    - 类型：frontend
    - Requirements: 1.4, 4.3
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：当 `uploadStatus === 'completed'` 时，更新 `url` 字段为云 URL

- [ ] 5. API 调用准备
  - [ ] 5.1 重构 `prepareAttachmentForApi` 函数
    - 类型：frontend
    - Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 优先使用 `url` 字段（如果是云 URL）
      - `uploadStatus === 'pending'` 时先查询后端
      - 回退到本地 URL 转换

- [ ] 6. 数据库持久化
  - [ ] 6.1 重构 `cleanAttachmentsForDb` 函数
    - 类型：frontend
    - Requirements: 1.6, 6.1, 6.2, 6.3, 6.4
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 清除 Blob/Base64 URL
      - 保留 HTTP URL
      - 移除 `file` 和 `base64Data` 属性

- [ ] 7. CONTINUITY LOGIC 处理
  - [ ] 7.1 重构 `findAttachmentByUrl` 函数
    - 类型：frontend
    - Requirements: 8.2, 8.3
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 先匹配 `url` 字段
      - 再匹配 `tempUrl` 字段
      - 回退到最近的图片附件

  - [ ] 7.2 更新 `processUserAttachments` 函数
    - 类型：frontend
    - Requirements: 8.1, 8.4
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：处理用户没有上传新附件时的 CONTINUITY LOGIC

- [ ] 8. 日志记录
  - [ ] 8.1 添加统一日志格式
    - 类型：frontend
    - Requirements: 7.1, 7.2, 7.3, 7.4
    - 文件：`frontend/hooks/handlers/attachmentUtils.ts`
    - 描述：
      - 记录附件来源、URL 类型、上传状态
      - 记录后端查询原因和结果
      - 记录 API 准备策略
      - 错误日志包含上下文信息

- [ ] 9. Handler 类更新
  - [ ] 9.1 更新 `ImageEditHandlerClass`
    - 类型：frontend
    - Requirements: 4.1, 4.2
    - 文件：`frontend/hooks/handlers/ImageEditHandlerClass.ts`
    - 描述：使用新的附件处理逻辑

  - [ ] 9.2 更新 `ImageGenHandlerClass`
    - 类型：frontend
    - Requirements: 1.2
    - 文件：`frontend/hooks/handlers/ImageGenHandlerClass.ts`
    - 描述：AI 返回图片时正确设置 `tempUrl`

  - [ ] 9.3 更新 `BaseHandler`
    - 类型：frontend
    - Requirements: 6.1, 6.2, 6.3
    - 文件：`frontend/hooks/handlers/BaseHandler.ts`
    - 描述：使用新的 `cleanAttachmentsForDb` 函数

## 依赖关系

```
1.1, 1.2 → 2.1, 2.2 → 3.1, 3.2 → 4.1, 4.2 → 5.1 → 6.1 → 7.1, 7.2 → 8.1 → 9.1, 9.2, 9.3
```

## 验收标准

1. 所有 URL 类型检测函数正确工作
2. `url` 字段在上传完成后更新为云 URL
3. `tempUrl` 字段正确保存临时/匹配 URL
4. 跨模式传递保留原始 ID 和状态
5. API 调用使用正确的 URL 优先级
6. 数据库持久化正确清理临时 URL
7. CONTINUITY LOGIC 正确匹配附件
8. 日志记录完整且格式统一
