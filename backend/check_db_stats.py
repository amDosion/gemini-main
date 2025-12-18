"""检查 upload_tasks 表字段统计"""
import psycopg2

conn = psycopg2.connect(
    host='192.168.50.115',
    port=5432,
    database='gemini-ai',
    user='ai',
    password='Z6LwNUH481dnjAmp2kMRPmg8xj8CtE'
)
cur = conn.cursor()

# 统计 NULL 字段
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN session_id IS NULL THEN 1 ELSE 0 END) as null_session,
        SUM(CASE WHEN message_id IS NULL THEN 1 ELSE 0 END) as null_message,
        SUM(CASE WHEN attachment_id IS NULL THEN 1 ELSE 0 END) as null_attachment,
        SUM(CASE WHEN source_file_path IS NULL THEN 1 ELSE 0 END) as null_source_path,
        SUM(CASE WHEN storage_id IS NULL THEN 1 ELSE 0 END) as null_storage,
        SUM(CASE WHEN source_file_path LIKE 'C:\\%%' OR source_file_path LIKE 'D:\\%%' OR source_file_path LIKE '/tmp%%' THEN 1 ELSE 0 END) as absolute_path
    FROM upload_tasks
""")
r = cur.fetchone()
print("=" * 60)
print("upload_tasks 表字段统计")
print("=" * 60)
print(f"总记录数: {r[0]}")
print(f"session_id 为 NULL: {r[1]}")
print(f"message_id 为 NULL: {r[2]}")
print(f"attachment_id 为 NULL: {r[3]}")
print(f"source_file_path 为 NULL: {r[4]}")
print(f"storage_id 为 NULL: {r[5]}")
print(f"source_file_path 是绝对路径: {r[6]}")
print("-" * 60)

# 查看所有 source_file_path 的示例
cur.execute("""
    SELECT id, source_file_path, created_at 
    FROM upload_tasks 
    ORDER BY created_at DESC
    LIMIT 5
""")
rows = cur.fetchall()
print("\nsource_file_path 示例:")
for row in rows:
    print(f"  ID: {row[0][:8]}...")
    print(f"  Path: {row[1]}")
    is_abs = row[1] and (row[1].startswith('C:') or row[1].startswith('D:') or row[1].startswith('/'))
    print(f"  是绝对路径: {is_abs}")
    print()

# 检查最早和最新的记录
cur.execute("""
    SELECT id, source_file_path, created_at,
           to_timestamp(created_at/1000) as created_time
    FROM upload_tasks 
    ORDER BY created_at ASC
    LIMIT 3
""")
print("最早的3条记录:")
for row in cur.fetchall():
    print(f"  ID: {row[0][:8]}...")
    print(f"  Path: {row[1][:60] if row[1] else 'NULL'}...")
    print(f"  Time: {row[3]}")
    print()

cur.execute("""
    SELECT id, source_file_path, created_at,
           to_timestamp(created_at/1000) as created_time
    FROM upload_tasks 
    ORDER BY created_at DESC
    LIMIT 3
""")
print("最新的3条记录:")
for row in cur.fetchall():
    print(f"  ID: {row[0][:8]}...")
    print(f"  Path: {row[1][:60] if row[1] else 'NULL'}...")
    print(f"  Time: {row[3]}")
    print()

conn.close()
