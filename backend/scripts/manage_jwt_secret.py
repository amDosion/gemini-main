#!/usr/bin/env python3
"""
JWT Secret Key 管理 CLI 工具

用法：
    # 查看当前密钥（仅显示前8个字符，用于验证）
    python -m backend.scripts.manage_jwt_secret show
    
    # 查看完整密钥（需要确认）
    python -m backend.scripts.manage_jwt_secret show --full
    
    # 生成新密钥
    python -m backend.scripts.manage_jwt_secret generate
    
    # 轮换密钥（正常轮换，不立即强制用户退出）
    python -m backend.scripts.manage_jwt_secret rotate
    
    # 强制轮换密钥（撤销所有 refresh tokens，仅在安全事件时使用）
    python -m backend.scripts.manage_jwt_secret rotate --force
    
    # 验证密钥文件是否存在
    python -m backend.scripts.manage_jwt_secret status
"""
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.jwt_secret_manager import JWTSecretManager, JWT_SECRET_FILE, JWT_SECRET_ENCRYPTED_FILE
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def show_secret(full: bool = False):
    """显示 JWT Secret Key"""
    try:
        secret = JWTSecretManager.get_secret_for_display()
        if not secret:
            print("❌ 无法获取 JWT Secret Key")
            return
        
        if full:
            # 显示完整密钥（需要确认）
            print("\n⚠️  警告：完整密钥将显示在终端中，请确保终端安全！")
            confirm = input("确认显示完整密钥？(yes/no): ")
            if confirm.lower() != 'yes':
                print("已取消")
                return
            
            print(f"\n🔑 JWT Secret Key (完整):")
            print(f"{secret}\n")
        else:
            # 仅显示前8个字符（用于验证）
            masked = secret[:8] + "..." + secret[-4:] if len(secret) > 12 else secret[:8] + "..."
            print(f"\n🔑 JWT Secret Key (部分): {masked}")
            print("   提示：使用 --full 参数查看完整密钥\n")
        
        # 显示文件信息
        if JWT_SECRET_ENCRYPTED_FILE.exists():
            print(f"✅ 密钥文件: {JWT_SECRET_ENCRYPTED_FILE} (加密)")
        elif JWT_SECRET_FILE.exists():
            print(f"⚠️  密钥文件: {JWT_SECRET_FILE} (未加密，建议升级)")
        else:
            print("❌ 密钥文件不存在")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"显示密钥失败: {e}", exc_info=True)


def generate_secret():
    """生成新的 JWT Secret Key"""
    try:
        # 检查是否已存在
        key_exists = JWT_SECRET_ENCRYPTED_FILE.exists() or JWT_SECRET_FILE.exists()
        
        if key_exists:
            print("\n⚠️  警告：JWT Secret Key 已存在！")
            print("生成新密钥将覆盖现有密钥，旧的 Token 将无法验证。")
            print("这将被视为正常轮换操作，不会立即强制用户退出登录。")
            print("旧的 Token 会在用户下次尝试刷新时自然失效。")
            confirm = input("确认生成新密钥？(yes/no): ")
            if confirm.lower() != 'yes':
                print("已取消")
                return
            
            # 覆盖生成：使用 rotate_secret（不清理 refresh tokens）
            secret = JWTSecretManager.rotate_secret(revoke_tokens=False)
            
            print("\n✅ JWT Secret Key 已生成并保存（正常轮换）")
            print(f"   文件: {JWT_SECRET_ENCRYPTED_FILE}")
            print(f"   密钥 (前8字符): {secret[:8]}...")
            print("\nℹ️  注意：旧的 Token 将自然失效，用户下次刷新时会需要重新登录")
        else:
            # 首次生成：不影响现有 tokens（因为没有）
            secret = JWTSecretManager.generate_secret_key()
            JWTSecretManager.save_secret(secret, encrypt=True)
            
            print("\n✅ JWT Secret Key 已生成并保存（首次生成）")
            print(f"   文件: {JWT_SECRET_ENCRYPTED_FILE}")
            print(f"   密钥 (前8字符): {secret[:8]}...")
        
        print("\n⚠️  注意：请确保此文件已添加到 .gitignore，不会提交到版本控制！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"生成密钥失败: {e}", exc_info=True)


def rotate_secret():
    """轮换 JWT Secret Key（正常轮换，不立即强制用户退出）"""
    try:
        print("\n⚠️  警告：轮换 JWT Secret Key 将导致旧的 Token 无法验证！")
        print("旧的 Token 会在用户下次尝试刷新时自然失效。")
        print("用户不会被立即强制退出登录，但下次刷新时需要重新登录。")
        print("\n如果需要立即强制所有用户退出登录（安全事件场景），")
        print("请使用 'rotate --force' 命令。")
        confirm = input("\n确认轮换密钥？(yes/no): ")
        if confirm.lower() != 'yes':
            print("已取消")
            return
        
        new_secret = JWTSecretManager.rotate_secret(revoke_tokens=False)
        
        print("\n✅ JWT Secret Key 已轮换（正常轮换）")
        print(f"   新密钥 (前8字符): {new_secret[:8]}...")
        print("\nℹ️  注意：旧的 Token 将自然失效，用户下次刷新时会需要重新登录")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"轮换密钥失败: {e}", exc_info=True)


def rotate_secret_force():
    """强制轮换 JWT Secret Key（安全事件场景，会撤销所有 refresh tokens）"""
    try:
        print("\n🚨 警告：强制轮换 JWT Secret Key！")
        print("此操作将：")
        print("  1. 生成新密钥")
        print("  2. 撤销数据库中的所有 refresh tokens")
        print("  3. 立即强制所有用户退出登录")
        print("\n仅在以下场景使用：")
        print("  - 密钥泄露或怀疑泄露")
        print("  - 安全事件响应")
        print("  - 需要立即强制所有用户重新登录")
        confirm = input("\n确认强制轮换密钥？(yes/no): ")
        if confirm.lower() != 'yes':
            print("已取消")
            return
        
        new_secret = JWTSecretManager.rotate_secret(revoke_tokens=True)
        
        print("\n✅ JWT Secret Key 已强制轮换（安全轮换）")
        print(f"   新密钥 (前8字符): {new_secret[:8]}...")
        print("\n⚠️  注意：所有现有的 refresh tokens 已被撤销，用户需要重新登录")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        logger.error(f"强制轮换密钥失败: {e}", exc_info=True)


def show_status():
    """显示密钥状态"""
    print("\n📊 JWT Secret Key 状态:\n")
    
    # 检查加密文件
    if JWT_SECRET_ENCRYPTED_FILE.exists():
        size = JWT_SECRET_ENCRYPTED_FILE.stat().st_size
        print(f"✅ 加密密钥文件存在: {JWT_SECRET_ENCRYPTED_FILE}")
        print(f"   大小: {size} 字节")
        print(f"   状态: 已加密存储（推荐）")
    else:
        print(f"❌ 加密密钥文件不存在: {JWT_SECRET_ENCRYPTED_FILE}")
    
    # 检查未加密文件
    if JWT_SECRET_FILE.exists():
        size = JWT_SECRET_FILE.stat().st_size
        print(f"⚠️  未加密密钥文件存在: {JWT_SECRET_FILE}")
        print(f"   大小: {size} 字节")
        print(f"   状态: 未加密（不安全，建议升级）")
    else:
        print(f"✅ 未加密密钥文件不存在（正常）")
    
    # 检查环境变量
    import os
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret:
        print(f"\n⚠️  环境变量 JWT_SECRET_KEY 已设置（不推荐）")
        print(f"   值 (前8字符): {env_secret[:8]}...")
    else:
        print(f"\n✅ 环境变量 JWT_SECRET_KEY 未设置（正常）")
    
    # 检查 ENCRYPTION_KEY
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        print(f"\n✅ ENCRYPTION_KEY 已设置（用于加密存储）")
    else:
        print(f"\n⚠️  ENCRYPTION_KEY 未设置（加密功能可能受限）")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="JWT Secret Key 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s show              # 显示密钥（部分）
  %(prog)s show --full       # 显示完整密钥
  %(prog)s generate          # 生成新密钥
  %(prog)s rotate            # 轮换密钥
  %(prog)s status            # 显示状态
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # show 命令
    show_parser = subparsers.add_parser('show', help='显示 JWT Secret Key')
    show_parser.add_argument('--full', action='store_true', help='显示完整密钥（需要确认）')
    
    # generate 命令
    subparsers.add_parser('generate', help='生成新的 JWT Secret Key')
    
    # rotate 命令
    rotate_parser = subparsers.add_parser('rotate', help='轮换 JWT Secret Key（正常轮换，不立即强制用户退出）')
    rotate_parser.add_argument('--force', action='store_true', help='强制轮换（撤销所有 refresh tokens，仅在安全事件时使用）')
    
    # status 命令
    subparsers.add_parser('status', help='显示密钥状态')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'show':
        show_secret(full=args.full)
    elif args.command == 'generate':
        generate_secret()
    elif args.command == 'rotate':
        if hasattr(args, 'force') and args.force:
            rotate_secret_force()
        else:
            rotate_secret()
    elif args.command == 'status':
        show_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
