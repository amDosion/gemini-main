"""
测试脚本：验证 Google API 返回的模型列表

这个脚本会：
1. 直接调用 Google API 获取原始模型列表
2. 检查是否包含 imagen-4.0 等图像生成模型
3. 验证我们的 model_capabilities.py 是否正确处理这些模型
"""

import os
import sys
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_google_api_models():
    """直接调用 Google API 获取模型列表"""
    print("=" * 60)
    print("步骤 1: 直接调用 Google API 获取原始模型列表")
    print("=" * 60)
    
    try:
        import google.generativeai as genai
        
        # 从环境变量或 .env 文件获取 API Key
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            # 尝试从 .env 文件读取
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GOOGLE_API_KEY=") or line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip('"\'')
                            break
        
        if not api_key:
            print("❌ 错误: 未找到 GOOGLE_API_KEY")
            print("请设置环境变量或在 backend/.env 文件中配置")
            return None
        
        print(f"✅ 找到 API Key: {api_key[:10]}...{api_key[-4:]}")
        
        # 配置 Google API
        genai.configure(api_key=api_key)
        
        # 获取所有模型
        all_models = list(genai.list_models())
        print(f"\n📊 Google API 返回的模型总数: {len(all_models)}")
        
        # 分类统计
        imagen_models = []
        gemini_models = []
        other_models = []
        
        for model in all_models:
            model_id = model.name.replace("models/", "")
            model_info = {
                "id": model_id,
                "name": model.display_name if hasattr(model, 'display_name') else model_id,
                "supported_methods": list(model.supported_generation_methods) if hasattr(model, 'supported_generation_methods') else [],
                "description": model.description if hasattr(model, 'description') else ""
            }
            
            if "imagen" in model_id.lower():
                imagen_models.append(model_info)
            elif "gemini" in model_id.lower():
                gemini_models.append(model_info)
            else:
                other_models.append(model_info)
        
        print(f"\n📸 Imagen 模型数量: {len(imagen_models)}")
        print(f"🤖 Gemini 模型数量: {len(gemini_models)}")
        print(f"📦 其他模型数量: {len(other_models)}")
        
        # 详细列出 Imagen 模型
        print("\n" + "=" * 60)
        print("Imagen 模型详情:")
        print("=" * 60)
        if imagen_models:
            for m in imagen_models:
                print(f"  - {m['id']}")
                print(f"    支持的方法: {m['supported_methods']}")
        else:
            print("  ❌ 没有找到 Imagen 模型!")
        
        # 列出支持 generateContent 的 Gemini 模型
        print("\n" + "=" * 60)
        print("支持 generateContent 的 Gemini 模型:")
        print("=" * 60)
        for m in gemini_models:
            if "generateContent" in m['supported_methods']:
                print(f"  - {m['id']}")
        
        return {
            "total": len(all_models),
            "imagen": imagen_models,
            "gemini": gemini_models,
            "other": other_models
        }
        
    except Exception as e:
        print(f"❌ 调用 Google API 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_our_filter():
    """测试我们的 model_capabilities.py 过滤逻辑"""
    print("\n" + "=" * 60)
    print("步骤 2: 测试我们的 model_capabilities.py")
    print("=" * 60)
    
    from app.services.model_capabilities import get_google_capabilities, build_model_config
    
    # 测试 imagen 模型
    test_models = [
        "imagen-4.0-generate-001",
        "imagen-4.0-ultra-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-3.0-generate-001",
        "gemini-2.0-flash-exp",
        "gemini-2.5-pro",
        "gemini-1.5-pro",
    ]
    
    print("\n测试模型能力推断:")
    for model_id in test_models:
        caps = get_google_capabilities(model_id)
        config = build_model_config("google", model_id)
        print(f"\n  {model_id}:")
        print(f"    vision={caps.vision}, search={caps.search}, reasoning={caps.reasoning}, coding={caps.coding}")


def test_google_service():
    """测试 GoogleService.get_available_models()"""
    print("\n" + "=" * 60)
    print("步骤 3: 测试 GoogleService.get_available_models()")
    print("=" * 60)
    
    import asyncio
    from app.services.google_service import GoogleService
    
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_API_KEY=") or line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip('"\'')
                        break
    
    if not api_key:
        print("❌ 错误: 未找到 GOOGLE_API_KEY")
        return
    
    async def run_test():
        service = GoogleService(api_key=api_key)
        models = await service.get_available_models()
        
        print(f"\n📊 GoogleService 返回的模型数量: {len(models)}")
        
        # 检查 imagen 模型
        imagen_models = [m for m in models if "imagen" in m.id.lower()]
        print(f"\n📸 Imagen 模型数量: {len(imagen_models)}")
        
        if imagen_models:
            print("\nImagen 模型详情:")
            for m in imagen_models:
                print(f"  - {m.id}")
                print(f"    capabilities: vision={m.capabilities.vision}, search={m.capabilities.search}")
        else:
            print("  ❌ GoogleService 没有返回 Imagen 模型!")
            print("\n  可能的原因:")
            print("  1. Google API 没有返回 imagen 模型（需要特殊权限？）")
            print("  2. 我们的过滤逻辑排除了这些模型")
        
        # 检查过滤条件
        print("\n" + "=" * 60)
        print("检查过滤条件 (generateContent):")
        print("=" * 60)
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        all_models = list(genai.list_models())
        
        for model in all_models:
            model_id = model.name.replace("models/", "")
            if "imagen" in model_id.lower():
                methods = list(model.supported_generation_methods) if hasattr(model, 'supported_generation_methods') else []
                has_generate = "generateContent" in methods
                print(f"  {model_id}:")
                print(f"    supported_methods: {methods}")
                print(f"    通过 generateContent 过滤: {'✅ 是' if has_generate else '❌ 否'}")
    
    asyncio.run(run_test())


if __name__ == "__main__":
    print("🔍 Google 模型 API 完整链路测试")
    print("=" * 60)
    
    # 步骤 1: 直接调用 Google API
    raw_models = test_google_api_models()
    
    # 步骤 2: 测试我们的能力推断
    test_our_filter()
    
    # 步骤 3: 测试 GoogleService
    test_google_service()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
