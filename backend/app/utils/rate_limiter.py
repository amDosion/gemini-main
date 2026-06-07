import time
from typing import Dict, List


class RateLimiter:
    """Rate limiter using in-memory storage"""

    def __init__(self):
        self.requests: Dict[str, List[float]] = {}

    async def check_rate_limit(
        self,
        user_id: str,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> bool:
        """Check if user is within rate limit"""
        current_time = time.time()
        window_start = current_time - window_seconds

        recent: List[float] = [
            req_time for req_time in self.requests.get(user_id, [])
            if req_time > window_start
        ]

        # Remove the entry entirely when the window is empty so memory stays
        # proportional to active users rather than accumulating all historical IDs.
        if not recent:
            self.requests.pop(user_id, None)
            self.requests[user_id] = [current_time]
            return True

        if len(recent) >= max_requests:
            return False

        recent.append(current_time)
        self.requests[user_id] = recent
        return True
