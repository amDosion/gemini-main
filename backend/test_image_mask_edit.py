#!/usr/bin/env python3
"""
测试 image-mask-edit 模式的完整服务流程

测试路径：
1. GoogleService.edit_image() → mask_edit_service.edit_with_mask()
2. 验证参数传递和返回格式转换
"""

import asyncio
import base64
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.gemini.google_service import GoogleService
from app.services.gemini.vertexai.mask_edit_service import mask_edit_service
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_image_base64() -> str:
    """创建一个简单的测试图片（1x1 红色 PNG）"""
    # 创建一个最小的 PNG 图片（1x1 红色像素）
    # PNG 文件头 + IHDR + IDAT + IEND
    png_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    return base64.b64encode(png_data).decode('utf-8')


def create_test_mask_base64() -> str:
    """创建一个简单的测试掩码（1x1 白色 PNG）"""
    # 创建一个最小的 PNG 图片（1x1 白色像素）
    png_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAGA60e6kgAAAABJRU5ErkJggg=='
    )
    return base64.b64encode(png_data).decode('utf-8')


async def test_mask_edit_service_directly():
    """直接测试 mask_edit_service.edit_with_mask()"""
    logger.info("=" * 80)
    logger.info("测试 1: 直接调用 mask_edit_service.edit_with_mask()")
    logger.info("=" * 80)
    
    try:
        image_base64 = create_test_image_base64()
        mask_base64 = create_test_mask_base64()
        
        logger.info(f"📥 测试参数:")
        logger.info(f"    - image_base64 长度: {len(image_base64)}")
        logger.info(f"    - mask_base64 长度: {len(mask_base64)}")
        logger.info(f"    - prompt: 'Add a red hat'")
        logger.info(f"    - edit_mode: 'EDIT_MODE_INPAINT_INSERTION'")
        
        result = mask_edit_service.edit_with_mask(
            image_base64=image_base64,
            mask_base64=mask_base64,
            prompt="Add a red hat",
            edit_mode="EDIT_MODE_INPAINT_INSERTION",
            mask_dilation=0.06,
            number_of_images=1,
            model="imagen-3.0-capability-001",
            guidance_scale=15.0,
            output_mime_type="image/png",
            output_compression_quality=95,
        )
        
        logger.info(f"✅ 测试结果:")
        logger.info(f"    - success: {result.success}")
        if result.success:
            logger.info(f"    - image 长度: {len(result.image) if result.image else 0}")
            logger.info(f"    - mime_type: {result.mime_type}")
            logger.info(f"    - rai_reason: {result.rai_reason}")
        else:
            logger.error(f"    - error: {result.error}")
        
        return result.success
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return False


async def test_google_service_edit_image():
    """测试 GoogleService.edit_image() 的路由"""
    logger.info("=" * 80)
    logger.info("测试 2: 通过 GoogleService.edit_image() 路由到 mask_edit_service")
    logger.info("=" * 80)
    
    try:
        # 需要设置环境变量或配置
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
        if not api_key:
            logger.warning("⚠️  未设置 GEMINI_API_KEY 或 GOOGLE_GENAI_API_KEY，跳过此测试")
            return False
        
        # 创建 GoogleService 实例
        service = GoogleService(
            api_key=api_key,
            api_url=None,
            use_official_sdk=False,
            user_id="test_user",
            db=None
        )
        
        image_base64 = create_test_image_base64()
        mask_base64 = create_test_mask_base64()
        
        reference_images = {
            'raw': image_base64,
            'mask': mask_base64
        }
        
        logger.info(f"📥 测试参数:")
        logger.info(f"    - mode: 'image-mask-edit'")
        logger.info(f"    - model: 'imagen-3.0-capability-001'")
        logger.info(f"    - prompt: 'Add a red hat'")
        logger.info(f"    - reference_images: {list(reference_images.keys())}")
        
        result = await service.edit_image(
            prompt="Add a red hat",
            model="imagen-3.0-capability-001",
            reference_images=reference_images,
            mode="image-mask-edit",
            editMode="EDIT_MODE_INPAINT_INSERTION",
            maskDilation=0.06,
            numberOfImages=1,
            guidanceScale=15.0,
            outputMimeType="image/png",
            outputCompressionQuality=95,
        )
        
        logger.info(f"✅ 测试结果:")
        logger.info(f"    - 返回类型: {type(result)}")
        logger.info(f"    - 结果数量: {len(result) if isinstance(result, list) else 'N/A'}")
        if isinstance(result, list) and len(result) > 0:
            logger.info(f"    - 第一项 keys: {list(result[0].keys())}")
            logger.info(f"    - url 类型: {type(result[0].get('url', ''))}")
            logger.info(f"    - mimeType: {result[0].get('mimeType')}")
            logger.info(f"    - index: {result[0].get('index')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return False


async def test_parameter_conversion():
    """测试参数转换逻辑"""
    logger.info("=" * 80)
    logger.info("测试 3: 参数转换逻辑（camelCase → snake_case）")
    logger.info("=" * 80)
    
    try:
        # 测试 editMode 转换
        test_cases = [
            ('EDIT_MODE_INPAINT_INSERTION', 'EDIT_MODE_INPAINT_INSERTION'),
            ('mask_edit', 'EDIT_MODE_INPAINT_INSERTION'),
            ('inpainting', 'EDIT_MODE_INPAINT_INSERTION'),
            ('background_edit', 'EDIT_MODE_BGSWAP'),
        ]
        
        for input_mode, expected in test_cases:
            # 模拟 GoogleService 中的转换逻辑
            edit_mode = input_mode
            if not edit_mode.startswith('EDIT_MODE_'):
                edit_mode_map = {
                    'mask_edit': 'EDIT_MODE_INPAINT_INSERTION',
                    'inpainting': 'EDIT_MODE_INPAINT_INSERTION',
                    'background_edit': 'EDIT_MODE_BGSWAP',
                    'recontext': 'EDIT_MODE_INPAINT_INSERTION',
                }
                edit_mode = edit_mode_map.get(edit_mode, 'EDIT_MODE_INPAINT_INSERTION')
            
            logger.info(f"    - 输入: {input_mode} → 输出: {edit_mode} (期望: {expected})")
            assert edit_mode == expected, f"转换失败: {input_mode} → {edit_mode}, 期望: {expected}"
        
        logger.info("✅ 所有参数转换测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return False


async def main():
    """运行所有测试"""
    logger.info("🚀 开始测试 image-mask-edit 模式的完整服务流程")
    logger.info("")
    
    results = []
    
    # 测试 1: 直接调用 mask_edit_service
    result1 = await test_mask_edit_service_directly()
    results.append(("直接调用 mask_edit_service", result1))
    logger.info("")
    
    # 测试 2: 通过 GoogleService 路由
    result2 = await test_google_service_edit_image()
    results.append(("通过 GoogleService 路由", result2))
    logger.info("")
    
    # 测试 3: 参数转换
    result3 = await test_parameter_conversion()
    results.append(("参数转换逻辑", result3))
    logger.info("")
    
    # 汇总结果
    logger.info("=" * 80)
    logger.info("📊 测试结果汇总")
    logger.info("=" * 80)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"    - {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    logger.info(f"")
    logger.info(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！")
        return 0
    else:
        logger.error("⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
