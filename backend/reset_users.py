"""
重置用户数据：删除所有注册账户及关联数据，重新创建新账户
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.core.password import hash_password
from app.models.db_models import (
    User, UserSettings, RefreshToken, IPLoginHistory, IPBlocklist,
    LoginAttempt,
    # 用户关联的业务数据
    ConfigProfile, ChatSession, MessageIndex,
    MessagesChat, MessagesImageGen, MessagesVideoGen, MessagesGeneric,
    MessagesImageChatEdit, MessagesImageMaskEdit, MessagesImageInpainting,
    MessagesImageBackgroundEdit, MessagesImageRecontext,
    MessageAttachment, GoogleChatSession, Persona, StorageConfig,
    ActiveStorage, UploadTask, VertexAIConfig,
    WorkflowTemplate, AgentMemoryBank, AgentMemory, AgentMemorySession,
    AgentCodeSandbox, AgentArtifact, AgentRegistry, AgentCard,
    ADKSession, A2ATask, A2AEvent,
    generate_user_id,
)

db = SessionLocal()
try:
    # ========== 1. 删除所有用户关联数据 ==========
    tables_to_clear = [
        # 认证相关
        RefreshToken, IPLoginHistory, IPBlocklist,
        LoginAttempt,
        # 消息和会话
        MessageAttachment, MessagesChat, MessagesImageGen, MessagesVideoGen,
        MessagesGeneric, MessagesImageChatEdit, MessagesImageMaskEdit,
        MessagesImageInpainting, MessagesImageBackgroundEdit, MessagesImageRecontext,
        MessageIndex, GoogleChatSession, ChatSession,
        # 配置
        ConfigProfile, UserSettings, Persona, StorageConfig, ActiveStorage,
        UploadTask, VertexAIConfig,
        # Agent 相关
        A2AEvent, A2ATask, AgentArtifact, AgentCodeSandbox,
        AgentMemory, AgentMemorySession, AgentMemoryBank,
        AgentRegistry, AgentCard, ADKSession, WorkflowTemplate,
    ]

    print("正在清除所有用户数据...")
    for model in tables_to_clear:
        count = db.query(model).delete()
        if count > 0:
            print(f"  已删除 {model.__tablename__}: {count} 条记录")

    # 删除用户表
    user_count = db.query(User).delete()
    print(f"  已删除 users: {user_count} 条记录")

    db.commit()
    print("✅ 所有用户数据已清除\n")

    # ========== 2. 创建新账户 ==========
    user_id = generate_user_id()
    email = "admin@example.com"
    password = "Admin@2026"

    new_user = User(
        id=user_id,
        email=email,
        password_hash=hash_password(password),
        name="Admin",
        status="active"
    )
    db.add(new_user)

    user_settings = UserSettings(
        user_id=user_id,
        active_profile_id=None
    )
    db.add(user_settings)

    db.commit()

    print("✅ 新账户创建成功")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print(f"  User ID:  {user_id}")
    print(f"  Status:   active")

except Exception as e:
    db.rollback()
    print(f"❌ 操作失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
