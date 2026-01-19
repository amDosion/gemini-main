"""
测试实际运行环境下的日志配置

模拟 FastAPI 应用启动和请求处理流程
"""

import sys
import os
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟 FastAPI 应用启动（导入 main.py 会触发 logger 配置）
print("=" * 80)
print("模拟 FastAPI 应用启动")
print("=" * 80)

# 导入 logger 配置（这会配置根 logger）
from app.core.logger import setup_root_logger, setup_logger
import logging

# 确保根 logger 已配置
setup_root_logger()

print("\n[启动检查] 根 logger 配置:")
root_logger = logging.getLogger()
print(f"  根 logger 级别: {root_logger.level} ({logging.getLevelName(root_logger.level)})")
print(f"  根 logger handlers: {len(root_logger.handlers)}")
if root_logger.handlers:
    for i, handler in enumerate(root_logger.handlers):
        print(f"    Handler {i}: {type(handler).__name__}, level: {handler.level}")

# 测试各个模块的 logger（模拟实际导入）
print("\n[模块导入测试] 模拟导入各个服务模块...")

# 模拟导入 modes.py
print("\n1. 导入 modes.py...")
from app.routers.core.modes import logger as modes_logger
print(f"   modes logger: {modes_logger.name}")
print(f"   modes logger level: {modes_logger.level}")
print(f"   modes logger propagate: {modes_logger.propagate}")
print(f"   modes logger handlers: {len(modes_logger.handlers)}")
modes_logger.info("[Modes] ✅ modes.py logger 测试")

# 模拟导入 GoogleService
print("\n2. 导入 GoogleService...")
from app.services.gemini.google_service import logger as google_logger
print(f"   GoogleService logger: {google_logger.name}")
print(f"   GoogleService logger level: {google_logger.level}")
print(f"   GoogleService logger propagate: {google_logger.propagate}")
print(f"   GoogleService logger handlers: {len(google_logger.handlers)}")
google_logger.info("[GoogleService] ✅ GoogleService logger 测试")

# 模拟导入 ImageGenerator
print("\n3. 导入 ImageGenerator...")
from app.services.gemini.image_generator import logger as image_gen_logger
print(f"   ImageGenerator logger: {image_gen_logger.name}")
print(f"   ImageGenerator logger level: {image_gen_logger.level}")
print(f"   ImageGenerator logger propagate: {image_gen_logger.propagate}")
print(f"   ImageGenerator logger handlers: {len(image_gen_logger.handlers)}")
image_gen_logger.info("[ImageGenerator] ✅ ImageGenerator logger 测试")

# 模拟导入 ImagenCoordinator
print("\n4. 导入 ImagenCoordinator...")
from app.services.gemini.imagen_coordinator import logger as coordinator_logger
print(f"   ImagenCoordinator logger: {coordinator_logger.name}")
print(f"   ImagenCoordinator logger level: {coordinator_logger.level}")
print(f"   ImagenCoordinator logger propagate: {coordinator_logger.propagate}")
print(f"   ImagenCoordinator logger handlers: {len(coordinator_logger.handlers)}")
coordinator_logger.info("[ImagenCoordinator] ✅ ImagenCoordinator logger 测试")

# 模拟导入 GeminiAPIImageGenerator
print("\n5. 导入 GeminiAPIImageGenerator...")
from app.services.gemini.imagen_gemini_api import logger as gemini_api_logger
print(f"   GeminiAPIImageGenerator logger: {gemini_api_logger.name}")
print(f"   GeminiAPIImageGenerator logger level: {gemini_api_logger.level}")
print(f"   GeminiAPIImageGenerator logger propagate: {gemini_api_logger.propagate}")
print(f"   GeminiAPIImageGenerator logger handlers: {len(gemini_api_logger.handlers)}")
gemini_api_logger.info("[GeminiAPIImageGenerator] ✅ GeminiAPIImageGenerator logger 测试")

# 模拟完整调用链
print("\n" + "=" * 80)
print("模拟完整调用链（模拟实际请求处理）")
print("=" * 80)

modes_logger.info("[Modes] ========== 开始处理模式请求 ==========")
modes_logger.info("[Modes] 📥 请求信息:")
modes_logger.info("[Modes]     - provider: google")
modes_logger.info("[Modes]     - mode: image-gen")
modes_logger.info("[Modes]     - user_id: test1234...")
modes_logger.info("[Modes]     - modelId: imagen-4.0-generate-preview-06-06")
modes_logger.info("[Modes]     - prompt长度: 4")
modes_logger.info("[Modes]     - attachments数量: 0")

modes_logger.info("[Modes] 🔄 [步骤1] 获取提供商凭证...")
modes_logger.info("[Modes] ✅ [步骤1] 凭证获取完成 (耗时: 5.12ms)")

modes_logger.info("[Modes] 🔄 [步骤2] 创建提供商服务...")
google_logger.info("[GoogleService] ========== 开始图片生成 ==========")
google_logger.info("[GoogleService] 📥 请求参数:")
google_logger.info("[GoogleService]     - model: imagen-4.0-generate-preview-06-06")
google_logger.info("[GoogleService]     - prompt: 欧洲女子")
google_logger.info("[GoogleService]     - prompt长度: 4")
google_logger.info("[GoogleService] 🔄 委托给 ImageGenerator.generate_image()...")

image_gen_logger.info("[ImageGenerator] ========== 开始图片生成 ==========")
image_gen_logger.info("[ImageGenerator] 📥 请求参数:")
image_gen_logger.info("[ImageGenerator]     - model: imagen-4.0-generate-preview-06-06")
image_gen_logger.info("[ImageGenerator]     - prompt: 欧洲女子")
image_gen_logger.info("[ImageGenerator] 🔄 [步骤2] 从 Coordinator 获取生成器...")

coordinator_logger.info("[ImagenCoordinator] 🔄 获取生成器...")
coordinator_logger.info("[ImagenCoordinator]     - api_mode: gemini_api")
coordinator_logger.info("[ImagenCoordinator] ✅ 使用缓存的 gemini_api 生成器")
coordinator_logger.info("[ImagenCoordinator]     - 生成器类型: GeminiAPIImageGenerator")

image_gen_logger.info("[ImageGenerator] ✅ [步骤2] 生成器获取完成: GeminiAPIImageGenerator")
image_gen_logger.info("[ImageGenerator] 🔄 [步骤3] 委托给生成器.generate_image()...")

gemini_api_logger.info("[GeminiAPIImageGenerator] ========== 开始生成图片 ==========")
gemini_api_logger.info("[GeminiAPIImageGenerator] 📥 请求参数:")
gemini_api_logger.info("[GeminiAPIImageGenerator]     - model: imagen-4.0-generate-preview-06-06")
gemini_api_logger.info("[GeminiAPIImageGenerator]     - prompt: 欧洲女子")
gemini_api_logger.info("[GeminiAPIImageGenerator] 🔄 [步骤3] 调用 Gemini API generate_images()...")
gemini_api_logger.info("[GeminiAPIImageGenerator] ✅ [步骤3] API调用完成 (耗时: 1234.56ms)")
gemini_api_logger.info("[GeminiAPIImageGenerator] ✅ [步骤4] 响应处理完成 (耗时: 5.67ms)")
gemini_api_logger.info("[GeminiAPIImageGenerator] ========== 图片生成完成 (总耗时: 1245.23ms) ==========")

image_gen_logger.info("[ImageGenerator] ✅ [步骤3] 生成器调用完成 (耗时: 1245.23ms)")
image_gen_logger.info("[ImageGenerator] ========== 图片生成完成 (总耗时: 1245.23ms) ==========")

google_logger.info("[GoogleService] ✅ 图片生成完成 (耗时: 1250.34ms)")
google_logger.info("[GoogleService] ========== 图片生成流程结束 ==========")

modes_logger.info("[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: 1250.34ms)")
modes_logger.info("[Modes] ========== 模式请求处理完成 (总耗时: 1500.00ms) ==========")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
print("\n如果上面的日志都正常显示，说明日志配置正确。")
print("如果某些日志没有显示，请检查：")
print("1. 根 logger 是否有 handler")
print("2. 子 logger 的 propagate 是否为 True")
print("3. 子 logger 的级别是否设置为 INFO 或更低")
