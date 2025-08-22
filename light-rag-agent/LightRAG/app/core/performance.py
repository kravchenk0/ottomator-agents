"""Performance optimization utilities for RAG operations."""
import asyncio
import hashlib
import time
from typing import Dict, Optional, Tuple, Any
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Optimizes RAG performance with intelligent caching and parallel processing."""
    
    def __init__(self, cache_ttl: int = 300, max_cache_size: int = 2000):
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self._result_cache: Dict[str, Tuple[Any, float]] = {}
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "avg_response_time": 0.0
        }
    
    def get_cache_key(self, query: str, mode: str = "hybrid") -> str:
        """Generate deterministic cache key."""
        cache_data = f"{query}|{mode}"
        return hashlib.md5(cache_data.encode('utf-8')).hexdigest()
    
    def get_cached(self, key: str) -> Optional[Any]:
        """Get cached result if valid."""
        self._metrics["total_requests"] += 1
        
        if key in self._result_cache:
            result, timestamp = self._result_cache[key]
            if time.time() - timestamp < self.cache_ttl:
                self._metrics["cache_hits"] += 1
                logger.debug(f"Cache hit for key {key[:8]}...")
                return result
            else:
                del self._result_cache[key]
        
        self._metrics["cache_misses"] += 1
        return None
    
    def set_cached(self, key: str, result: Any) -> None:
        """Store result in cache with TTL."""
        self._result_cache[key] = (result, time.time())
        
        # Cleanup if cache too large
        if len(self._result_cache) > self.max_cache_size:
            self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired = [k for k, (_, ts) in self._result_cache.items() 
                   if now - ts > self.cache_ttl]
        
        for key in expired[:len(expired)//2]:  # Remove half of expired
            del self._result_cache[key]
        
        logger.debug(f"Cache cleanup: removed {len(expired)//2} entries")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return performance metrics."""
        hit_rate = 0.0
        if self._metrics["total_requests"] > 0:
            hit_rate = self._metrics["cache_hits"] / self._metrics["total_requests"]
        
        return {
            **self._metrics,
            "cache_hit_rate": hit_rate,
            "cache_size": len(self._result_cache)
        }
    
    async def parallel_process(self, tasks: list, max_concurrent: int = 3) -> list:
        """Process multiple async tasks in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_task(task):
            async with semaphore:
                return await task
        
        return await asyncio.gather(*[bounded_task(task) for task in tasks])


class QueryOptimizer:
    """Optimizes query parameters based on query complexity."""
    
    @staticmethod
    def get_optimal_mode(query: str) -> str:
        """Determine optimal search mode based on query."""
        words = len(query.split())
        
        if words <= 3:
            return "naive"  # Fastest for simple queries
        elif words <= 5:
            return "local"   # Good for short queries
        elif words <= 10:
            return "hybrid"  # Balanced
        else:
            return "global"  # Comprehensive for complex queries
    
    @staticmethod
    def get_optimal_timeout(query: str) -> int:
        """Calculate optimal timeout based on query complexity."""
        words = len(query.split())
        
        if words <= 3:
            return 10  # Very fast
        elif words <= 7:
            return 20  # Fast
        elif words <= 15:
            return 30  # Medium
        else:
            return 45  # Conservative for complex queries
    
    @staticmethod
    def should_use_cache(query: str) -> bool:
        """Determine if query result should be cached."""
        # Cache everything except very short queries that might be typos
        return len(query) > 2


# Global optimizer instance
_optimizer = None

def get_optimizer() -> PerformanceOptimizer:
    """Get or create global optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer