#!/usr/bin/env python3
"""
ENCRYPTION_KEY 管理 CLI 工具

用法：
    # 查看当前密钥（仅显示前8个字符，用于验证）
    python -m backend.scripts.manage_encryption_key show
    
    # 查看完整密钥（需要确认）
    python -m backend.scripts.manage_encryption_key show --full
    
    # 生成新密钥
    python -m backend.scripts.manage_encryption_key generate
    
    # 验证密钥文件是否存在
    python -m backend.scripts.manage_encryption_key status
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.encryption_key_manager import EncryptionKeyManager, ENCRYPTION_KEY_FILE
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def show_key(full: bool = False):
    """显示 ENCRYPTION_KEY"""
    try:
        # 优先从环境变量读取
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            print("\n✅ ENCRYPTION_KEY 从环境变量读取")
            if full:
                print(f"\n🔑 ENCRYPTION_KEY (完整):")
                print(f"{env_key}\n")
            else:
                masked = env_key[:8] + "..." + env_key[-4:] if len(env_key) > 12 else env_key[:8] + "..."
                print(f"\n🔑 ENCRYPTION_KEY (部分): {masked}")
                print("   提示：使用 --full 参数查看完整密钥\n")
            return
        
        # 从文件读取
        file_key = EncryptionKeyManager.load_key_from_file()
        if file_key:
            print("\n✅ ENCRYPTION_KEY 从文件读取")
            if full:
                print("\n⚠️  警告：完整密钥将显示在终端中，请确保终端安全！")
                confirm = input("确认显示完整密钥？(yes/no): ")
                if confirm.lower() != 'yes':
                    print("已取消")
                    return
                
                print(f"\n🔑 ENCRYPTION_KEY (完整):")
                print(f"{file_key}\n")
            else:
                masked = file_key[:8] + "..." + file_key[-4:] if len(file_key) > 12 else file_key[:8] + "..."
                print(f"\n🔑 ENCRYPTION_KEY (部分): {masked}")
                print("   提示：使用 --full 参数查看完整密钥\n")
            
            # 显示文件信息
            if ENCRYPTION_KEY_FILE.exists():
                size = ENCRYPTION_KEY_FILE.stat().st_size
                print(f"✅ 密钥文件: {ENCRYPTION_KEY_FILE}")
                print(f"   大小: {size} 字节")
            return
        
        print("❌ 无法获取 ENCRYPTION_KEY（环境变量和文件都不存在）")
        print("   提示：运行 'generate' 命令生成新密钥")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"显示密钥失败: {e}", exc_info=True)


def generate_key():
    """生成新的 ENCRYPTION_KEY"""
    try:
        # 检查是否已存在（环境变量或文件）
        env_key = os.getenv("ENCRYPTION_KEY")
        file_key = EncryptionKeyManager.load_key_from_file()
        
        if env_key or file_key:
            print("\n⚠️  警告：ENCRYPTION_KEY 已存在！")
            if env_key:
                print("   当前从环境变量读取")
            if file_key:
                print("   当前从文件读取")
            print("\n生成新密钥将覆盖现有密钥，所有用旧密钥加密的数据将无法解密！")
            print("这包括：")
            print("  - JWT Secret Key（如果已加密）")
            print("  - 所有 API keys（如果已加密）")
            print("  - 其他敏感数据（如果已加密）")
            confirm = input("\n确认生成新密钥？(yes/no): ")
            if confirm.lower() != 'yes':
                print("已取消")
                return
        
        # 生成新密钥
        new_key = EncryptionKeyManager.generate_key()
        
        # 保存到文件（如果环境变量未设置）
        if not env_key:
            EncryptionKeyManager.save_key(new_key)
            print("\n✅ ENCRYPTION_KEY 已生成并保存到文件")
            print(f"   文件: {ENCRYPTION_KEY_FILE}")
            print(f"   密钥 (前8字符): {new_key[:8]}...")
            print("\n⚠️  注意：")
            print("  1. 请确保此文件已添加到 .gitignore，不会提交到版本控制！")
            print("  2. 生产环境建议设置 ENCRYPTION_KEY 环境变量，而不是使用文件存储")
            print("  3. 如果使用环境变量，请删除此文件：")
            print(f"     rm {ENCRYPTION_KEY_FILE}")
        else:
            print("\n✅ ENCRYPTION_KEY 已生成（仅显示，未保存）")
            print(f"   密钥 (前8字符): {new_key[:8]}...")
            print("\n⚠️  注意：")
            print("  当前使用环境变量 ENCRYPTION_KEY，请手动设置环境变量：")
            print(f"  export ENCRYPTION_KEY={new_key}")
            print("  或添加到 .env 文件：")
            print(f"  ENCRYPTION_KEY={new_key}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"生成密钥失败: {e}", exc_info=True)


def show_status():
    """显示密钥状态"""
    print("\n📊 ENCRYPTION_KEY 状态:\n")
    
    # 检查环境变量
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        print(f"✅ 环境变量 ENCRYPTION_KEY 已设置（推荐用于生产环境）")
        print(f"   值 (前8字符): {env_key[:8]}...")
    else:
        print(f"❌ 环境变量 ENCRYPTION_KEY 未设置")
    
    # 检查文件
    if ENCRYPTION_KEY_FILE.exists():
        size = ENCRYPTION_KEY_FILE.stat().st_size
        print(f"\n✅ 密钥文件存在: {ENCRYPTION_KEY_FILE}")
        print(f"   大小: {size} 字节")
        print(f"   状态: 文件存储（适用于开发环境）")
    else:
        print(f"\n❌ 密钥文件不存在: {ENCRYPTION_KEY_FILE}")
    
    # 显示优先级说明
    print("\n📝 密钥获取优先级：")
    print("  1. 环境变量 ENCRYPTION_KEY（生产环境推荐）")
    print("  2. 文件 backend/credentials/.encryption_key（开发环境）")
    print("  3. 自动生成（首次运行）")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="ENCRYPTION_KEY 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s show              # 显示密钥（部分）
  %(prog)s show --full       # 显示完整密钥
  %(prog)s generate          # 生成新密钥
  %(prog)s status            # 显示状态
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # show 命令
    show_parser = subparsers.add_parser('show', help='显示 ENCRYPTION_KEY')
    show_parser.add_argument('--full', action='store_true', help='显示完整密钥（需要确认）')
    
    # generate 命令
    subparsers.add_parser('generate', help='生成新的 ENCRYPTION_KEY')
    
    # status 命令
    subparsers.add_parser('status', help='显示密钥状态')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'show':
        show_key(full=args.full)
    elif args.command == 'generate':
        generate_key()
    elif args.command == 'status':
        show_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
