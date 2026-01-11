"""验证 imagen_configs 表字段是否存在"""

from backend.app.core.database import engine
from sqlalchemy import text

def verify_fields():
    """验证字段是否存在"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'imagen_configs' 
            AND column_name IN ('hidden_models', 'saved_models')
        """))
        
        rows = result.fetchall()
        print("字段列表:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
        
        if len(rows) == 2:
            print("\n✅ 所有字段都已存在！")
        else:
            print(f"\n⚠️  只找到 {len(rows)} 个字段，预期 2 个")

if __name__ == "__main__":
    verify_fields()
