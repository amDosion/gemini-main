"""检查 upload_tasks 表中的任务状态"""
import psycopg2

conn = psycopg2.connect(
    host="192.168.50.115",
    port=5432,
    database="gemini-ai",
    user="ai",
    password="Z6LwNUH481dnjAmp2kMRPmg8xj8CtE"
)

cur = conn.cursor()

# 查询最近的上传任务
cur.execute("""
    SELECT id, session_id, message_id, attachment_id, status, target_url, error_message, created_at
    FROM upload_tasks
    ORDER BY created_at DESC
    LIMIT 20
""")

print("最近的上传任务:")
print("-" * 100)
for row in cur.fetchall():
    task_id, session_id, message_id, attachment_id, status, target_url, error_message, created_at = row
    print(f"任务ID: {task_id[:8]}...")
    print(f"  会话ID: {session_id[:8] if session_id else 'None'}...")
    print(f"  消息ID: {message_id[:8] if message_id else 'None'}...")
    print(f"  附件ID: {attachment_id[:8] if attachment_id else 'None'}...")
    print(f"  状态: {status}")
    print(f"  目标URL: {target_url[:50] if target_url else 'None'}...")
    print(f"  错误: {error_message}")
    print("-" * 100)

conn.close()
