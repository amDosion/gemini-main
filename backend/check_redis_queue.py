"""
检查 Redis 队列状态

使用方法：
    python backend/check_redis_queue.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.redis_queue_service import redis_queue

async def check_redis_queue():
    """检查 Redis 队列状态"""
    print("=" * 80)
    print("检查 Redis 队列状态")
    print("=" * 80)

    try:
        # 1. 检查连接
        print("\n1. Redis 连接:")
        print("-" * 80)
        try:
            await redis_queue._redis.ping()
            print("  ✅ Redis 连接正常")
        except Exception as e:
            print(f"  ❌ Redis 连接失败: {e}")
            return
        print("-" * 80)

        # 2. 检查队列长度
        print("\n2. 队列长度:")
        print("-" * 80)
        high_len = await redis_queue._redis.llen(redis_queue.QUEUE_HIGH)
        normal_len = await redis_queue._redis.llen(redis_queue.QUEUE_NORMAL)
        low_len = await redis_queue._redis.llen(redis_queue.QUEUE_LOW)
        dlq_len = await redis_queue._redis.llen(redis_queue.DLQ)
        
        print(f"  高优先级队列: {high_len} 个任务")
        print(f"  普通优先级队列: {normal_len} 个任务")
        print(f"  低优先级队列: {low_len} 个任务")
        print(f"  死信队列: {dlq_len} 个任务")
        print("-" * 80)

        # 3. 查看队列统计
        print("\n3. 队列统计:")
        print("-" * 80)
        stats = await redis_queue.get_stats()
        print(f"  总入队: {stats.get('total_enqueued', 0)}")
        print(f"  总出队: {stats.get('total_dequeued', 0)}")
        print(f"  总完成: {stats.get('total_completed', 0)}")
        print(f"  总失败: {stats.get('total_failed', 0)}")
        print("-" * 80)

        # 4. 查看队列中的任务ID
        if normal_len > 0:
            print("\n4. 普通队列中的任务:")
            print("-" * 80)
            tasks = await redis_queue._redis.lrange(redis_queue.QUEUE_NORMAL, 0, 9)
            for i, task_id in enumerate(tasks, 1):
                print(f"  {i}. {task_id}")
            print("-" * 80)

        print("\n✅ 检查完成")

    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_redis_queue())
