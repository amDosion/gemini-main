"""
Celery 配置和初始化
用于异步任务队列（如文件上传）
"""
import os
from celery import Celery

# 导入统一的环境变量加载模块（确保 .env 文件已加载）
from .env_loader import _ENV_LOADED  # noqa: F401

# Redis 配置
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# 构建 Redis URL
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

print(f"[Celery] Redis URL: redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

# 创建 Celery 应用
celery_app = Celery(
    'gemini_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.upload_tasks']  # 自动发现任务模块
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务执行配置
    task_track_started=True,           # 跟踪任务开始状态
    task_time_limit=300,               # 任务最大执行时间 5 分钟
    task_soft_time_limit=240,          # 软超时 4 分钟

    # Worker 配置
    worker_prefetch_multiplier=1,      # Worker 每次只预取 1 个任务（避免积压）
    worker_max_tasks_per_child=50,     # Worker 进程处理 50 个任务后重启（防止内存泄漏）

    # 结果保留时间
    result_expires=3600,               # 结果保留 1 小时

    # 任务路由（可选，用于不同队列）
    task_routes={
        'app.tasks.upload_tasks.*': {'queue': 'upload_queue'},  # 上传任务使用专用队列
    },

    # 并发控制
    worker_concurrency=3,              # 最多 3 个并发任务（避免资源耗尽）
)

print("[Celery] Celery 应用已初始化")
