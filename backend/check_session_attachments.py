"""检查 chat_sessions 表中的附件 URL"""
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

# 查询最近的会话
cur.execute("""
    SELECT id, title, messages
    FROM chat_sessions
    WHERE mode = 'image-edit'
    ORDER BY created_at DESC
    LIMIT 5
""")

print("最近的图片编辑会话:")
print("=" * 100)
for row in cur.fetchall():
    session_id, title, messages = row
    print(f"\n会话ID: {session_id}")
    print(f"标题: {title}")
    print("-" * 80)
    
    if messages:
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:50]
            attachments = msg.get('attachments', [])
            
            print(f"  [{role}] {content}...")
            for att in attachments:
                url = att.get('url', '')
                upload_status = att.get('uploadStatus', 'unknown')
                att_id = att.get('id', 'unknown')[:8]
                
                # 判断 URL 类型和长度
                if url == '':
                    url_type = "❌ 空字符串"
                    url_len = 0
                elif url is None:
                    url_type = "❌ None"
                    url_len = 0
                elif url.startswith('blob:'):
                    url_type = "⚠️ Blob URL"
                    url_len = len(url)
                elif url.startswith('data:'):
                    url_type = "⚠️ Base64"
                    url_len = len(url)
                elif url.startswith('http'):
                    url_type = "✅ 永久URL"
                    url_len = len(url)
                else:
                    url_type = "❓ 未知"
                    url_len = len(url) if url else 0
                
                print(f"    附件 {att_id}: {url_type} (长度: {url_len}) | 状态: {upload_status}")
                if url and url.startswith('http'):
                    print(f"      URL: {url[:60]}...")

print("\n" + "=" * 100)
conn.close()
