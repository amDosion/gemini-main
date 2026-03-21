"""
密码哈希工具 - 使用 bcrypt 进行密码哈希和验证
"""
import hashlib
import bcrypt

# bcrypt 计算成本（默认 12，兼顾安全与性能）
_BCRYPT_ROUNDS = 12


def _preprocess_password(password: str) -> str:
    """
    预处理密码：统一使用 SHA256 预处理，避免 bcrypt 72 字节限制
    
    bcrypt 限制密码最大 72 字节，我们统一先用 SHA256 哈希，
    然后再用 bcrypt 哈希，这样既保证了安全性，又避免了长度限制问题。
    
    Args:
        password: 明文密码（字符串）
        
    Returns:
        预处理后的密码字符串（SHA256 十六进制，64 字符）
    """
    password_bytes = password.encode('utf-8')
    # 使用 SHA256 哈希，得到固定 32 字节
    sha256_hash = hashlib.sha256(password_bytes).digest()
    # 转换为十六进制字符串（64 字符）
    return sha256_hash.hex()


def hash_password(password: str) -> str:
    """
    对密码进行哈希处理
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码字符串
    """
    # 预处理密码（SHA256 哈希，避免 bcrypt 72 字节限制）
    processed_password = _preprocess_password(password)
    # 使用 bcrypt 哈希预处理后的密码（兼容标准 $2b$ 哈希格式）
    hashed = bcrypt.hashpw(
        processed_password.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    )
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        密码是否匹配
    """
    # 预处理密码（SHA256 哈希，避免 bcrypt 72 字节限制）
    processed_password = _preprocess_password(plain_password)
    try:
        return bcrypt.checkpw(
            processed_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # 非法哈希格式或空值按不匹配处理
        return False
