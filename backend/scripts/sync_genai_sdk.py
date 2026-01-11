"""
同步 Google GenAI SDK 参考代码

从参考目录复制最新代码到项目本地目录
使用方法: python backend/scripts/sync_genai_sdk.py
"""

import shutil
from pathlib import Path
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_genai_sdk():
    """同步参考代码到本地目录"""
    
    # 获取脚本所在目录，然后找到项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    # 路径定义
    reference_path = project_root / ".kiro" / "specs" / "参考" / "python-genai-main" / "google" / "genai"
    local_path = project_root / "backend" / "app" / "lib" / "google" / "genai"
    
    print(f"项目根目录: {project_root}")
    print(f"参考目录: {reference_path}")
    print(f"目标目录: {local_path}")
    print("-" * 80)
    
    # 检查参考目录是否存在
    if not reference_path.exists():
        logger.error(f"❌ 参考目录不存在: {reference_path}")
        logger.info("请确保参考代码在正确的位置")
        return False
    
    logger.info(f"✅ 找到参考目录: {reference_path}")
    
    # 创建目标目录
    local_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果目标目录已存在，先备份
    if local_path.exists():
        backup_path = local_path.parent / "genai_backup"
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(local_path, backup_path)
        logger.info(f"📦 已备份现有代码到: {backup_path}")
        shutil.rmtree(local_path)
    
    # 复制新代码
    logger.info("正在复制代码...")
    shutil.copytree(reference_path, local_path)
    logger.info(f"✅ 同步完成: {reference_path} -> {local_path}")
    
    # 创建必要的 __init__.py 文件
    google_init = local_path.parent / "__init__.py"
    if not google_init.exists():
        google_init.write_text("# Google package\n")
        logger.info(f"✅ 创建了 {google_init}")
    
    # 检查关键文件
    key_files = ['__init__.py', 'client.py', 'models.py']
    missing_files = []
    for file in key_files:
        if not (local_path / file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.warning(f"⚠️  缺少关键文件: {missing_files}")
        return False
    
    logger.info("✅ 所有关键文件检查通过")
    return True

if __name__ == "__main__":
    print("=" * 80)
    print("Google GenAI SDK 同步工具")
    print("=" * 80)
    print()
    
    success = sync_genai_sdk()
    
    print()
    print("=" * 80)
    if success:
        print("✅ SDK 同步成功！")
        print()
        print("使用方法：")
        print("1. 设置环境变量使用本地代码：")
        print("   PowerShell: $env:GOOGLE_GENAI_USE_LOCAL='1'")
        print("   CMD: set GOOGLE_GENAI_USE_LOCAL=1")
        print("   Linux/Mac: export GOOGLE_GENAI_USE_LOCAL=1")
        print()
        print("2. 或修改 backend/app/lib/google_genai_loader.py 中的 USE_LOCAL_SDK 变量")
    else:
        print("❌ SDK 同步失败！")
        print("请检查错误信息并重试")
        sys.exit(1)
