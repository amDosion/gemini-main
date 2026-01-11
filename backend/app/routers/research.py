from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import hashlib
import time
import logging

from ..dependencies import get_rate_limiter, get_cache, get_validator
from ..services.interactions_service import InteractionsService
from ..utils.rate_limiter import RateLimiter
from ..utils.research_cache import ResearchCache
from ..utils.prompt_security_validator import PromptSecurityValidator
from ..utils.error_handler import handle_gemini_error
from ..utils.performance_metrics import performance_metrics

router = APIRouter(prefix="/api/research", tags=["research"])
logger = logging.getLogger(__name__)


class ResearchStartRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=10000)
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    format: Optional[str] = None
    include_private_data: bool = False
    file_search_store_names: Optional[List[str]] = None
    language: Optional[str] = None
    tone: Optional[str] = None


class ResearchStartResponse(BaseModel):
    interaction_id: str
    status: str
    cached: bool = False


class ResearchStatusResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[str] = None
    usage: Optional[dict] = None


class ResearchContinueRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=10000)
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True


class ResearchFollowupRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=5000)


class ResearchSummarizeRequest(BaseModel):
    format: Optional[str] = "markdown"
    max_length: Optional[int] = 1000


class ResearchFormatRequest(BaseModel):
    output_format: str = Field(..., description="Output format (json, xml, yaml, etc.)")
    output_schema: Optional[dict] = Field(None, description="Custom output schema")


@router.post("/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    authorization: str = Header(None),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_cache),
    validator: PromptSecurityValidator = Depends(get_validator)
):
    """Start a deep research task"""
    
    start_time = time.time()
    success = False
    
    try:
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        api_key = authorization.split(' ')[1]
        user_id = extract_user_id(api_key)
        
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试",
                    "suggestions": [
                        "等待1分钟后重试",
                        "减少请求频率"
                    ]
                }
            )
        
        is_safe, warnings = validator.validate_prompt(request.prompt)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_ARGUMENT",
                    "message": "输入包含不安全内容",
                    "warnings": warnings
                }
            )
        
        prompt_hash = hashlib.sha256(request.prompt.encode()).hexdigest()
        cached_result = cache.get_cached_result(prompt_hash)
        if cached_result:
            performance_metrics.record_cache_hit()
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            return ResearchStartResponse(
                interaction_id=cached_result.get('interaction_id', ''),
                status='completed',
                cached=True
            )
        
        performance_metrics.record_cache_miss()
        
        try:
            # 使用 InteractionsService 替代直接 SDK 调用
            service = InteractionsService(api_key=api_key)
            
            full_prompt = build_prompt(request)
            
            tools = []
            if request.include_private_data and request.file_search_store_names:
                tools.append({
                    "type": "file_search",
                    "file_search_store_names": request.file_search_store_names
                })
            
            # 调用 InteractionsService.create_interaction()
            interaction = await service.create_interaction(
                agent=request.agent,
                input=full_prompt,
                background=True,
                tools=tools if tools else None,
                store=True  # 启用状态存储，支持多轮追问
            )
            
            cache.cache_interaction(interaction.id, {
                'prompt': request.prompt,
                'status': interaction.status,
                'created_at': datetime.now().isoformat()
            }, ttl=3600)
            
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            
            return ResearchStartResponse(
                interaction_id=interaction.id,
                status=interaction.status
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success=False)
            raise handle_gemini_error(e)
    
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(e)


@router.get("/status/{interaction_id}", response_model=ResearchStatusResponse)
async def get_research_status(
    interaction_id: str,
    authorization: str = Header(None),
    cache: ResearchCache = Depends(get_cache)
):
    """Get research task status"""
    
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    
    cached_interaction = cache.get_cached_interaction(interaction_id)
    if cached_interaction and cached_interaction.get('status') == 'completed':
        return ResearchStatusResponse(
            status='completed',
            result=cached_interaction.get('result')
        )
    
    try:
        # 使用 InteractionsService 替代直接 SDK 调用
        service = InteractionsService(api_key=api_key)
        
        # 调用 InteractionsService.get_interaction()
        interaction = await service.get_interaction(interaction_id)
        
        if interaction.status == "completed":
            result_text = extract_result(interaction.outputs)
            
            cache.cache_interaction(interaction_id, {
                'status': 'completed',
                'result': result_text,
                'completed_at': datetime.now().isoformat()
            }, ttl=3600)
            
            if cached_interaction:
                prompt_hash = hashlib.sha256(
                    cached_interaction.get('prompt', '').encode()
                ).hexdigest()
                cache.cache_research_result(prompt_hash, result_text, ttl=86400)
            
            return ResearchStatusResponse(
                status="completed",
                result=result_text,
                usage=interaction.usage.__dict__ if interaction.usage else None
            )
        
        elif interaction.status == "failed":
            error_message = extract_error(interaction)
            
            return ResearchStatusResponse(
                status="failed",
                error=error_message
            )
        
        else:
            progress = extract_progress(interaction.outputs)
            
            return ResearchStatusResponse(
                status="in_progress",
                progress=progress
            )
        
    except Exception as e:
        raise handle_gemini_error(e)


@router.post("/cancel/{interaction_id}")
async def cancel_research(
    interaction_id: str,
    authorization: str = Header(None),
    cache: ResearchCache = Depends(get_cache)
):
    """Cancel research task"""
    
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    
    try:
        # 使用 InteractionsService 替代直接 SDK 调用
        service = InteractionsService(api_key=api_key)
        
        # 调用 InteractionsService.delete_interaction()
        await service.delete_interaction(interaction_id)
        
        cache.delete_cached_interaction(interaction_id)
        
        return {"message": "Research task cancelled"}
        
    except Exception as e:
        raise handle_gemini_error(e)


@router.post("/continue/{interaction_id}", response_model=ResearchStartResponse)
async def continue_research(
    interaction_id: str,
    request: ResearchContinueRequest,
    authorization: str = Header(None),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_cache),
    validator: PromptSecurityValidator = Depends(get_validator)
):
    """
    Continue research based on previous interaction
    
    Uses previous_interaction_id to link research tasks and maintain context.
    Allows continuing research with a new prompt based on previous results.
    
    Args:
        interaction_id: Previous interaction ID to continue from
        request: Continue research request with new prompt
        authorization: Bearer token for authentication
        rate_limiter: Rate limiting dependency
        cache: Cache dependency
        validator: Security validator dependency
        
    Returns:
        ResearchStartResponse with new interaction_id and status
        
    Raises:
        HTTPException: Authentication, rate limit, or validation errors
    """
    
    start_time = time.time()
    success = False
    
    try:
        # 1. 认证检查
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        api_key = authorization.split(' ')[1]
        user_id = extract_user_id(api_key)
        
        # 2. 速率限制检查
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试",
                    "suggestions": [
                        "等待1分钟后重试",
                        "减少请求频率"
                    ]
                }
            )
        
        # 3. 输入验证
        is_safe, warnings = validator.validate_prompt(request.prompt)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_ARGUMENT",
                    "message": "输入包含不安全内容",
                    "warnings": warnings
                }
            )
        
        # 4. 验证 previous_interaction_id 存在
        service = InteractionsService(api_key=api_key)
        try:
            previous_interaction = await service.get_interaction(interaction_id)
            if previous_interaction.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_ARGUMENT",
                        "message": f"Previous interaction must be completed (current status: {previous_interaction.status})"
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Previous interaction {interaction_id} not found"
                }
            )
        
        logger.info(f"Continuing research from interaction {interaction_id}")
        
        # 5. 创建新的交互，使用 previous_interaction_id
        try:
            new_interaction = await service.create_interaction(
                agent=request.agent,
                input=request.prompt,
                previous_interaction_id=interaction_id,
                background=True,
                store=True
            )
            
            # 6. 缓存新交互
            cache.cache_interaction(new_interaction.id, {
                'prompt': request.prompt,
                'status': new_interaction.status,
                'previous_interaction_id': interaction_id,
                'created_at': datetime.now().isoformat()
            }, ttl=3600)
            
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            
            logger.info(f"Continue research created: {new_interaction.id}")
            
            return ResearchStartResponse(
                interaction_id=new_interaction.id,
                status=new_interaction.status
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success=False)
            raise handle_gemini_error(e)
    
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(e)


@router.post("/followup/{interaction_id}", response_model=ResearchStartResponse)
async def followup_research(
    interaction_id: str,
    request: ResearchFollowupRequest,
    authorization: str = Header(None),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_cache),
    validator: PromptSecurityValidator = Depends(get_validator)
):
    """
    Ask follow-up questions about research results
    
    Uses previous_interaction_id to maintain research context.
    Allows asking questions about completed research without starting new research.
    
    Args:
        interaction_id: Previous interaction ID to ask about
        request: Follow-up question request
        authorization: Bearer token for authentication
        rate_limiter: Rate limiting dependency
        cache: Cache dependency
        validator: Security validator dependency
        
    Returns:
        ResearchStartResponse with new interaction_id and status
        
    Raises:
        HTTPException: Authentication, rate limit, or validation errors
    """
    
    start_time = time.time()
    success = False
    
    try:
        # 1. 认证检查
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        api_key = authorization.split(' ')[1]
        user_id = extract_user_id(api_key)
        
        # 2. 速率限制检查
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试",
                    "suggestions": [
                        "等待1分钟后重试",
                        "减少请求频率"
                    ]
                }
            )
        
        # 3. 输入验证
        is_safe, warnings = validator.validate_prompt(request.question)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_ARGUMENT",
                    "message": "输入包含不安全内容",
                    "warnings": warnings
                }
            )
        
        # 4. 验证 previous_interaction_id 存在
        service = InteractionsService(api_key=api_key)
        try:
            previous_interaction = await service.get_interaction(interaction_id)
            if previous_interaction.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_ARGUMENT",
                        "message": f"Previous interaction must be completed (current status: {previous_interaction.status})"
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Previous interaction {interaction_id} not found"
                }
            )
        
        logger.info(f"Follow-up question for interaction {interaction_id}")
        
        # 5. 创建新的交互，使用 Model 而非 Agent（追问不需要重新研究）
        try:
            # 使用 Model 进行追问，速度更快
            new_interaction = await service.create_interaction(
                model="gemini-2.5-flash",  # 使用快速模型
                input=request.question,
                previous_interaction_id=interaction_id,
                background=False,  # 追问不需要后台执行
                store=True
            )
            
            # 6. 缓存新交互
            cache.cache_interaction(new_interaction.id, {
                'question': request.question,
                'status': new_interaction.status,
                'previous_interaction_id': interaction_id,
                'created_at': datetime.now().isoformat()
            }, ttl=3600)
            
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            
            logger.info(f"Follow-up created: {new_interaction.id}")
            
            return ResearchStartResponse(
                interaction_id=new_interaction.id,
                status=new_interaction.status
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success=False)
            raise handle_gemini_error(e)
    
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(e)


def build_prompt(request: ResearchStartRequest) -> str:
    """Construct full prompt with format, language, and tone"""
    full_prompt = request.prompt
    
    if request.format:
        full_prompt += f"\n\n{request.format}"
    
    if request.language:
        full_prompt += f"\n\nPlease respond in {request.language}."
    
    if request.tone:
        tone_instructions = {
            'professional': 'Use a professional and formal tone.',
            'casual': 'Use a casual and conversational tone.',
            'technical': 'Use technical language appropriate for experts.'
        }
        full_prompt += f"\n\n{tone_instructions.get(request.tone, '')}"
    
    return full_prompt


def extract_result(outputs: List) -> str:
    """Extract final report from outputs"""
    result_text = ""
    for output in outputs:
        if hasattr(output, 'text') and output.type == 'text':
            result_text += output.text
    return result_text


def extract_error(interaction) -> str:
    """Extract error message from interaction"""
    if hasattr(interaction, 'error'):
        return str(interaction.error)
    return "Research task failed"


def extract_progress(outputs: List) -> str:
    """Extract progress from thought_summary"""
    for output in reversed(outputs):
        if hasattr(output, 'type') and output.type == 'thought_summary':
            return output.content.text
    return "Research in progress..."


def extract_user_id(api_key: str) -> str:
    """Generate user ID from API key hash"""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


@router.post("/summarize/{interaction_id}", response_model=ResearchStartResponse)
async def summarize_research(
    interaction_id: str,
    request: ResearchSummarizeRequest,
    authorization: str = Header(None),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_cache)
):
    """
    Summarize research results using Model
    
    Uses Agent for research, then uses Model to summarize the results.
    This provides a concise summary of the research findings.
    
    Args:
        interaction_id: Previous research interaction ID
        request: Summarize request with format and max_length
        authorization: Bearer token for authentication
        rate_limiter: Rate limiting dependency
        cache: Cache dependency
        
    Returns:
        ResearchStartResponse with new interaction_id and status
        
    Raises:
        HTTPException: Authentication, rate limit, or validation errors
    """
    
    start_time = time.time()
    success = False
    
    try:
        # 1. 认证检查
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        api_key = authorization.split(' ')[1]
        user_id = extract_user_id(api_key)
        
        # 2. 速率限制检查
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试"
                }
            )
        
        # 3. 验证 previous_interaction_id 存在且已完成
        service = InteractionsService(api_key=api_key)
        try:
            previous_interaction = await service.get_interaction(interaction_id)
            if previous_interaction.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_ARGUMENT",
                        "message": f"Previous interaction must be completed (current status: {previous_interaction.status})"
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Previous interaction {interaction_id} not found"
                }
            )
        
        logger.info(f"Summarizing research from interaction {interaction_id}")
        
        # 4. 构建总结提示
        summarize_prompt = f"Please provide a concise summary of the research findings in {request.format} format"
        if request.max_length:
            summarize_prompt += f", limited to approximately {request.max_length} words"
        summarize_prompt += "."
        
        # 5. 使用 Model 进行总结（而非 Agent）
        try:
            new_interaction = await service.create_interaction(
                model="gemini-2.5-flash",  # 使用快速模型
                input=summarize_prompt,
                previous_interaction_id=interaction_id,
                background=False,  # 总结不需要后台执行
                store=True
            )
            
            # 6. 缓存新交互
            cache.cache_interaction(new_interaction.id, {
                'type': 'summarize',
                'format': request.format,
                'status': new_interaction.status,
                'previous_interaction_id': interaction_id,
                'created_at': datetime.now().isoformat()
            }, ttl=3600)
            
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            
            logger.info(f"Summary created: {new_interaction.id}")
            
            return ResearchStartResponse(
                interaction_id=new_interaction.id,
                status=new_interaction.status
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success=False)
            raise handle_gemini_error(e)
    
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(e)


@router.post("/format/{interaction_id}", response_model=ResearchStartResponse)
async def format_research(
    interaction_id: str,
    request: ResearchFormatRequest,
    authorization: str = Header(None),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_cache)
):
    """
    Format research results using Model
    
    Uses Agent for research, then uses Model to format the results
    into a specific format (JSON, XML, YAML, etc.).
    
    Args:
        interaction_id: Previous research interaction ID
        request: Format request with output_format and optional schema
        authorization: Bearer token for authentication
        rate_limiter: Rate limiting dependency
        cache: Cache dependency
        
    Returns:
        ResearchStartResponse with new interaction_id and status
        
    Raises:
        HTTPException: Authentication, rate limit, or validation errors
    """
    
    start_time = time.time()
    success = False
    
    try:
        # 1. 认证检查
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        api_key = authorization.split(' ')[1]
        user_id = extract_user_id(api_key)
        
        # 2. 速率限制检查
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试"
                }
            )
        
        # 3. 验证 previous_interaction_id 存在且已完成
        service = InteractionsService(api_key=api_key)
        try:
            previous_interaction = await service.get_interaction(interaction_id)
            if previous_interaction.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_ARGUMENT",
                        "message": f"Previous interaction must be completed (current status: {previous_interaction.status})"
                    }
                )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Previous interaction {interaction_id} not found"
                }
            )
        
        logger.info(f"Formatting research from interaction {interaction_id} to {request.output_format}")
        
        # 4. 构建格式化提示
        format_prompt = f"Please format the research findings as {request.output_format.upper()}"
        if request.output_schema:
            format_prompt += f" following this schema: {request.output_schema}"
        format_prompt += "."

        # 5. 使用 Model 进行格式化（可选使用结构化输出）
        try:
            generation_config = None
            response_format = None

            # 如果是 JSON 格式且提供了 schema，使用结构化输出
            if request.output_format.lower() == "json" and request.output_schema:
                response_format = request.output_schema
            
            new_interaction = await service.create_interaction(
                model="gemini-2.5-flash",  # 使用快速模型
                input=format_prompt,
                previous_interaction_id=interaction_id,
                background=False,  # 格式化不需要后台执行
                response_format=response_format,
                store=True
            )
            
            # 6. 缓存新交互
            cache.cache_interaction(new_interaction.id, {
                'type': 'format',
                'output_format': request.output_format,
                'status': new_interaction.status,
                'previous_interaction_id': interaction_id,
                'created_at': datetime.now().isoformat()
            }, ttl=3600)
            
            success = True
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success)
            
            logger.info(f"Format created: {new_interaction.id}")
            
            return ResearchStartResponse(
                interaction_id=new_interaction.id,
                status=new_interaction.status
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            performance_metrics.record_request(response_time, success=False)
            raise handle_gemini_error(e)
    
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(e)
