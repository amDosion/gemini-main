# 测试验证指南

## 修复内容总结

### 问题描述
在 chat 模式上传图片后，图片在对话历史中显示为 `ERR_FILE_NOT_FOUND` 错误。

### 根本原因
1. `AttachmentGrid.tsx` 只使用 `att.url || att.fileUri`，缺少 `att.tempUrl` 降级
2. `InputArea.tsx` 在发送消息后立即清空附件，导致 Blob URL 被释放
3. 用户消息中的图片 URL 失效

### 修复方案
参考 `ImageEditView` 的成功实践：
1. **`AttachmentGrid.tsx`**：添加 URL 优先级降级策略（`url -> tempUrl -> fileUri`）
2. **`InputArea.tsx`**：在发送前将 Blob URL 转换为 Base64 Data URL（永久有效）

---

## 测试步骤

### 测试 1：基本图片上传和显示

**步骤**：
1. 打开应用，进入 chat 模式
2. 点击附件按钮，上传一张图片（例如：`test-image.jpg`）
3. 在输入框输入文本："这是一张测试图片"
4. 点击发送按钮

**预期结果**：
- ✅ 用户消息中的图片正常显示（不报 `ERR_FILE_NOT_FOUND`）
- ✅ 图片可以点击放大查看
- ✅ 图片可以下载
- ✅ 图片可以编辑（点击 Edit 按钮）

**验证点**：
- 检查浏览器控制台，确认没有 `ERR_FILE_NOT_FOUND` 错误
- 检查图片 URL 是否为 Base64 Data URL（以 `data:image/` 开头）

---

### 测试 2：多张图片上传

**步骤**：
1. 上传 3 张图片
2. 发送消息

**预期结果**：
- ✅ 所有图片都正常显示
- ✅ 每张图片都可以独立操作（放大、下载、编辑）

---

### 测试 3：对话历史中的图片

**步骤**：
1. 发送包含图片的消息
2. 继续发送几条文本消息
3. 向上滚动查看历史消息

**预期结果**：
- ✅ 历史消息中的图片仍然可见
- ✅ 图片缩略图可以点击

---

### 测试 4：页面刷新后的图片

**步骤**：
1. 发送包含图片的消息
2. 刷新页面（F5）
3. 查看对话历史

**预期结果**：
- ⚠️ 如果图片已上传到云存储，刷新后仍然可见
- ⚠️ 如果图片未上传（uploadStatus: 'pending'），刷新后可能不可见（这是预期行为，需要后续优化）

---

### 测试 5：视频和音频附件

**步骤**：
1. 上传一个视频文件（例如：`test-video.mp4`）
2. 发送消息
3. 上传一个音频文件（例如：`test-audio.mp3`）
4. 发送消息

**预期结果**：
- ✅ 视频和音频都正常显示
- ✅ 视频和音频可以播放

---

### 测试 6：跨模式传递附件

**步骤**：
1. 在 chat 模式上传图片并发送
2. 点击图片的 "Edit" 按钮，进入 image-edit 模式
3. 在 image-edit 模式编辑图片
4. 发送编辑后的图片

**预期结果**：
- ✅ 图片可以正常传递到 image-edit 模式
- ✅ 编辑后的图片可以正常显示

---

## 调试技巧

### 检查图片 URL 类型

在浏览器控制台运行：
```javascript
// 查看最后一条消息的附件
const lastMsg = messages[messages.length - 1];
console.log('附件 URL:', lastMsg.attachments[0].url);
console.log('附件 tempUrl:', lastMsg.attachments[0].tempUrl);
console.log('附件 uploadStatus:', lastMsg.attachments[0].uploadStatus);
```

### 检查 Blob URL 是否被释放

在浏览器控制台运行：
```javascript
// 尝试加载 Blob URL
const img = new Image();
img.src = 'blob:http://localhost:3000/xxx'; // 替换为实际的 Blob URL
img.onload = () => console.log('✅ Blob URL 有效');
img.onerror = () => console.log('❌ Blob URL 已失效');
```

### 检查 Base64 URL

在浏览器控制台运行：
```javascript
// 检查是否为 Base64 URL
const url = lastMsg.attachments[0].url;
console.log('是否为 Base64:', url.startsWith('data:image/'));
```

---

## 已知问题和限制

### 1. 页面刷新后图片可能不可见
**原因**：Base64 URL 存储在内存中，刷新后丢失  
**解决方案**：需要等待云存储上传完成，或者实现本地缓存

### 2. Base64 URL 体积较大
**原因**：Base64 编码会增加约 33% 的体积  
**影响**：可能影响消息加载速度  
**解决方案**：优先使用云存储 URL，Base64 只作为临时方案

### 3. 大图片可能导致性能问题
**原因**：Base64 URL 会占用大量内存  
**建议**：限制图片大小，或者压缩图片后再转换为 Base64

---

## 回归测试清单

在修复后，确保以下功能仍然正常：

- [ ] chat 模式的基本对话功能
- [ ] image-gen 模式的图片生成
- [ ] image-edit 模式的图片编辑
- [ ] image-outpainting 模式的图片扩展
- [ ] video-gen 模式的视频生成
- [ ] audio-gen 模式的音频生成
- [ ] pdf-extract 模式的 PDF 提取
- [ ] virtual-try-on 模式的虚拟试穿

---

## 性能测试

### 测试场景 1：上传大图片
- 上传 5MB 的图片
- 测量转换为 Base64 的时间
- 预期：< 1 秒

### 测试场景 2：上传多张图片
- 上传 10 张图片（每张 1MB）
- 测量总处理时间
- 预期：< 5 秒

### 测试场景 3：对话历史加载
- 创建包含 50 条消息的对话（每条消息包含 1 张图片）
- 测量页面加载时间
- 预期：< 3 秒

---

## 成功标准

修复被认为成功，当且仅当：

1. ✅ 所有测试步骤通过
2. ✅ 没有新的错误或警告
3. ✅ 性能测试通过
4. ✅ 回归测试通过
5. ✅ 代码审查通过

---

## 下一步优化

如果基本功能测试通过，可以考虑以下优化：

1. **实现云存储 URL 自动更新**
   - 监听上传完成事件
   - 自动将 Base64 URL 替换为云存储 URL

2. **实现本地缓存**
   - 使用 IndexedDB 缓存图片
   - 刷新后可以从缓存恢复

3. **实现图片压缩**
   - 在转换为 Base64 前压缩图片
   - 减少内存占用和传输体积

4. **实现懒加载**
   - 对话历史中的图片懒加载
   - 提高页面加载速度
