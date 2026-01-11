"""
测试参考目录中的 SDK 是否可以直接运行

使用方法: python backend/scripts/test_reference_sdk.py
"""

import sys
import os
from pathlib import Path

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# 获取项目根目录
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent

# 参考 SDK 路径
reference_sdk_path = project_root / ".kiro" / "specs" / "参考" / "python-genai-main"

print("=" * 80)
print("测试参考 SDK 是否可以直接运行")
print("=" * 80)
print()

# 检查目录是否存在
if not reference_sdk_path.exists():
    print(f"❌ 参考目录不存在: {reference_sdk_path}")
    sys.exit(1)

print(f"✅ 参考目录存在: {reference_sdk_path}")
print()

# 方法 1: 添加到 Python 路径直接导入
print("方法 1: 添加到 Python 路径")
print("-" * 80)

google_path = reference_sdk_path / "google"
if str(google_path.parent) not in sys.path:
    sys.path.insert(0, str(google_path.parent))
    print(f"✅ 已添加路径: {google_path.parent}")

try:
    from google import genai
    print(f"✅ 成功导入 google.genai")
    print(f"   模块路径: {genai.__file__}")
    print(f"   版本: {getattr(genai, '__version__', 'unknown')}")
    
    # 测试创建客户端（不需要真实 API key）
    try:
        client = genai.Client(api_key="test-key")
        print("✅ 客户端创建成功")
    except Exception as e:
        print(f"⚠️  客户端创建失败（这是正常的，因为没有有效 API key）")
        print(f"   错误: {str(e)[:100]}")
    
    # 检查关键模块
    key_modules = ['models', 'client', 'types', 'live']
    for module_name in key_modules:
        try:
            module = getattr(genai, module_name, None)
            if module:
                print(f"✅ {module_name} 模块可用")
            else:
                print(f"⚠️  {module_name} 模块不可用")
        except Exception as e:
            print(f"❌ {module_name} 模块导入失败: {e}")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print()
    print("可能的原因：")
    print("1. 缺少依赖包（google-auth, pydantic, httpx 等）")
    print("2. Python 版本不兼容（需要 Python >= 3.10）")
    print("3. 代码结构不完整")
    sys.exit(1)

print()
print("=" * 80)
print("方法 2: 检查依赖")
print("-" * 80)

# 检查关键依赖
required_packages = [
    'google.auth',
    'pydantic',
    'httpx',
    'websockets',
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package.replace('.', '_') if '.' in package else package)
        print(f"✅ {package} 已安装")
    except ImportError:
        print(f"❌ {package} 未安装")
        missing_packages.append(package)

if missing_packages:
    print()
    print("⚠️  缺少以下依赖包：")
    for pkg in missing_packages:
        print(f"   - {pkg}")
    print()
    print("安装命令：")
    print("pip install google-auth pydantic httpx websockets")

print()
print("=" * 80)
print("结论")
print("=" * 80)

if missing_packages:
    print("⚠️  参考 SDK 代码完整，但需要安装依赖后才能使用")
    print()
    print("建议：")
    print("1. 安装依赖: pip install -r .kiro/specs/参考/python-genai-main/requirements.txt")
    print("2. 或安装完整包: pip install google-genai")
    print("3. 然后可以直接使用参考代码")
else:
    print("✅ 参考 SDK 可以直接使用！")
    print()
    print("使用方法：")
    print("1. 将参考代码添加到 Python 路径")
    print("2. 直接导入: from google import genai")
    print("3. 使用: client = genai.Client(api_key='your-key')")
