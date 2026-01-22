# 编写测试

为指定的代码编写测试用例。

## 测试框架

- **前端**: Vitest + @testing-library/react
- **后端**: pytest + pytest-asyncio

## 前端测试模板

### 组件测试

```typescript
// __tests__/[ComponentName].test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { [ComponentName] } from '../components/[ComponentName]';

// Mock 依赖
vi.mock('../hooks/useXxx', () => ({
  useXxx: () => ({
    data: mockData,
    loading: false,
    error: null
  })
}));

describe('[ComponentName]', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly', () => {
    render(<[ComponentName] prop1="value" />);
    expect(screen.getByText('expected text')).toBeInTheDocument();
  });

  it('handles user interaction', async () => {
    const onAction = vi.fn();
    render(<[ComponentName] onAction={onAction} />);

    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith(expectedValue);
    });
  });

  it('shows loading state', () => {
    render(<[ComponentName] loading={true} />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('handles error state', () => {
    render(<[ComponentName] error={new Error('Test error')} />);
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
```

### Hook 测试

```typescript
// __tests__/use[HookName].test.ts
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { use[HookName] } from '../hooks/use[HookName]';

// Mock API
vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn()
  }
}));

describe('use[HookName]', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial state', () => {
    const { result } = renderHook(() => use[HookName]());

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('fetches data on execute', async () => {
    const mockData = { id: '1', name: 'test' };
    apiClient.get.mockResolvedValue(mockData);

    const { result } = renderHook(() => use[HookName]());

    await act(async () => {
      await result.current.execute();
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.loading).toBe(false);
  });

  it('handles errors', async () => {
    apiClient.get.mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => use[HookName]());

    await act(async () => {
      await result.current.execute();
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('API Error');
  });
});
```

## 后端测试模板

### 单元测试

```python
# tests/test_[service_name].py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.[module].[service] import [Service]


class Test[Service]:
    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        return [Service](
            api_key="test-key",
            user_id="test-user",
            db=mock_db
        )

    @pytest.mark.asyncio
    async def test_method_success(self, service):
        """测试正常情况"""
        result = await service.method(params)

        assert result is not None
        assert "expected_key" in result

    @pytest.mark.asyncio
    async def test_method_with_mock(self, service):
        """测试使用 Mock"""
        with patch.object(service, 'client') as mock_client:
            mock_client.call.return_value = {"content": "test"}

            result = await service.method(params)

            assert result["content"] == "test"
            mock_client.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_method_error_handling(self, service):
        """测试错误处理"""
        with patch.object(service, 'client', side_effect=Exception("API Error")):
            with pytest.raises(Exception) as exc_info:
                await service.method(params)

            assert "API Error" in str(exc_info.value)
```

### 集成测试

```python
# tests/test_routes_[module].py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app


class TestRoutes[Module]:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        # 创建测试 token
        return {"Authorization": "Bearer test-token"}

    def test_get_list(self, client, auth_headers):
        """测试获取列表"""
        response = client.get("/api/[endpoint]", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_item(self, client, auth_headers):
        """测试创建"""
        response = client.post(
            "/api/[endpoint]",
            json={"name": "test", "value": "data"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test"

    def test_unauthorized_access(self, client):
        """测试未授权访问"""
        response = client.get("/api/[endpoint]")

        assert response.status_code == 401

    def test_not_found(self, client, auth_headers):
        """测试资源不存在"""
        response = client.get(
            "/api/[endpoint]/nonexistent-id",
            headers=auth_headers
        )

        assert response.status_code == 404
```

## 运行测试

```bash
# 前端
npm run test                    # 运行所有测试
npm run test -- [file.test.ts]  # 运行特定文件
npm run test:coverage           # 覆盖率报告

# 后端
pytest                          # 运行所有测试
pytest tests/test_xxx.py        # 运行特定文件
pytest --cov=app               # 覆盖率报告
pytest -v                       # 详细输出
```

## 使用示例

```
/test frontend/hooks/useChat.ts
```

```
/test backend/app/services/gemini/chat_handler.py
```

```
/test 为 MessageItem 组件编写完整的测试用例
```
