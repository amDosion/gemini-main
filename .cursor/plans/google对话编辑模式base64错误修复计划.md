# Google对话编辑模式Base64错误修复计划

## 问题根因分析

### 完整流程（根据日志和代码）

1. **前端** (`ImageEditView.tsx` → `attachmentUtils.ts:prepareAttachmentForApi`)
   - 从画布获取图片URL：`https://img.dicry.com/uploads/1768542604886_generated-1768542602652.png`
   - 正确识别为HTTP URL
   - ✅ 直接传递 `url` 字段，**不设置 `base64Data`**（日志：`✅ HTTP URL，直接传递（后端会自己下载）`）

2. **后端路由层** (`backend/app/routers/core/modes.py:102-145`)
   - `convert_attachments_to_reference_images()` 从 `attachment.url` 获取数据
   - ✅ HTTP URL被正确设置为 `reference_images['raw'] = "https://img.dicry.com/..."`（字符串）

3. **ConversationalImageEditService** (`backend/app/services/gemini/conversational_image_edit_service.py:711-768`)
   - ❌ **问题所在**：`_convert_reference_images()` 第724-729行
   - 当 `raw_img` 是字符串时，错误地将所有非 `data:` 开头的字符串当作base64
   - HTTP URL `"https://..."` 被错误地转换为 `"data:image/png;base64,https://..."`
   - 这个错误的字符串传递给 `send_edit_message()`

4. **send_edit_message()** (第357-385行)
   - 尝试从 `"data:image/png;base64,https://..."` 中提取base64部分
   - 提取到的字符串是 `"https://..."`（长度为65个字符）
   - ❌ 尝试解码 `"https://..."` 作为base64，报错：`number of data characters (65) cannot be 1 more than a multiple of 4`

### 问题代码

```python:724:729:backend/app/services/gemini/conversational_image_edit_service.py
if isinstance(raw_img, str):
    # 字符串格式：直接作为 Base64 或 Data URL
    reference_images_list.append({
        'url': f"data:image/png;base64,{raw_img}" if not raw_img.startswith('data:') else raw_img,
        'mimeType': 'image/png'
    })
```

**问题**：这个逻辑假设所有非 `data:` 开头的字符串都是base64数据，但实际上HTTP URL也是字符串！

## 修复方案

### 修复 `_convert_reference_images()` 方法

在字符串处理逻辑中，**先判断是否是HTTP URL**，如果是HTTP URL，直接使用，不要添加base64前缀。

```python
if isinstance(raw_img, str):
    # 判断字符串类型
    if raw_img.startswith('http://') or raw_img.startswith('https://'):
        # HTTP URL：直接使用，后端会下载
        reference_images_list.append({
            'url': raw_img,
            'mimeType': 'image/png'
        })
    elif raw_img.startswith('data:'):
        # Data URL：直接使用
        reference_images_list.append({
            'url': raw_img,
            'mimeType': 'image/png'
        })
    else:
        # 其他字符串（可能是base64）：添加data URL前缀
        reference_images_list.append({
            'url': f"data:image/png;base64,{raw_img}",
            'mimeType': 'image/png'
        })
```

## 实施步骤

1. 修改 `backend/app/services/gemini/conversational_image_edit_service.py` 中的 `_convert_reference_images()` 方法
2. 在字符串处理逻辑中添加HTTP URL判断
3. 确保HTTP URL被正确传递，不被错误地转换为base64格式

## 文件修改清单

- `backend/app/services/gemini/conversational_image_edit_service.py`
  - 修改 `_convert_reference_images()` 方法（第724-729行）
  - 添加HTTP URL检测逻辑

## 验证要点

修复后，前端发送HTTP URL时：
1. ✅ `convert_attachments_to_reference_images()` 将HTTP URL设置为 `reference_images['raw']`
2. ✅ `_convert_reference_images()` 识别HTTP URL，直接传递，不添加base64前缀
3. ✅ `send_edit_message()` 正确处理HTTP URL，后端会下载图片