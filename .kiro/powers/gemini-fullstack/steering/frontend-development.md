---
inclusion: fileMatch
fileMatchPattern: "frontend/**/*.{ts,tsx,js,jsx}"
---

# 前端开发 Steering 指南

## React 组件开发规范

### 组件结构

每个 React 组件应该遵循以下结构：

```typescript
import React from 'react';

// 1. 类型定义
interface ComponentProps {
  // Props 定义
}

// 2. 组件实现
export const Component: React.FC<ComponentProps> = ({ ...props }) => {
  // 3. Hooks
  const [state, setState] = useState();
  
  // 4. 事件处理
  const handleEvent = () => {
    // 处理逻辑
  };
  
  // 5. 渲染
  return (
    <div>
      {/* JSX */}
    </div>
  );
};
```

### 模块化原则

- **单个文件 < 200 行**
- **每个组件独立文件**
- **协调组件组装子组件**

**示例**：
```
components/chat/
├── ChatView.tsx         # 协调组件（< 200 行）
├── MessageList.tsx      # 消息列表（< 200 行）
├── InputArea.tsx        # 输入区域（< 200 行）
└── MessageItem.tsx      # 单条消息（< 200 行）
```

## TypeScript 类型定义最佳实践

### 类型优先

```typescript
// ✅ 正确：先定义类型
interface User {
  id: string;
  name: string;
  email: string;
}

const user: User = {
  id: '1',
  name: 'John',
  email: 'john@example.com'
};

// ❌ 错误：使用 any
const user: any = { ... };
```

### 使用泛型

```typescript
// ✅ 正确：使用泛型
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

const response: ApiResponse<User> = await fetchUser();
```

## Custom Hooks 使用指南

### Hook 命名

- 以 `use` 开头
- 描述性命名
- 单一职责

```typescript
// ✅ 正确
export const useAuth = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  
  const login = async (credentials: Credentials) => {
    // 登录逻辑
  };
  
  return { user, loading, login };
};

// ❌ 错误：职责过多
export const useEverything = () => {
  // 包含太多功能
};
```

### Hook 组合

```typescript
// 组合多个 Hooks
export const useChatRoom = (roomId: string) => {
  const { user } = useAuth();
  const { messages, sendMessage } = useMessages(roomId);
  const { isConnected } = useWebSocket(roomId);
  
  return {
    user,
    messages,
    sendMessage,
    isConnected
  };
};
```

## 状态管理模式

### 本地状态 vs 全局状态

**本地状态**（useState）：
- 组件内部使用
- 不需要跨组件共享
- 简单的 UI 状态

**全局状态**（Zustand/Context）：
- 跨组件共享
- 用户认证状态
- 应用配置

### Zustand 示例

```typescript
import create from 'zustand';

interface AuthStore {
  user: User | null;
  setUser: (user: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null })
}));
```

## 性能优化建议

### 1. 使用 React.memo

```typescript
// 避免不必要的重渲染
export const MessageItem = React.memo<MessageItemProps>(({ message }) => {
  return <div>{message.content}</div>;
});
```

### 2. 使用 useMemo 和 useCallback

```typescript
// 缓存计算结果
const sortedMessages = useMemo(() => {
  return messages.sort((a, b) => a.timestamp - b.timestamp);
}, [messages]);

// 缓存回调函数
const handleSend = useCallback((content: string) => {
  sendMessage(content);
}, [sendMessage]);
```

### 3. 代码分割

```typescript
// 懒加载组件
const ChatView = React.lazy(() => import('./components/chat/ChatView'));

// 使用 Suspense
<Suspense fallback={<Loading />}>
  <ChatView />
</Suspense>
```

## 错误处理

### Error Boundary

```typescript
class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false };
  
  static getDerivedStateFromError(error: Error) {
    return { hasError: true };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}
```

### 异步错误处理

```typescript
const fetchData = async () => {
  try {
    setLoading(true);
    const data = await api.getData();
    setData(data);
  } catch (error) {
    setError(error as Error);
    toast.error('Failed to fetch data');
  } finally {
    setLoading(false);
  }
};
```

## 测试策略

### 单元测试

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });
  
  it('calls onClick when clicked', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### 集成测试

```typescript
describe('ChatView', () => {
  it('sends message when form is submitted', async () => {
    render(<ChatView roomId="123" />);
    
    const input = screen.getByPlaceholderText('Type a message');
    const button = screen.getByText('Send');
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });
  });
});
```

## 代码风格

### 命名规范

- **组件**：PascalCase（`ChatView`, `MessageList`）
- **函数**：camelCase（`sendMessage`, `handleClick`）
- **常量**：UPPER_SNAKE_CASE（`API_BASE_URL`）
- **类型/接口**：PascalCase（`User`, `MessageProps`）

### 文件组织

```
components/
├── chat/
│   ├── ChatView.tsx
│   ├── ChatView.test.tsx
│   ├── MessageList.tsx
│   ├── MessageList.test.tsx
│   └── index.ts
└── common/
    ├── Button.tsx
    ├── Button.test.tsx
    └── index.ts
```

## 常见问题

### 问题 1：组件过大

**症状**：单个组件超过 200 行

**解决方案**：
1. 提取子组件
2. 提取 Custom Hooks
3. 提取工具函数

### 问题 2：Props drilling

**症状**：Props 层层传递

**解决方案**：
1. 使用 Context API
2. 使用状态管理库（Zustand）
3. 组件组合模式

### 问题 3：性能问题

**症状**：组件频繁重渲染

**解决方案**：
1. 使用 React.memo
2. 使用 useMemo/useCallback
3. 优化状态结构

---

**版本**: v1.0.0  
**最后更新**: 2026-01-10
