"""Advanced monitoring utilities for performance tracking."""

import time
import logging
from typing import Dict, Any, Optional
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor and track performance metrics for debugging 504 errors."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "timeout_errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_response_time": 0.0,
            "slow_requests": 0,  # > 30s
            "fast_requests": 0,  # < 5s
        }
        self.request_times = []
        self.slow_request_details = []
    
    def start_request(self) -> float:
        """Start timing a request."""
        self.metrics["total_requests"] += 1
        return time.time()
    
    def end_request(self, start_time: float, success: bool = True, cached: bool = False, timeout: bool = False):
        """End timing a request and update metrics."""
        duration = time.time() - start_time
        self.request_times.append(duration)
        
        if success:
            self.metrics["successful_requests"] += 1
        
        if timeout:
            self.metrics["timeout_errors"] += 1
            self.slow_request_details.append({
                "duration": duration,
                "timestamp": time.time(),
                "timeout": True
            })
        
        if cached:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1
        
        if duration > 30:
            self.metrics["slow_requests"] += 1
            if not timeout:  # Don't double-count timeouts
                self.slow_request_details.append({
                    "duration": duration,
                    "timestamp": time.time(),
                    "timeout": False
                })
        elif duration < 5:
            self.metrics["fast_requests"] += 1
        
        # Update rolling average (last 100 requests)
        if len(self.request_times) > 100:
            self.request_times = self.request_times[-100:]
        
        self.metrics["average_response_time"] = sum(self.request_times) / len(self.request_times)
        
        # Log slow requests for debugging
        if duration > 15:
            logger.warning(f"Slow request detected: {duration:.2f}s (timeout={timeout}, cached={cached})")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        total = self.metrics["total_requests"]
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            "success_rate": self.metrics["successful_requests"] / total * 100,
            "timeout_rate": self.metrics["timeout_errors"] / total * 100,
            "cache_hit_rate": self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"]) * 100 if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0 else 0,
            "slow_request_rate": self.metrics["slow_requests"] / total * 100,
            "fast_request_rate": self.metrics["fast_requests"] / total * 100,
        }
    
    def get_slow_requests(self) -> list:
        """Get details of slow requests for analysis."""
        return self.slow_request_details[-10:]  # Last 10 slow requests
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.__init__()

# Global monitor instance
_monitor = PerformanceMonitor()

def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _monitor

def monitor_performance(func_name: str = None):
    """Decorator to monitor function performance."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = func_name or func.__name__
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                if duration > 5:
                    logger.info(f"[{name}] completed in {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[{name}] failed after {duration:.2f}s: {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = func_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                if duration > 2:
                    logger.info(f"[{name}] completed in {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[{name}] failed after {duration:.2f}s: {e}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

@asynccontextmanager
async def performance_context(operation_name: str):
    """Context manager for monitoring performance of code blocks."""
    start_time = time.time()
    logger.debug(f"[{operation_name}] starting...")
    
    try:
        yield
        duration = time.time() - start_time
        logger.debug(f"[{operation_name}] completed in {duration:.3f}s")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{operation_name}] failed after {duration:.3f}s: {e}")
        raise

class RequestLogger:
    """Enhanced request logging for debugging."""
    
    @staticmethod
    def log_request_start(request_id: str, endpoint: str, user_id: str, query: str):
        """Log the start of a request."""
        logger.info(f"[{request_id}] START {endpoint} - user={user_id}, query_len={len(query)}")
    
    @staticmethod
    def log_request_end(request_id: str, duration: float, status: str, cached: bool = False):
        """Log the end of a request."""
        cache_info = " (cached)" if cached else ""
        logger.info(f"[{request_id}] END {status} - {duration:.2f}s{cache_info}")
    
    @staticmethod
    def log_performance_issue(request_id: str, issue_type: str, details: Dict[str, Any]):
        """Log performance issues for debugging."""
        logger.warning(f"[{request_id}] PERFORMANCE_ISSUE {issue_type}: {details}")
    
    @staticmethod
    def log_optimization_result(operation: str, before: float, after: float):
        """Log optimization results."""
        improvement = ((before - after) / before) * 100 if before > 0 else 0
        logger.info(f"[OPTIMIZATION] {operation}: {before:.2f}s -> {after:.2f}s ({improvement:.1f}% improvement)")

# Global request logger
request_logger = RequestLogger()