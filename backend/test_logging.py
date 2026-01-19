"""
测试日志配置脚本

用于验证：
1. 根 logger 是否正常配置
2. 子 logger（使用 __name__）是否能正常输出
3. 各个服务模块的 logger 是否能正常输出
4. 是否有日志重复问题
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入日志配置（这会配置根 logger）
from app.core.logger import setup_root_logger, setup_logger
import logging

print("=" * 80)
print("开始测试日志配置")
print("=" * 80)

# 1. 测试根 logger
print("\n[测试1] 根 logger 配置")
root_logger = logging.getLogger()
print(f"  根 logger 级别: {root_logger.level}")
print(f"  根 logger handlers 数量: {len(root_logger.handlers)}")
if root_logger.handlers:
    print(f"  根 logger handler 类型: {type(root_logger.handlers[0]).__name__}")
root_logger.info("✅ 根 logger 测试日志")

# 2. 测试 modes.py 的 logger（使用 __name__）
print("\n[测试2] modes.py logger (backend.app.routers.core.modes)")
modes_logger = logging.getLogger("backend.app.routers.core.modes")
modes_logger.setLevel(logging.INFO)
modes_logger.propagate = True
print(f"  logger 名称: {modes_logger.name}")
print(f"  logger 级别: {modes_logger.level}")
print(f"  logger propagate: {modes_logger.propagate}")
print(f"  logger handlers 数量: {len(modes_logger.handlers)}")
modes_logger.info("[Modes] ========== 开始处理模式请求 ==========")
modes_logger.info("[Modes] 📥 请求信息:")
modes_logger.info("[Modes]     - provider: google")
modes_logger.info("[Modes]     - mode: image-gen")

# 3. 测试 GoogleService 的 logger
print("\n[测试3] GoogleService logger (backend.app.services.gemini.google_service)")
google_logger = logging.getLogger("backend.app.services.gemini.google_service")
google_logger.setLevel(logging.INFO)
google_logger.propagate = True
print(f"  logger 名称: {google_logger.name}")
print(f"  logger 级别: {google_logger.level}")
print(f"  logger propagate: {google_logger.propagate}")
print(f"  logger handlers 数量: {len(google_logger.handlers)}")
google_logger.info("[GoogleService] ========== 开始图片生成 ==========")
google_logger.info("[GoogleService] 📥 请求参数:")
google_logger.info("[GoogleService]     - model: imagen-4.0-generate-preview-06-06")

# 4. 测试 ImageGenerator 的 logger
print("\n[测试4] ImageGenerator logger (backend.app.services.gemini.image_generator)")
image_gen_logger = logging.getLogger("backend.app.services.gemini.image_generator")
image_gen_logger.setLevel(logging.INFO)
image_gen_logger.propagate = True
print(f"  logger 名称: {image_gen_logger.name}")
print(f"  logger 级别: {image_gen_logger.level}")
print(f"  logger propagate: {image_gen_logger.propagate}")
print(f"  logger handlers 数量: {len(image_gen_logger.handlers)}")
image_gen_logger.info("[ImageGenerator] ========== 开始图片生成 ==========")
image_gen_logger.info("[ImageGenerator] 🔄 [步骤2] 从 Coordinator 获取生成器...")

# 5. 测试 ImagenCoordinator 的 logger
print("\n[测试5] ImagenCoordinator logger (backend.app.services.gemini.imagen_coordinator)")
coordinator_logger = logging.getLogger("backend.app.services.gemini.imagen_coordinator")
coordinator_logger.setLevel(logging.INFO)
coordinator_logger.propagate = True
print(f"  logger 名称: {coordinator_logger.name}")
print(f"  logger 级别: {coordinator_logger.level}")
print(f"  logger propagate: {coordinator_logger.propagate}")
print(f"  logger handlers 数量: {len(coordinator_logger.handlers)}")
coordinator_logger.info("[ImagenCoordinator] 🔄 获取生成器...")
coordinator_logger.info("[ImagenCoordinator]     - api_mode: gemini_api")

# 6. 测试 GeminiAPIImageGenerator 的 logger
print("\n[测试6] GeminiAPIImageGenerator logger (backend.app.services.gemini.imagen_gemini_api)")
gemini_api_logger = logging.getLogger("backend.app.services.gemini.imagen_gemini_api")
gemini_api_logger.setLevel(logging.INFO)
gemini_api_logger.propagate = True
print(f"  logger 名称: {gemini_api_logger.name}")
print(f"  logger 级别: {gemini_api_logger.level}")
print(f"  logger propagate: {gemini_api_logger.propagate}")
print(f"  logger handlers 数量: {len(gemini_api_logger.handlers)}")
gemini_api_logger.info("[GeminiAPIImageGenerator] ========== 开始生成图片 ==========")
gemini_api_logger.info("[GeminiAPIImageGenerator] 🔄 [步骤3] 调用 Gemini API generate_images()...")

# 7. 测试完整调用链（模拟实际调用）
print("\n[测试7] 完整调用链模拟")
print("  模拟从 modes.py -> GoogleService -> ImageGenerator -> ImagenCoordinator -> GeminiAPIImageGenerator")
modes_logger.info("[Modes] ========== 开始处理模式请求 ==========")
modes_logger.info("[Modes] 🔄 [步骤6] 调用服务方法: GoogleService.generate_image()...")
google_logger.info("[GoogleService] ========== 开始图片生成 ==========")
google_logger.info("[GoogleService] 🔄 委托给 ImageGenerator.generate_image()...")
image_gen_logger.info("[ImageGenerator] ========== 开始图片生成 ==========")
image_gen_logger.info("[ImageGenerator] 🔄 [步骤2] 从 Coordinator 获取生成器...")
coordinator_logger.info("[ImagenCoordinator] 🔄 获取生成器...")
coordinator_logger.info("[ImagenCoordinator] ✅ 使用缓存的 gemini_api 生成器")
image_gen_logger.info("[ImageGenerator] ✅ [步骤2] 生成器获取完成: GeminiAPIImageGenerator")
image_gen_logger.info("[ImageGenerator] 🔄 [步骤3] 委托给生成器.generate_image()...")
gemini_api_logger.info("[GeminiAPIImageGenerator] ========== 开始生成图片 ==========")
gemini_api_logger.info("[GeminiAPIImageGenerator] ✅ [步骤3] API调用完成 (耗时: 1234.56ms)")
gemini_api_logger.info("[GeminiAPIImageGenerator] ========== 图片生成完成 (总耗时: 1245.23ms) ==========")
image_gen_logger.info("[ImageGenerator] ✅ [步骤3] 生成器调用完成 (耗时: 1245.23ms)")
google_logger.info("[GoogleService] ✅ 图片生成完成 (耗时: 1250.34ms)")
modes_logger.info("[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: 1250.34ms)")
modes_logger.info("[Modes] ========== 模式请求处理完成 (总耗时: 1500.00ms) ==========")

# 8. 检查是否有重复日志
print("\n[测试8] 检查日志重复问题")
print("  如果上面的日志每条都只出现一次，说明没有重复问题")
print("  如果某些日志出现多次，说明有重复问题")

# 9. 测试 main logger（应该有独立的 handler）
print("\n[测试9] main logger 配置")
main_logger = setup_logger("main")
print(f"  logger 名称: {main_logger.name}")
print(f"  logger 级别: {main_logger.level}")
print(f"  logger propagate: {main_logger.propagate}")
print(f"  logger handlers 数量: {len(main_logger.handlers)}")
main_logger.info("[Main] 这是 main logger 的测试日志（应该只出现一次）")

print("\n" + "=" * 80)
print("日志配置测试完成")
print("=" * 80)
print("\n请检查上面的日志输出：")
print("1. 每个服务的日志是否都正常显示？")
print("2. 是否有日志重复？")
print("3. 日志格式是否正确（包含时间戳、logger名称、级别、消息）？")
