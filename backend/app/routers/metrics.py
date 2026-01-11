"""
性能监控路由

提供性能指标查询接口。
"""
from fastapi import APIRouter, Query
from typing import Optional
from ..utils.performance_metrics import performance_metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/performance")
async def get_performance_metrics():
    """
    获取性能指标
    
    Returns:
        性能指标数据
    """
    return {
        "success": True,
        "data": performance_metrics.get_metrics()
    }


@router.get("/hourly")
async def get_hourly_stats(hours: int = Query(24, ge=1, le=168)):
    """
    获取小时统计数据
    
    Args:
        hours: 小时数（1-168）
        
    Returns:
        小时统计数据
    """
    return {
        "success": True,
        "data": performance_metrics.get_hourly_stats(hours)
    }


@router.post("/reset")
async def reset_metrics():
    """
    重置性能指标
    
    Returns:
        操作结果
    """
    performance_metrics.reset()
    return {
        "success": True,
        "message": "Performance metrics reset successfully"
    }
