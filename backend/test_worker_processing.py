"""
测试 Worker 池是否能处理任务
直接向 Redis 队列手动添加任务，观察 Worker 是否能处理

使用方法：
    python backend/test_worker_processing.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import uuid

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from backend.app.services.redis_queue_service import RedisQueueService
from sqlalchemy import text

async def test_worker_processing():
    """测试 Worker 池处理任务的完整流程"""
    print("=" * 80)
    print("Worker 池处理测试")
    print("=" * 80)

    redis_queue = RedisQueueService()

    try:
        # 1. 连接 Redis
        print("\n[1] 连接 Redis...")
        await redis_queue.connect()
        print("  ✅ Redis 连接成功")

        # 2. 查看初始状态
        print("\n[2] 初始状态:")
        print("-" * 80)
        high_len = await redis_queue._redis.llen(redis_queue.QUEUE_HIGH)
        normal_len = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)
        low_len = await redis_queue._redis.llen(redis_queue.QUEUE_LOW)
        print(f"  高优先级队列: {high_len} 个任务")
        print(f"  普通优先级队列: {normal_len} 个任务")
        print(f"  低优先级队列: {low_len} 个任务")

        # 3. 在数据库中创建测试任务
        print("\n[3] 创建测试任务...")
        task_id = str(uuid.uuid4())
        test_filename = f"test-worker-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        created_timestamp = int(datetime.now().timestamp() * 1000)

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO upload_tasks
                (id, filename, status, priority, retry_count, session_id, message_id, attachment_id, created_at)
                VALUES
                (:id, :filename, 'pending', 'normal', 0, :session_id, :message_id, :attachment_id, :created_at)
            """), {
                'id': task_id,
                'filename': test_filename,
                'session_id': str(uuid.uuid4()),
                'message_id': str(uuid.uuid4()),
                'attachment_id': str(uuid.uuid4()),
                'created_at': created_timestamp
            })

        print(f"  ✅ 任务已创建: {task_id[:8]}...")
        print(f"  文件名: {test_filename}")

        # 4. 手动将任务 ID 入队到 Redis
        print("\n[4] 手动入队到 Redis...")
        await redis_queue._redis.lpush(redis_queue.QUEUE_NORMAL, task_id)
        print(f"  ✅ 任务已入队")

        # 5. 验证队列长度
        normal_len_after = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)
        print(f"  普通队列长度: {normal_len} → {normal_len_after}")

        # 6. 监控 30 秒，观察任务是否被处理
        print("\n[5] 监控任务处理 (30 秒)...")
        print("-" * 80)

        for i in range(30):
            await asyncio.sleep(1)

            # 检查 Redis 队列
            queue_len = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)

            # 检查数据库状态
            with engine.begin() as conn:
                result = conn.execute(text("""
                    SELECT status, target_url, error_message
                    FROM upload_tasks
                    WHERE id = :id
                """), {'id': task_id})
                row = result.fetchone()
                status = row[0] if row else None
                target_url = row[1] if row else None
                error_msg = row[2] if row else None

            # 打印状态
            print(f"  [{i+1}秒] 队列: {queue_len} | 状态: {status}", end="")
            if target_url:
                print(f" | URL: {target_url[:50]}...")
            elif error_msg:
                print(f" | 错误: {error_msg[:50]}...")
            else:
                print()

            # 如果任务完成或失败，提前退出
            if status in ['completed', 'failed']:
                print(f"\n  ✅ 任务已 {status}")
                break

        # 7. 最终状态
        print("\n[6] 最终状态:")
        print("-" * 80)

        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT
                    status,
                    target_url,
                    error_message,
                    retry_count,
                    created_at,
                    completed_at
                FROM upload_tasks
                WHERE id = :id
            """), {'id': task_id})
            row = result.fetchone()

            if row:
                print(f"  状态: {row[0]}")
                print(f"  目标URL: {row[1] or 'NULL'}")
                print(f"  错误: {row[2] or 'NULL'}")
                print(f"  重试次数: {row[3]}")
                print(f"  创建时间: {row[4]}")
                print(f"  完成时间: {row[5] or 'NULL'}")

        queue_len_final = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)
        print(f"\n  最终队列长度: {queue_len_final}")

        # 8. 分析结果
        print("\n[7] 分析结果:")
        print("-" * 80)

        if row[0] == 'completed':
            print("  ✅ 成功！Worker 池正常处理了任务")
        elif row[0] == 'failed':
            print("  ⚠️  任务被处理但失败了")
            print(f"  失败原因: {row[2]}")
        elif row[0] == 'uploading':
            print("  ⚠️  任务正在处理中（可能处理时间过长）")
        elif row[0] == 'pending' and queue_len_final < normal_len_after:
            print("  ❌ 任务从队列中消失但状态仍是 pending")
            print("  可能原因: Worker 取出任务但未处理或处理过程中崩溃")
        elif row[0] == 'pending' and queue_len_final == normal_len_after:
            print("  ❌ 任务在队列中但未被处理")
            print("  可能原因: Worker 池未运行或 Worker 循环被阻塞")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await redis_queue.disconnect()
        print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_worker_processing())
