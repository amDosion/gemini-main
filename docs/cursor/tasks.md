# 附件处理统一后端化 - 任务文档

> **项目名称**: 附件处理统一后端化重构
> **版本**: v1.0
> **创建日期**: 2026-01-18
> **预计工期**: 7 周
> **团队规模**: 后端 2人 + 前端 2人

---

## 目录

1. [任务总览](#1-任务总览)
2. [阶段1: 后端准备（第1-2周）](#2-阶段1-后端准备第1-2周)
3. [阶段2: 前后端并行开发（第3-4周）](#3-阶段2-前后端并行开发第3-4周)
4. [阶段3: 逐步切换（第5-6周）](#4-阶段3-逐步切换第5-6周)
5. [阶段4: 清理和优化（第7周）](#5-阶段4-清理和优化第7周)
6. [任务依赖关系](#6-任务依赖关系)
7. [风险缓解任务](#7-风险缓解任务)

---

## 1. 任务总览

### 1.1 里程碑

| 里程碑 | 时间 | 交付物 | 验收标准 |
|-------|------|--------|---------|
| **M1: 后端服务完成** | 第2周末 | AttachmentService, Worker Pool增强 | 单元测试通过率 > 90% |
| **M2: 前端集成完成** | 第4周末 | 前端新代码 + 旧代码保留 | 集成测试通过，A/B测试可启动 |
| **M3: 生产环境上线** | 第6周末 | 100%流量切换到新流程 | 性能指标达标，无P0故障 |
| **M4: 代码清理完成** | 第7周末 | 删除旧代码，文档更新 | 代码审查通过，文档完整 |

### 1.2 优先级定义

- **P0**: 关键任务，阻塞后续工作，必须按时完成
- **P1**: 重要任务，影响项目进度
- **P2**: 次要任务，可延后或并行

---

## 2. 阶段1: 后端准备（第1-2周）

### 2.1 任务分解

#### TASK-101: 创建 AttachmentService（P0）

**负责人**: 后端开发1
**工时**: 3天
**依赖**: 无

**详细步骤**:

1. **创建文件结构**
   ```bash
   backend/app/services/common/
   └── attachment_service.py
   ```

2. **实现类骨架**
   ```python
   class AttachmentService:
       def __init__(self, db: Session):
           self.db = db

       async def process_user_upload(...) -> Dict[str, Any]:
           pass

       async def process_ai_result(...) -> Dict[str, Any]:
           pass

       async def resolve_continuity_attachment(...) -> Optional[Dict[str, Any]]:
           pass

       async def get_cloud_url(...) -> Optional[str]:
           pass
   ```

3. **实现 process_ai_result 方法**
   - 检测 URL 类型（Base64 vs HTTP）
   - 创建临时代理 URL（如果是 Base64）
   - 创建 MessageAttachment 记录
   - 提交 Worker Pool 任务
   - 返回显示 URL

4. **实现 resolve_continuity_attachment 方法**
   - 在 messages 中查找 activeImageUrl
   - 查询数据库获取附件
   - 检查 upload_status
   - 返回云 URL 或提交任务

5. **实现 process_user_upload 方法**
   - 创建 MessageAttachment 记录
   - 提交 Worker Pool 任务（source_file_path）
   - 返回任务信息

6. **实现 get_cloud_url 方法**
   - 查询 MessageAttachment
   - 优先返回 UploadTask.target_url
   - 否则返回 attachment.url

**验收标准**:
- ✅ 所有方法有单元测试（覆盖率 > 90%）
- ✅ 支持 Base64 和 HTTP URL
- ✅ 正确创建临时代理 URL
- ✅ 正确提交 Worker Pool 任务

---

#### TASK-102: 增强 Worker Pool（P0）

**负责人**: 后端开发1
**工时**: 2天
**依赖**: TASK-101

**详细步骤**:

1. **数据库迁移**
   ```sql
   ALTER TABLE upload_tasks ADD COLUMN source_ai_url TEXT;
   ALTER TABLE upload_tasks ADD COLUMN source_attachment_id VARCHAR(255);
   
   CREATE INDEX idx_upload_tasks_source_ai_url ON upload_tasks(source_ai_url);
   CREATE INDEX idx_upload_tasks_source_attachment_id ON upload_tasks(source_attachment_id);
   ```

2. **修改 UploadTask 模型**
   ```python
   class UploadTask(Base):
       # 现有字段
       source_file_path = Column(String, nullable=True)
       source_url = Column(String, nullable=True)
       
       # 新增字段
       source_ai_url = Column(Text, nullable=True)
       source_attachment_id = Column(String, nullable=True)
   ```

3. **增强 _get_file_content 方法**
   - 支持 source_ai_url（Base64 或 HTTP）
   - 支持 source_attachment_id（复用已有附件）
   - 返回 None 表示无需上传（复用场景）

4. **修改 _process_task 方法**
   - 处理返回 None 的情况（复用附件）
   - 更新附件 URL 指向已有云 URL

**验收标准**:
- ✅ 支持 4 种 source 类型
- ✅ Base64 Data URL 正确解码
- ✅ 复用附件逻辑正确
- ✅ 单元测试通过

---

#### TASK-103: 添加临时代理端点（P0）

**负责人**: 后端开发2
**工时**: 1天
**依赖**: TASK-101

**详细步骤**:

1. **创建路由文件**
   ```bash
   backend/app/routers/core/
   └── attachments.py
   ```

2. **实现 GET /api/temp-images/{attachment_id}**
   - 查询 MessageAttachment
   - 读取 temp_url（Base64 或 HTTP）
   - Base64 解码并返回图片字节流
   - HTTP URL 重定向

3. **添加缓存控制头**
   - Cache-Control: no-cache
   - 防止浏览器缓存临时图片

**验收标准**:
- ✅ 端点正常工作
- ✅ Base64 正确解码
- ✅ 浏览器能正确显示图片
- ✅ 性能测试：响应时间 < 100ms

---

#### TASK-104: 修改 modes.py 集成 AttachmentService（P0）

**负责人**: 后端开发2
**工时**: 2天
**依赖**: TASK-101, TASK-102

**详细步骤**:

1. **Gen 模式集成**
   - 调用 AI 服务生成图片
   - 使用 AttachmentService.process_ai_result 处理结果
   - 返回 display_url 给前端

2. **Edit 模式集成**
   - 处理用户上传（保留 FormData）
   - 处理 CONTINUITY LOGIC（使用 resolve_continuity_attachment）
   - 使用 AttachmentService.process_ai_result 处理编辑结果

3. **API 响应格式**
   - 返回 attachmentId, displayUrl, uploadStatus, taskId

**验收标准**:
- ✅ Gen 模式正常工作
- ✅ Edit 模式正常工作
- ✅ CONTINUITY LOGIC 正常工作
- ✅ 集成测试通过

---

#### TASK-105: 添加新 API 端点（P1）

**负责人**: 后端开发2
**工时**: 1天
**依赖**: TASK-101

**详细步骤**:

1. **POST /api/attachments/resolve-continuity**
   - 接收 activeImageUrl, sessionId
   - 调用 AttachmentService.resolve_continuity_attachment
   - 返回附件信息

2. **GET /api/attachments/{attachmentId}/cloud-url**
   - 调用 AttachmentService.get_cloud_url
   - 返回云 URL 和上传状态

**验收标准**:
- ✅ 端点正常工作
- ✅ 返回格式正确
- ✅ 单元测试通过

---

### 2.2 阶段1 验收标准

- ✅ 所有 P0 任务完成
- ✅ 单元测试覆盖率 > 90%
- ✅ 向后兼容性验证通过
- ✅ 代码审查通过

---

## 3. 阶段2: 前后端并行开发（第3-4周）

### 3.1 任务分解

#### TASK-201: 前端创建轻量化 attachmentUtils（P0）

**负责人**: 前端开发1
**工时**: 3天
**依赖**: TASK-104

**详细步骤**:

1. **创建新文件**
   ```bash
   frontend/hooks/handlers/
   └── attachmentUtilsV2.ts
   ```

2. **实现核心函数**
   - `handleFileSelect()` - 文件选择（仅创建Blob URL预览）
   - `submitGenRequest()` - Gen模式请求（使用新API）
   - `submitEditRequest()` - Edit模式请求（使用新API）

3. **保留旧代码**
   - 标记为 `@deprecated`
   - 保留旧函数，但标记为废弃

**验收标准**:
- ✅ 新代码正常工作
- ✅ 旧代码仍然可用（向后兼容）
- ✅ 代码量减少60%（1016行 → 400行）

---

#### TASK-202: 前端修改Gen模式（P0）

**负责人**: 前端开发1
**工时**: 2天
**依赖**: TASK-201

**详细步骤**:

1. **修改 ImageGenHandler**
   - 使用新的 `submitGenRequest()`
   - 直接使用 `display_url` 显示（无需下载）
   - 移除 `processMediaResult()` 调用

2. **测试验证**
   - Google模式：Base64 → 代理URL显示
   - Tongyi模式：HTTP URL直接显示

**验收标准**:
- ✅ Gen模式正常工作
- ✅ 图片立即显示（无延迟）
- ✅ 异步上传正常

---

#### TASK-203: 前端修改Edit模式（P0）

**负责人**: 前端开发2
**工时**: 3天
**依赖**: TASK-201

**详细步骤**:

1. **修改 ImageEditHandler**
   - 用户上传：保留FormData上传
   - CONTINUITY LOGIC：发送 `activeImageUrl`，后端负责解析
   - 移除 `processUserAttachments()` 调用
   - 移除 `findAttachmentByUrl()` 调用

2. **测试验证**
   - 用户上传正常
   - CONTINUITY LOGIC正常
   - 跨模式传递正常

**验收标准**:
- ✅ Edit模式正常工作
- ✅ CONTINUITY LOGIC正常工作
- ✅ 跨模式传递正常

---

#### TASK-204: A/B测试准备（P1）

**负责人**: 前端开发2
**工时**: 1天
**依赖**: TASK-202, TASK-203

**详细步骤**:

1. **添加Feature Flag**
   ```typescript
   export const FEATURE_FLAGS = {
     USE_UNIFIED_ATTACHMENT_SERVICE: false  // 默认关闭
   };
   ```

2. **实现切换逻辑**
   - 新流程：使用 `attachmentUtilsV2.ts`
   - 旧流程：使用 `attachmentUtils.ts`（保留）

3. **监控指标**
   - 性能指标（延迟、请求数）
   - 错误率
   - 用户反馈

**验收标准**:
- ✅ Feature Flag正常工作
- ✅ 可以随时切换新旧流程
- ✅ 监控指标正常收集

---

### 3.2 阶段2 验收标准

- ✅ 所有 P0 任务完成
- ✅ 前端新代码正常工作
- ✅ 旧代码保留（向后兼容）
- ✅ A/B测试可以启动
- ✅ 集成测试通过

---

## 4. 阶段3: 逐步切换（第5-6周）

### 4.1 任务分解

#### TASK-301: 启用新流程（P0）

**负责人**: 前端开发1
**工时**: 0.5天
**依赖**: TASK-204

**详细步骤**:

1. **修改Feature Flag**
   ```typescript
   export const FEATURE_FLAGS = {
     USE_UNIFIED_ATTACHMENT_SERVICE: true  // 默认启用
   };
   ```

2. **监控关键指标**
   - API响应时间
   - 错误率
   - 用户投诉

**验收标准**:
- ✅ 新流程默认启用
- ✅ 监控指标正常
- ✅ 无P0故障

---

#### TASK-302: 性能监控和优化（P1）

**负责人**: 后端开发1
**工时**: 2天
**依赖**: TASK-301

**详细步骤**:

1. **监控指标**
   - API P50/P90/P99延迟
   - Worker Pool队列长度
   - 上传成功率
   - 前端错误率

2. **性能优化**
   - 优化数据库查询
   - 优化Worker Pool队列
   - 优化临时代理端点

**验收标准**:
- ✅ 性能指标达标（延迟减少40%）
- ✅ 无性能劣化
- ✅ 监控告警正常

---

#### TASK-303: 问题修复（P0）

**负责人**: 全团队
**工时**: 持续
**依赖**: TASK-301

**详细步骤**:

1. **收集问题**
   - 用户反馈
   - 错误日志
   - 性能监控

2. **修复问题**
   - 及时响应
   - 快速修复
   - 验证修复

**验收标准**:
- ✅ 问题及时修复
- ✅ 无P0故障累积
- ✅ 用户满意度提升

---

#### TASK-304: 100%流量切换（P0）

**负责人**: 前端开发1
**工时**: 0.5天
**依赖**: TASK-302, TASK-303

**详细步骤**:

1. **确认指标达标**
   - 性能指标正常
   - 错误率 < 0.5%
   - 用户反馈良好

2. **移除Feature Flag**
   - 删除Feature Flag代码
   - 默认使用新流程
   - 保留旧代码（标记为废弃）

**验收标准**:
- ✅ 100%流量使用新流程
- ✅ 性能指标达标
- ✅ 无P0故障

---

### 4.2 阶段3 验收标准

- ✅ 新流程100%启用
- ✅ 性能指标达标（延迟减少40%）
- ✅ 错误率 < 0.5%
- ✅ 用户反馈良好
- ✅ 无P0故障

---

## 5. 阶段4: 清理和优化（第7周）

### 5.1 任务分解

#### TASK-401: 删除旧代码（P1）

**负责人**: 前端开发1
**工时**: 1天
**依赖**: TASK-304

**详细步骤**:

1. **删除清单**
   ```typescript
   // frontend/hooks/handlers/attachmentUtils.ts
   // 【删除】以下函数（共616行）:
   - processUserAttachments (157行)
   - processMediaResult (57行)
   - sourceToFile (70行)
   - findAttachmentByUrl (61行)
   - tryFetchCloudUrl (34行)
   - cleanAttachmentsForDb (71行)
   - 辅助函数 (166行)
   
   // 保留（仅50行）:
   - handleFileSelect
   - createBlobPreview
   - URL类型常量
   ```

2. **代码审查**
   - 确认删除不影响功能
   - 确认无引用旧函数
   - 确认测试通过

**验收标准**:
- ✅ 旧代码删除
- ✅ 代码审查通过
- ✅ 测试通过

---

#### TASK-402: 更新文档（P2）

**负责人**: 全团队
**工时**: 1天
**依赖**: TASK-401

**详细步骤**:

1. **更新API文档**
   - 更新API端点说明
   - 更新请求/响应格式
   - 更新示例代码

2. **更新开发文档**
   - 更新架构文档
   - 更新开发指南
   - 更新故障排查指南

**验收标准**:
- ✅ 文档完整
- ✅ 文档准确
- ✅ 文档可读

---

#### TASK-403: 性能报告（P2）

**负责人**: 后端开发1
**工时**: 1天
**依赖**: TASK-304

**详细步骤**:

1. **收集数据**
   - 性能指标对比
   - 代码量对比
   - 用户反馈

2. **生成报告**
   - 性能改善报告
   - 代码质量报告
   - 用户满意度报告

**验收标准**:
- ✅ 报告完整
- ✅ 数据准确
- ✅ 结论清晰

---

### 5.2 阶段4 验收标准

- ✅ 旧代码删除
- ✅ 文档更新
- ✅ 性能报告完成
- ✅ 项目总结完成

---

## 6. 任务依赖关系

### 6.1 依赖图

```
阶段1（后端准备）:
  TASK-101 (AttachmentService)
    ↓
  TASK-102 (Worker Pool增强) ──┐
    ↓                           │
  TASK-103 (临时代理端点)       │
    ↓                           │
  TASK-104 (modes.py集成) ←─────┘
    ↓
  TASK-105 (新API端点)

阶段2（前后端并行）:
  TASK-201 (前端轻量化) ← TASK-104
    ↓
  TASK-202 (Gen模式) ──┐
    ↓                  │
  TASK-203 (Edit模式) ─┼─→ TASK-204 (A/B测试)

阶段3（逐步切换）:
  TASK-301 (启用新流程) ← TASK-204
    ↓
  TASK-302 (性能监控) ──┐
    ↓                  │
  TASK-303 (问题修复) ──┼─→ TASK-304 (100%切换)

阶段4（清理）:
  TASK-401 (删除旧代码) ← TASK-304
    ↓
  TASK-402 (更新文档) ──┐
    ↓                  │
  TASK-403 (性能报告) ──┘
```

### 6.2 关键路径

**关键路径**: TASK-101 → TASK-102 → TASK-104 → TASK-201 → TASK-202 → TASK-203 → TASK-301 → TASK-304

**总工期**: 7周（14个工作日）

---

## 7. 风险缓解任务

### 7.1 技术风险

#### RISK-001: 后端API延迟增加

**风险**: 新架构可能导致API响应时间增加

**缓解措施**:
- TASK-302: 性能监控和优化
- 设置告警阈值（P99延迟 > 2000ms）
- Feature Flag快速回滚

#### RISK-002: Worker Pool负载增加

**风险**: 新增source类型可能导致Worker Pool负载增加

**缓解措施**:
- 增加Worker数量
- 优化队列管理
- 监控队列长度（告警阈值 > 100）

#### RISK-003: 向后兼容性问题

**风险**: 新架构可能破坏向后兼容性

**缓解措施**:
- TASK-105: 保留旧API
- 充分测试（单元测试 + 集成测试）
- 逐步迁移（A/B测试）

### 7.2 业务风险

#### RISK-004: 前端显示问题

**风险**: 新流程可能导致前端显示异常

**缓解措施**:
- TASK-204: A/B测试
- 逐步迁移（10% → 50% → 100%）
- 实时监控错误率

#### RISK-005: 数据迁移失败

**风险**: 数据库迁移可能失败

**缓解措施**:
- 备份数据库
- 测试迁移脚本
- 准备回滚方案

### 7.3 监控和告警

**必须监控**:
1. API响应时间（P50, P90, P99）
2. Worker Pool队列长度
3. 上传成功率
4. 前端错误率
5. 用户投诉数量

**告警阈值**:
- API P99延迟 > 2000ms
- Worker Pool队列 > 100
- 上传失败率 > 1%
- 前端错误率 > 0.5%

### 7.4 回滚计划

**触发条件**:
- 新流程错误率 > 1%
- 用户投诉增加
- 性能劣化

**回滚步骤**:
1. Feature Flag改为false
2. 前端立即切换回旧流程
3. 后端保持兼容（旧API仍然工作）
4. 分析问题，修复后再次尝试

---

**文档版本**: v1.0
**最后更新**: 2026-01-18
