"""
性能监控模块

收集和记录 Deep Research Agent 的性能指标。
"""
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading


class PerformanceMetrics:
    """性能指标收集器"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._response_times: List[float] = []
        self._success_count = 0
        self._failure_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._completion_times: List[float] = []
        self._start_time = datetime.now()
        
        # 按时间段统计
        self._hourly_stats: Dict[str, Dict] = defaultdict(lambda: {
            'requests': 0,
            'success': 0,
            'failure': 0,
            'total_response_time': 0.0,
        })
    
    def record_request(self, response_time: float, success: bool, completion_time: Optional[float] = None):
        """
        记录请求指标
        
        Args:
            response_time: 响应时间（秒）
            success: 是否成功
            completion_time: 完成时间（秒，可选）
        """
        with self._lock:
            self._response_times.append(response_time)
            
            if success:
                self._success_count += 1
                if completion_time:
                    self._completion_times.append(completion_time)
            else:
                self._failure_count += 1
            
            # 记录小时统计
            hour_key = datetime.now().strftime('%Y-%m-%d %H:00')
            self._hourly_stats[hour_key]['requests'] += 1
            self._hourly_stats[hour_key]['total_response_time'] += response_time
            if success:
                self._hourly_stats[hour_key]['success'] += 1
            else:
                self._hourly_stats[hour_key]['failure'] += 1
    
    def record_cache_hit(self):
        """记录缓存命中"""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self._lock:
            self._cache_misses += 1
    
    def get_metrics(self) -> Dict:
        """
        获取性能指标
        
        Returns:
            包含所有指标的字典
        """
        with self._lock:
            total_requests = self._success_count + self._failure_count
            
            metrics = {
                'total_requests': total_requests,
                'success_count': self._success_count,
                'failure_count': self._failure_count,
                'success_rate': self._success_count / total_requests if total_requests > 0 else 0.0,
                'failure_rate': self._failure_count / total_requests if total_requests > 0 else 0.0,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'cache_hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) 
                                  if (self._cache_hits + self._cache_misses) > 0 else 0.0,
                'avg_response_time': sum(self._response_times) / len(self._response_times) 
                                     if self._response_times else 0.0,
                'min_response_time': min(self._response_times) if self._response_times else 0.0,
                'max_response_time': max(self._response_times) if self._response_times else 0.0,
                'avg_completion_time': sum(self._completion_times) / len(self._completion_times) 
                                       if self._completion_times else 0.0,
                'uptime_seconds': (datetime.now() - self._start_time).total_seconds(),
            }
            
            return metrics
    
    def get_hourly_stats(self, hours: int = 24) -> List[Dict]:
        """
        获取最近N小时的统计数据
        
        Args:
            hours: 小时数
            
        Returns:
            小时统计列表
        """
        with self._lock:
            now = datetime.now()
            stats = []
            
            for i in range(hours):
                hour = now - timedelta(hours=i)
                hour_key = hour.strftime('%Y-%m-%d %H:00')
                
                if hour_key in self._hourly_stats:
                    data = self._hourly_stats[hour_key]
                    avg_response_time = (data['total_response_time'] / data['requests'] 
                                        if data['requests'] > 0 else 0.0)
                    
                    stats.append({
                        'hour': hour_key,
                        'requests': data['requests'],
                        'success': data['success'],
                        'failure': data['failure'],
                        'success_rate': data['success'] / data['requests'] if data['requests'] > 0 else 0.0,
                        'avg_response_time': avg_response_time,
                    })
                else:
                    stats.append({
                        'hour': hour_key,
                        'requests': 0,
                        'success': 0,
                        'failure': 0,
                        'success_rate': 0.0,
                        'avg_response_time': 0.0,
                    })
            
            return list(reversed(stats))
    
    def reset(self):
        """重置所有指标"""
        with self._lock:
            self._response_times.clear()
            self._success_count = 0
            self._failure_count = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._completion_times.clear()
            self._hourly_stats.clear()
            self._start_time = datetime.now()


# 全局性能指标实例
performance_metrics = PerformanceMetrics()
