"""
初始化数据库并创建测试用户
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import Base, engine, SessionLocal
from app.models import db_models  # 导入所有模型
from app.core.password import hash_password
from app.models.db_models import User, UserSettings, generate_user_id

# 1. 创建所有表
print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")

# 2. 创建测试用户
db = SessionLocal()
try:
    # 检查用户是否已存在
    test_email = "xcgrmini@example.com"
    existing_user = db.query(User).filter(User.email == test_email).first()

    if existing_user:
        print(f"\nUser {test_email} already exists!")
        print(f"  ID: {existing_user.id}")
        print(f"  Status: {existing_user.status}")
    else:
        # 创建新用户
        user_id = generate_user_id()
        new_user = User(
            id=user_id,
            email=test_email,
            password_hash=hash_password("rRMRbChRoAWt&@5Rs!rYNGO8dg42gk"),
            name="Test User",
            status="active"
        )
        db.add(new_user)

        # 创建用户设置
        user_settings = UserSettings(
            user_id=user_id,
            active_profile_id=None  # 初始未配置
        )
        db.add(user_settings)

        db.commit()
        print(f"\nUser created successfully!")
        print(f"  Email: {test_email}")
        print(f"  Password: rRMRbChRoAWt&@5Rs!rYNGO8dg42gk")
        print(f"  ID: {user_id}")
        print(f"  Status: active")

    print("\nDatabase initialization complete!")
    print("You can now log in with the test account.")

except Exception as e:
    print(f"Error: {e}")
    db.rollback()
    import traceback
    traceback.print_exc()
finally:
    db.close()
