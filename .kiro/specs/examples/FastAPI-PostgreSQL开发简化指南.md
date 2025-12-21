# FastAPI + PostgreSQL 后端开发简化指南

> 提升 FastAPI + PostgreSQL 开发效率的工具、库和最佳实践

## 目录

- [核心依赖安装](#核心依赖安装)
- [1. FastCRUD - 零代码 CRUD](#1-fastcrud---零代码-crud)
- [2. SQLModel - 模型统一方案](#2-sqlmodel---模型统一方案)
- [3. Alembic - 数据库迁移](#3-alembic---数据库迁移)
- [4. FastAPI-Admin - 管理后台](#4-fastapi-admin---管理后台)
- [5. 项目脚手架生成器](#5-项目脚手架生成器)
- [6. 查询构建器和性能优化](#6-查询构建器和性能优化)
- [7. 完整项目架构示例](#7-完整项目架构示例)
- [8. 进阶 ORM 方案](#8-进阶-orm-方案)
- [推荐组合方案](#推荐组合方案)

---

## 核心依赖安装

### 基础依赖
```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary alembic pydantic
```

### 异步驱动（推荐）
```bash
pip install sqlalchemy[asyncio] asyncpg
```

### 完整开发环境
```bash
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic pydantic-settings python-dotenv
```

---

## 1. FastCRUD - 零代码 CRUD

### 安装
```bash
pip install fastcrud
```

### 基础用法

```python
from fastapi import FastAPI, Depends
from fastcrud import FastCRUD, crud_router
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

# 创建 FastAPI 应用
app = FastAPI()

# 自动生成 CRUD
user_crud = FastCRUD(User)

# 自动生成所有端点
app.include_router(
    crud_router(
        session=get_db,
        model=User,
        crud=user_crud,
        prefix="/users",
        tags=["users"]
    )
)
```

### 自动生成的端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/users` | 列表查询（支持分页、过滤、排序） |
| GET | `/users/{id}` | 单个查询 |
| POST | `/users` | 创建 |
| PUT | `/users/{id}` | 完整更新 |
| PATCH | `/users/{id}` | 部分更新 |
| DELETE | `/users/{id}` | 删除 |

### 高级查询

```python
# GET /users?skip=0&limit=10&name__like=%john%&age__gte=18
# 自动支持：
# - 分页：skip, limit
# - 过滤：field__operator=value
# - 排序：order_by=field
```

---

## 2. SQLModel - 模型统一方案

### 安装
```bash
pip install sqlmodel
```

### 核心特性

SQLModel = **Pydantic** + **SQLAlchemy**

一个类同时用于：
- 数据库表定义（ORM）
- 请求验证（Pydantic）
- 响应序列化（Pydantic）

### 基础示例

```python
from sqlmodel import Field, SQLModel, create_engine, Session, select
from typing import Optional

# 单一模型定义
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(unique=True)
    age: Optional[int] = None

# 直接用作请求/响应模型
@app.post("/users", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@app.get("/users", response_model=list[User])
def get_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users
```

### 模型继承（推荐架构）

```python
from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List

# 基础模型
class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    name: str
    age: Optional[int] = None

# 数据库表模型
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    posts: List["Post"] = Relationship(back_populates="author")

# 创建请求模型
class UserCreate(UserBase):
    password: str  # 明文密码，仅用于创建

# 更新请求模型
class UserUpdate(SQLModel):
    name: Optional[str] = None
    age: Optional[int] = None

# 公开响应模型
class UserPublic(UserBase):
    id: int

# 带关联的响应模型
class UserWithPosts(UserPublic):
    posts: List["PostPublic"] = []
```

### 关系定义

```python
class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="user.id")
    
    # 关系
    author: User = Relationship(back_populates="posts")

# 使用
@app.get("/users/{user_id}", response_model=UserWithPosts)
def get_user_with_posts(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    return user  # 自动加载关联的 posts
```

---

## 3. Alembic - 数据库迁移

### 初始化

```bash
# 安装
pip install alembic

# 初始化
alembic init alembic
```

### 配置

**alembic/env.py**
```python
from models import Base  # 导入所有模型的 Base

target_metadata = Base.metadata
```

**alembic.ini**
```ini
sqlalchemy.url = postgresql://user:password@localhost/dbname
```

### 基础命令

```bash
# 自动生成迁移文件
alembic revision --autogenerate -m "create users table"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看历史
alembic history

# 查看当前版本
alembic current
```

### 简化脚本

**scripts/db.py**
```python
import click
from alembic.config import Config
from alembic import command

@click.group()
def cli():
    """数据库管理工具"""
    pass

@cli.command()
@click.option('--message', '-m', required=True, help='迁移说明')
def migrate(message):
    """生成迁移文件"""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)
    click.echo(f"✓ 已生成迁移: {message}")

@cli.command()
def upgrade():
    """应用所有迁移"""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    click.echo("✓ 数据库已更新")

@cli.command()
def downgrade():
    """回滚一次迁移"""
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, "-1")
    click.echo("✓ 已回滚")

if __name__ == '__main__':
    cli()
```

**使用：**
```bash
python scripts/db.py migrate -m "add user table"
python scripts/db.py upgrade
```

---

## 4. FastAPI-Admin - 管理后台

### 安装
```bash
pip install fastapi-admin
```

### 配置

```python
from fastapi_admin.app import app as admin_app
from fastapi_admin.resources import Model, Field

# 定义资源
class UserResource(Model):
    label = "用户管理"
    model = User
    fields = [
        Field(name="id", label="ID", display=True),
        Field(name="name", label="姓名"),
        Field(name="email", label="邮箱"),
        Field(name="created_at", label="创建时间"),
    ]

# 挂载管理后台
app.mount("/admin", admin_app)
admin_app.register(UserResource)
```

访问 `http://localhost:8000/admin` 即可看到管理界面！

---

## 5. 项目脚手架生成器

### FastAPI-MVC

```bash
pip install fastapi-mvc
fastapi-mvc create my-project
```

生成的项目结构：
```
my-project/
├── app/
│   ├── models/          # 数据库模型
│   ├── schemas/         # Pydantic 模型
│   ├── api/
│   │   └── endpoints/   # 路由端点
│   ├── core/
│   │   ├── config.py    # 配置
│   │   └── security.py  # 认证
│   └── db/
│       └── session.py   # 数据库连接
├── alembic/             # 迁移文件
├── tests/               # 测试
├── docker-compose.yml   # Docker 配置
└── requirements.txt
```

### Cookiecutter Full-Stack

```bash
pip install cookiecutter
cookiecutter gh:tiangolo/full-stack-fastapi-postgresql
```

自动生成：
- ✅ FastAPI + SQLAlchemy
- ✅ PostgreSQL
- ✅ Alembic 迁移
- ✅ Docker 和 Docker Compose
- ✅ JWT 用户认证
- ✅ 邮件发送
- ✅ Celery 后台任务
- ✅ 完整测试框架
- ✅ CI/CD 配置

---
FastAPI + PostgreSQL + SQLAlchemy



## 6. 查询构建器和性能优化

### SQLAlchemy 2.0 风格（类型安全）

```python
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

async def get_users_by_age(
    session: AsyncSession, 
    min_age: int,
    max_age: Optional[int] = None
) -> List[User]:
    # 类型安全的查询构建
    stmt = select(User).where(User.age >= min_age)
    
    if max_age:
        stmt = stmt.where(User.age <= max_age)
    
    stmt = stmt.order_by(User.name)
    
    result = await session.execute(stmt)
    return result.scalars().all()

async def search_users(
    session: AsyncSession,
    keyword: str,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[User], int]:
    # 搜索查询
    base_stmt = select(User).where(
        or_(
            User.name.ilike(f"%{keyword}%"),
            User.email.ilike(f"%{keyword}%")
        )
    )
    
    # 获取总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = await session.scalar(count_stmt)
    
    # 分页查询
    stmt = base_stmt.offset(skip).limit(limit)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    return users, total
```

### asyncpg 直接查询（极致性能）

```python
import asyncpg
from typing import List, Dict, Optional

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=10,
            max_size=20
        )
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
    
    async def fetch_users(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM users OFFSET $1 LIMIT $2",
                skip, limit
            )
            return [dict(row) for row in rows]
    
    async def create_user(self, name: str, email: str) -> Dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *",
                name, email
            )
            return dict(row)
    
    async def execute_query(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

# 使用
db = Database("postgresql://user:pass@localhost/dbname")

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

@app.get("/users")
async def get_users(skip: int = 0, limit: int = 100):
    users = await db.fetch_users(skip, limit)
    return users
```

### 性能优化技巧

```python
# 1. 使用连接池
from sqlalchemy.pool import NullPool, QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True  # 检查连接有效性
)

# 2. 批量插入
async def bulk_create_users(session: AsyncSession, users: List[UserCreate]):
    db_users = [User(**user.model_dump()) for user in users]
    session.add_all(db_users)
    await session.commit()

# 3. 预加载关联（避免 N+1 问题）
from sqlalchemy.orm import selectinload

stmt = select(User).options(selectinload(User.posts))
result = await session.execute(stmt)
users = result.scalars().all()

# 4. 只查询需要的字段
stmt = select(User.id, User.name, User.email)
result = await session.execute(stmt)
users = result.all()
```

---

## 7. 完整项目架构示例

### 项目结构

```
app/
├── api/
│   ├── __init__.py
│   ├── deps.py              # 依赖注入
│   └── v1/
│       ├── __init__.py
│       ├── endpoints/
│       │   ├── users.py
│       │   └── posts.py
│       └── router.py
├── core/
│   ├── __init__.py
│   ├── config.py            # 配置
│   └── security.py          # 认证
├── crud/
│   ├── __init__.py
│   ├── base.py              # 基础 CRUD
│   └── user.py              # 用户 CRUD
├── db/
│   ├── __init__.py
│   ├── base.py              # Base 类
│   └── session.py           # 数据库会话
├── models/
│   ├── __init__.py
│   └── user.py              # 数据库模型
├── schemas/
│   ├── __init__.py
│   └── user.py              # Pydantic 模型
└── main.py                  # 应用入口
```

### models/user.py

```python
from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    posts: List["Post"] = Relationship(back_populates="author")
```

### schemas/user.py

```python
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('密码至少 8 个字符')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserPublic(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### crud/base.py

```python
from typing import TypeVar, Generic, Type, Optional, List, Union, Dict, Any
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        通用 CRUD 对象
        
        **参数**
        * `model`: SQLModel 模型类
        """
        self.model = model
    
    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """通过 ID 获取单条记录"""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """获取多条记录"""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType
    ) -> ModelType:
        """创建记录"""
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """更新记录"""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def delete(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        """删除记录"""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj
```

### crud/user.py

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def get_by_email(
        self, db: AsyncSession, *, email: str
    ) -> Optional[User]:
        """通过邮箱获取用户"""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self, db: AsyncSession, *, obj_in: UserCreate
    ) -> User:
        """创建用户（加密密码）"""
        db_obj = User(
            email=obj_in.email,
            name=obj_in.name,
            hashed_password=get_password_hash(obj_in.password),
            is_active=obj_in.is_active,
            is_superuser=obj_in.is_superuser
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def authenticate(
        self, db: AsyncSession, *, email: str, password: str
    ) -> Optional[User]:
        """验证用户"""
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def is_active(self, user: User) -> bool:
        """检查用户是否激活"""
        return user.is_active
    
    def is_superuser(self, user: User) -> bool:
        """检查是否超级用户"""
        return user.is_superuser

user = CRUDUser(User)
```

### db/session.py

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=True,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# 创建异步会话工厂
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        yield session
```

### api/deps.py

```python
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.user import User
from app.crud.user import user as user_crud
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库依赖"""
    async with async_session() as session:
        yield session

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """获取当前用户"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    user_id: int = payload.get("sub")
    user = await user_crud.get(db, id=user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前激活用户"""
    if not user_crud.is_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未激活"
        )
    return current_user
```

### api/v1/endpoints/users.py

```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.crud.user import user as user_crud
from app.schemas.user import UserCreate, UserUpdate, UserPublic
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[UserPublic])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户列表"""
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users

@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新用户"""
    user = await user_crud.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    user = await user_crud.create(db, obj_in=user_in)
    return user

@router.get("/{user_id}", response_model=UserPublic)
async def read_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取指定用户"""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user

@router.put("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新用户"""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    user = await user_crud.update(db, db_obj=user, obj_in=user_in)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除用户"""
    user = await user_crud.delete(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
```

### main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import init_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库"""
    await init_db()

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI"}
```

---

## 8. 进阶 ORM 方案

### Piccolo ORM

异步优先的现代 ORM

```bash
pip install piccolo[postgres]
```

**特性：**
- 🚀 异步查询
- 🔄 自动迁移
- 🎨 Admin UI
- 🔍 查询构建器

```python
from piccolo.table import Table
from piccolo.columns import Varchar, Integer, Boolean

class User(Table):
    name = Varchar()
    email = Varchar(unique=True)
    age = Integer()
    is_active = Boolean(default=True)

# 查询
users = await User.select().where(User.age > 18).run()

# 创建
user = User(name="John", email="john@example.com", age=25)
await user.save()
```

### Tortoise ORM

Django 风格的异步 ORM

```bash
pip install tortoise-orm[asyncpg]
```

```python
from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    is_active = fields.BooleanField(default=True)
    
    class Meta:
        table = "users"

# 查询
users = await User.filter(is_active=True).all()
user = await User.get(email="john@example.com")
```

---

## 推荐组合方案

### 🥇 方案 A - 最简单（推荐新手）

```
SQLModel + FastCRUD + Alembic
```

**优点：**
- 学习曲线平缓
- 代码量少
- 自动生成 CRUD

**适合：**
- 快速原型
- 小型项目
- MVP 开发

### 🥈 方案 B - 最灵活（推荐中大型项目）

```
SQLAlchemy 2.0 + Pydantic V2 + 自定义 CRUD 基类 + Alembic
```

**优点：**
- 完全控制
- 高度可定制
- 类型安全

**适合：**
- 企业级应用
- 复杂业务逻辑
- 长期维护项目

### 🥉 方案 C - 极致性能（推荐高并发场景）

```
asyncpg 直接查询 + Pydantic 验证 + 手动迁移
```

**优点：**
- 性能最佳
- 资源占用少
- 精确控制

**适合：**
- 高并发 API
- 性能敏感应用
- 数据密集型任务

---

## 开发工具推荐

### 数据库管理
- **DBeaver** - 免费多平台数据库工具
- **pgAdmin** - PostgreSQL 官方管理工具
- **DataGrip** - JetBrains 付费工具（功能强大）

### API 测试
- **HTTPie** - 命令行 HTTP 客户端
- **Postman** - 图形化 API 测试
- **FastAPI 自带文档** - `/docs` Swagger UI

### 开发环境
```bash
# VSCode 推荐插件
- Python
- Pylance
- SQLTools
- Thunder Client
- Database Client

# 代码质量
pip install ruff black mypy
```

---

## 常见问题

### 1. 如何处理数据库事务？

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def transfer_money(db: AsyncSession, from_id: int, to_id: int, amount: float):
    async with db.begin():  # 自动处理事务
        # 操作 1
        await db.execute(...)
        # 操作 2
        await db.execute(...)
        # 自动提交或回滚
```

### 2. 如何实现软删除？

```python
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deleted_at: Optional[datetime] = None
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

# 软删除
async def soft_delete(db: AsyncSession, user_id: int):
    user = await user_crud.get(db, id=user_id)
    user.deleted_at = datetime.utcnow()
    await db.commit()

# 查询时排除已删除
stmt = select(User).where(User.deleted_at.is_(None))
```

### 3. 如何优化 N+1 查询？

```python
from sqlalchemy.orm import selectinload

# 预加载关联数据
stmt = select(User).options(
    selectinload(User.posts),
    selectinload(User.comments)
)
users = await session.execute(stmt)
```

---

## 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [SQLModel 文档](https://sqlmodel.tiangolo.com/)
- [Alembic 文档](https://alembic.sqlalchemy.org/)
- [asyncpg 文档](https://magicstack.github.io/asyncpg/)

---

**最后更新：** 2025-01-08
