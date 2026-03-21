from fastapi import HTTPException


def handle_gemini_error(error: Exception) -> HTTPException:
    """Handle Gemini API errors"""
    error_str = str(error)
    
    if '429' in error_str or 'quota' in error_str.lower():
        return HTTPException(
            status_code=429,
            detail={
                "error": "RESOURCE_EXHAUSTED",
                "message": "API配额已用尽",
                "original_error": error_str,
                "suggestions": [
                    "等待配额重置",
                    "升级到更高配额计划",
                    "减少请求频率"
                ]
            }
        )
    
    if '400' in error_str or 'invalid' in error_str.lower():
        return HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_ARGUMENT",
                "message": "请求参数无效",
                "original_error": error_str,
                "suggestions": [
                    "检查prompt格式",
                    "确认agent名称正确",
                    "验证工具配置"
                ]
            }
        )
    
    if '503' in error_str or 'overloaded' in error_str.lower():
        return HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "服务暂时过载",
                "original_error": error_str,
                "suggestions": [
                    "稍后重试",
                    "使用指数退避策略"
                ]
            }
        )
    
    return HTTPException(
        status_code=500,
        detail={
            "error": "INTERNAL_ERROR",
            "message": f"内部错误: {error_str}",
            "original_error": error_str,
            "suggestions": [
                "联系技术支持",
                "查看错误日志"
            ]
        }
    )
