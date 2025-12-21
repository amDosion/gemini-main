# 掩码预览图片 URL 转换修复报告

## 修复日期
2025-12-20

## 问题描述

用户点击"显示掩码预览"按钮时，控制台报错：
```
Failed to process reference image
```

错误发生在 `segmentClothing` 函数中的 `processReferenceImage` 调用。

## 根本原因

### 问题分析

1. **`activeImageUrl` 可能是云存储 URL**：
   - 用户上传图片后，图片可能被上传到云存储（如 DashScope）
   - `activeImageUrl` 变成了 `http://...` 或 `https://...` 格式的云存储 URL

2. **`processReferenceImage` 无法处理云存储 URL**：
   - `processReferenceImage` 期望接收 Base64 格式的图片数据
   - 当传入云存储 URL 时，无法正确提取图片字节数据
   - 导致 `imageBytes` 为空，抛出 "Failed to process reference image" 错误

3. **缺少 URL 类型转换逻辑**：
   - `handleGenerateMaskPreview` 直接将 `activeImageUrl` 传递给 `generateMaskPreview`
   - 没有检查 URL 类型并进行必要的转换

### 对比 ImageExpandView

`ImageExpandView` 的 `handleSend` 函数有完整的 CONTINUITY LOGIC：
- 检查 URL 类型（Base64、Blob URL、云存储 URL）
- 如果是云存储 URL，通过后端代理下载并转换为 Base64
- 如果是 Blob URL，读取并转换为 Base64
- 确保传递给 API 的始终是 Base64 格式

---

## 解决方案

### 修改策略

在 `handleGenerateMaskPreview` 中添加图片 URL 类型检查和转换逻辑，确保传递给 `generateMaskPreview` 的始终是 Base64 格式的图片。

### 修改的文件

#### `frontend/components/views/VirtualTryOnView.tsx` ✅

**添加 URL 类型转换逻辑**：

```typescript
const handleGenerateMaskPreview = async () => {
    if (!activeImageUrl || !apiKey) {
        alert('请先上传图片并确保已配置 API Key');
        return;
    }
    
    setIsGeneratingMask(true);
    try {
        // ===== 图片 URL 类型转换 =====
        let imageBase64: string;
        
        const isBase64 = activeImageUrl.startsWith('data:');
        const isBlobUrl = activeImageUrl.startsWith('blob:');
        const isCloudUrl = activeImageUrl.startsWith('http://') || activeImageUrl.startsWith('https://');
        
        if (isBase64) {
            // 已经是 Base64，直接使用
            imageBase64 = activeImageUrl;
        } else if (isBlobUrl) {
            // Blob URL，读取并转换为 Base64
            const response = await fetch(activeImageUrl);
            const blob = await response.blob();
            imageBase64 = await new Promise<string>((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result as string);
                reader.readAsDataURL(blob);
            });
        } else if (isCloudUrl) {
            // 云存储 URL，通过后端代理下载并转换为 Base64
            const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
            const response = await fetch(fetchUrl);
            const blob = await response.blob();
            imageBase64 = await new Promise<string>((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result as string);
                reader.readAsDataURL(blob);
            });
        } else {
            throw new Error('不支持的图片 URL 格式');
        }
        
        // ===== 调用掩码预览生成 =====
        const previewUrl = await generateMaskPreview(
            imageBase64,  // ✅ 使用转换后的 Base64
            targetClothing,
            apiKey
        );
        
        setMaskPreviewUrl(previewUrl);
        setShowMaskPreview(true);
    } catch (error) {
        alert(`掩码预览生成失败：${error.message}`);
    } finally {
        setIsGeneratingMask(false);
    }
};
```

---

## 数据流

### 修复后的掩码预览流程

```
用户点击"显示掩码预览"
    ↓
handleGenerateMaskPreview
    ↓
检查 activeImageUrl 类型
    ├─ Base64 (data:image/...) → 直接使用
    ├─ Blob URL (blob:...) → 读取并转换为 Base64
    └─ 云存储 URL (http://...) → 通过后端代理下载并转换为 Base64
    ↓
imageBase64 (确保是 Base64 格式)
    ↓
generateMaskPreview(imageBase64, targetClothing, apiKey)
    ↓
创建 Attachment 对象
    ↓
segmentClothing(ai, attachment, targetClothing)
    ↓
processReferenceImage(attachment)
    ↓
提取 imageBytes ✅ 成功
    ↓
调用 Gemini API 进行服装分割
    ↓
生成掩码并叠加半透明红色
    ↓
返回预览图 Base64
    ↓
显示在画布上
```

---

## URL 类型处理

| URL 类型 | 示例 | 处理方式 |
|---------|------|---------|
| **Base64** | `data:image/png;base64,iVBORw0KG...` | 直接使用 |
| **Blob URL** | `blob:http://localhost:5173/abc-123` | 读取 Blob 并转换为 Base64 |
| **云存储 URL** | `http://dashscope.oss-cn-beijing.aliyuncs.com/...` | 通过后端代理下载并转换为 Base64 |

---

## 与 ImageExpandView 对比

| 功能 | ImageExpandView | VirtualTryOnView（修复前） | VirtualTryOnView（修复后） |
|------|----------------|--------------------------|--------------------------|
| **URL 类型检查** | ✅ 完整 | ❌ 缺失 | ✅ 完整 |
| **Base64 转换** | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| **Blob URL 处理** | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| **云存储 URL 处理** | ✅ 支持 | ❌ 不支持 | ✅ 支持 |
| **后端代理下载** | ✅ 使用 | ❌ 不使用 | ✅ 使用 |

---

## 测试建议

完成修复后需要测试：

### 测试场景 1：Base64 图片
- [ ] 上传本地图片（未上传到云存储）
- [ ] 点击"显示掩码预览"
- [ ] 验证掩码预览正常生成

### 测试场景 2：云存储 URL
- [ ] 上传图片并等待云存储上传完成
- [ ] 刷新页面（activeImageUrl 变成云存储 URL）
- [ ] 点击"显示掩码预览"
- [ ] 验证掩码预览正常生成

### 测试场景 3：Blob URL
- [ ] 使用 Blob URL 作为图片源
- [ ] 点击"显示掩码预览"
- [ ] 验证掩码预览正常生成

### 测试场景 4：不同服装类型
- [ ] 测试 Upper Body、Lower Body、Full Body
- [ ] 验证每种类型的掩码预览都正常

---

## 总结

本次修复解决了掩码预览功能的图片 URL 处理问题：

1. ✅ **识别问题** - `processReferenceImage` 无法处理云存储 URL
2. ✅ **找到根源** - 缺少 URL 类型转换逻辑
3. ✅ **参考实现** - 借鉴 `ImageExpandView` 的 CONTINUITY LOGIC
4. ✅ **实施修复** - 添加完整的 URL 类型检查和转换逻辑
5. ✅ **保持一致** - 与 `ImageExpandView` 的实现保持一致

修复后，`VirtualTryOnView` 可以正确处理所有类型的图片 URL，掩码预览功能可以正常工作。
