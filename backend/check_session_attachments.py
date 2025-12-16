"""检查会话中附件的 URL 状态，并修复空 URL 的附件"""
import psycopg2
import json

conn = psycopg2.connect(
    host="192.168.50.115",
    port=5432,
    database="gemini-ai",
    user="ai",
    password="Z6LwNUH481dnjAmp2kMRPmg8xj8CtE"
)

cur = conn.cursor()

# 先查询最近的上传任务
print("最近的上传任务:")
print("=" * 100)
cur.execute("""
    SELECT id, session_id, message_id, attachment_id, status, target_url, error_message, created_at
    FROM upload_tasks
    ORDER BY created_at DESC
    LIMIT 20
""")
for row in cur.fetchall():
    task_id, session_id, message_id, attachment_id, status, target_url, error_message, created_at = row
    print(f"任务: {task_id[:8]}...")
    print(f"  会话: {session_id[:8] if session_id else 'None'}..., 消息: {message_id[:8] if message_id else 'None'}..., 附件: {attachment_id[:8] if attachment_id else 'None'}...")
    print(f"  状态: {status}, URL: {target_url[:50] if target_url else 'None'}...")
    if error_message:
        print(f"  错误: {error_message}")
    print()

print("\n" + "=" * 100)
print("最近的会话附件状态:")
print("=" * 100)

# 查询最近的会话
cur.execute("""
    SELECT id, title, messages
    FROM chat_sessions
    ORDER BY created_at DESC
    LIMIT 5
""")

print("最近的会话附件状态:")
print("=" * 100)
for row in cur.fetchall():
    session_id, title, messages = row
    print(f"\n会话: {title} ({session_id[:8]}...)")
    print("-" * 80)
    
    if messages:
        for msg in messages:
            msg_id = msg.get('id', '')[:8]
            role = msg.get('role', '')
            mode = msg.get('mode', '')
            attachments = msg.get('attachments', [])
            
            if attachments:
                print(f"  消息 {msg_id}... ({role}, {mode}):")
                for att in attachments:
                    att_id = att.get('id', '')[:8]
                    url = att.get('url', '')
                    status = att.get('uploadStatus', '')
                    name = att.get('name', '')
                    
                    url_display = url[:60] + '...' if url and len(url) > 60 else url or '(空)'
                    print(f"    - {name}: {url_display}")
                    print(f"      ID: {att_id}..., Status: {status}")

conn.close()


conn.close()
