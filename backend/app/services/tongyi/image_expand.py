"""
图片扩展（Out-Painting）服务
封装 DashScope API 调用逻辑

⚠️ 注意：DashScope API 对图片大小有限制
当图片下载失败时，后端会：
1. 下载图片
2. 上传到 DashScope 临时 OSS（使用 dashscope_file_upload 服务）
3. 使用 oss:// URL 调用 DashScope API
"""
from typing import Optional, Tuple
from dataclasses import dataclass
import requests
import time
import logging

# 导入独立的上传服务
from .file_upload import upload_bytes_to_dashscope

logger = logging.getLogger(__name__)

# DashScope API 配置
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


@dataclass
class OutPaintingResult:
    """扩图结果"""
    success: bool
    task_id: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None


class ImageExpandService:
    """图片扩展服务"""

    @staticmethod
    def download_image(url: str) -> Optional[bytes]:
        """下载图片"""
        try:
            logger.info(f"[OutPainting] 下载图片: {url[:60]}...")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                logger.info(f"[OutPainting] 下载成功，大小: {len(response.content)} bytes")
                return response.content
            else:
                logger.warning(f"[OutPainting] 下载失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[OutPainting] 下载异常: {str(e)}")
            return None

    @staticmethod
    def is_download_error(error: str) -> bool:
        """
        检测是否为图片下载相关错误
        
        匹配的错误类型：
        1. "Download...timed out" - 下载超时
        2. "InvalidParameter.FileDownload" - 下载失败
        3. "download for input_image error" - 下载错误
        """
        if not error:
            return False
        error_lower = error.lower()
        return (
            ("download" in error_lower and "timed out" in error_lower) or
            ("filedownload" in error_lower) or
            ("download" in error_lower and "error" in error_lower)
        )

    @staticmethod
    def build_parameters(
        mode: str,
        x_scale: float = 2.0,
        y_scale: float = 2.0,
        left_offset: int = 0,
        right_offset: int = 0,
        top_offset: int = 0,
        bottom_offset: int = 0,
        angle: int = 0,
        output_ratio: str = "16:9"
    ) -> dict:
        """
        构建扩图参数
        
        Args:
            mode: 扩图模式（scale/offset/ratio）
            其他参数根据模式不同而不同
        
        Returns:
            DashScope API 参数字典
        """
        # 固定参数（不暴露给前端）
        parameters = {
            "best_quality": True,           # 始终使用最佳质量
            "limit_image_size": False,      # 不限制图片大小
            "add_watermark": False          # 不添加水印
        }
        
        if mode == "offset":
            # Offset 模式（像素偏移）
            parameters["left_offset"] = left_offset
            parameters["right_offset"] = right_offset
            parameters["top_offset"] = top_offset
            parameters["bottom_offset"] = bottom_offset
            # 如果所有偏移都是 0，默认向右扩展
            if not any([left_offset, right_offset, top_offset, bottom_offset]):
                parameters["right_offset"] = 512
        elif mode == "ratio":
            # Ratio 模式（比例）
            parameters["angle"] = angle
            parameters["output_ratio"] = output_ratio
        else:
            # Scale 模式（缩放，默认）
            parameters["x_scale"] = x_scale
            parameters["y_scale"] = y_scale
        
        return parameters


    def submit_task(
        self,
        image_url: str,
        api_key: str,
        parameters: dict,
        use_oss_resolve: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        提交扩图任务
        
        Args:
            image_url: 图片 URL
            api_key: DashScope API Key
            parameters: 扩图参数
            use_oss_resolve: 是否使用 OSS 资源解析（oss:// URL 需要）
        
        Returns:
            (success, task_id, error_msg)
        """
        submit_url = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/image2image/out-painting"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }
        
        # 如果使用 oss:// URL，需要添加 OssResourceResolve 头
        if use_oss_resolve:
            headers["X-DashScope-OssResourceResolve"] = "enable"
        
        body = {
            "model": "image-out-painting",
            "input": {
                "image_url": image_url
            },
            "parameters": parameters
        }
        
        logger.info(f"[OutPainting] 提交任务，参数: {parameters}")
        
        try:
            response = requests.post(submit_url, headers=headers, json=body, timeout=30)
            
            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except:
                    pass
                logger.error(f"[OutPainting] 提交失败: {error_msg}")
                return False, None, error_msg
            
            task_id = response.json().get("output", {}).get("task_id")
            if not task_id:
                return False, None, "未获取到任务 ID"
            
            logger.info(f"[OutPainting] 任务已提交: {task_id}")
            return True, task_id, None
            
        except requests.Timeout:
            return False, None, "请求超时"
        except Exception as e:
            return False, None, str(e)

    def poll_task(self, task_id: str, api_key: str, max_retries: int = 120) -> OutPaintingResult:
        """
        轮询任务状态
        
        Args:
            task_id: 任务 ID
            api_key: DashScope API Key
            max_retries: 最大重试次数（默认 120 次，每次 5 秒，共 10 分钟）
        
        Returns:
            OutPaintingResult
        """
        task_url = f"{DASHSCOPE_BASE_URL}/api/v1/tasks/{task_id}"
        task_headers = {"Authorization": f"Bearer {api_key}"}
        
        for i in range(max_retries):
            time.sleep(5)
            
            try:
                task_response = requests.get(task_url, headers=task_headers, timeout=30)
                if task_response.status_code != 200:
                    continue
                
                task_data = task_response.json()
                task_status = task_data.get("output", {}).get("task_status")
                
                if task_status == "SUCCEEDED":
                    output_url = task_data.get("output", {}).get("output_image_url")
                    logger.info(f"[OutPainting] 任务成功: {output_url}")
                    return OutPaintingResult(
                        success=True,
                        task_id=task_id,
                        output_url=output_url
                    )
                elif task_status == "FAILED":
                    error_msg = task_data.get("output", {}).get("message", "任务失败")
                    error_code = task_data.get("output", {}).get("code", "")
                    logger.error(f"[OutPainting] 任务失败: {error_code} - {error_msg}")
                    return OutPaintingResult(
                        success=False,
                        task_id=task_id,
                        error=f"{error_code}: {error_msg}"
                    )
                else:
                    logger.debug(f"[OutPainting] 任务处理中: {task_status} ({i+1}/{max_retries})")
            except Exception as e:
                logger.error(f"[OutPainting] 轮询异常: {str(e)}")
                continue
        
        return OutPaintingResult(
            success=False,
            task_id=task_id,
            error="任务超时（10分钟）"
        )

    def execute_with_fallback(
        self,
        image_url: str,
        api_key: str,
        parameters: dict
    ) -> OutPaintingResult:
        """
        执行扩图任务（带备用方案）
        
        如果首次提交失败或任务执行失败（图片下载错误），
        会自动尝试上传到 DashScope OSS 后重试
        
        Args:
            image_url: 图片 URL
            api_key: DashScope API Key
            parameters: 扩图参数
        
        Returns:
            OutPaintingResult
        """
        logger.info(f"[OutPainting] 原始图片 URL: {image_url}")
        
        # ✅ 检测是否是 oss:// URL，如果是则需要启用 OssResourceResolve
        is_oss_url = image_url.startswith("oss://")
        if is_oss_url:
            logger.info(f"[OutPainting] 检测到 oss:// URL，启用 OssResourceResolve")
        
        # 1. 首次提交任务
        success, task_id, error_msg = self.submit_task(
            image_url, api_key, parameters, 
            use_oss_resolve=is_oss_url  # ✅ 根据 URL 类型自动设置
        )
        
        if not success:
            # 检查是否为图片下载错误
            if self.is_download_error(error_msg or ""):
                return self._retry_with_oss(image_url, api_key, parameters)
            return OutPaintingResult(success=False, error=f"提交任务失败: {error_msg}")
        
        # 2. 轮询任务状态
        result = self.poll_task(task_id, api_key)
        
        # 3. 如果任务失败且是图片下载错误，尝试备用方案
        if not result.success and self.is_download_error(result.error or ""):
            return self._retry_with_oss(image_url, api_key, parameters)
        
        return result

    def _retry_with_oss(
        self,
        original_url: str,
        api_key: str,
        parameters: dict
    ) -> OutPaintingResult:
        """
        使用 DashScope OSS 重试
        
        1. 下载原图
        2. 上传到 DashScope OSS（使用独立的上传服务）
        3. 使用 oss:// URL 重新提交任务
        """
        logger.info(f"[OutPainting] 图片下载失败，尝试备用方案（上传到 DashScope OSS）...")
        
        # 1. 下载图片
        image_data = self.download_image(original_url)
        if not image_data:
            return OutPaintingResult(success=False, error="备用方案失败：无法下载原图")
        
        # 2. 上传到 DashScope OSS（使用独立的上传服务）
        logger.info(f"[OutPainting] 图片大小: {len(image_data)} bytes，上传到 DashScope OSS...")
        filename = f"expand-{int(time.time())}.png"
        upload_result = upload_bytes_to_dashscope(image_data, filename, api_key)
        if not upload_result.success:
            return OutPaintingResult(success=False, error=f"备用方案失败：{upload_result.error}")
        
        # 3. 使用 oss:// URL 重新提交任务
        logger.info(f"[OutPainting] 使用 DashScope OSS URL 重新提交: {upload_result.oss_url}")
        success, task_id, error_msg = self.submit_task(upload_result.oss_url, api_key, parameters, use_oss_resolve=True)
        
        if not success:
            return OutPaintingResult(success=False, error=f"备用方案提交失败: {error_msg}")
        
        # 4. 轮询任务状态
        return self.poll_task(task_id, api_key)


# 单例实例
image_expand_service = ImageExpandService()
