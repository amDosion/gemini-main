import time
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

MAX_INTERACTIONS = 500
MAX_RESULTS = 500


class ResearchCache:
    """Research cache using in-memory storage with size limits"""
    
    def __init__(self):
        self.interactions: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def _cleanup_expired(self):
        """清理过期条目"""
        now = time.time()
        expired_interactions = [k for k, v in self.interactions.items() if now > v.get("expires_at", 0)]
        for k in expired_interactions:
            del self.interactions[k]
        expired_results = [k for k, v in self.results.items() if now > v.get("expires_at", 0)]
        for k in expired_results:
            del self.results[k]
    
    def _evict_oldest(self, cache: Dict, max_size: int):
        """超出上限时移除最早过期的条目"""
        if len(cache) <= max_size:
            return
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k].get("expires_at", 0))
        to_remove = len(cache) - max_size
        for k in sorted_keys[:to_remove]:
            del cache[k]
    
    def cache_interaction(
        self,
        interaction_id: str,
        data: Dict[str, Any],
        ttl: int = 3600
    ):
        """Cache interaction metadata"""
        self._cleanup_expired()
        self.interactions[interaction_id] = {
            "data": data,
            "expires_at": time.time() + ttl
        }
        self._evict_oldest(self.interactions, MAX_INTERACTIONS)
    
    def get_cached_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get cached interaction"""
        if interaction_id not in self.interactions:
            return None
        
        cached = self.interactions[interaction_id]
        if time.time() > cached["expires_at"]:
            del self.interactions[interaction_id]
            return None
        
        return cached["data"]
    
    def cache_research_result(
        self,
        prompt_hash: str,
        result: str,
        ttl: int = 86400
    ):
        """Cache research result"""
        self._cleanup_expired()
        self.results[prompt_hash] = {
            "result": result,
            "expires_at": time.time() + ttl
        }
        self._evict_oldest(self.results, MAX_RESULTS)
    
    def get_cached_result(self, prompt_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached research result"""
        if prompt_hash not in self.results:
            return None
        
        cached = self.results[prompt_hash]
        if time.time() > cached["expires_at"]:
            del self.results[prompt_hash]
            return None
        
        return cached
    
    def delete_cached_interaction(self, interaction_id: str):
        """Delete cached interaction"""
        if interaction_id in self.interactions:
            del self.interactions[interaction_id]
