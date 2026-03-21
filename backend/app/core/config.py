"""
应用配置模块
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict

# 导入统一的环境变量加载模块（确保 .env 文件已加载）
from .env_loader import _ENV_LOADED  # noqa: F401

ADK_RUNTIME_STRATEGY_VALUES = (
    "official_only",
    "official_or_legacy",
    "allow_legacy",
)


def normalize_adk_runtime_strategy(
    raw_value: str,
    *,
    default: str = "official_or_legacy",
    reject_invalid: bool = True,
) -> str:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        normalized = str(default or "").strip().lower() or "official_or_legacy"
    if normalized in ADK_RUNTIME_STRATEGY_VALUES:
        return normalized
    if reject_invalid:
        allowed = ", ".join(ADK_RUNTIME_STRATEGY_VALUES)
        raise ValueError(f"invalid ADK runtime strategy: {normalized}. Allowed values: {allowed}")
    return str(default or "official_or_legacy").strip().lower()


def is_adk_runtime_fallback_allowed(*, runtime_strategy: str, strict_mode: bool) -> bool:
    normalized_strategy = normalize_adk_runtime_strategy(
        runtime_strategy,
        default="official_or_legacy",
        reject_invalid=False,
    )
    return normalized_strategy == "allow_legacy" and not bool(strict_mode)


def build_adk_runtime_contract_payload(
    *,
    runtime_strategy_raw: str,
    strict_mode: bool,
) -> dict[str, Union[str, bool]]:
    runtime_strategy = normalize_adk_runtime_strategy(
        runtime_strategy_raw,
        default="official_or_legacy",
        reject_invalid=True,
    )
    strict_mode_enabled = bool(strict_mode)
    return {
        "runtime_strategy": runtime_strategy,
        "strict_mode": strict_mode_enabled,
        "fallback_allowed": is_adk_runtime_fallback_allowed(
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode_enabled,
        ),
    }


class Settings(BaseSettings):
    """应用配置类"""

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "21574"))

    # 数据库配置（必须设置，仅支持 PostgreSQL）
    # 注意：实际的数据库连接由 backend/app/core/database.py 处理，该模块要求必须设置 DATABASE_URL 环境变量
    database_url: str = os.getenv("DATABASE_URL", "")

    # GCP / Vertex AI 配置（用于 Virtual Try-On 等功能）
    gcp_project_id: Optional[str] = os.getenv("GCP_PROJECT_ID")
    gcp_location: str = os.getenv("GCP_LOCATION", "us-central1")
    google_application_credentials: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Redis 配置
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")

    # 上传队列配置
    upload_queue_workers: int = int(os.getenv("UPLOAD_QUEUE_WORKERS", "5"))
    upload_queue_max_retries: int = int(os.getenv("UPLOAD_QUEUE_MAX_RETRIES", "3"))
    upload_queue_retry_delay: float = float(os.getenv("UPLOAD_QUEUE_RETRY_DELAY", "2.0"))
    upload_queue_rate_limit: int = int(os.getenv("UPLOAD_QUEUE_RATE_LIMIT", "10"))
    
    # Worker 运行模式
    # - "embedded": 内嵌在主进程中运行（默认，推荐，使用 Redis 队列系统）
    # - "disabled": 禁用 Worker（需要外部 Worker 服务）
    worker_mode: str = os.getenv("WORKER_MODE", "embedded")

    # Workflow 引用安全配置
    # 默认禁止读取本地文件引用（file://、绝对/相对路径），仅允许显式开启
    workflow_allow_local_file_reference: bool = os.getenv("WORKFLOW_ALLOW_LOCAL_FILE_REFERENCE", "false").lower() == "true"
    # workflow history 图片预览/下载链路的受信任基准地址（仅允许 origin，不允许 path/query）
    workflow_history_public_base_url: str = os.getenv(
        "WORKFLOW_HISTORY_PUBLIC_BASE_URL",
        os.getenv("PUBLIC_BASE_URL", ""),
    ).strip()
    # Host 头白名单（逗号分隔）。为空时自动使用 localhost + workflow_history_public_base_url 的 host。
    trusted_hosts_raw: str = os.getenv("TRUSTED_HOSTS", "")

    # MCP stdio 命令执行策略
    # - allowlist: 仅允许 MCP_STDIO_ALLOWED_COMMANDS 列表中的命令（默认）
    # - deny_all: 禁用所有 stdio 命令执行
    # - allow_all: 允许任意命令（仅用于向后兼容/过渡）
    mcp_stdio_command_policy: str = os.getenv("MCP_STDIO_COMMAND_POLICY", "allowlist")
    mcp_stdio_allowed_commands_raw: str = os.getenv(
        "MCP_STDIO_ALLOWED_COMMANDS",
        "node,npx,python,python3,uv,uvx",
    )
    # ADK runtime 编排策略：
    # - official_only: 仅允许官方 ADK runtime
    # - official_or_legacy: 官方优先，默认禁止 legacy fallback（显式 allow_legacy 才允许）
    # - allow_legacy: 显式允许 legacy fallback（strict_mode=true 时仍会被阻断）
    adk_runtime_strategy_raw: str = os.getenv("ADK_RUNTIME_STRATEGY", "official_or_legacy")
    # strict mode 开关（开启后即使策略允许 legacy，也会阻断 fallback 输出）
    adk_strict_mode: bool = os.getenv("ADK_STRICT_MODE", "false").lower() == "true"

    # 认证配置
    environment: str = os.getenv("ENVIRONMENT", "development").lower()
    allow_registration: bool = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"
    enable_global_auth_boundary: bool = os.getenv("ENABLE_GLOBAL_AUTH_BOUNDARY", "true").lower() == "true"
    # 注意：jwt_secret_key 不再从环境变量读取，由 jwt_utils.py 管理
    # 保留此字段仅用于向后兼容，实际使用 jwt_utils.py 中的 JWT_SECRET_KEY
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    @property
    def redis_url(self) -> str:
        """构建 Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """是否为生产环境（仅 production 视为生产）"""
        return (self.environment or "").strip().lower() == "production"

    @property
    def mcp_stdio_allowed_commands(self) -> list[str]:
        """解析 stdio 命令白名单（逗号分隔）"""
        commands: list[str] = []
        seen = set()
        for item in (self.mcp_stdio_allowed_commands_raw or "").split(","):
            command = item.strip().lower()
            if not command or command in seen:
                continue
            seen.add(command)
            commands.append(command)
        return commands

    @property
    def adk_runtime_strategy(self) -> str:
        """归一化 ADK runtime strategy 配置。"""
        return normalize_adk_runtime_strategy(
            self.adk_runtime_strategy_raw,
            reject_invalid=True,
        )

    @property
    def adk_runtime_contract(self) -> dict[str, Union[str, bool]]:
        """
        ADK runtime 合同统一读取入口。
        """
        payload = build_adk_runtime_contract_payload(
            runtime_strategy_raw=self.adk_runtime_strategy_raw,
            strict_mode=bool(self.adk_strict_mode),
        )
        return {
            "runtime_strategy": str(payload["runtime_strategy"]),
            "strict_mode": bool(payload["strict_mode"]),
            "fallback_allowed": bool(payload["fallback_allowed"]),
        }

    @staticmethod
    def _normalize_trusted_host_entry(raw: str) -> str:
        value = str(raw or "").strip().lower()
        if not value:
            return ""
        if value == "*":
            return "*"
        if value.startswith("*."):
            return value
        if "://" in value:
            parsed = urlparse(value)
            value = str(parsed.hostname or "").strip().lower()
        elif value.startswith("["):
            end_idx = value.find("]")
            if end_idx > 1:
                value = value[1:end_idx]
        elif value.count(":") == 1:
            host_part, port_part = value.rsplit(":", 1)
            if port_part.isdigit():
                value = host_part
        return value.strip().strip(".")

    @property
    def trusted_hosts(self) -> list[str]:
        hosts: list[str] = []
        seen: set[str] = set()

        def push(raw_value: str) -> None:
            normalized = self._normalize_trusted_host_entry(raw_value)
            if not normalized:
                return
            if normalized == "*":
                hosts.clear()
                hosts.append("*")
                seen.clear()
                seen.add("*")
                return
            if "*" in seen:
                return
            if normalized in seen:
                return
            seen.add(normalized)
            hosts.append(normalized)

        for item in str(self.trusted_hosts_raw or "").split(","):
            push(item)
        if hosts:
            return hosts

        for local_host in ("localhost", "127.0.0.1", "::1"):
            push(local_host)

        parsed = urlparse(str(self.workflow_history_public_base_url or "").strip())
        configured_host = str(parsed.hostname or "").strip().lower()
        if configured_host:
            push(configured_host)
        return hosts

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # 忽略未定义的环境变量（如 PYTHONUNBUFFERED、LOG_LEVEL 等）
    )


# 全局配置实例
settings = Settings()
