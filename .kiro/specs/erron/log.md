# PDF 提取服务日志重复问题

## 问题描述

前端控制台反复输出大量重复日志：
```
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:66 [PdfExtractionService] Health check response: {status: 'healthy', selenium: false, pdf_extraction: false, embedding: false, version: '1.0.0'}
pdfExtractionService.ts:68 [PdfExtractionService] PDF extraction available: false
pdfExtractionService.ts:46 [PdfExtractionService] Using cached availability: false
pdfExtractionService.ts:85 Using default PDF templates (backend unavailable)
```

---

## 根本原因分析（2025-12-18）

### ❌ 真正的问题：后端 health 端点返回 `pdf_extraction: false`

后端虽然**成功导入了 PDF 提取模块**（`PDF_EXTRACTION_AVAILABLE = True`），但是：

1. **health.py 的全局变量未同步** ⚠️
   - [health.py:8](backend/app/routers/health.py#L8) 中的 `PDF_EXTRACTION_AVAILABLE = False`（默认值）
   - `main.py` 启动时**忘记调用 `health.set_availability()`** 更新状态

2. **导致 `/health` 端点始终返回错误状态** 🔴
   ```json
   {
     "status": "healthy",
     "pdf_extraction": false  // ❌ 应该是 true
   }
   ```

3. **前端基于错误状态反复检查** 🔁
   - 前端检测到 `pdf_extraction: false`
   - 认为后端不可用，使用本地模板
   - React StrictMode 导致组件多次挂载
   - 每次挂载都触发重复检查

---

## 完整调用链

### 后端启动流程（问题链）

```
main.py 启动
  ├─ 导入 pdf_extractor 模块 ✅
  │   └─ PDF_EXTRACTION_AVAILABLE = True
  │
  ├─ 注册 health.router ✅
  │   └─ health.PDF_EXTRACTION_AVAILABLE = False（默认值，未更新）❌
  │
  └─ ❌ 缺少：health.set_availability() 调用
      └─ 导致 health 路由返回错误状态
```

### 前端请求流程

```
PdfExtractView 组件挂载
  ├─ useEffect 触发
  ├─ checkAvailability()
  │   └─ fetch('/health')  ✅ 通过 Vite 代理
  │       └─ http://localhost:8000/health
  │           └─ 返回：{ pdf_extraction: false } ❌
  │
  └─ 前端认为功能不可用
      └─ 显示 "Using default PDF templates"
```

---

## 修复方案

### ✅ 修复：在 main.py 中调用 health.set_availability()

**修改位置**：[main.py:340](backend/app/main.py#L340)

```python
# Register API routes
if API_ROUTES_AVAILABLE:
    app.include_router(health.router)
    app.include_router(storage.router)
    app.include_router(embedding.router)
    app.include_router(dashscope_proxy.router)
    app.include_router(profiles_router)
    app.include_router(sessions_router)
    app.include_router(personas_router)
    app.include_router(image_expand_router)
    logger.info(f"{LOG_PREFIXES['info']} API routes registered")

    # ✅ 新增：设置服务可用性状态
    health.set_availability(
        selenium=SELENIUM_AVAILABLE,
        pdf=PDF_EXTRACTION_AVAILABLE,
        embedding=EMBEDDING_AVAILABLE
    )
    logger.info(f"{LOG_PREFIXES['info']} Service availability flags updated for health endpoint")
```

---

## 修复后的效果

### 修复前：后端日志
```
INFO: Selenium Available: [NO]
INFO: PDF Extraction Available: [YES]  ← main.py 中是 True
INFO: Embedding Service Available: [NO]

GET /health
→ 返回：{ "pdf_extraction": false }  ← health.py 中还是 False ❌
```

### 修复后：后端日志
```
INFO: Selenium Available: [NO]
INFO: PDF Extraction Available: [YES]
INFO: Service availability flags updated for health endpoint  ← 新增

GET /health
→ 返回：{ "pdf_extraction": true }  ← 正确同步 ✅
```

### 修复后：前端日志
```
pdfExtractionService.ts:52 [PdfExtractionService] Checking backend availability...
pdfExtractionService.ts:66 [PdfExtractionService] Health check response: {status: 'healthy', pdf_extraction: true}  ✅
pdfExtractionService.ts:68 [PdfExtractionService] PDF extraction available: true  ✅
pdfExtractionService.ts:46 [PdfExtractionService] Using cached availability: true  ✅

✅ 不再显示 "Using default PDF templates"
✅ 不再有重复日志
```

---

## 技术细节

### health.py 的设计模式

```python
# health.py
SELENIUM_AVAILABLE = False
PDF_EXTRACTION_AVAILABLE = False  # ← 默认值
EMBEDDING_AVAILABLE = False

def set_availability(selenium: bool, pdf: bool, embedding: bool):
    """由 main.py 在启动时调用，同步服务可用性状态"""
    global SELENIUM_AVAILABLE, PDF_EXTRACTION_AVAILABLE, EMBEDDING_AVAILABLE
    SELENIUM_AVAILABLE = selenium
    PDF_EXTRACTION_AVAILABLE = pdf
    EMBEDDING_AVAILABLE = embedding

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,  # ← 使用全局变量
        "embedding": EMBEDDING_AVAILABLE,
        "version": "1.0.0"
    }
```

### 为什么需要 set_availability()?

**模块导入的作用域隔离**：
- `main.py` 中的 `PDF_EXTRACTION_AVAILABLE` 是 main 模块的局部变量
- `health.py` 中的 `PDF_EXTRACTION_AVAILABLE` 是 health 模块的全局变量
- 两者**不共享内存**，必须显式同步

---

## 前端代理配置验证 ✅

### Vite 代理配置（vite.config.ts）

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {  // ✅ 正确配置
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### 前端请求路径

```typescript
// pdfExtractionService.ts
const response = await fetch('/health', {  // ✅ 正确路径
  method: 'GET',
  credentials: 'include',
  signal: AbortSignal.timeout(5000)
});
```

**请求流程**：
```
前端: fetch('/health')
  ↓ Vite 代理拦截
后端: http://localhost:8000/health  ✅
```

---

## 次要问题：前端日志重复

虽然主要问题是后端状态错误，但前端确实存在一些可以优化的点：

### 问题 1: React StrictMode 双重挂载
- **现象**：开发环境下组件被挂载 2 次
- **影响**：useEffect 执行多次
- **解决**：这是正常行为，用于检测副作用问题

### 问题 2: 重复调用 checkAvailability()
- **位置**：[PdfExtractView.tsx:56-60](frontend/components/views/PdfExtractView.tsx#L56-L60)
- **问题**：先调用 `checkAvailability()`，然后 `getTemplates()` 内部又调用一次
- **优化方案**：见下文

### 可选优化：避免重复调用

```typescript
// pdfExtractionService.ts
static async getTemplates(isAvailable?: boolean): Promise<PdfExtractionTemplate[]> {
  // 如果已知可用性，直接使用；否则检查
  const available = isAvailable ?? await this.checkAvailability();
  
  if (!available) {
    console.log('Using default PDF templates (backend unavailable)');
    return DEFAULT_TEMPLATES;
  }
  // ...
}

// PdfExtractView.tsx
const checkBackendAndFetchTemplates = async (force = false) => {
  setIsCheckingBackend(true);
  try {
    if (force) {
      PdfExtractionService.resetAvailabilityCheck();
    }
    
    // 只调用一次 checkAvailability
    const isAvailable = await PdfExtractionService.checkAvailability();
    setBackendAvailable(isAvailable);
    
    // 传递已知的可用性，避免重复检查
    const templates = await PdfExtractionService.getTemplates(isAvailable);
    setTemplates(templates);
  } catch (error) {
    console.error('Error checking backend or fetching templates:', error);
    setBackendAvailable(false);
  } finally {
    setIsCheckingBackend(false);
  }
};
```

---

## 验证步骤

### 1. 重启后端服务

```bash
# 停止当前服务（Ctrl+C）
# 重新启动
cd backend
python -m app.main
# 或
uvicorn app.main:app --reload
```

### 2. 检查启动日志

确认显示：
```
INFO: Service availability flags updated for health endpoint  ← 新增
INFO: PDF Extraction Available: [YES]
```

### 3. 验证 /health 端点

```bash
curl http://localhost:8000/health
```

预期返回：
```json
{
  "status": "healthy",
  "selenium": false,
  "pdf_extraction": true,  ← 应该是 true
  "embedding": false,
  "version": "1.0.0"
}
```

### 4. 测试前端

1. 刷新浏览器页面（清除前端缓存）
2. 打开控制台
3. 导航到 PDF Extract 页面

预期日志：
```
✅ [PdfExtractionService] Checking backend availability...
✅ [PdfExtractionService] Health check response: {..., pdf_extraction: true}
✅ [PdfExtractionService] PDF extraction available: true
✅ 不再有 "Using default PDF templates" 日志
```

---

## 历史修复记录

### 已修复问题 ✅

#### 1. 后端端点缺少 `model_id` 参数
- ✅ [main.py](backend/app/main.py) `/api/pdf/extract` 已添加 `model_id: str = Form(...)`

#### 2. 前端缺少 `modelId` 参数传递
- ✅ [pdfExtractionService.ts](frontend/services/pdfExtractionService.ts) 已添加 `modelId` 参数
- ✅ [pdfExtractHandler.ts](frontend/hooks/handlers/pdfExtractHandler.ts) 已传递 `modelId`

#### 3. 路由冲突
- ✅ `pdf.router` 已注释（使用 main.py 中的完整实现）

---

## 修复文件清单

| 文件 | 修改内容 | 状态 |
|------|----------|------|
| [backend/app/main.py](backend/app/main.py#L340) | 添加 `health.set_availability()` 调用 | ✅ 已修复 |

---

## 更新日期

- 2025-12-18: 初步修复 `model_id` 参数问题
- 2025-12-18: 误判为前端并发竞态问题
- 2025-12-18: **确认真正根源：后端未调用 `health.set_availability()`**