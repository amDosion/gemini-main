# 数据库迁移说明

## 新增表

以下表需要在数据库中创建：

1. `agent_memory_banks` - Memory Bank 实例
2. `agent_memories` - 记忆数据
3. `agent_memory_sessions` - Memory Bank 会话
4. `agent_code_sandboxes` - 代码执行沙箱
5. `agent_artifacts` - 代码执行 Artifact
6. `agent_registry` - 智能体注册表
7. `agent_cards` - Agent Card 定义
8. `a2a_tasks` - A2A 协议任务
9. `a2a_events` - A2A 事件队列
10. `adk_sessions` - ADK 会话

## 迁移步骤

如果使用 Alembic：

1. 生成迁移脚本：
   ```bash
   alembic revision --autogenerate -m "Add Agent Engine tables"
   ```

2. 检查生成的迁移脚本

3. 应用迁移：
   ```bash
   alembic upgrade head
   ```

## 手动创建表（如果不用 Alembic）

可以直接使用 SQLAlchemy 创建表：

```python
from app.core.database import Base, engine
from app.models.db_models import (
    AgentMemoryBank, AgentMemory, AgentMemorySession,
    AgentCodeSandbox, AgentArtifact,
    AgentRegistry, AgentCard,
    A2ATask, A2AEvent,
    ADKSession
)

# 创建所有表
Base.metadata.create_all(bind=engine)
```
