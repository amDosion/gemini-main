import time
from typing import Dict
from datetime import datetime, timedelta


class RateLimiter:
    """Rate limiter using in-memory storage"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
    
    async def check_rate_limit(
        self,
        user_id: str,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> bool:
        """Check if user is within rate limit"""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > window_start
        ]
        
        if len(self.requests[user_id]) >= max_requests:
            return False
        
        self.requests[user_id].append(current_time)
        return True
