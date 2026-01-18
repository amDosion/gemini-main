"""
路径工具模块

统一管理项目路径，支持相对路径，兼容 VPS 和 Docker 部署。

策略：
1. 优先使用环境变量 PROJECT_ROOT
2. 回退到基于代码位置的自动计算（带验证）
3. 所有路径都基于项目根目录的相对路径
"""
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 缓存项目根目录，避免重复计算
_project_root_cache: Optional[str] = None


def get_project_root() -> str:
    """
    获取项目根目录
    
    优先级：
    1. 环境变量 PROJECT_ROOT
    2. 基于代码位置自动计算（带验证）
    3. 当前工作目录（最后回退）
    
    Returns:
        str: 项目根目录的绝对路径
    """
    global _project_root_cache
    
    # 如果已缓存，直接返回
    if _project_root_cache:
        return _project_root_cache
    
    # 1. 优先使用环境变量
    project_root = os.getenv('PROJECT_ROOT')
    if project_root:
        project_root = os.path.abspath(project_root)
        if _validate_project_root(project_root):
            _project_root_cache = project_root
            logger.info(f"[PathUtils] 使用环境变量 PROJECT_ROOT: {project_root}")
            return project_root
        else:
            logger.warning(f"[PathUtils] 环境变量 PROJECT_ROOT 指向的目录无效: {project_root}")
    
    # 2. 基于代码位置自动计算
    # 从 backend/app/core/path_utils.py 向上三级到项目根目录
    current_file = Path(__file__).resolve()
    # backend/app/core/path_utils.py
    # → backend/app/core/
    # → backend/app/
    # → backend/
    # → project root
    calculated_root = current_file.parent.parent.parent.parent
    
    if _validate_project_root(str(calculated_root)):
        _project_root_cache = str(calculated_root)
        logger.info(f"[PathUtils] 自动计算项目根目录: {_project_root_cache}")
        return _project_root_cache
    
    # 3. 最后回退：使用当前工作目录
    cwd = os.getcwd()
    if _validate_project_root(cwd):
        _project_root_cache = cwd
        logger.warning(f"[PathUtils] 使用当前工作目录作为项目根目录: {cwd}")
        return cwd
    
    # 如果所有方法都失败，仍然返回计算值（但记录警告）
    _project_root_cache = str(calculated_root)
    logger.error(
        f"[PathUtils] ⚠️ 无法验证项目根目录，使用计算值: {_project_root_cache}\n"
        f"建议设置环境变量 PROJECT_ROOT 指向项目根目录"
    )
    return _project_root_cache


def _validate_project_root(project_root: str) -> bool:
    """
    验证项目根目录是否有效
    
    检查标准：
    1. 目录存在
    2. 包含 backend/app/temp 目录（或可以创建）
    3. 包含 backend/app 目录
    
    Args:
        project_root: 待验证的项目根目录路径
        
    Returns:
        bool: 是否为有效的项目根目录
    """
    if not project_root or not os.path.exists(project_root):
        return False
    
    # 检查关键目录
    backend_app = os.path.join(project_root, 'backend', 'app')
    if not os.path.exists(backend_app):
        return False
    
    # 检查或创建 temp 目录
    temp_dir = os.path.join(project_root, 'backend', 'app', 'temp')
    try:
        os.makedirs(temp_dir, exist_ok=True)
        return os.path.exists(temp_dir)
    except Exception:
        return False


def get_temp_dir() -> str:
    """
    获取临时文件目录（绝对路径）
    
    路径格式：{project_root}/backend/app/temp
    
    Returns:
        str: 临时目录的绝对路径
    """
    project_root = get_project_root()
    temp_dir = os.path.join(project_root, 'backend', 'app', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def get_temp_dir_relative() -> str:
    """
    获取临时文件目录（相对路径，用于数据库存储）
    
    路径格式：backend/app/temp
    
    Returns:
        str: 临时目录的相对路径（相对于项目根目录）
    """
    return 'backend/app/temp'


def _is_path_within_root(path: str, root: str) -> bool:
    """
    验证路径是否在指定的根目录内（防止路径遍历攻击）

    Args:
        path: 待验证的路径
        root: 根目录路径

    Returns:
        bool: 路径是否在根目录内
    """
    try:
        # 将两个路径都解析为绝对路径并规范化
        abs_path = os.path.abspath(os.path.normpath(path))
        abs_root = os.path.abspath(os.path.normpath(root))

        # 使用 os.path.commonpath 检查是否有共同的父路径
        # 如果 abs_path 在 abs_root 内，它们的共同路径应该是 abs_root
        common = os.path.commonpath([abs_path, abs_root])
        return common == abs_root
    except (ValueError, TypeError):
        # 如果路径无效或在不同驱动器上，返回 False
        return False


def resolve_relative_path(relative_path: str) -> str:
    """
    将相对路径解析为绝对路径（带路径遍历保护）

    相对路径格式：backend/app/temp/upload_xxx.png

    Args:
        relative_path: 相对路径（相对于项目根目录）

    Returns:
        str: 绝对路径

    Raises:
        ValueError: 如果路径尝试遍历到项目根目录之外
    """
    project_root = get_project_root()

    # 如果已经是绝对路径，验证后返回
    if os.path.isabs(relative_path):
        if not _is_path_within_root(relative_path, project_root):
            raise ValueError(f"Path traversal attempt detected: {relative_path}")
        return relative_path

    # 拼接项目根目录
    absolute_path = os.path.normpath(os.path.join(project_root, relative_path))

    # 验证解析后的路径仍在项目根目录内
    if not _is_path_within_root(absolute_path, project_root):
        raise ValueError(f"Path traversal attempt detected: {relative_path}")

    return absolute_path


def to_relative_path(absolute_path: str) -> str:
    """
    将绝对路径转换为相对路径（相对于项目根目录，带路径遍历保护）

    Args:
        absolute_path: 绝对路径

    Returns:
        str: 相对路径

    Raises:
        ValueError: 如果路径在项目根目录之外
    """
    project_root = get_project_root()

    # 验证路径在项目根目录内
    if not _is_path_within_root(absolute_path, project_root):
        raise ValueError(f"Path is outside project root: {absolute_path}")

    try:
        # 转换为相对路径
        relative_path = os.path.relpath(absolute_path, project_root)
        # 确保使用正斜杠（跨平台兼容）
        return relative_path.replace('\\', '/')
    except ValueError as e:
        # 如果无法转换（不在同一驱动器或路径无效），记录并抛出异常
        logger.error(f"[PathUtils] 无法将绝对路径转换为相对路径: {absolute_path}")
        raise ValueError(f"Cannot convert path to relative: {absolute_path}") from e


def ensure_relative_path(path: str) -> str:
    """
    确保路径是相对路径（相对于项目根目录）
    
    如果输入是绝对路径，转换为相对路径
    如果输入已经是相对路径，直接返回
    
    Args:
        path: 路径（绝对或相对）
        
    Returns:
        str: 相对路径
    """
    if os.path.isabs(path):
        return to_relative_path(path)
    return path.replace('\\', '/')  # 统一使用正斜杠
