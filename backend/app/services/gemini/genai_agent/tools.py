"""
Tools Integration - 工具集成管理

提供工具注册、调用和管理功能
支持 Browser 工具（web_search, read_webpage, selenium_browse）
"""

import logging
import re
from typing import Dict, Any, List, Optional
import json
import os
import sys
import asyncio
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# URL 检测正则表达式（使用共享工具中的实现）
def is_url(text: str) -> bool:
    """
    检测文本是否是 URL
    
    Args:
        text: 要检测的文本
        
    Returns:
        如果是 URL 返回 True，否则返回 False
    """
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    
    # 使用共享工具中的 URL 检测函数
    try:
        from ...gemini.shared.utils import is_url as shared_is_url
        return shared_is_url(text)
    except ImportError:
        # 如果导入失败，使用简单的检测
        # 检查是否以 http:// 或 https:// 开头
        if text.startswith(('http://', 'https://')):
            return True
        
        # 检查是否包含常见的 URL 特征
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return bool(url_pattern.match(text))


class ToolManager:
    """工具管理器"""
    
    def __init__(self, tools: List[Dict[str, Any]]):
        """
        初始化工具管理器
        
        Args:
            tools: 工具配置列表
        """
        self.tools = tools
        self._registered_tools = {}
        self._register_tools()
        logger.info(f"[ToolManager] Initialized with {len(self.tools)} tools")
    
    def _register_tools(self):
        """注册工具"""
        for tool in self.tools:
            tool_type = tool.get('type')
            if tool_type == 'google_search':
                self._register_google_search()
            elif tool_type == 'file_search':
                self._register_file_search(tool.get('file_search_store_names', []))
            elif tool_type == 'code_execution':
                self._register_code_execution()
            elif tool_type == 'browser' or tool_type == 'enable_browser':
                # 注册 Browser 工具
                self._register_browser_tools()
            # 可以添加更多工具类型
        
        # 如果没有显式注册 Browser 工具，但检测到 URL，自动注册
        # 注意：这里无法直接访问 prompt，需要在外部调用时处理
    
    def _register_google_search(self):
        """注册 Google Search 工具"""
        self._registered_tools['google_search'] = {
            'name': 'google_search',
            'description': 'Search the web using Google Search',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Search query'
                    }
                },
                'required': ['query']
            }
        }
    
    def _register_file_search(self, store_names: List[str]):
        """注册 File Search 工具"""
        if store_names:
            self._registered_tools['file_search'] = {
                'name': 'file_search',
                'description': 'Search in uploaded documents',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query'
                        },
                        'store_names': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'File search store names'
                        },
                        'top_k': {
                            'type': 'integer',
                            'description': 'Maximum number of matches to return (1-100)',
                            'minimum': 1,
                            'maximum': 100
                        },
                        'metadata_filter': {
                            'type': 'object',
                            'description': 'Optional file-level filters (extensions/path_contains/max_file_size_bytes/file_glob)'
                        }
                    },
                    'required': ['query']
                },
                'store_names': store_names
            }
    
    def _register_code_execution(self):
        """注册 Code Execution 工具"""
        self._registered_tools['code_execution'] = {
            'name': 'code_execution',
            'description': 'Execute Python code',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {
                        'type': 'string',
                        'description': 'Python code to execute'
                    }
                },
                'required': ['code']
            }
        }
    
    def _register_browser_tools(self):
        """注册 Browser 工具（web_search, read_webpage, selenium_browse）"""
        # 导入 Browser 工具声明
        try:
            from ..common.browser import get_tool_declarations
            browser_tools = get_tool_declarations()
            
            for tool_decl in browser_tools:
                tool_name = tool_decl['name']
                self._registered_tools[tool_name] = {
                    'name': tool_name,
                    'description': tool_decl['description'],
                    'parameters': tool_decl['parameters']
                }
            
            logger.info(f"[ToolManager] Registered {len(browser_tools)} browser tools: {[t['name'] for t in browser_tools]}")
        except ImportError as e:
            logger.warning(f"[ToolManager] Failed to import browser tools: {e}")
        except Exception as e:
            logger.error(f"[ToolManager] Failed to register browser tools: {e}", exc_info=True)
    
    def get_tools(self) -> Optional[List[Any]]:
        """
        获取工具列表（GenAI SDK 格式）
        
        Returns:
            GenAI SDK Tool 对象列表，或 None
        """
        if not self._registered_tools:
            return None
        
        try:
            from google.genai import types as genai_types
            
            # 转换为 GenAI SDK Tool 格式
            tools = []
            for tool_name, tool_def in self._registered_tools.items():
                # 创建 FunctionDeclaration
                func_decl = genai_types.FunctionDeclaration(
                    name=tool_def['name'],
                    description=tool_def['description'],
                    parameters=tool_def['parameters']
                )
                
                # 创建 Tool（包含 FunctionDeclaration）
                tool = genai_types.Tool(
                    function_declarations=[func_decl]
                )
                tools.append(tool)
            
            logger.info(f"[ToolManager] Converted {len(tools)} tools to GenAI SDK format")
            return tools if tools else None
            
        except ImportError:
            # 如果导入失败，使用字典格式（向后兼容）
            logger.warning("[ToolManager] google.genai.types not available, using dict format")
            tools = []
            for tool_name, tool_def in self._registered_tools.items():
                tools.append({
                    'function_declarations': [{
                        'name': tool_def['name'],
                        'description': tool_def['description'],
                        'parameters': tool_def['parameters']
                    }]
                })
            return tools if tools else None
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            if tool_name == 'google_search':
                return await self._execute_google_search(args.get('query', ''))
            elif tool_name == 'file_search':
                default_store_names = self._registered_tools.get('file_search', {}).get('store_names', [])
                return await self._execute_file_search(
                    args.get('query', ''),
                    args.get('store_names') or default_store_names,
                    top_k=args.get('top_k', 20),
                    metadata_filter=args.get('metadata_filter'),
                )
            elif tool_name == 'code_execution':
                return await self._execute_code(args.get('code', ''))
            elif tool_name in ['web_search', 'read_webpage', 'selenium_browse']:
                # Browser 工具
                return await self._execute_browser_tool(tool_name, args)
            else:
                return {
                    'error': f'Unknown tool: {tool_name}'
                }
        except Exception as e:
            logger.error(f"[ToolManager] Tool execution failed: {e}", exc_info=True)
            return {
                'error': str(e)
            }
    
    async def _execute_google_search(self, query: str) -> Dict[str, Any]:
        """执行 Google Search"""
        clean_query = (query or "").strip()
        if not clean_query:
            return {
                "success": False,
                "error": "query is required",
                "query": query,
                "results": [],
            }

        logger.info(f"[ToolManager] Google Search: {clean_query}")
        try:
            from ..common.browser import web_search

            raw = web_search(clean_query)
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, list):
                results = parsed
            elif isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
                results = parsed.get("results", [])
            else:
                results = []

            return {
                "success": True,
                "query": clean_query,
                "results": results,
            }
        except Exception as e:
            logger.error(f"[ToolManager] Google Search failed: {e}", exc_info=True)
            return {
                "success": False,
                "query": clean_query,
                "error": str(e),
                "results": [],
            }

    def _resolve_local_search_files(self, store_names: List[str]) -> List[Path]:
        files: List[Path] = []
        for store in store_names:
            value = str(store or "").strip()
            if not value:
                continue
            path = Path(value).expanduser()
            if not path.exists():
                continue
            if path.is_file():
                files.append(path)
                continue
            if path.is_dir():
                for candidate in path.rglob("*"):
                    if candidate.is_file():
                        files.append(candidate)
        return files

    @staticmethod
    def _normalize_file_filters(metadata_filter: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(metadata_filter, dict):
            return {}
        normalized: Dict[str, Any] = {}

        extensions = metadata_filter.get("extensions")
        if isinstance(extensions, list):
            ext_values = []
            for value in extensions:
                ext = str(value or "").strip().lower()
                if not ext:
                    continue
                ext_values.append(ext if ext.startswith(".") else f".{ext}")
            if ext_values:
                normalized["extensions"] = set(ext_values)

        path_contains = metadata_filter.get("path_contains")
        if isinstance(path_contains, str) and path_contains.strip():
            normalized["path_contains"] = [path_contains.strip().lower()]
        elif isinstance(path_contains, list):
            values = [str(v).strip().lower() for v in path_contains if str(v).strip()]
            if values:
                normalized["path_contains"] = values

        file_glob = metadata_filter.get("file_glob")
        if isinstance(file_glob, str) and file_glob.strip():
            normalized["file_glob"] = [file_glob.strip()]
        elif isinstance(file_glob, list):
            values = [str(v).strip() for v in file_glob if str(v).strip()]
            if values:
                normalized["file_glob"] = values

        max_size = metadata_filter.get("max_file_size_bytes")
        try:
            max_size_int = int(max_size)
            if max_size_int > 0:
                normalized["max_file_size_bytes"] = max_size_int
        except Exception:
            pass

        return normalized

    def _file_matches_filters(self, path: Path, file_filters: Dict[str, Any]) -> bool:
        if not file_filters:
            return True

        extensions = file_filters.get("extensions")
        if isinstance(extensions, set) and extensions and path.suffix.lower() not in extensions:
            return False

        path_contains = file_filters.get("path_contains")
        if isinstance(path_contains, list) and path_contains:
            lower_path = str(path).lower()
            if not all(token in lower_path for token in path_contains):
                return False

        file_glob = file_filters.get("file_glob")
        if isinstance(file_glob, list) and file_glob:
            if not any(path.match(pattern) for pattern in file_glob):
                return False

        max_size = file_filters.get("max_file_size_bytes")
        if isinstance(max_size, int) and max_size > 0:
            try:
                if path.stat().st_size > max_size:
                    return False
            except Exception:
                return False

        return True

    @staticmethod
    def _is_text_searchable_file(path: Path) -> bool:
        return path.suffix.lower() in {
            ".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml",
            ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".sql",
            ".html", ".htm", ".css", ".log",
        }

    async def _execute_file_search(
        self,
        query: str,
        store_names: List[str],
        top_k: int = 20,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行 File Search"""
        clean_query = (query or "").strip()
        if not clean_query:
            return {
                "success": False,
                "error": "query is required",
                "query": query,
                "matches": [],
            }

        safe_top_k = max(1, min(int(top_k or 20), 100))
        file_filters = self._normalize_file_filters(metadata_filter)

        logger.info(
            f"[ToolManager] File Search: query={clean_query!r}, stores={store_names}, top_k={safe_top_k}, filters={file_filters}"
        )
        files = self._resolve_local_search_files(store_names)
        if not files:
            return {
                "success": False,
                "query": clean_query,
                "store_names": store_names,
                "error": "No readable local files found from store_names",
                "matches": [],
            }

        pattern = re.compile(re.escape(clean_query), re.IGNORECASE)
        matches: List[Dict[str, Any]] = []
        max_matches = safe_top_k
        max_file_size = 2 * 1024 * 1024  # 2 MB

        for path in files:
            if len(matches) >= max_matches:
                break
            if not self._is_text_searchable_file(path):
                continue
            if not self._file_matches_filters(path, file_filters):
                continue
            try:
                if path.stat().st_size > max_file_size:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                match = pattern.search(line)
                if not match:
                    continue
                line_text = line.rstrip("\n")
                snippet_start = max(0, match.start() - 80)
                snippet_end = min(len(line_text), match.end() + 80)
                snippet = line_text[snippet_start:snippet_end].strip()
                if len(snippet) > 240:
                    snippet = f"{snippet[:237]}..."
                highlight_start = max(0, match.start() - snippet_start)
                highlight_end = min(len(snippet), highlight_start + len(match.group(0)))
                matches.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "snippet": snippet,
                        "highlights": [
                            {
                                "start": highlight_start,
                                "end": highlight_end,
                            }
                        ],
                    }
                )
                if len(matches) >= max_matches:
                    break

        return {
            "success": True,
            "query": clean_query,
            "store_names": store_names,
            "top_k": safe_top_k,
            "metadata_filter": {
                key: sorted(value) if isinstance(value, set) else value
                for key, value in file_filters.items()
            },
            "searched_files": len(files),
            "matches": matches,
        }

    async def _execute_code(self, code: str) -> Dict[str, Any]:
        """执行代码"""
        clean_code = (code or "").strip()
        if not clean_code:
            return {
                "success": False,
                "status": "invalid_input",
                "error": "code is required",
                "output": "",
            }

        logger.info(f"[ToolManager] Code Execution: {clean_code[:80]}...")
        timeout_sec = int(os.getenv("GEMINI_TOOL_CODE_TIMEOUT_SEC", "12"))
        max_output_chars = int(os.getenv("GEMINI_TOOL_CODE_MAX_OUTPUT", "12000"))

        with tempfile.TemporaryDirectory(prefix="gemini-tool-code-") as tmp_dir:
            script_path = Path(tmp_dir) / "script.py"
            script_path.write_text(clean_code, encoding="utf-8")
            start = asyncio.get_running_loop().time()
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmp_dir,
                )
                stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
                elapsed_ms = int((asyncio.get_running_loop().time() - start) * 1000)
                stdout = (stdout_b or b"").decode("utf-8", errors="replace")
                stderr = (stderr_b or b"").decode("utf-8", errors="replace")
                output = stdout[:max_output_chars]
                error_text = stderr[:max_output_chars]

                if process.returncode == 0:
                    return {
                        "success": True,
                        "status": "success",
                        "output": output,
                        "error": "",
                        "execution_time_ms": elapsed_ms,
                        "return_code": 0,
                    }
                return {
                    "success": False,
                    "status": "failed",
                    "output": output,
                    "error": error_text or f"Process exited with code {process.returncode}",
                    "execution_time_ms": elapsed_ms,
                    "return_code": process.returncode,
                }
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "status": "timeout",
                    "output": "",
                    "error": f"Code execution timed out after {timeout_sec}s",
                    "execution_time_ms": timeout_sec * 1000,
                    "return_code": None,
                }
            except Exception as e:
                logger.error(f"[ToolManager] Code execution failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "status": "error",
                    "output": "",
                    "error": str(e),
                }
    
    async def _execute_browser_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 Browser 工具
        
        Args:
            tool_name: 工具名称（web_search, read_webpage, selenium_browse）
            args: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 导入 Browser 工具
            from ..common.browser import AVAILABLE_TOOLS
            
            if tool_name not in AVAILABLE_TOOLS:
                return {
                    'error': f'Browser tool {tool_name} not found'
                }
            
            tool_func = AVAILABLE_TOOLS[tool_name]
            logger.info(f"[ToolManager] Executing browser tool: {tool_name} with args: {args}")
            
            # 执行工具（可能是同步或异步）
            import asyncio
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**args)
            else:
                # 同步函数在异步上下文中执行
                result = await asyncio.to_thread(tool_func, **args)
            
            # 处理 selenium_browse 返回的结构化响应
            if tool_name == 'selenium_browse':
                if isinstance(result, dict):
                    if result.get('error'):
                        return {
                            'error': result['error']
                        }
                    else:
                        return {
                            'result': result.get('content', ''),
                            'screenshot': result.get('screenshot'),  # Base64 截图
                            'success': True
                        }
            
            # 其他工具返回字符串
            return {
                'result': result if isinstance(result, str) else str(result),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"[ToolManager] Browser tool execution failed: {e}", exc_info=True)
            return {
                'error': str(e),
                'success': False
            }
