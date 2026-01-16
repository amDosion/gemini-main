# Frontend 前端文档

## 概述
这是一个基于 React + TypeScript + Vite 的现代化前端应用，提供 AI 对话、图像生成/编辑、深度研究等多种功能。

## 技术栈

- **框架**: React 18
- **语言**: TypeScript
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **图标**: Lucide React
- **状态管理**: React Context API + Custom Hooks
- **数据持久化**: IndexedDB (通过自定义服务)

## 目录结构

```
frontend/
├── components/          # React 组件
│   ├── layout/         # 布局组件（Header等）
│   └── README.md       # 组件开发文档
├── hooks/              # 自定义 React Hooks
│   ├── useModels.ts    # 模型管理
│   ├── useSettings.ts  # 设置管理
│   └── README.md       # Hooks 文档
├── services/           # 业务逻辑和 API 服务
│   ├── db.ts          # IndexedDB 数据库服务
│   ├── llmService.ts  # LLM API 服务
│   └── ...
├── contexts/          # React Context 提供者
│   └── ToastContext.tsx
├── types/             # TypeScript 类型定义
│   └── types.ts
└── README.md          # 本文件
```

## 核心功能模块

### 1. 配置管理系统 (Profile System)
- 支持多个 API 配置（Google、DeepSeek、OpenAI 等）
- 配置持久化到 IndexedDB
- 快速切换不同的提供商配置
- 模型列表缓存优化

### 2. 模型选择系统
- 根据应用模式智能过滤模型
- 支持模型搜索
- 显示模型能力标识
- 详细的过滤和选择日志

### 3. 应用模式系统
支持多种工作模式：
- `chat`: 标准对话
- `image-gen`: 文生图
- `image-*-edit`: 图像编辑（多种子模式）
- `video-gen`: 视频生成
- `audio-gen`: 音频生成
- `deep-research`: 深度研究
- `pdf-extract`: PDF 提取
- `virtual-try-on`: 虚拟试衣

### 4. 日志系统
完整的前端日志系统，记录：
- 用户操作
- 状态变化
- 性能指标
- 错误信息

## 快速开始

### 开发环境设置
```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

### 开发服务器
默认运行在 `http://localhost:5173`

## 开发指南

### 添加新功能
1. 在 `types/types.ts` 中定义类型
2. 在 `services/` 中实现业务逻辑
3. 在 `hooks/` 中封装状态管理逻辑
4. 在 `components/` 中实现 UI 组件
5. 更新相关文档

### 状态管理模式

**本地组件状态**
```typescript
const [state, setState] = useState(initialValue);
```

**跨组件共享状态**
```typescript
// 使用 Context
const value = useContext(SomeContext);
```

**持久化状态**
```typescript
// 使用自定义 Hook
const { settings, updateSettings } = useSettings();
```

### API 调用模式
```typescript
// services/someService.ts
export const someService = {
    async fetchData(params: Params): Promise<Result> {
        const response = await fetch('/api/endpoint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        
        if (!response.ok) {
            throw new Error('API call failed');
        }
        
        return response.json();
    }
};

// 在组件中使用
const handleFetch = async () => {
    try {
        setLoading(true);
        const data = await someService.fetchData(params);
        // 处理数据
    } catch (error) {
        console.error('Error:', error);
        showError('操作失败');
    } finally {
        setLoading(false);
    }
};
```

### 日志使用指南

**创建日志器**
```typescript
const LOG_PREFIX = '[ComponentName]';

const logger = {
    info: (message: string, data?: any) => {
        console.log(`%c${LOG_PREFIX} ℹ️ ${message}`, 'color: #3b82f6', data || '');
    },
    success: (message: string, data?: any) => {
        console.log(`%c${LOG_PREFIX} ✅ ${message}`, 'color: #10b981', data || '');
    },
    // ... 其他级别
};
```

**使用日志**
```typescript
// 记录操作
logger.info('用户点击按钮', { buttonId: 'submit' });

// 记录成功
logger.success('数据加载完成', { count: data.length });

// 记录错误
logger.error('API 调用失败', error);

// 分组日志
logger.group('复杂操作');
logger.info('步骤 1');
logger.info('步骤 2');
logger.groupEnd();
```

### 性能优化技巧

**1. 使用 useMemo 缓存计算结果**
```typescript
const filteredData = useMemo(() => {
    return data.filter(item => condition(item));
}, [data, condition]);
```

**2. 使用 useCallback 缓存函数**
```typescript
const handleClick = useCallback(() => {
    // 处理逻辑
}, [dependencies]);
```

**3. 延迟加载组件**
```typescript
const HeavyComponent = React.lazy(() => import('./HeavyComponent'));

<Suspense fallback={<Loading />}>
    <HeavyComponent />
</Suspense>
```

**4. 避免内联对象和数组**
```typescript
// ❌ 不好 - 每次渲染创建新对象
<Component style={{ color: 'red' }} />

// ✅ 好 - 使用稳定引用
const style = { color: 'red' };
<Component style={style} />
```

## 调试技巧

### 1. 使用浏览器开发者工具
- **Console**: 查看日志输出
- **Network**: 检查 API 调用
- **React DevTools**: 检查组件树和状态
- **Performance**: 分析性能瓶颈

### 2. 查看详细日志
打开控制台，查找带有特定前缀的日志：
- `[Header-ModelSwitch]`: Header 组件日志
- 其他组件的日志前缀...

### 3. 常见问题排查

**模型不显示？**
1. 检查控制台的模型过滤日志
2. 确认当前 appMode
3. 查看模型的过滤原因

**API 调用失败？**
1. 检查 Network 标签
2. 查看请求和响应
3. 确认 API Key 配置正确

**状态不更新？**
1. 检查 useState/useEffect 的依赖数组
2. 使用 React DevTools 查看状态变化
3. 确认没有状态直接修改（mutation）

## 代码风格指南

### TypeScript
- 启用严格模式
- 为所有函数参数和返回值添加类型
- 使用接口（interface）定义对象结构
- 避免使用 `any`，使用 `unknown` 代替

### React
- 使用函数组件和 Hooks
- Props 使用解构赋值
- 事件处理函数命名：`handle` + 事件名
- 组件导出使用命名导出

### 样式
- 优先使用 Tailwind 实用类
- 保持类名可读性
- 使用一致的间距和颜色
- 响应式设计：移动优先

## 测试策略

### 单元测试
测试独立的函数和 Hooks
```typescript
// hooks/useModels.test.ts
describe('useModels', () => {
    it('should filter models by appMode', () => {
        // 测试逻辑
    });
});
```

### 集成测试
测试组件交互
```typescript
// components/Header.test.tsx
describe('Header', () => {
    it('should switch models when clicked', () => {
        // 测试逻辑
    });
});
```

## 部署

### 构建优化
```bash
# 生产构建（自动优化）
npm run build

# 分析构建大小
npm run build -- --report
```

### 环境变量
创建 `.env` 文件：
```
VITE_API_BASE_URL=https://api.example.com
VITE_APP_VERSION=1.0.0
```

## 更新日志

### 2026-01-15
- ✅ 修复 useModels Hook 作用域错误
- ✅ 添加 Header 组件完整日志系统
- ✅ 创建详细的开发文档
- ✅ 优化模型过滤性能

### 未来计划
- [ ] 添加单元测试覆盖
- [ ] 实现主题切换功能
- [ ] 优化移动端体验
- [ ] 添加更多日志监控点

## 相关文档

- [组件开发指南](./components/README.md)
- [Hooks 使用文档](./hooks/README.md)
- [Header 组件详细文档](./components/layout/README.md)

## 贡献指南

1. 遵循现有代码风格
2. 添加必要的类型定义
3. 为新功能添加日志
4. 更新相关文档
5. 测试所有改动

## 技术支持

遇到问题？
1. 查看控制台日志
2. 阅读相关文档
3. 检查 GitHub Issues
4. 联系开发团队

---

**最后更新**: 2026-01-15
**维护者**: 开发团队
