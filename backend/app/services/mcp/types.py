"""
MCP 类型定义
定义 MCP 服务使用的数据类型
"""

from typing import Dict, Any, Optional, List, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil


class MCPServerType(str, Enum):
    """MCP 服务器类型"""
    STDIO = "stdio"       # 标准输入输出（进程通信）
    SSE = "sse"           # Server-Sent Events（HTTP 流）
    HTTP = "http"         # HTTP（自定义）
    STREAMABLE_HTTP = "streamableHttp"  # Streamable HTTP（MCP over HTTP）


class MCPStdioPolicyError(ValueError):
    """stdio 命令策略校验失败"""


_STDIO_POLICY_ALLOWLIST = "allowlist"
_STDIO_POLICY_DENY_ALL = "deny_all"
_STDIO_POLICY_ALLOW_ALL = "allow_all"
_STDIO_POLICY_ALIASES = {
    "allowlist": _STDIO_POLICY_ALLOWLIST,
    "whitelist": _STDIO_POLICY_ALLOWLIST,
    "minimal": _STDIO_POLICY_ALLOWLIST,
    "deny_all": _STDIO_POLICY_DENY_ALL,
    "denyall": _STDIO_POLICY_DENY_ALL,
    "deny": _STDIO_POLICY_DENY_ALL,
    "allow_all": _STDIO_POLICY_ALLOW_ALL,
    "allowall": _STDIO_POLICY_ALLOW_ALL,
    "off": _STDIO_POLICY_DENY_ALL,
    "disabled": _STDIO_POLICY_DENY_ALL,
}

_SHELL_COMMANDS = {
    "sh",
    "bash",
    "zsh",
    "dash",
    "ksh",
    "fish",
    "pwsh",
    "powershell",
    "powershell.exe",
    "cmd",
    "cmd.exe",
}


def _normalize_stdio_policy(raw_policy: Optional[str]) -> str:
    policy = (raw_policy or _STDIO_POLICY_ALLOWLIST).strip().lower()
    normalized = _STDIO_POLICY_ALIASES.get(policy)
    if normalized:
        return normalized
    raise MCPStdioPolicyError(
        f"invalid MCP stdio policy '{raw_policy}'. "
        "Supported values: allowlist, deny_all, allow_all"
    )


def _normalize_command_name(command: Optional[str]) -> str:
    raw = (command or "").strip()
    if not raw:
        return ""
    return Path(raw).name.strip().lower()


def _is_explicit_command_path(command: str) -> bool:
    raw = (command or "").strip()
    if not raw:
        return False
    if "/" in raw or "\\" in raw:
        return True
    if raw.startswith("."):
        return True
    return bool(Path(raw).drive)


def _resolve_command_real_path(command: str, *, context_prefix: str) -> Path:
    raw = (command or "").strip()
    if not raw:
        raise MCPStdioPolicyError(f"{context_prefix}stdio server requires non-empty 'command'")

    if _is_explicit_command_path(raw):
        try:
            return Path(raw).expanduser().resolve(strict=True)
        except FileNotFoundError as exc:
            raise MCPStdioPolicyError(
                f"{context_prefix}stdio command '{raw}' does not exist"
            ) from exc
        except OSError as exc:
            raise MCPStdioPolicyError(
                f"{context_prefix}failed to resolve stdio command '{raw}': {exc}"
            ) from exc

    located = shutil.which(raw)
    if not located:
        raise MCPStdioPolicyError(
            f"{context_prefix}stdio command '{raw}' cannot be resolved from PATH"
        )

    try:
        return Path(located).resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise MCPStdioPolicyError(
            f"{context_prefix}failed to resolve stdio command '{raw}' real path: {exc}"
        ) from exc


def _collect_allowlisted_real_paths_by_name(
    allowed_commands: Optional[Iterable[str]],
) -> Dict[str, set[str]]:
    real_paths: Dict[str, set[str]] = {}
    for item in allowed_commands or []:
        raw = (item or "").strip()
        if not raw:
            continue
        name = _normalize_command_name(raw)
        if not name:
            continue

        try:
            resolved = _resolve_command_real_path(raw, context_prefix="")
        except MCPStdioPolicyError:
            # 忽略无法解析的 allowlist 项，仅依赖名称匹配。
            continue

        real_paths.setdefault(name, set()).add(str(resolved))

    return real_paths


def _is_python_command(command_name: str) -> bool:
    return command_name.startswith("python") or command_name.startswith("pypy")


def _is_node_command(command_name: str) -> bool:
    return command_name in {"node", "nodejs"}


def _is_shell_command(command_name: str) -> bool:
    return command_name in _SHELL_COMMANDS


def _find_high_risk_arg(command_name: str, args: Optional[List[str]]) -> Optional[str]:
    if not args:
        return None

    for arg in args:
        token = str(arg).strip().lower()
        if not token:
            continue

        if _is_python_command(command_name):
            if token == "-c" or (token.startswith("-c") and len(token) > 2):
                return str(arg)

        if _is_node_command(command_name):
            if token == "-e" or token == "--eval":
                return str(arg)
            if token.startswith("--eval="):
                return str(arg)
            if token.startswith("-e") and len(token) > 2:
                return str(arg)

        if _is_shell_command(command_name):
            if token in {"-c", "--command", "/c", "-command", "-encodedcommand"}:
                return str(arg)
            if token.startswith("--command="):
                return str(arg)

    return None


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "is_error": self.is_error
        }


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    server_type: MCPServerType
    command: Optional[str] = None           # stdio: 命令（如 "node", "python"）
    args: Optional[List[str]] = None        # stdio: 参数（如 ["server.js"]）
    env: Optional[Dict[str, str]] = None    # stdio: 环境变量
    url: Optional[str] = None               # sse/http/streamableHttp: 服务器 URL
    timeout: float = 30.0                   # 超时时间（秒）

    def validate(self) -> None:
        """验证配置"""
        if self.server_type == MCPServerType.STDIO:
            if not self.command:
                raise ValueError("stdio server requires 'command' parameter")
        elif self.server_type in (
            MCPServerType.SSE,
            MCPServerType.HTTP,
            MCPServerType.STREAMABLE_HTTP,
        ):
            if not self.url:
                raise ValueError(f"{self.server_type.value} server requires 'url' parameter")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "server_type": self.server_type.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "timeout": self.timeout
        }


def validate_mcp_stdio_command_policy(
    config: MCPServerConfig,
    *,
    policy: Optional[str],
    allowed_commands: Optional[Iterable[str]],
    context: Optional[str] = None,
) -> None:
    """
    校验 stdio 模式命令是否符合策略。

    仅对 stdio 生效；http/sse/streamable-http 不受影响。
    """
    if config.server_type != MCPServerType.STDIO:
        return

    command_raw = (config.command or "").strip()
    normalized_policy = _normalize_stdio_policy(policy)
    context_prefix = f"[{context}] " if context else ""
    command_real_path = _resolve_command_real_path(command_raw, context_prefix=context_prefix)
    command_name = _normalize_command_name(str(command_real_path))

    high_risk_arg = _find_high_risk_arg(command_name, config.args)
    if high_risk_arg is not None:
        raise MCPStdioPolicyError(
            f"{context_prefix}stdio command '{command_raw}' contains high-risk argument "
            f"'{high_risk_arg}' and is blocked"
        )

    if normalized_policy == _STDIO_POLICY_ALLOW_ALL:
        return

    if normalized_policy == _STDIO_POLICY_DENY_ALL:
        raise MCPStdioPolicyError(
            f"{context_prefix}stdio execution is disabled by policy 'deny_all'"
        )

    normalized_allowlist: List[str] = []
    allowlist_set = set()
    for item in allowed_commands or []:
        normalized = _normalize_command_name(item)
        if not normalized or normalized in allowlist_set:
            continue
        allowlist_set.add(normalized)
        normalized_allowlist.append(normalized)

    if command_name not in allowlist_set:
        allowed_text = ", ".join(normalized_allowlist) if normalized_allowlist else "<empty>"
        raise MCPStdioPolicyError(
            f"{context_prefix}stdio command '{command_raw}' is not allowed by policy "
            f"'allowlist'. Allowed commands: {allowed_text}. "
            "Use MCP_STDIO_ALLOWED_COMMANDS to extend allowlist, "
            "or MCP_STDIO_COMMAND_POLICY=allow_all for compatibility mode."
        )

    real_paths_by_name = _collect_allowlisted_real_paths_by_name(allowed_commands)
    allowed_real_paths = real_paths_by_name.get(command_name, set())
    command_real_path_text = str(command_real_path)

    if _is_explicit_command_path(command_raw):
        if not allowed_real_paths:
            raise MCPStdioPolicyError(
                f"{context_prefix}stdio command '{command_raw}' uses explicit path "
                "but no resolvable allowlist executable was found for this command name"
            )
        if command_real_path_text not in allowed_real_paths:
            allowed_real_paths_text = ", ".join(sorted(allowed_real_paths))
            raise MCPStdioPolicyError(
                f"{context_prefix}stdio command '{command_raw}' resolves to "
                f"'{command_real_path_text}', which does not match allowlisted real path(s): "
                f"{allowed_real_paths_text}"
            )
    elif allowed_real_paths and command_real_path_text not in allowed_real_paths:
        allowed_real_paths_text = ", ".join(sorted(allowed_real_paths))
        raise MCPStdioPolicyError(
            f"{context_prefix}stdio command '{command_raw}' resolves to "
            f"'{command_real_path_text}', which does not match allowlisted real path(s): "
            f"{allowed_real_paths_text}"
        )


@dataclass
class GeminiTool:
    """Gemini 工具定义（用于转换）"""
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
