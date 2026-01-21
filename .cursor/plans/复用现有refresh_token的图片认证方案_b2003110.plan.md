---
name: 复用现有refresh_token的图片认证方案
overview: 直接使用现有的 access_token（通过 URL 参数），复用现有的 refresh_token 自动刷新机制，无需创建新的临时 token
todos: []
---

# 复用现有 refresh_token 的图片认证方案

## 一、问题分析

**用户需求**：

1. Base64 阅读不方便（字符串太长）
2. Base64 体积很大（+33%）
3. 需要能立即显示
4. **支持长期工作**：长时间工作后仍可使用图片
5. **复用现有的 refresh_token 机制**

**关键洞察**：

- 系统已经有 `refresh_token` 机制（7天有效期）
- 前端已经有自动刷新机制（`useAuth.ts` 每 22 小时自动刷新）
- 前端已经有 401 错误自动刷新机制（`apiClient.ts`）
- **可以直接使用现有的 `access_token`，无需创建新的临时 token**

## 二、推荐方案：使用现有 access_token + 自动刷新

### 2.1 方案原理

**核心思路**：

1. **使用现有的 access_token**：通过 URL 参数传递当前的 `access_token`
2. **复用自动刷新机制**：前端已有的自动刷新机制会自动更新 `access_token`
3. **前端自动更新 URL**：当 `access_token` 刷新后，自动更新图片 URL 中的 token
4. **长期工作支持**：通过自动刷新，可以持续工作数小时甚至数天

**数据流**：

```
1. 后端生成图片后，返回 URL（使用当前的 access_token）
   display_url = f"/api/temp-images/{attachment_id}?token={current_access_token}"
   ↓
2. 前端显示：<img src="/api/temp-images/{attachment_id}?token={current_access_token}" />
   ↓
3. 如果 access_token 过期（15分钟后）：
   - 前端自动刷新（useAuth.ts 或 apiClient.ts）
   - 获取新的 access_token
   - 自动更新图片 URL 中的 token
   ↓
4. 后端验证 token，返回图片
```

### 2.2 方案优势

**优点**：

- ✅ **完全复用现有机制**：不需要创建新的临时 token
- ✅ **响应体小**：只有 URL，不会给前端造成压力
- ✅ **阅读方便**：URL 比 Base64 短很多
- ✅ **支持长期工作**：通过自动刷新，可以持续工作
- ✅ **实现简单**：只需修改两个地方（后端 URL 生成 + 前端 URL 更新）
- ✅ **安全性好**：使用现有的 JWT 验证机制

**缺点**：

- ❌ Token 暴露在 URL 中（但只用于临时附件，风险可控）
- ❌ 前端需要处理 URL 更新（但逻辑简单）

### 2.3 实施步骤

#### 步骤 1：修改附件服务返回带 access_token 的 URL

**位置**：`backend/app/services/common/attachment_service.py`

**关键点**：需要从 request 中获取当前的 access_token

```python
from app.core.user_context import get_current_user_id
from fastapi import Request

async def process_ai_result(
    self,
    ai_url: str,
    mime_type: str,
    session_id: str,
    message_id: str,
    user_id: str,
    request: Optional[Request] = None,  # ✅ 新增：用于获取 access_token
    prefix: str = 'generated'
) -> Dict[str, Any]:
    # ... 创建附件记录 ...
    
    # ✅ 获取当前的 access_token（从 request 中）
    access_token = None
    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                access_token = parts[1]
        
        # 如果没有 Authorization header，尝试从 Cookie 获取
        if not access_token:
            access_token = request.cookies.get("access_token")
    
    # ✅ 如果有 access_token，返回带 token 的 URL
    if access_token:
        display_url = f"/api/temp-images/{attachment_id}?token={access_token}"
        logger.info(f"[AttachmentService]     - 使用 access_token 创建 URL（支持自动刷新）")
    else:
        # 降级：如果没有 token，直接返回 Base64（向后兼容）
        display_url = ai_url
        logger.info(f"[AttachmentService]     - 未找到 access_token，直接返回 Base64")
    
    return {
        'attachment_id': attachment_id,
        'display_url': display_url,
        'cloud_url': '',
        'status': 'pending',
        'task_id': task_id
    }
```

**注意**：需要修改调用 `process_ai_result` 的地方，传入 `request` 参数。

#### 步骤 2：修改临时图片端点支持 URL 参数 token

**位置**：`backend/app/routers/core/attachments.py`

```python
from fastapi import Query
from app.core.user_context import get_current_user_id, require_user_id
from app.core.jwt_utils import decode_token, TokenPayload

@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
    request: Request,
    token: Optional[str] = Query(None, description="Access token from URL parameter"),
    db: Session = Depends(get_db)
):
    """
    临时图片代理端点（支持 URL 参数 access_token + 自动刷新）
    
    智能路由：
    1. 如果附件已上传完成 → 直接重定向到云URL（不需要 token）
    2. 如果附件还在临时状态 → 需要 token 验证
    
    认证方式（优先级，仅用于临时附件）：
    1. URL 参数中的 token（access_token）
    2. Authorization header（向后兼容）
    3. Cookie（向后兼容）
    """
    # 先查询附件（不限制 user_id）
    attachment = db.query(MessageAttachment).filter_by(id=attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # ✅ 场景 1：已上传的附件 → 直接重定向到云URL（不需要 token）
    if attachment.upload_status == 'completed' and attachment.url and attachment.url.startswith('http'):
        logger.info(f"[TempImage] ✅ 附件已上传完成，重定向到云URL: {attachment.url[:80]}...")
        return RedirectResponse(url=attachment.url)
    
    # ✅ 场景 2：临时附件（Base64 或 HTTP 临时URL）→ 需要 token 验证
    if not attachment.temp_url:
        raise HTTPException(status_code=404, detail="Temp URL not available")
    
    # 提取 user_id（优先级：URL 参数 > Authorization header > Cookie）
    user_id = None
    token_source = None
    
    if token:
        try:
            payload: TokenPayload = decode_token(token)
            if payload.type != "access":
                raise HTTPException(status_code=403, detail="Invalid token type")
            user_id = payload.sub
            token_source = "URL parameter (access_token)"
            logger.info(f"[TempImage] ✅ Token 验证成功 (URL参数): user_id={user_id[:8]}...")
        except JWTError as e:
            logger.warning(f"[TempImage] ❌ URL参数Token验证失败: {e}")
            raise HTTPException(status_code=403, detail="Invalid or expired token")
    
    # 向后兼容：如果没有 URL 参数 token，使用 Authorization header 或 Cookie
    if not user_id:
        user_id = require_user_id(request)
        auth_header = request.headers.get("Authorization")
        cookie_token = request.cookies.get("access_token")
        if auth_header:
            token_source = "Authorization header"
        elif cookie_token:
            token_source = "Cookie (access_token)"
    
    logger.info(
        f"[TempImage] 收到请求: attachment_id={attachment_id[:8]}..., "
        f"user_id={user_id[:8]}..., "
        f"token来源={token_source}, "
        f"upload_status={attachment.upload_status}"
    )
    
    # ✅ 权限检查：临时附件需要验证 user_id 匹配
    if attachment.user_id != user_id:
        logger.warning(
            f"[TempImage] ❌ 权限检查失败: "
            f"attachment.user_id={attachment.user_id[:8]}..., "
            f"current_user={user_id[:8]}..."
        )
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # 处理临时 URL
    # ... 返回图片 ...
```

#### 步骤 3：前端自动更新图片 URL（当 access_token 刷新时）

**位置**：`frontend/components/views/ImageGenView.tsx` 或创建工具函数

**方案 A：监听 token 刷新事件**

```typescript
// frontend/utils/imageTokenUpdate.ts

import { listenTokenRefresh } from '@/services/authSync';

/**
 * 更新图片 URL 中的 token（当 access_token 刷新时）
 */
export function setupImageTokenAutoUpdate() {
  listenTokenRefresh((newAccessToken) => {
    // 查找所有包含 /api/temp-images/ 的图片
    const images = document.querySelectorAll('img[src*="/api/temp-images/"]');
    
    images.forEach((img) => {
      const src = img.getAttribute('src');
      if (src && src.includes('/api/temp-images/')) {
        // 更新 URL 中的 token
        const url = new URL(src, window.location.origin);
        url.searchParams.set('token', newAccessToken);
        img.setAttribute('src', url.toString());
        console.log('[ImageTokenUpdate] ✅ 图片 URL token 已更新');
      }
    });
  });
}
```

**方案 B：在图片组件中处理**

```typescript
// frontend/components/views/ImageGenView.tsx

import { useEffect, useState } from 'react';
import { getAccessToken } from '@/services/auth';
import { listenTokenRefresh } from '@/services/authSync';

const ImageWithAutoToken: React.FC<{ src: string; alt?: string }> = ({ src, alt }) => {
  const [imageUrl, setImageUrl] = useState(src);
  
  useEffect(() => {
    // 监听 token 刷新
    const updateToken = (newAccessToken: string) => {
      if (src.includes('/api/temp-images/')) {
        const url = new URL(src, window.location.origin);
        url.searchParams.set('token', newAccessToken);
        setImageUrl(url.toString());
        console.log('[ImageWithAutoToken] ✅ Token 已更新');
      }
    };
    
    // 注册监听器
    const unsubscribe = listenTokenRefresh(updateToken);
    
    return () => {
      unsubscribe?.();  // 清理
    };
  }, [src]);
  
  return <img src={imageUrl} alt={alt} />;
};
```

### 2.4 关于自动刷新的说明

**现有的自动刷新机制**：

1. **useAuth.ts**：每 22 小时自动刷新（静默刷新）
2. **apiClient.ts**：401 错误时自动刷新（按需刷新）

**图片 URL 更新策略**：

- **方案 A**：全局监听 token 刷新，自动更新所有图片 URL
- **方案 B**：在图片组件中监听，按需更新

**推荐方案 A**：全局监听更简单，一次设置，所有图片自动更新。

### 2.5 长期工作支持

**工作原理**：

1. **初始**：后端返回 URL 带当前的 `access_token`
2. **15 分钟后**：`access_token` 过期
3. **自动刷新**：前端检测到 401 或定时刷新，获取新的 `access_token`
4. **自动更新**：前端监听 token 刷新事件，自动更新图片 URL
5. **持续工作**：可以持续工作数小时甚至数天

**优势**：

- ✅ 完全复用现有的自动刷新机制
- ✅ 无需额外的 token 管理
- ✅ 支持长期工作（通过自动刷新）

### 2.6 性能对比

| 方案 | 响应体大小 | 实现复杂度 | 长期工作 | 复用现有机制 |

|------|-----------|-----------|---------|-------------|

| **Base64** | 大（+33%） | 低 | ✅ 是 | ✅ 是 |

| **压缩 Base64** | 中（-50-70%） | 中 | ✅ 是 | ✅ 是 |

| **临时 Token + 签名** | 小 | 高 | ✅ 是（自动刷新） | ❌ 否 |

| **现有 access_token** | 小 | 低 | ✅ 是（自动刷新） | ✅ 是 |

## 三、实施计划

### 阶段 1：修改后端 URL 生成（0.5 天）

1. ✅ 修改 `attachment_service.py`：从 request 获取 access_token
2. ✅ 返回带 token 的 URL
3. ✅ 修改调用处：传入 request 参数
4. ✅ 测试：确保 URL 格式正确

### 阶段 2：修改临时图片端点（0.5 天）

1. ✅ 修改 `attachments.py`：支持从 URL 参数读取 access_token
2. ✅ 保持向后兼容（支持 Authorization header 和 Cookie）
3. ✅ 测试：确保图片可以正常显示

### 阶段 3：前端自动更新 URL（0.5 天）

1. ✅ 创建图片 token 更新工具函数
2. ✅ 监听 token 刷新事件，自动更新图片 URL
3. ✅ 测试：确保 token 刷新后图片 URL 自动更新

### 阶段 4：测试验证（0.5 天）

1. ✅ 测试完整流程：生成 → 显示 → 自动刷新 → 更新 URL
2. ✅ 测试长期工作场景（数小时）
3. ✅ 测试 token 过期和自动刷新
4. ✅ 测试向后兼容性

## 四、代码示例

### 4.1 后端修改（`attachment_service.py`）

```python
async def process_ai_result(
    self,
    ai_url: str,
    mime_type: str,
    session_id: str,
    message_id: str,
    user_id: str,
    request: Optional[Request] = None,  # ✅ 新增
    prefix: str = 'generated'
) -> Dict[str, Any]:
    # ... 创建附件记录 ...
    
    # ✅ 获取当前的 access_token
    access_token = None
    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                access_token = parts[1]
        if not access_token:
            access_token = request.cookies.get("access_token")
    
    # ✅ 返回带 token 的 URL（如果有）
    if access_token and ai_url.startswith('data:'):
        display_url = f"/api/temp-images/{attachment_id}?token={access_token}"
    else:
        display_url = ai_url  # 降级：直接返回 Base64
    
    return {
        'attachment_id': attachment_id,
        'display_url': display_url,
        'cloud_url': '',
        'status': 'pending',
        'task_id': task_id
    }
```

### 4.2 临时图片端点（`attachments.py`）

```python
@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    attachment = db.query(MessageAttachment).filter_by(id=attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # ✅ 已上传的附件 → 直接返回云URL
    if attachment.upload_status == 'completed' and attachment.url and attachment.url.startswith('http'):
        return RedirectResponse(url=attachment.url)
    
    # ✅ 临时附件 → 需要 token 验证
    user_id = None
    if token:
        try:
            payload: TokenPayload = decode_token(token)
            if payload.type != "access":
                raise HTTPException(status_code=403, detail="Invalid token type")
            user_id = payload.sub
        except JWTError:
            raise HTTPException(status_code=403, detail="Invalid or expired token")
    
    if not user_id:
        user_id = require_user_id(request)
    
    # 权限检查
    if attachment.user_id != user_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # 返回图片
    # ...
```

### 4.3 前端自动更新（`imageTokenUpdate.ts`）

```typescript
import { listenTokenRefresh } from '@/services/authSync';

export function setupImageTokenAutoUpdate() {
  listenTokenRefresh((newAccessToken) => {
    const images = document.querySelectorAll('img[src*="/api/temp-images/"]');
    images.forEach((img) => {
      const src = img.getAttribute('src');
      if (src && src.includes('/api/temp-images/')) {
        const url = new URL(src, window.location.origin);
        url.searchParams.set('token', newAccessToken);
        img.setAttribute('src', url.toString());
      }
    });
  });
}
```

## 五、总结

**推荐方案**：**使用现有 access_token + 自动刷新**

**核心改变**：

1. ✅ 后端从 request 获取当前的 `access_token`
2. ✅ 返回带 token 的 URL：`/api/temp-images/{attachment_id}?token={access_token}`
3. ✅ 前端监听 token 刷新事件，自动更新图片 URL
4. ✅ 完全复用现有的自动刷新机制

**优势**：

- 🎯 **完全复用现有机制**：不需要创建新的临时 token
- 📖 **阅读方便**：URL 比 Base64 短很多
- ⏰ **支持长期工作**：通过自动刷新，可以持续工作
- 🔒 **安全**：使用现有的 JWT 验证机制
- 💡 **实现简单**：只需修改三个地方

**预计时间**：2 天（包括测试）