---
name: database
description: |
  数据库模型和操作开发。适用于：
  - 创建新的数据库模型
  - 修改现有模型结构
  - 添加数据库迁移
  - 实现数据查询和操作
---

# 数据库开发技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 创建新的数据库模型
- 修改现有模型结构
- 添加数据库迁移
- 实现数据查询和操作

## 项目结构

```
backend/app/
├── core/
│   └── database.py       # 数据库连接和会话管理
├── models/
│   └── db_models.py      # 所有数据库模型
└── services/
    └── common/           # 数据访问服务
```

## 数据库配置

### 连接配置
```python
# backend/app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./database.db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 模型模板

### 基础模型

```python
# backend/app/models/db_models.py
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class BaseModel:
    """模型基类"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class XxxModel(Base, BaseModel):
    """示例模型"""
    __tablename__ = "xxx"

    # 基础字段
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # JSON 字段（如需要）
    metadata = Column(Text)  # 存储 JSON 字符串

    # 关系
    user = relationship("User", back_populates="xxx_items")

    # 索引
    __table_args__ = (
        Index("idx_xxx_user_name", "user_id", "name"),
        Index("idx_xxx_active", "is_active"),
    )

    def to_dict(self) -> dict:
        """转换为字典（camelCase 格式）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "description": self.description,
            "isActive": self.is_active,
            "sortOrder": self.sort_order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def from_dict(cls, data: dict, user_id: str) -> "XxxModel":
        """从字典创建（支持 camelCase）"""
        return cls(
            user_id=user_id,
            name=data.get("name"),
            description=data.get("description"),
            is_active=data.get("isActive", True),
            sort_order=data.get("sortOrder", 0)
        )
```

### 关联模型

```python
class Parent(Base, BaseModel):
    __tablename__ = "parents"

    name = Column(String(255), nullable=False)

    # 一对多关系
    children = relationship("Child", back_populates="parent", cascade="all, delete-orphan")


class Child(Base, BaseModel):
    __tablename__ = "children"

    parent_id = Column(String(36), ForeignKey("parents.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # 多对一关系
    parent = relationship("Parent", back_populates="children")
```

### 多对多关系

```python
# 关联表
tag_item_association = Table(
    "tag_item",
    Base.metadata,
    Column("tag_id", String(36), ForeignKey("tags.id"), primary_key=True),
    Column("item_id", String(36), ForeignKey("items.id"), primary_key=True)
)


class Tag(Base, BaseModel):
    __tablename__ = "tags"
    name = Column(String(100), unique=True, nullable=False)
    items = relationship("Item", secondary=tag_item_association, back_populates="tags")


class Item(Base, BaseModel):
    __tablename__ = "items"
    name = Column(String(255), nullable=False)
    tags = relationship("Tag", secondary=tag_item_association, back_populates="items")
```

## 查询操作

### 基础查询

```python
from sqlalchemy.orm import Session
from .db_models import XxxModel

# 获取单个（必须加 user_id）
def get_by_id(db: Session, item_id: str, user_id: str) -> XxxModel | None:
    return db.query(XxxModel).filter(
        XxxModel.id == item_id,
        XxxModel.user_id == user_id
    ).first()

# 获取列表
def get_all(db: Session, user_id: str) -> list[XxxModel]:
    return db.query(XxxModel).filter(
        XxxModel.user_id == user_id
    ).order_by(XxxModel.created_at.desc()).all()

# 分页查询
def get_paginated(
    db: Session,
    user_id: str,
    offset: int = 0,
    limit: int = 20
) -> list[XxxModel]:
    return db.query(XxxModel).filter(
        XxxModel.user_id == user_id
    ).offset(offset).limit(limit).all()

# 条件查询
def get_by_name(db: Session, user_id: str, name: str) -> list[XxxModel]:
    return db.query(XxxModel).filter(
        XxxModel.user_id == user_id,
        XxxModel.name.ilike(f"%{name}%")
    ).all()
```

### 创建和更新

```python
# 创建
def create(db: Session, user_id: str, data: dict) -> XxxModel:
    item = XxxModel.from_dict(data, user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

# 更新
def update(db: Session, item_id: str, user_id: str, data: dict) -> XxxModel | None:
    item = get_by_id(db, item_id, user_id)
    if not item:
        return None

    for key, value in data.items():
        # 转换 camelCase 到 snake_case
        snake_key = camel_to_snake(key)
        if hasattr(item, snake_key):
            setattr(item, snake_key, value)

    db.commit()
    db.refresh(item)
    return item

# 删除
def delete(db: Session, item_id: str, user_id: str) -> bool:
    item = get_by_id(db, item_id, user_id)
    if not item:
        return False

    db.delete(item)
    db.commit()
    return True
```

### 批量操作

```python
# 批量创建
def bulk_create(db: Session, user_id: str, items: list[dict]) -> list[XxxModel]:
    models = [XxxModel.from_dict(item, user_id) for item in items]
    db.add_all(models)
    db.commit()
    for model in models:
        db.refresh(model)
    return models

# 批量更新
def bulk_update(db: Session, user_id: str, updates: list[dict]) -> int:
    count = 0
    for update in updates:
        item_id = update.pop("id", None)
        if item_id and update(db, item_id, user_id, update):
            count += 1
    return count

# 批量删除
def bulk_delete(db: Session, user_id: str, ids: list[str]) -> int:
    result = db.query(XxxModel).filter(
        XxxModel.id.in_(ids),
        XxxModel.user_id == user_id
    ).delete(synchronize_session=False)
    db.commit()
    return result
```

### 高级查询

```python
from sqlalchemy import select, and_, or_, func

# 使用 select 语句
def get_with_select(db: Session, user_id: str) -> list[XxxModel]:
    stmt = select(XxxModel).where(
        XxxModel.user_id == user_id,
        XxxModel.is_active == True
    ).order_by(XxxModel.sort_order)

    return db.execute(stmt).scalars().all()

# 聚合查询
def get_count(db: Session, user_id: str) -> int:
    return db.query(func.count(XxxModel.id)).filter(
        XxxModel.user_id == user_id
    ).scalar()

# 分组查询
def get_grouped_count(db: Session, user_id: str) -> list[tuple]:
    return db.query(
        XxxModel.category,
        func.count(XxxModel.id)
    ).filter(
        XxxModel.user_id == user_id
    ).group_by(XxxModel.category).all()

# JOIN 查询
def get_with_relations(db: Session, user_id: str) -> list[XxxModel]:
    return db.query(XxxModel).options(
        joinedload(XxxModel.children)
    ).filter(
        XxxModel.user_id == user_id
    ).all()
```

## 事务处理

```python
from contextlib import contextmanager

@contextmanager
def transaction(db: Session):
    """事务上下文管理器"""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise

# 使用
with transaction(db):
    item1 = XxxModel(...)
    db.add(item1)
    item2 = YyyModel(...)
    db.add(item2)
    # 自动提交或回滚
```

## 迁移（手动）

```python
# 创建表
def create_tables():
    Base.metadata.create_all(bind=engine)

# 添加列（如果数据库支持）
def add_column():
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE xxx ADD COLUMN new_field VARCHAR(255)"))
        conn.commit()
```

## 前端 IndexedDB

```typescript
// frontend/services/db.ts
import Dexie, { Table } from 'dexie';

interface XxxItem {
  id: string;
  userId: string;
  name: string;
  createdAt: number;
}

class AppDatabase extends Dexie {
  xxxItems!: Table<XxxItem>;

  constructor() {
    super('app-database');
    this.version(1).stores({
      xxxItems: 'id, userId, name, createdAt'
    });
  }
}

export const db = new AppDatabase();

// 使用
await db.xxxItems.add(item);
const items = await db.xxxItems.where('userId').equals(userId).toArray();
await db.xxxItems.delete(id);
```

## 开发步骤

1. **设计模型**：确定字段、关系、索引
2. **创建模型类**：在 db_models.py 中添加
3. **添加 to_dict/from_dict**：转换方法
4. **实现查询函数**：基础 CRUD
5. **创建表**：运行迁移或 create_all
6. **测试**：编写单元测试

## 注意事项

- 所有查询必须加 `user_id` 过滤（数据隔离）
- 使用 `to_dict()` 返回 camelCase 格式
- 敏感字段（如 api_key）不返回明文
- 使用事务处理多步操作
- 添加必要的索引优化查询
- 使用 `relationship` 定义关系
