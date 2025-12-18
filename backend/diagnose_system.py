"""
系统诊断脚本 - 检查整个上传流程

使用方法：
    python backend/diagnose_system.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from backend.app.services.redis_queue_service import RedisQueueService
from sqlalchemy import text

async def diagnose():
    """全面诊断系统状态"""
    print("=" * 80)
    print("系统诊断 - Redis 队列 + Worker 池 + 数据库")
    print("=" * 80)

    # 1. 检查 Redis 连接
    print("\n1. Redis 连接测试:")
    print("-" * 80)
    redis_queue = RedisQueueService()
    try:
        await redis_queue.connect()
        print("  ✅ Redis 连接成功")
        
        # 检查队列长度
        high_len = await redis_queue._redis.llen(redis_queue.QUEUE_HIGH)
        normal_len = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)
        low_len = await redis_queue._redis.llen(redis_queue.QUEUE_LOW)
        dlq_len = await redis_queue._redis.llen(redis_queue.DEAD_LETTER)
        
        print(f"  - 高优先级队列: {high_len} 个任务")
        print(f"  - 普通优先级队列: {normal_len} 个任务")
        print(f"  - 低优先级队列: {low_len} 个任务")
        print(f"  - 死信队列: {dlq_len} 个任务")
        
        # 查看队列中的任务ID
        if normal_len > 0:
            print(f"\n  普通队列中的任务 ID:")
            tasks = await redis_queue._redis.lrange(redis_queue.QUEUE_NORMAL, 0, 9)
            for i, task_id in enumerate(tasks, 1):
                print(f"    {i}. {task_id}")
        
        # 查看统计信息
        stats = await redis_queue.get_stats()
        print(f"\n  队列统计:")
        print(f"    - 总入队: {stats.get('total_enqueued', 0)}")
        print(f"    - 总出队: {stats.get('total_dequeued', 0)}")
        print(f"    - 总完成: {stats.get('total_completed', 0)}")
        print(f"    - 总失败: {stats.get('total_failed', 0)}")
        
        await redis_queue.disconnect()
    except Exception as e:
        print(f"  ❌ Redis 连接失败: {e}")
        import traceback
        traceback.print_exc()
    print("-" * 80)

    # 2. 检查数据库
    print("\n2. 数据库任务状态:")
    print("-" * 80)
    try:
        with engine.begin() as conn:
            # 统计各状态的任务数量
            result = conn.execute(text("""
                SELECT status, COUNT(*) as count
                FROM upload_tasks
                GROUP BY status;
            """))
            print("  按状态统计:")
            for row in result:
                print(f"    - {row[0]}: {row[1]} 条")
            
            # 查看最近的任务详情
            result = conn.execute(text("""
                SELECT
                    id,
                    filename,
                    status,
                    priority,
                    retry_count,
                    created_at,
                    completed_at,
                    error_message
                FROM upload_tasks
                ORDER BY created_at DESC
                LIMIT 5;
            """))
            
            print("\n  最近 5 条任务:")
            rows = result.fetchall()
            for row in rows:
                print(f"\n    任务: {row[0][:8]}...")
                print(f"      文件: {row[1]}")
                print(f"      状态: {row[2]}")
                print(f"      优先级: {row[3] or 'NULL'}")
                print(f"      重试: {row[4] or 'NULL'}")
                print(f"      创建时间: {row[5]}")
                print(f"      完成时间: {row[6] or 'NULL'}")
                if row[7]:
                    print(f"      错误: {row[7]}")
    except Exception as e:
        print(f"  ❌ 数据库查询失败: {e}")
    print("-" * 80)

    # 3. 检查数据一致性
    print("\n3. 数据一致性检查:")
    print("-" * 80)
    try:
        with engine.begin() as conn:
            # 查询 pending 状态的任务
            result = conn.execute(text("""
                SELECT id FROM upload_tasks
                WHERE status = 'pending'
                ORDER BY created_at DESC;
            """))
            
            pending_tasks = [row[0] for row in result.fetchall()]
            print(f"  数据库中 pending 任务: {len(pending_tasks)} 个")
            
            if pending_tasks:
                print(f"\n  前 5 个 pending 任务 ID:")
                for task_id in pending_tasks[:5]:
                    print(f"    - {task_id[:8]}...")
        
        # 检查这些任务是否在 Redis 队列中
        if pending_tasks:
            await redis_queue.connect()
            in_redis = 0
            for task_id in pending_tasks[:5]:
                # 检查是否在任何队列中
                in_high = await redis_queue._redis.lpos(redis_queue.QUEUE_HIGH, task_id)
                in_normal = await redis_queue._redis.lpos(redis_queue.QUEUE_NORMAL, task_id)
                in_low = await redis_queue._redis.lpos(redis_queue.QUEUE_LOW, task_id)
                
                if in_high is not None or in_normal is not None or in_low is not None:
                    in_redis += 1
                    queue = "high" if in_high is not None else ("normal" if in_normal is not None else "low")
                    print(f"    ✅ {task_id[:8]}... 在 Redis {queue} 队列中")
                else:
                    print(f"    ❌ {task_id[:8]}... 不在 Redis 队列中")
            
            await redis_queue.disconnect()
            
            print(f"\n  一致性: {in_redis}/{min(len(pending_tasks), 5)} 个任务在 Redis 中")
    except Exception as e:
        print(f"  ❌ 一致性检查失败: {e}")
    print("-" * 80)

    print("\n✅ 诊断完成")

if __name__ == "__main__":
    asyncio.run(diagnose())
