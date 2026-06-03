"""
对抗验证测试（RED-first）：redis_queue_service 性能/正确性修复

覆盖：
- P1: is_task_queued 应使用 O(1) Set 成员检查（SISMEMBER），而非对每个优先级队列做
       O(N) 的 LPOS 列表扫描。enqueue/dequeue 必须同步维护该索引 Set。
- P2: Lua 脚本（限流、释放锁）应通过 register_script() 注册一次（EVALSHA 复用），
       而不是每次调用都重发完整脚本字符串。
- P6: append_task_log 的 RPUSH+LTRIM+EXPIRE 三次往返应被 pipeline 合并为一次往返。

使用假 async redis 客户端（fakeredis 不可用，见 notes）。
"""

import pytest

from app.services.common.redis_queue_service import RedisQueueService


class _FakePipeline:
    def __init__(self, client):
        self._client = client
        self._ops = []

    def rpush(self, key, *values):
        self._ops.append(("rpush", key, values))
        return self

    def ltrim(self, key, start, end):
        self._ops.append(("ltrim", key, start, end))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    def sadd(self, key, *members):
        self._ops.append(("sadd", key, members))
        return self

    def lpush(self, key, *values):
        self._ops.append(("lpush", key, values))
        return self

    def srem(self, key, *members):
        self._ops.append(("srem", key, members))
        return self

    def hincrby(self, key, field, amount=1):
        self._ops.append(("hincrby", key, field, amount))
        return self

    async def execute(self):
        self._client.pipeline_executions += 1
        results = []
        for op in self._ops:
            name = op[0]
            if name == "rpush":
                self._client._lists.setdefault(op[1], []).extend(op[2])
                results.append(len(self._client._lists[op[1]]))
            elif name == "lpush":
                self._client._lists.setdefault(op[1], [])[:0] = list(op[2])
                results.append(len(self._client._lists[op[1]]))
            elif name == "sadd":
                self._client._sets.setdefault(op[1], set()).update(op[2])
                results.append(len(op[2]))
            elif name == "srem":
                s = self._client._sets.get(op[1], set())
                removed = 0
                for m in op[2]:
                    if m in s:
                        s.discard(m)
                        removed += 1
                results.append(removed)
            elif name == "hincrby":
                h = self._client._hashes.setdefault(op[1], {})
                h[op[2]] = h.get(op[2], 0) + op[3]
                results.append(h[op[2]])
            else:
                results.append(None)
        return results


class _FakeScript:
    """register_script() 返回的可调用脚本对象（EVALSHA 语义）。"""

    def __init__(self, client, body):
        self._client = client
        self._body = body

    async def __call__(self, keys=None, args=None, client=None):
        self._client.script_calls += 1
        # 限流脚本返回 1（允许）；释放锁脚本返回 1（删除成功）
        return 1


class _FakeRedis:
    def __init__(self):
        self._lists = {}
        self._sets = {}
        self._hashes = {}
        # 计数器用于断言
        self.lpos_calls = 0
        self.sismember_calls = 0
        self.eval_calls = 0
        self.script_calls = 0
        self.registered_scripts = 0
        self.pipeline_executions = 0

    # --- list ops ---
    async def lpush(self, key, *values):
        self._lists.setdefault(key, [])[:0] = list(values)
        return len(self._lists[key])

    async def rpush(self, key, *values):
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    async def llen(self, key):
        return len(self._lists.get(key, []))

    async def lpos(self, key, value):
        self.lpos_calls += 1
        lst = self._lists.get(key, [])
        return lst.index(value) if value in lst else None

    async def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    async def ltrim(self, key, start, end):
        return True

    async def brpop(self, keys, timeout=0):
        for key in keys:
            lst = self._lists.get(key, [])
            if lst:
                val = lst.pop()  # 右出
                return (key, val)
        return None

    # --- set ops ---
    async def sadd(self, key, *members):
        self._sets.setdefault(key, set()).update(members)
        return len(members)

    async def srem(self, key, *members):
        s = self._sets.get(key, set())
        removed = 0
        for m in members:
            if m in s:
                s.discard(m)
                removed += 1
        return removed

    async def sismember(self, key, member):
        self.sismember_calls += 1
        return member in self._sets.get(key, set())

    # --- hash / misc ---
    async def hincrby(self, key, field, amount=1):
        h = self._hashes.setdefault(key, {})
        h[field] = h.get(field, 0) + amount
        return h[field]

    async def expire(self, key, ttl):
        return True

    async def eval(self, *a, **k):
        self.eval_calls += 1
        return 1

    def register_script(self, body):
        self.registered_scripts += 1
        return _FakeScript(self, body)

    def pipeline(self, transaction=True):
        return _FakePipeline(self)


@pytest.fixture
def svc():
    s = RedisQueueService()
    s._redis = _FakeRedis()
    return s


@pytest.mark.asyncio
async def test_is_task_queued_uses_sismember_not_lpos(svc):
    """P1: is_task_queued 应使用 SISMEMBER（O(1)），不应做 LPOS 列表扫描。"""
    await svc.enqueue("task-1", "normal")

    redis = svc._redis
    redis.lpos_calls = 0
    redis.sismember_calls = 0

    assert await svc.is_task_queued("task-1") is True
    assert await svc.is_task_queued("task-missing") is False

    assert redis.lpos_calls == 0, "is_task_queued 不应再使用 LPOS 列表扫描"
    assert redis.sismember_calls >= 1, "is_task_queued 应使用 SISMEMBER 集合成员检查"


@pytest.mark.asyncio
async def test_enqueue_dequeue_maintain_index_set(svc):
    """P1: enqueue/dequeue 必须同步维护索引 Set，使队列内容与 Set 一致。"""
    await svc.enqueue("task-x", "high")
    assert await svc.is_task_queued("task-x") is True

    popped = await svc.dequeue(timeout=0)
    assert popped == "task-x"
    # 出队后索引 Set 应不再包含该任务
    assert await svc.is_task_queued("task-x") is False


@pytest.mark.asyncio
async def test_rate_limit_uses_registered_script(svc):
    """P2: 限流应使用 register_script()/EVALSHA 复用，而非每次重发脚本字符串。"""
    redis = svc._redis
    ok = await svc.acquire_rate_token()
    assert ok is True
    assert redis.eval_calls == 0, "acquire_rate_token 不应使用 raw eval（每次重发脚本字符串）"
    assert redis.registered_scripts >= 1, "应通过 register_script 注册限流脚本"
    assert redis.script_calls >= 1, "应通过已注册脚本对象（EVALSHA）调用"


@pytest.mark.asyncio
async def test_release_lock_uses_registered_script(svc):
    """P2: 释放锁应使用 register_script()/EVALSHA 复用。"""
    redis = svc._redis
    result = await svc.release_lock("task-1", "worker-0")
    assert result is True
    assert redis.eval_calls == 0, "release_lock 不应使用 raw eval"
    assert redis.script_calls >= 1, "release_lock 应通过已注册脚本对象调用"


@pytest.mark.asyncio
async def test_append_task_log_uses_pipeline(svc):
    """P6: append_task_log 应用一次 pipeline 合并 RPUSH/LTRIM/EXPIRE。"""
    redis = svc._redis
    before = redis.pipeline_executions
    await svc.append_task_log("task-1", "info", "hello", source="test")
    assert redis.pipeline_executions == before + 1, (
        "append_task_log 应使用单次 pipeline().execute() 合并三次往返"
    )
    # 行为保持：日志确实写入
    logs = await svc.get_task_logs("task-1", tail=10)
    assert any(entry.get("message") == "hello" for entry in logs)


@pytest.mark.asyncio
async def test_scripts_registered_once_across_calls(svc):
    """P2: 多次调用限流不应重复注册脚本（EVALSHA 复用，只注册一次）。"""
    redis = svc._redis
    await svc.acquire_rate_token()
    registered_after_first = redis.registered_scripts
    await svc.acquire_rate_token()
    await svc.acquire_rate_token()
    assert redis.registered_scripts == registered_after_first, (
        "限流脚本应只注册一次并复用，不应每次调用都重新注册"
    )
