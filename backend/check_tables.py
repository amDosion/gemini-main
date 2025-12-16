"""检查数据库中的表"""
import psycopg2
import sys

conn = psycopg2.connect(
    host="192.168.50.115",
    port=5432,
    database="gemini-ai",
    user="ai",
    password="Z6LwNUH481dnjAmp2kMRPmg8xj8CtE"
)

cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public'
""")
tables = cur.fetchall()
table_names = [t[0] for t in tables]
print(f"所有表: {table_names}", flush=True)
sys.stdout.flush()

conn.close()
