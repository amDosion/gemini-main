import time
from typing import Dict, Optional, Any


class ResearchCache:
    """Research cache using in-memory storage"""
    
    def __init__(self):
        self.interactions: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def cache_interaction(
        self,
        interaction_id: str,
        data: Dict[str, Any],
        ttl: int = 3600
    ):
        """Cache interaction metadata"""
        self.interactions[interaction_id] = {
            'data': data,
            'expires_at': time.time() + ttl
        }
    
    def get_cached_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get cached interaction"""
        if interaction_id not in self.interactions:
            return None
        
        cached = self.interactions[interaction_id]
        if time.time() > cached['expires_at']:
            del self.interactions[interaction_id]
            return None
        
        return cached['data']
    
    def cache_research_result(
        self,
        prompt_hash: str,
        result: str,
        ttl: int = 86400
    ):
        """Cache research result"""
        self.results[prompt_hash] = {
            'result': result,
            'expires_at': time.time() + ttl
        }
    
    def get_cached_result(self, prompt_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached research result"""
        if prompt_hash not in self.results:
            return None
        
        cached = self.results[prompt_hash]
        if time.time() > cached['expires_at']:
            del self.results[prompt_hash]
            return None
        
        return cached
    
    def delete_cached_interaction(self, interaction_id: str):
        """Delete cached interaction"""
        if interaction_id in self.interactions:
            del self.interactions[interaction_id]
