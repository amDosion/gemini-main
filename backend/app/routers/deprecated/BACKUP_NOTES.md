# 已废弃路由备份说明

## 备份状态

这些路由文件已移动到 `deprecated/` 目录作为备份，**不再在 `main.py` 中注册和调用**。

## 备份文件列表

| 文件 | 原路径 | 新路径 | 迁移目标 | 状态 |
|------|--------|--------|----------|------|
| `generate.py` | `routers/generate.py` | `routers/deprecated/generate.py` | `core/modes.py` | ✅ 已备份 |
| `image_edit.py` | `routers/image_edit.py` | `routers/deprecated/image_edit.py` | `core/modes.py` | ✅ 已备份 |
| `image_expand.py` | `routers/image_expand.py` | `routers/deprecated/image_expand.py` | `core/modes.py` | ✅ 已备份 |
| `tryon.py` | `routers/tryon.py` | `routers/deprecated/tryon.py` | `core/modes.py` | ✅ 已备份 |
| `google_modes.py` | `routers/google_modes.py` | `routers/deprecated/google_modes.py` | `core/modes.py` | ✅ 已备份 |
| `qwen_modes.py` | `routers/qwen_modes.py` | `routers/deprecated/qwen_modes.py` | `core/modes.py` | ✅ 已备份 |
| `tongyi_chat.py` | `routers/tongyi_chat.py` | `routers/deprecated/tongyi_chat.py` | `core/chat.py` | ✅ 已备份 |
| `google_chat.py` | `routers/providers/google_chat.py` | `routers/deprecated/google_chat.py.bak` | `core/chat.py` | ✅ 已备份 |
| `tongyi_image.py` | `routers/providers/tongyi_image.py` | `routers/deprecated/tongyi_image.py.bak` | `core/modes.py` | ✅ 已备份 |

## 重要说明

### ✅ 已完成的工作

1. **文件已移动**：所有废弃路由文件已移动到 `deprecated/` 目录
2. **导入路径已更新**：所有文件的相对导入路径已从 `..` 更新为 `...`（因为文件在子目录中）
3. **main.py 已更新**：已从 `main.py` 中移除对这些废弃路由的调用和注册
4. **新架构已启用**：`core/chat.py` 和 `core/modes.py` 已注册并正常工作

### ⚠️ 当前状态

- **废弃路由不再被调用**：这些文件保留在 `deprecated/` 目录中作为备份，但不会在应用启动时注册
- **新架构已生效**：所有功能应通过 `core/chat.py` 和 `core/modes.py` 访问
- **测试阶段**：需要测试新架构是否完全覆盖了旧路由的功能

### 📋 下一步计划

1. **测试新架构**：
   - [ ] 测试 `core/chat.py` 是否覆盖了 `tongyi_chat.py` 的功能
   - [ ] 测试 `core/modes.py` 是否覆盖了所有废弃路由的功能
   - [ ] 进行集成测试，确保所有功能正常工作

2. **观察期**（1-2 周）：
   - [ ] 监控日志，确认没有前端调用废弃路由
   - [ ] 确认新架构稳定运行

3. **最终清理**（测试成功后）：
   - [ ] 确认新架构完全正常工作
   - [ ] 删除 `deprecated/` 目录中的所有文件
   - [ ] 更新文档

## 路由映射关系

### 聊天路由

| 旧路由 | 新路由 |
|--------|--------|
| `/api/chat/tongyi` (tongyi_chat.py) | `/api/modes/tongyi/chat` (core/chat.py) |
| `/api/chat/google` (google_chat.py) | `/api/modes/google/chat` (core/chat.py) |

### 模式路由

| 旧路由 | 新路由 |
|--------|--------|
| `/api/generate/{provider}/image` (generate.py) | `/api/modes/{provider}/image-gen` (core/modes.py) |
| `/api/generate/{provider}/video` (generate.py) | `/api/modes/{provider}/video-gen` (core/modes.py) |
| `/api/generate/{provider}/audio` (generate.py) | `/api/modes/{provider}/audio-gen` (core/modes.py) |
| `/api/image/edit` (image_edit.py) | `/api/modes/{provider}/image-edit` (core/modes.py) |
| `/api/image/expand` (image_expand.py) | `/api/modes/{provider}/image-outpainting` (core/modes.py) |
| `/api/tryon` (tryon.py) | `/api/modes/{provider}/virtual-try-on` (core/modes.py) |
| `/api/google/modes/{mode}` (google_modes.py) | `/api/modes/google/{mode}` (core/modes.py) |
| `/api/qwen/modes/{mode}` (qwen_modes.py) | `/api/modes/tongyi/{mode}` (core/modes.py) |
| `/api/generate/tongyi/image` (tongyi_image.py) | `/api/modes/tongyi/image-gen` (core/modes.py) |

## 恢复方法

如果需要临时恢复某个废弃路由（例如测试或紧急回滚）：

1. 在 `main.py` 中取消注释对应的导入和注册
2. 重启应用
3. 测试功能是否正常

**注意**：恢复废弃路由只是临时措施，应尽快迁移到新架构。

---

**备份日期**: 2026-01-14  
**备份原因**: 架构重构，迁移到统一路由  
**维护者**: Development Team
