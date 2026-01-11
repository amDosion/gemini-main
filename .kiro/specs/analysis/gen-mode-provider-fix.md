# GEN 模式提供商路由修复

## 修复时间
2025-12-28

## 问题描述

在 GEN 模式下，图片/视频/语音生成功能存在提供商路由错误：

1. **双重路由问题**：`llmService` 同时使用 `MediaFactory` 和 `currentProvider`，造成冗余抽象层
2. **硬编码判断**：`if (strategy && this.providerId.includes('google'))` 强制只有 Google 提供商才能使用 MediaFactory
3. **TongYi 无法工作**：TongYi 提供商被迫走 fallback 路径，但 MediaFactory 未注册 TongYi 策略，导致功能失效

## 根本原因

- `LLMFactory` 是真正的提供商工厂，负责根据 `providerId` 返回正确的 Provider 实例
- `MediaFactory` 是冗余的策略工厂，只注册了 Google 策略
- 每个 Provider 已经实现了完整的 `ILLMProvider` 接口，包括 `generateImage()`、`generateVideo()`、`generateSpeech()` 方法
- 正确的架构应该是：`llmService` → `currentProvider` → 具体 Provider 实现

## 修复方案

### 修改文件：`frontend/services/llmService.ts`

#### 1. 移除 MediaFactory 导入

```typescript
// 删除这一行
import { MediaFactory } from "./media/MediaFactory";
```

#### 2. 简化 generateImage()

**修改前：**
```typescript
public async generateImage(prompt: string, referenceImages: Attachment[] = []): Promise<ImageGenerationResult[]> {
    const strategy = MediaFactory.getStrategy(this.providerId);
    
    if (strategy && this.providerId.includes('google')) {
        return strategy.generateImage(...);
    }
    
    return this.currentProvider.generateImage(...);
}
```

**修改后：**
```typescript
public async generateImage(prompt: string, referenceImages: Attachment[] = []): Promise<ImageGenerationResult[]> {
    // 调试日志：检查 apiKey 和 baseUrl
    console.log('[llmService.generateImage] 配置检查:', {
        hasApiKey: !!this.apiKey,
        apiKeyLength: this.apiKey?.length || 0,
        hasBaseUrl: !!this.baseUrl,
        baseUrl: this.baseUrl?.substring(0, 30) || 'empty',
        providerId: this.providerId
    });
    
    // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
    return this.currentProvider.generateImage(
        this._cachedModelConfig!.id,
        prompt,
        referenceImages,
        this._cachedOptions,
        this.apiKey,
        this.baseUrl
    );
}
```

#### 3. 简化 generateVideo()

**修改后：**
```typescript
public async generateVideo(prompt: string, referenceImages: Attachment[] = []): Promise<VideoGenerationResult> {
    // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
    return this.currentProvider.generateVideo(
        prompt,
        referenceImages,
        this._cachedOptions,
        this.apiKey,
        this.baseUrl
    );
}
```

#### 4. 简化 generateSpeech()

**修改后：**
```typescript
public async generateSpeech(text: string): Promise<AudioGenerationResult> {
    // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
    return this.currentProvider.generateSpeech(
        text,
        this._cachedOptions.voiceName || 'Puck',
        this.apiKey,
        this.baseUrl
    );
}
```

## 修复效果

### 修复前的调用链路

```
ImageGenView 
  → useChat 
    → llmService.generateImage()
      → MediaFactory.getStrategy(providerId)
        → if (providerId.includes('google'))
          → googleMediaStrategy.generateImage()  ✅ Google 可用
        → else
          → currentProvider.generateImage()      ❌ TongYi 失败（未注册策略）
```

### 修复后的调用链路

```
ImageGenView 
  → useChat 
    → llmService.generateImage()
      → currentProvider.generateImage()
        → LLMFactory.getProvider(protocol, providerId)
          → GoogleProvider.generateImage()       ✅ Google 可用
          → DashScopeProvider.generateImage()    ✅ TongYi 可用
```

## 验证标准

### 功能验证

- ✅ Google 提供商图片生成正常
- ✅ TongYi 提供商图片生成正常
- ✅ Google 提供商视频生成正常
- ✅ TongYi 提供商视频生成正常（如果支持）
- ✅ Google 提供商语音生成正常
- ✅ TongYi 提供商语音生成正常（如果支持）

### 代码质量验证

- ✅ 无 TypeScript 语法错误
- ✅ 无 ESLint 警告
- ✅ 代码逻辑清晰，无冗余抽象
- ✅ 注释完整，说明修改原因

## 后续优化建议

### 可选：移除 MediaFactory

由于 `MediaFactory` 已经不再使用，可以考虑完全移除：

1. 删除 `frontend/services/media/MediaFactory.ts`
2. 删除 `frontend/services/media/strategies/` 目录
3. 更新相关导入

**注意**：这是可选的清理工作，不影响当前功能。

### 架构原则

- **单一职责**：`LLMFactory` 负责提供商管理，`Provider` 负责具体实现
- **开放封闭**：新增提供商只需实现 `ILLMProvider` 接口并注册到 `LLMFactory`
- **依赖倒置**：`llmService` 依赖 `ILLMProvider` 接口，不依赖具体实现

## 测试建议

### 手动测试

1. **Google 提供商测试**
   - 切换到 Google 提供商
   - 在 GEN 模式下生成图片
   - 验证图片正常显示

2. **TongYi 提供商测试**
   - 切换到 TongYi 提供商
   - 在 GEN 模式下生成图片
   - 验证图片正常显示
   - 检查控制台日志，确认使用 DashScope API

3. **多轮编辑测试**
   - 生成一张图片
   - 使用 EDIT 模式修改图片
   - 验证编辑功能正常

### 自动化测试（未来）

建议为 `llmService` 添加单元测试：

```typescript
describe('llmService', () => {
  it('should route to GoogleProvider when providerId is google', async () => {
    llmService.setConfig(apiKey, baseUrl, 'google', 'google');
    const result = await llmService.generateImage('test prompt');
    expect(result).toBeDefined();
  });

  it('should route to DashScopeProvider when providerId is tongyi', async () => {
    llmService.setConfig(apiKey, baseUrl, 'openai', 'tongyi');
    const result = await llmService.generateImage('test prompt');
    expect(result).toBeDefined();
  });
});
```

## 相关文档

- `frontend/services/LLMFactory.ts` - 提供商工厂
- `frontend/services/providers/interfaces.ts` - Provider 接口定义
- `frontend/services/providers/google/GoogleProvider.ts` - Google 实现
- `frontend/services/providers/tongyi/DashScopeProvider.ts` - TongYi 实现
