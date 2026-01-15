"""
系统配置服务 - 管理系统级别的配置（如注册开关等）
"""
import json
import logging
from sqlalchemy.orm import Session
from typing import Optional, Any, Dict
from ...models.db_models import SystemConfig

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIGS = {
    "allow_registration": {
        "value": "false",  # 默认关闭注册
        "description": "是否允许用户注册"
    },
    "max_login_attempts": {
        "value": "5",  # 最大登录尝试次数
        "description": "单个IP或邮箱的最大登录失败次数"
    },
    "login_lockout_duration": {
        "value": "900",  # 15分钟（秒）
        "description": "登录失败后锁定时间（秒）"
    },
    "max_login_attempts_per_ip": {
        "value": "10",  # 单个IP的最大尝试次数
        "description": "单个IP地址的最大登录尝试次数（包括所有邮箱）"
    }
}


def is_private_ip(ip: str) -> bool:
    """
    检查 IP 地址是否为私有 IP（内网 IP）
    
    Args:
        ip: IP 地址字符串
    
    Returns:
        True 如果是私有 IP，False 如果是公网 IP
    """
    if not ip or ip == "unknown":
        return False
    
    # IPv4 私有地址范围
    private_ranges = [
        ("10.0.0.0", "10.255.255.255"),      # Class A
        ("172.16.0.0", "172.31.255.255"),   # Class B
        ("192.168.0.0", "192.168.255.255"), # Class C
        ("127.0.0.0", "127.255.255.255"),   # Loopback
        ("169.254.0.0", "169.254.255.255"), # Link-local
    ]
    
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        
        # 检查是否为 IPv4 私有地址
        if ip_obj.version == 4:
            for start, end in private_ranges:
                if ipaddress.ip_address(start) <= ip_obj <= ipaddress.ip_address(end):
                    return True
        
        # IPv6 私有地址
        if ip_obj.version == 6:
            if ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_loopback:
                return True
        
        return False
    except (ValueError, AttributeError):
        # 如果无法解析 IP，假设是公网 IP（让后续验证处理）
        return False


def get_client_ip(request, prefer_public: bool = True) -> str:
    """
    获取客户端真实 IP 地址（优先获取公网 IP）
    
    优先级顺序：
    1. X-Forwarded-For 头（取第一个非私有 IP）
    2. X-Real-IP 头（如果是公网 IP）
    3. CF-Connecting-IP 头（Cloudflare）
    4. True-Client-IP 头（某些 CDN）
    5. 直接连接 IP（request.client.host）
    
    Args:
        request: FastAPI 请求对象
        prefer_public: 是否优先返回公网 IP（如果为 False，返回第一个找到的 IP）
    
    Returns:
        客户端 IP 地址字符串
    """
    ip_candidates = []
    
    # 1. 检查 X-Forwarded-For 头（可能包含多个 IP，逗号分隔）
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 解析所有 IP（从左到右，第一个是原始客户端 IP）
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        ip_candidates.extend(ips)
    
    # 2. 检查 X-Real-IP 头
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        ip_candidates.append(real_ip.strip())
    
    # 3. 检查 CF-Connecting-IP 头（Cloudflare）
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        ip_candidates.append(cf_ip.strip())
    
    # 4. 检查 True-Client-IP 头（某些 CDN/代理）
    true_client_ip = request.headers.get("True-Client-IP")
    if true_client_ip:
        ip_candidates.append(true_client_ip.strip())
    
    # 5. 检查 X-Client-IP 头
    x_client_ip = request.headers.get("X-Client-IP")
    if x_client_ip:
        ip_candidates.append(x_client_ip.strip())
    
    # 6. 回退到直接连接 IP
    if request.client:
        ip_candidates.append(request.client.host)
    
    # 去重并过滤无效 IP
    seen = set()
    valid_ips = []
    for ip in ip_candidates:
        ip = ip.strip()
        if ip and ip not in seen and ip != "unknown":
            seen.add(ip)
            valid_ips.append(ip)
    
    if not valid_ips:
        return "unknown"
    
    # 如果 prefer_public=True，优先返回公网 IP
    if prefer_public:
        for ip in valid_ips:
            if not is_private_ip(ip):
                return ip
        # 如果没有公网 IP，返回第一个（可能是内网 IP）
        return valid_ips[0]
    else:
        # 返回第一个找到的 IP
        return valid_ips[0]


async def get_public_ip_from_service() -> Optional[str]:
    """
    通过第三方服务获取服务器的公网 IP（备用方案）
    
    注意：这个方法获取的是服务器的公网 IP，不是客户端的 IP。
    主要用于验证服务器配置或作为备用方案。
    
    Returns:
        公网 IP 地址，如果获取失败则返回 None
    """
    import httpx
    services = [
        "https://api.ipify.org?format=text",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
    ]
    
    for service_url in services:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(service_url)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # 验证是否为有效 IP
                    if ip and not is_private_ip(ip):
                        return ip
        except Exception as e:
            logger.debug(f"[IPService] 从 {service_url} 获取 IP 失败: {e}")
            continue
    
    return None


async def get_ip_info(ip: str) -> Optional[Dict[str, Any]]:
    """
    获取 IP 地址的详细信息（地理位置、ISP 等）
    
    这是一个可选功能，使用免费的 IP 地理位置 API。
    注意：频繁调用可能有限制，建议仅在需要时使用。
    
    Args:
        ip: IP 地址字符串
    
    Returns:
        包含 IP 信息的字典，如果获取失败则返回 None
        格式：
        {
            "ip": "xxx.xxx.xxx.xxx",
            "country": "CN",
            "country_name": "China",
            "region": "Beijing",
            "city": "Beijing",
            "isp": "China Telecom",
            "is_private": False
        }
    """
    if not ip or ip == "unknown" or is_private_ip(ip):
        return {
            "ip": ip,
            "is_private": True,
            "note": "Private IP address"
        }
    
    import httpx
    
    # 使用免费的 IP 地理位置 API（ip-api.com，无需 API key）
    # 注意：免费版本有速率限制（45 请求/分钟）
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # ip-api.com 免费 API（JSON 格式）
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,isp,query"
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "ip": data.get("query", ip),
                        "country": data.get("countryCode", ""),
                        "country_name": data.get("country", ""),
                        "region": data.get("regionName", ""),
                        "city": data.get("city", ""),
                        "isp": data.get("isp", ""),
                        "is_private": False
                    }
    except Exception as e:
        logger.debug(f"[IPService] 获取 IP 信息失败 {ip}: {e}")
    
    # 如果获取失败，至少返回基本信息
    return {
        "ip": ip,
        "is_private": False,
        "note": "Failed to fetch detailed information"
    }


def initialize_system_configs(db: Session) -> None:
    """
    初始化系统配置（如果不存在则创建默认配置）
    
    Args:
        db: 数据库会话
    """
    try:
        for key, config_data in DEFAULT_CONFIGS.items():
            existing = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if not existing:
                system_config = SystemConfig(
                    key=key,
                    value=config_data["value"],
                    description=config_data["description"]
                )
                db.add(system_config)
                logger.info(f"[SystemConfig] 初始化配置: {key} = {config_data['value']}")
        
        db.commit()
        logger.info("[SystemConfig] ✅ 系统配置初始化完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[SystemConfig] ❌ 初始化系统配置失败: {e}", exc_info=True)
        raise


def get_system_config(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    """
    获取系统配置值
    
    Args:
        db: 数据库会话
        key: 配置键
        default: 默认值（如果配置不存在）
    
    Returns:
        配置值（字符串），如果不存在则返回 default
    """
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if config:
            return config.value
        return default
    except Exception as e:
        logger.error(f"[SystemConfig] 获取配置失败 {key}: {e}", exc_info=True)
        return default


def get_system_config_bool(db: Session, key: str, default: bool = False) -> bool:
    """
    获取系统配置值（布尔类型）
    
    Args:
        db: 数据库会话
        key: 配置键
        default: 默认值
    
    Returns:
        配置值（布尔类型）
    """
    value = get_system_config(db, key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def get_system_config_int(db: Session, key: str, default: int = 0) -> int:
    """
    获取系统配置值（整数类型）
    
    Args:
        db: 数据库会话
        key: 配置键
        default: 默认值
    
    Returns:
        配置值（整数类型）
    """
    value = get_system_config(db, key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"[SystemConfig] 配置 {key} 的值 '{value}' 无法转换为整数，使用默认值 {default}")
        return default


def set_system_config(db: Session, key: str, value: str, description: Optional[str] = None) -> SystemConfig:
    """
    设置系统配置值
    
    Args:
        db: 数据库会话
        key: 配置键
        value: 配置值
        description: 配置描述（可选）
    
    Returns:
        更新后的 SystemConfig 对象
    """
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = SystemConfig(
                key=key,
                value=value,
                description=description or DEFAULT_CONFIGS.get(key, {}).get("description")
            )
            db.add(config)
        
        db.commit()
        logger.info(f"[SystemConfig] 更新配置: {key} = {value}")
        return config
    except Exception as e:
        db.rollback()
        logger.error(f"[SystemConfig] ❌ 设置配置失败 {key}: {e}", exc_info=True)
        raise
