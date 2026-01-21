# 性能优化设计文档

> **项目名称**: 前端性能优化  
> **版本**: v2.0（最优综合方案）  
> **创建日期**: 2026-01-21  
> **来源**: 基于代码分析和性能测试

---

## 一、设计概述

### 1.1 设计目标

基于代码分析，提出**单一最优综合方案**，解决首次加载性能问题，确保 FCP < 1.8s，LCP < 2.5s。

**当前性能指标**：
- **FCP**: 7.2s（目标 < 1.8s）❌
- **LCP**: 14.2s（目标 < 2.5s）❌
- **初始 bundle**: 包含 100+ 个组件文件

### 1.2 代码分析结果

**关键发现**：

1. **App.tsx (第 9-20 行)**：使用 barrel file 同步导入所有视图组件
   ```typescript
   import { ChatView, AgentView, MultiAgentView, StudioView, ... } from './components';
   ```

2. **StudioView.tsx (第 4-14 行)**：同步导入所有 11 个子视图
   ```typescript
   import { ImageGenView } from './ImageGenView';
   import { ImageEditView } from './ImageEditView';
   // ... 其他 9 个子视图
   ```

3. **useInitData.ts (第 71, 90 行)**：同步等待 `/api/init`，然后同步调用 `LLMFactory.initialize()`
   ```typescript
   const data = await apiClient.get<InitData>('/api/init');
   await LLMFactory.initialize(); // 阻塞渲染
   ```

4. **init_service.py (第 163-260 行)**：查询所有会话（无限制），包含所有消息和附件
   ```python
   sessions = user_query.get_all(ChatSession)  # 无限制
   ```

5. **Header.tsx (第 25-27, 86 行)**：需要 `profiles`, `activeProfileId`, `visibleModels`（来自 `cachedModels`）

### 1.3 最优综合方案

**核心策略**：**分层加载 + 代码分割 + 数据优化**

1. **代码分割**：懒加载所有非 chat 模式的视图组件（减少初始 bundle 60-70%）
2. **数据分层加载**：关键数据立即加载，非关键数据延迟加载（减少阻塞时间 70%）
3. **异步初始化**：LLMFactory.initialize() 后台执行（不阻塞渲染）
4. **会话数据优化**：限制会话数量（20个），但必须包含最新会话（减少响应体积 30-50%）

---

## 二、详细设计方案

### 2.1 代码分割：懒加载非关键视图组件

#### 2.1.1 设计思路

**关键原则**：
- ✅ **ChatView 保持同步加载**：默认模式，必须立即可用
- ✅ **其他视图懒加载**：AgentView, MultiAgentView, StudioView, LiveAPIView
- ✅ **Studio 子视图懒加载**：11 个子视图全部懒加载
- ✅ **MultiAgent 组件懒加载**：12 个组件全部懒加载

#### 2.1.2 实施步骤

**步骤 1**：修改 `frontend/App.tsx`

```typescript
// 修改前（第 9-20 行）
import {
  AppLayout,
  ChatView,
  AgentView,
  MultiAgentView,
  StudioView,
  SettingsModal,
  ImageModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen
} from './components';

// 修改后
import { lazy, Suspense } from 'react';
import {
  AppLayout,
  ChatView,  // ✅ 保持同步加载（默认模式）
  SettingsModal,
  ImageModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen
} from './components';

// ✅ 懒加载非关键视图
const AgentView = lazy(() => import('./components/views/AgentView'));
const MultiAgentView = lazy(() => import('./components/views/MultiAgentView'));
const StudioView = lazy(() => import('./components/views/StudioView'));
const LiveAPIView = lazy(() => import('./components/live/LiveAPIView'));

// 在 Routes 中使用 Suspense
<Suspense fallback={<LoadingSpinner />}>
  <Routes>
    <Route path="/" element={<ChatView />} />  {/* ✅ 同步加载 */}
    <Route path="/agent" element={<AgentView />} />
    <Route path="/multi-agent" element={<MultiAgentView />} />
    <Route path="/studio" element={<StudioView />} />
    <Route path="/live" element={<LiveAPIView />} />
  </Routes>
</Suspense>
```

**步骤 2**：修改 `frontend/components/views/StudioView.tsx`

```typescript
// 修改前（第 4-14 行）
import { ImageGenView } from './ImageGenView';
import { ImageEditView } from './ImageEditView';
// ... 其他 9 个子视图

// 修改后
import { lazy, Suspense } from 'react';
import { LoadingSpinner } from '../common/LoadingSpinner';

// ✅ 所有 Studio 子视图懒加载
const ImageGenView = lazy(() => import('./ImageGenView'));
const ImageEditView = lazy(() => import('./ImageEditView'));
const ImageMaskEditView = lazy(() => import('./ImageMaskEditView'));
const ImageInpaintingView = lazy(() => import('./ImageInpaintingView'));
const ImageBackgroundEditView = lazy(() => import('./ImageBackgroundEditView'));
const ImageRecontextView = lazy(() => import('./ImageRecontextView'));
const VideoGenView = lazy(() => import('./VideoGenView'));
const AudioGenView = lazy(() => import('./AudioGenView'));
const PdfExtractView = lazy(() => import('./PdfExtractView'));
const ImageExpandView = lazy(() => import('./ImageExpandView'));
const VirtualTryOnView = lazy(() => import('./VirtualTryOnView'));

// 在 switch 语句中使用 Suspense
export const StudioView: React.FC<StudioViewProps> = React.memo((props) => {
  const renderView = () => {
    switch (props.mode) {
      case 'image-gen': return <ImageGenView {...props} />;
      case 'image-chat-edit': return <ImageEditView {...props} />;
      // ... 其他模式
      default: return <ImageGenView {...props} />;
    }
  };
  
  return (
    <Suspense fallback={<LoadingSpinner />}>
      {renderView()}
    </Suspense>
  );
});
```

**预期效果**：
- 初始 bundle 大小减少 60-70%
- FCP 从 7.2s 降至 < 3s
- 网络请求减少 80+ 个组件文件

---

### 2.2 数据分层加载：关键数据立即加载，非关键数据延迟加载

#### 2.2.1 设计思路

**关键数据定义**（必须在首次渲染前加载）：
- `profiles`: 提供商配置列表（Header 需要显示提供商选择器）
- `activeProfileId`: 当前激活的提供商ID
- `activeProfile`: 当前激活的提供商配置（包含 providerId, apiKey 等）
- `cachedModels`: 缓存的模型列表（Header 需要显示模型选择器，chat 模式必需）
- `dashscopeKey`: 通义千问的 API Key（如果使用通义千问）

**非关键数据定义**（可以延迟加载）：
- `sessions`: 会话列表元数据（只包含 id, title, mode, createdAt, updatedAt, messageCount，不包含消息内容）
- `sessionsTotal`: 总会话数量（用于分页）
- `sessionsHasMore`: 是否还有更多会话（用于滚动加载）
- `personas`: 角色列表（可以延迟加载）
- `storageConfigs`: 云存储配置（可以延迟加载）
- `imagenConfig`: Imagen 配置（可以延迟加载）

**设计原则**：
- ✅ 关键数据必须阻塞渲染（Header 和 chat 模式需要）
- ✅ 非关键数据后台加载（不影响首次渲染）
- ✅ 如果非关键数据未加载，使用空数组作为默认值

#### 2.2.2 实施步骤

**步骤 1**：创建后端端点 `backend/app/routers/user/init.py`

```python
@router.get("/init/critical")
async def get_critical_init_data(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取关键初始化数据（阻塞渲染）
    
    关键数据包括：
    - profiles: 提供商配置列表
    - activeProfileId: 当前激活的提供商ID
    - activeProfile: 当前激活的提供商配置
    - cachedModels: 缓存的模型列表（Header 需要显示模型选择器）
    - dashscopeKey: 通义千问的 API Key
    """
    from ...services.common.init_service import _query_profiles
    
    profiles_result = await _query_profiles(user_id, db)
    
    # 查询 cachedModels（从 activeProfile 获取）
    cached_models = None
    if profiles_result.get("activeProfile"):
        # 这里需要调用模型查询逻辑，获取用户可用的模型列表
        # 简化示例：从 activeProfile 中提取模型信息
        # 实际实现需要根据后端模型查询逻辑
        pass
    
    return {
        "profiles": profiles_result["profiles"],
        "activeProfileId": profiles_result["activeProfileId"],
        "activeProfile": profiles_result["activeProfile"],
        "cachedModels": cached_models,
        "dashscopeKey": profiles_result["dashscopeKey"]
    }

@router.get("/init/non-critical")
async def get_non_critical_init_data(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取非关键初始化数据（后台加载）
    
    非关键数据包括：
    - sessions: 会话列表元数据（只返回最近的 20 个，不包含消息内容）
    - sessionsTotal: 总会话数量（用于分页）
    - sessionsHasMore: 是否还有更多会话（用于滚动加载）
    - personas: 角色列表
    - storageConfigs: 云存储配置
    - imagenConfig: Imagen 配置
    """
    from ...services.common.init_service import (
        _query_sessions_metadata,  # ✅ 改为元数据查询
        _query_personas, 
        _query_storage_configs,
        _query_vertex_ai_config
    )
    import asyncio
    
    # 并行查询非关键数据
    sessions_result, personas_result, storage_result, vertex_ai_result = await asyncio.gather(
        _query_sessions_metadata(user_id, db, limit=20, offset=0),  # ✅ 只返回元数据
        _query_personas(user_id, db),
        _query_storage_configs(user_id, db),
        _query_vertex_ai_config(user_id, db),
        return_exceptions=True
    )
    
    return {
        "sessions": sessions_result.get("sessions", []) if isinstance(sessions_result, dict) else [],
        "sessionsTotal": sessions_result.get("total", 0) if isinstance(sessions_result, dict) else 0,
        "sessionsHasMore": sessions_result.get("hasMore", False) if isinstance(sessions_result, dict) else False,
        "personas": personas_result.get("personas", []) if isinstance(personas_result, dict) else [],
        "storageConfigs": storage_result.get("storageConfigs", []) if isinstance(storage_result, dict) else [],
        "activeStorageId": storage_result.get("activeStorageId") if isinstance(storage_result, dict) else None,
        "imagenConfig": vertex_ai_result.get("imagenConfig") if isinstance(vertex_ai_result, dict) else None
    }
```

**步骤 2**：修改 `backend/app/services/common/init_service.py`

**注意**：此步骤已在 2.3.2 步骤 1 中实现，这里不再重复。新的 `_query_sessions_metadata` 函数只返回会话元数据，不包含消息内容。

**步骤 3**：修改 `frontend/hooks/useInitData.ts`（支持会话元数据）

```typescript
export const useInitData = (isAuthenticated: boolean): UseInitDataReturn => {
  const [criticalData, setCriticalData] = useState<Partial<InitData> | null>(null);
  const [nonCriticalData, setNonCriticalData] = useState<Partial<InitData> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [isConfigReady, setIsConfigReady] = useState<boolean>(false);
  const [retryTrigger, setRetryTrigger] = useState(0);
  
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const retry = useCallback(() => {
    setRetryTrigger(count => count + 1);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    if (!isAuthenticated) {
      setCriticalData(null);
      setNonCriticalData(null);
      setIsLoading(false);
      setError(null);
      setIsConfigReady(false);
      return;
    }

    const fetchData = async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      setIsLoading(true);
      setError(null);

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        abortControllerRef.current = new AbortController();

        try {
          // ✅ 步骤 1：先加载关键数据（阻塞渲染）
          const critical = await apiClient.get<Partial<InitData>>('/api/init/critical');
          
          if (!isMountedRef.current) return;

          setCriticalData(critical);
          setError(null);
          
          // ✅ 步骤 2：关键数据加载完成后，立即渲染
          // Header 可以显示提供商和模型选择器
          // chat 模式可以正常工作
          
          // ✅ 步骤 3：后台加载非关键数据（不阻塞渲染）
          apiClient.get<Partial<InitData>>('/api/init/non-critical')
            .then(nonCritical => {
              if (isMountedRef.current) {
                setNonCriticalData(nonCritical);
              }
            })
            .catch(err => {
              console.warn('[useInitData] 非关键数据加载失败:', err);
              // 非关键数据失败不影响主流程
            });
          
          // ✅ 步骤 4：后台异步初始化 LLMFactory（不阻塞渲染）
          LLMFactory.initialize().catch(err => {
            console.warn('[useInitData] LLMFactory 初始化失败:', err);
          });
          
          return; // 成功，退出重试循环
        } catch (e) {
          if (!isMountedRef.current) return;

          const error = e as Error;
          if (error.message === 'Unauthorized') {
            setError(error);
            return;
          }

          if (attempt < MAX_RETRIES) {
            const delay = BASE_RETRY_DELAY * Math.pow(2, attempt);
            await new Promise(resolve => setTimeout(resolve, delay));
          } else {
            setError(error);
          }
        }
      }
    };

    fetchData().finally(() => {
      if (isMountedRef.current) {
        setIsLoading(false);
        setIsConfigReady(true);
      }
    });

    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isAuthenticated, retryTrigger]);

  // ✅ 合并关键数据和非关键数据
  const initData = useMemo(() => {
    if (!criticalData) return null;
    return {
      ...criticalData,
      ...nonCriticalData,
      // 如果非关键数据还未加载，使用空数组作为默认值
      sessions: nonCriticalData?.sessions || [],  // ✅ 只包含元数据，不包含消息
      sessionsTotal: nonCriticalData?.sessionsTotal || 0,
      sessionsHasMore: nonCriticalData?.sessionsHasMore || false,
      personas: nonCriticalData?.personas || [],
      storageConfigs: nonCriticalData?.storageConfigs || [],
      activeStorageId: nonCriticalData?.activeStorageId || null,
      imagenConfig: nonCriticalData?.imagenConfig || null
    };
  }, [criticalData, nonCriticalData]);

  return { initData, isLoading, error, isConfigReady, retry };
};
```

**预期效果**：
- FCP 从 7.2s 降至 < 2s（改善 72%）
- LCP 从 14.2s 降至 < 3s（改善 79%）
- 关键数据加载时间减少 70%（只加载必要数据）
- 非关键数据（会话元数据）响应体积减少 70-90%（不包含消息内容）

---

### 2.3 会话数据优化：返回会话列表元数据 + 第一个会话的完整消息

#### 2.3.1 设计思路

**关键约束**：
- ✅ **必须返回最新的会话列表元数据**：sidebar 需要显示会话列表（只需要 id, title, mode, createdAt, updatedAt, messageCount）
- ✅ **第一个会话必须包含完整消息**：默认选择第一个会话，右侧 ChatView 需要立即显示消息（不能分页，必须完整）
- ✅ **其他会话不包含消息**：其他会话的 messages 为空数组，按需加载
- ✅ **限制初始数量**：只返回最近的 20 个会话元数据（而不是所有会话）
- ✅ **支持滚动加载更多**：提供分页/游标加载接口，支持惰性加载
- ✅ **按需加载消息**：当用户选择其他会话时，调用 `/api/sessions/{session_id}` 加载该会话的完整消息内容

**设计理由**：
- `useSessions` hook 需要 `initData.sessions` 来初始化会话列表（左侧 Sidebar）
- `useSessionSync` 在第 42 行：`setMessages(session.messages)` - 从 `session.messages` 中获取消息
- **消息加载流程**：
  1. 初始加载：返回会话列表元数据 + 第一个会话的完整消息（不能分页）
  2. 默认选择第一个会话：`setCurrentSessionId(preparedSessions[0].id)`（第 125 行）
  3. `useSessionSync` 检测到会话切换，从 `session.messages` 加载消息到右侧 ChatView
  4. 用户选择其他会话：如果 `session.messages` 为空，调用 `/api/sessions/{session_id}` 加载消息
- 如果 sessions 为空，会触发 `refreshSessions()`，增加额外的 API 请求
- 支持滚动加载更多可以进一步减少初始响应体积

#### 2.3.2 实施步骤

**步骤 1**：修改 `backend/app/services/common/init_service.py`

```python
async def _query_sessions_with_first_messages(user_id: str, db: Session, limit: int = 20) -> Dict[str, Any]:
    """
    查询会话列表 + 第一个会话的完整消息
    
    注意：
    1. 返回最近的 N 个会话元数据（用于左侧 Sidebar）
    2. 第一个会话必须包含完整消息（不能分页，用于右侧 ChatView）
    3. 其他会话的 messages 为空数组（按需加载）
    
    Returns:
        {
            "sessions": [
                {
                    "id": str,
                    "title": str,
                    "mode": str,
                    "personaId": str | null,
                    "createdAt": datetime,
                    "updatedAt": datetime,
                    "messageCount": int,  # 消息数量（用于显示）
                    "messages": [...]  # ✅ 第一个会话包含完整消息，其他为空数组
                }
            ],
            "total": int,  # 总会话数量（用于分页）
            "hasMore": bool  # 是否还有更多会话
        }
    """
    try:
        logger.info(f"[InitService] 查询 Sessions（包含第一个会话的完整消息，limit={limit}）...")
        
        # ✅ 查询会话列表（按更新时间排序）
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(
            ChatSession.updated_at.desc()  # 按更新时间排序，获取最新的会话
        ).limit(limit).all()
        
        if not sessions:
            logger.info(f"[InitService] Sessions 加载成功: 0 个会话")
            return {
                "sessions": [],
                "total": 0,
                "hasMore": False,
                "error": None
            }
        
        # ✅ 查询总会话数量（用于分页）
        total_count = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).count()
        
        # ✅ 批量查询每个会话的消息数量（用于显示）
        from sqlalchemy import func
        session_ids = [s.id for s in sessions]
        message_counts = db.query(
            MessageIndex.session_id,
            func.count(MessageIndex.id).label('count')
        ).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).group_by(MessageIndex.session_id).all()
        
        # 构建消息数量映射
        message_count_map = {session_id: count for session_id, count in message_counts}
        
        # ✅ 第一个会话：加载完整消息（不能分页）
        from ...utils.message_utils import get_message_table_class_by_name
        from collections import defaultdict
        
        first_session_id = sessions[0].id
        first_session_messages = []
        
        # 查询第一个会话的消息索引
        first_indexes = db.query(MessageIndex).filter(
            MessageIndex.session_id == first_session_id,
            MessageIndex.user_id == user_id
        ).order_by(MessageIndex.seq.asc()).all()
        
        if first_indexes:
            # 收集 message_ids 和 table_names
            first_message_ids = [idx.id for idx in first_indexes]
            first_table_message_ids: Dict[str, Set[str]] = defaultdict(set)
            for idx in first_indexes:
                first_table_message_ids[idx.table_name].add(idx.id)
            
            # 批量查询模式表
            first_messages_by_table: Dict[str, Dict[str, Any]] = {}
            for table_name, msg_ids in first_table_message_ids.items():
                try:
                    table_class = get_message_table_class_by_name(table_name)
                    messages = db.query(table_class).filter(
                        table_class.id.in_(list(msg_ids))
                    ).all()
                    first_messages_by_table[table_name] = {msg.id: msg for msg in messages}
                except ValueError:
                    continue
            
            # 批量查询附件
            first_attachments_by_message: Dict[str, List[MessageAttachment]] = defaultdict(list)
            attachments = db.query(MessageAttachment).filter(
                MessageAttachment.message_id.in_(first_message_ids),
                MessageAttachment.user_id == user_id
            ).all()
            for att in attachments:
                first_attachments_by_message[att.message_id].append(att)
            
            # 组装第一个会话的完整消息（不能分页）
            first_session_messages = assemble_messages_v3(
                first_session_id,
                first_indexes,
                first_messages_by_table,
                first_attachments_by_message
            )
        
        # ✅ 构建会话列表
        sessions_result = []
        for idx, session in enumerate(sessions):
            session_dict = {
                "id": session.id,
                "title": session.title,
                "mode": session.mode,
                "personaId": session.persona_id,
                "createdAt": session.created_at.isoformat() if session.created_at else None,
                "updatedAt": session.updated_at.isoformat() if session.updated_at else None,
                "messageCount": message_count_map.get(session.id, 0)
            }
            
            # ✅ 第一个会话包含完整消息，其他会话 messages 为空数组
            if idx == 0:
                session_dict["messages"] = first_session_messages  # ✅ 完整消息（不能分页）
            else:
                session_dict["messages"] = []  # ✅ 其他会话按需加载
            
            sessions_result.append(session_dict)
        
        has_more = len(sessions) < total_count
        
        logger.info(f"[InitService] Sessions 加载成功: {len(sessions_result)} 个会话（总共 {total_count} 个），第一个会话包含 {len(first_session_messages)} 条消息")
        
        return {
            "sessions": sessions_result,
            "total": total_count,
            "hasMore": has_more,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 加载失败: {e}")
        return {
            "sessions": [],
            "total": 0,
            "hasMore": False,
            "error": str(e)
        }
```

**步骤 2**：创建滚动加载更多接口 `backend/app/routers/user/init.py`

```python
@router.get("/init/sessions/more")
async def get_more_sessions_metadata(
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(20, ge=1, le=50, description="每页数量"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取更多会话元数据（滚动加载）
    
    支持分页加载，用于前端滚动加载更多会话
    注意：返回的会话 messages 为空数组（按需加载）
    """
    from ...services.common.init_service import _query_sessions_metadata_only
    
    result = await _query_sessions_metadata_only(user_id, db, limit=limit, offset=offset)
    return result
```

**步骤 2.1**：添加只返回元数据的辅助函数 `backend/app/services/common/init_service.py`

```python
async def _query_sessions_metadata_only(user_id: str, db: Session, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    只查询会话元数据（不包含消息内容）
    
    用于滚动加载更多会话（messages 为空数组）
    """
    try:
        logger.info(f"[InitService] 查询 Sessions 元数据（limit={limit}, offset={offset}）...")
        
        # 查询会话元数据（不包含消息）
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(
            ChatSession.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        if not sessions:
            return {
                "sessions": [],
                "total": 0,
                "hasMore": False,
                "error": None
            }
        
        # 查询总会话数量
        total_count = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).count()
        
        # 批量查询每个会话的消息数量
        from sqlalchemy import func
        session_ids = [s.id for s in sessions]
        message_counts = db.query(
            MessageIndex.session_id,
            func.count(MessageIndex.id).label('count')
        ).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).group_by(MessageIndex.session_id).all()
        
        message_count_map = {session_id: count for session_id, count in message_counts}
        
        # 构建会话元数据列表（messages 为空数组）
        sessions_result = []
        for session in sessions:
            session_dict = {
                "id": session.id,
                "title": session.title,
                "mode": session.mode,
                "personaId": session.persona_id,
                "createdAt": session.created_at.isoformat() if session.created_at else None,
                "updatedAt": session.updated_at.isoformat() if session.updated_at else None,
                "messageCount": message_count_map.get(session.id, 0),
                "messages": []  # ✅ 滚动加载的会话 messages 为空数组
            }
            sessions_result.append(session_dict)
        
        has_more = (offset + limit) < total_count
        
        logger.info(f"[InitService] Sessions 元数据加载成功: {len(sessions_result)} 个会话（总共 {total_count} 个）")
        
        return {
            "sessions": sessions_result,
            "total": total_count,
            "hasMore": has_more,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 元数据加载失败: {e}")
        return {
            "sessions": [],
            "total": 0,
            "hasMore": False,
            "error": str(e)
        }
```

**步骤 3**：修改 `backend/app/routers/user/init.py` 中的非关键数据端点

```python
@router.get("/init/non-critical")
async def get_non_critical_init_data(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取非关键初始化数据（后台加载）
    
    非关键数据包括：
    - sessions: 会话列表元数据（只返回最近的 20 个，不包含消息内容）
    - personas: 角色列表
    - storageConfigs: 云存储配置
    - imagenConfig: Imagen 配置
    """
    from ...services.common.init_service import (
        _query_sessions_metadata,  # ✅ 改为元数据查询
        _query_personas, 
        _query_storage_configs,
        _query_vertex_ai_config
    )
    import asyncio
    
    # 并行查询非关键数据
    sessions_result, personas_result, storage_result, vertex_ai_result = await asyncio.gather(
        _query_sessions_metadata(user_id, db, limit=20, offset=0),  # ✅ 只返回元数据
        _query_personas(user_id, db),
        _query_storage_configs(user_id, db),
        _query_vertex_ai_config(user_id, db),
        return_exceptions=True
    )
    
    return {
        "sessions": sessions_result.get("sessions", []) if isinstance(sessions_result, dict) else [],
        "sessionsTotal": sessions_result.get("total", 0) if isinstance(sessions_result, dict) else 0,
        "sessionsHasMore": sessions_result.get("hasMore", False) if isinstance(sessions_result, dict) else False,
        "personas": personas_result.get("personas", []) if isinstance(personas_result, dict) else [],
        "storageConfigs": storage_result.get("storageConfigs", []) if isinstance(storage_result, dict) else [],
        "activeStorageId": storage_result.get("activeStorageId") if isinstance(storage_result, dict) else None,
        "imagenConfig": vertex_ai_result.get("imagenConfig") if isinstance(vertex_ai_result, dict) else None
    }
```

**步骤 4**：创建获取单个会话的路由端点 `backend/app/routers/user/sessions.py`

```python
@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取单个会话的完整数据（包含消息内容）
    
    用于用户选择会话时按需加载消息
    """
    from .sessions import get_session_by_id
    return await get_session_by_id(session_id, user_id, db)
```

**步骤 5**：修改前端 `frontend/hooks/useSessionSync.ts` 支持按需加载消息

```typescript
import { apiClient } from '../services/apiClient';

export const useSessionSync = ({
  currentSessionId,
  sessions,
  activeModelConfig,
  setMessages,
  setAppMode
}: UseSessionSyncProps) => {
  const prevSessionIdRef = useRef<string | null>(null);
  const prevModelConfigRef = useRef<typeof activeModelConfig>(undefined);
  const sessionsRef = useRef(sessions);
  const loadingMessagesRef = useRef<Set<string>>(new Set()); // 正在加载消息的会话 ID

  // Sync sessions to ref
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    if (currentSessionId) {
      const session = sessionsRef.current.find(s => s.id === currentSessionId);
      if (session) {
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
        if (isSessionSwitch) {
          // ✅ 检查会话是否有消息数据
          if (session.messages && session.messages.length > 0) {
            // 会话已有消息数据（第一个会话或已缓存的会话），直接使用
            setMessages(session.messages);
            
            // 恢复会话模式
            const storedMode = session.mode;
            if (storedMode) {
              setAppMode(storedMode as AppMode);
            } else {
              const lastMsg = [...session.messages].reverse().find(m => m.mode);
              setAppMode((lastMsg?.mode || 'chat') as AppMode);
            }
            
            // 更新 llmService
            if (activeModelConfig) {
              llmService.startNewChat(session.messages, activeModelConfig);
              prevModelConfigRef.current = activeModelConfig;
            }
          } else {
            // ✅ 会话没有消息数据，按需加载（不能分页，必须完整）
            if (!loadingMessagesRef.current.has(currentSessionId)) {
              loadingMessagesRef.current.add(currentSessionId);
              
              // 调用 API 加载会话的完整消息内容（不能分页）
              apiClient.get<ChatSession>(`/api/sessions/${currentSessionId}`)
                .then(fullSession => {
                  // 更新 sessions 中的消息数据（用于缓存）
                  const sessionIndex = sessionsRef.current.findIndex(s => s.id === currentSessionId);
                  if (sessionIndex >= 0) {
                    sessionsRef.current[sessionIndex].messages = fullSession.messages || [];
                  }
                  
                  // 设置消息到右侧 ChatView
                  setMessages(fullSession.messages || []);
                  
                  // 恢复会话模式
                  const storedMode = fullSession.mode;
                  if (storedMode) {
                    setAppMode(storedMode as AppMode);
                  } else {
                    const lastMsg = [...(fullSession.messages || [])].reverse().find(m => m.mode);
                    setAppMode((lastMsg?.mode || 'chat') as AppMode);
                  }
                  
                  // 更新 llmService
                  if (activeModelConfig) {
                    llmService.startNewChat(fullSession.messages || [], activeModelConfig);
                    prevModelConfigRef.current = activeModelConfig;
                  }
                  
                  loadingMessagesRef.current.delete(currentSessionId);
                })
                .catch(err => {
                  console.error(`[useSessionSync] 加载会话 ${currentSessionId} 的消息失败:`, err);
                  setMessages([]); // 加载失败，设置为空数组
                  loadingMessagesRef.current.delete(currentSessionId);
                });
            }
          }
          
          prevSessionIdRef.current = currentSessionId;
        }

        // Only update llmService when model actually changes (not session switch)
        const isModelSwitch = prevModelConfigRef.current?.id !== activeModelConfig?.id;
        if (!isSessionSwitch && isModelSwitch && activeModelConfig) {
          const messagesToUse = session.messages && session.messages.length > 0 
            ? session.messages 
            : [];
          llmService.startNewChat(messagesToUse, activeModelConfig);
          prevModelConfigRef.current = activeModelConfig;
        }
      }
    }
  }, [currentSessionId, activeModelConfig, setMessages, setAppMode]);
};
```

**步骤 6**：修改前端 `frontend/hooks/useSessions.ts` 支持滚动加载

```typescript
// 在 useSessions hook 中添加滚动加载功能
const [hasMoreSessions, setHasMoreSessions] = useState(false);
const [isLoadingMore, setIsLoadingMore] = useState(false);

const loadMoreSessions = useCallback(async () => {
  if (isLoadingMore || !hasMoreSessions) return;
  
  try {
    setIsLoadingMore(true);
    const offset = sessions.length;
    const result = await apiClient.get<{
      sessions: ChatSession[];
      total: number;
      hasMore: boolean;
    }>(`/api/init/sessions/more?offset=${offset}&limit=20`);
    
    if (result.sessions.length > 0) {
      // ✅ 注意：返回的会话只包含元数据，messages 为空数组（按需加载）
      const preparedSessions = prepareSessions(result.sessions.map(s => ({
        ...s,
        messages: s.messages || [] // 滚动加载的会话 messages 为空数组
      })));
      setSessions(prev => [...prev, ...preparedSessions]);
      setHasMoreSessions(result.hasMore);
    }
  } catch (error) {
    console.error('Failed to load more sessions:', error);
  } finally {
    setIsLoadingMore(false);
  }
}, [sessions.length, hasMoreSessions, isLoadingMore, prepareSessions]);

// 初始化时设置 hasMoreSessions
useEffect(() => {
  if (initData?.sessionsHasMore !== undefined) {
    setHasMoreSessions(initData.sessionsHasMore);
  }
}, [initData?.sessionsHasMore]);
```

**步骤 7**：修改前端 `frontend/components/layout/Sidebar.tsx` 支持滚动加载

```typescript
// 在 Sidebar 组件中添加滚动监听
const sidebarRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  const handleScroll = () => {
    if (!sidebarRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = sidebarRef.current;
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100; // 距离底部 100px 时加载
    
    if (isNearBottom && hasMoreSessions && !isLoadingMore) {
      loadMoreSessions();
    }
  };
  
  const sidebar = sidebarRef.current;
  if (sidebar) {
    sidebar.addEventListener('scroll', handleScroll);
    return () => sidebar.removeEventListener('scroll', handleScroll);
  }
}, [hasMoreSessions, isLoadingMore, loadMoreSessions]);

// 在渲染会话列表时添加加载更多指示器
{sessions.map(session => (
  // ... 会话项渲染
))}

{isLoadingMore && (
  <div className="px-4 py-2 text-center text-xs text-slate-500">
    <LoadingSpinner size="sm" /> 加载更多...
  </div>
)}

{!hasMoreSessions && sessions.length > 0 && (
  <div className="px-4 py-2 text-center text-xs text-slate-500">
    已加载全部会话
  </div>
)}
```

**消息加载流程说明**：

1. **初始加载**：
   - `/api/init/non-critical` 返回：
     * 会话列表元数据（最近的 20 个）
     * **第一个会话包含完整消息**（不能分页，用于右侧 ChatView）
     * 其他会话的 `messages` 为空数组 `[]`
   - `useSessions` 初始化会话列表（左侧 Sidebar）
   - 默认选择第一个会话（`setCurrentSessionId(preparedSessions[0].id)`，第 125 行）
   - `useSessionSync` 检测到会话切换，从 `session.messages` 加载消息到右侧 ChatView（第 42 行）

2. **用户选择其他会话（左侧 → 右侧）**：
   - `useSessionSync` 检测到 `currentSessionId` 变化
   - 检查 `session.messages` 是否为空或未定义
   - **如果为空**：调用 `/api/sessions/{session_id}` 加载该会话的完整消息内容（不能分页）
   - **如果不为空**：直接使用已有的消息数据（已缓存）
   - 将加载的消息设置到右侧 ChatView（通过 `setMessages`）
   - 更新 `llmService.startNewChat()` 以支持流式传输

3. **滚动加载更多会话（左侧 Sidebar）**：
   - 用户滚动 Sidebar 到底部
   - 调用 `/api/init/sessions/more?offset=...&limit=20` 加载更多会话元数据
   - 新加载的会话 `messages` 字段为空数组 `[]`，触发按需加载

**关键设计点**：
- ✅ **左侧（Sidebar）**：显示会话列表元数据
- ✅ **右侧（ChatView）**：显示选中会话的消息内容
- ✅ **第一个会话**：初始加载时必须包含完整消息（不能分页），确保右侧 ChatView 可以立即显示
- ✅ **其他会话**：按需加载，当用户选择时调用 `/api/sessions/{session_id}` 加载完整消息（不能分页）
- ✅ **缓存机制**：加载后的消息可以缓存在 `sessions` 中，避免重复加载

**预期效果**：
- 响应体积减少 70-90%（不包含消息内容，只返回元数据）
- 网络传输时间显著减少
- 支持滚动加载更多，用户体验良好
- 初始加载只返回 20 个会话元数据，后续按需加载

---

## 三、实施计划

### 3.1 阶段 1：代码分割（1-2 小时）

**步骤**：
1. 修改 `App.tsx`：懒加载非关键视图组件
2. 修改 `StudioView.tsx`：懒加载所有子视图
3. 添加 Suspense 边界和加载状态
4. 测试所有路由正常加载

**验收标准**：
- ✅ 所有非关键视图组件使用懒加载
- ✅ 初始 bundle 大小减少 60-70%
- ✅ FCP 从 7.2s 降至 < 3s

---

### 3.2 阶段 2：数据分层加载（2-3 小时）

**步骤**：
1. 创建 `/api/init/critical` 端点（关键数据）
2. 创建 `/api/init/non-critical` 端点（非关键数据）
3. 修改 `init_service.py`：限制会话数量（20个）
4. 修改 `useInitData.ts`：先加载关键数据，再加载非关键数据
5. 将 `LLMFactory.initialize()` 移到后台异步执行

**验收标准**：
- ✅ 关键数据包含 profiles, activeProfile, cachedModels
- ✅ 前端先加载关键数据，再加载非关键数据
- ✅ Header 可以正常显示提供商和模型选择器
- ✅ chat 模式可以正常工作
- ✅ FCP 从 7.2s 降至 < 2s

---

### 3.3 阶段 3：测试和优化（1-2 小时）

**步骤**：
1. 功能测试：所有视图正常加载
2. 性能测试：使用 Lighthouse 验证性能改进
3. 回归测试：确保所有现有功能正常工作

**验收标准**：
- ✅ FCP < 1.8s（达到目标）
- ✅ LCP < 2.5s（达到目标）
- ✅ 所有现有功能正常工作

---

## 四、预期效果

### 4.1 性能指标

- **FCP**: 从 7.2s 降至 < 1.8s（改善 75%）
- **LCP**: 从 14.2s 降至 < 2.5s（改善 82%）
- **初始 bundle 大小**: 减少 60-70%
- **网络请求**: 减少 80+ 个不必要的组件请求
- **响应体积**: 减少 30-50%（取决于用户会话数量）

### 4.2 用户体验

- ✅ 首次加载时间显著减少
- ✅ 关键功能（chat 模式）立即可用
- ✅ 非关键功能按需加载
- ✅ 所有现有功能正常工作

---

## 五、风险评估

### 5.1 技术风险

1. **风险**：懒加载可能导致首次访问某个模式时延迟
   - **概率**：中
   - **影响**：低
   - **缓解措施**：添加 Suspense 边界和加载状态，用户体验良好

2. **风险**：拆分 `/api/init` 可能导致多次请求
   - **概率**：低
   - **影响**：低
   - **缓解措施**：关键数据立即加载，非关键数据后台加载，总时间减少

### 5.2 业务风险

1. **风险**：优化可能影响现有功能
   - **概率**：低
   - **影响**：高
   - **缓解措施**：充分测试，确保向后兼容

---

## 六、相关文档

- `requirements.md` - 需求文档
- `tasks.md` - 任务文档
- `complete-performance-analysis.md` - 完整性能分析报告
- `network-performance-analysis.md` - 网络性能分析报告
- `performance-analysis.md` - 性能分析报告
