"""ExecutionContext - 节点间数据传递"""

import re
from typing import Dict, Any, Optional, List


class ExecutionContext:
    """工作流执行上下文，管理节点间数据传递"""

    def __init__(self, initial_input: Dict[str, Any]):
        self._outputs: Dict[str, Any] = {}
        self._output_history: Dict[str, List[Any]] = {}
        self._output_order: List[str] = []
        self._errors: Dict[str, str] = {}
        self._loop_iterations: Dict[str, int] = {}
        self.initial_input = initial_input

    def set_output(self, node_id: str, output: Any):
        self._outputs[node_id] = output
        self._output_history.setdefault(node_id, []).append(output)
        self._output_order.append(node_id)

    def get_output(self, node_id: str) -> Optional[Any]:
        return self._outputs.get(node_id)

    def get_latest_output(self) -> Optional[Any]:
        if not self._output_order:
            return None
        return self._outputs.get(self._output_order[-1])

    def get_node_history(self, node_id: str) -> List[Any]:
        return self._output_history.get(node_id, [])

    def increment_loop_iteration(self, node_id: str) -> int:
        current = self._loop_iterations.get(node_id, 0) + 1
        self._loop_iterations[node_id] = current
        return current

    def get_loop_iteration(self, node_id: str) -> int:
        return self._loop_iterations.get(node_id, 0)

    def set_error(self, node_id: str, error: str):
        self._errors[node_id] = error

    def get_error(self, node_id: str) -> Optional[str]:
        return self._errors.get(node_id)

    def _resolve_path(self, data: Any, path: str) -> Any:
        if path is None or path == "":
            return data

        normalized = re.sub(r'\[(\d+)\]', r'.\1', path)
        parts = [part for part in normalized.split('.') if part != ""]
        current = data

        for part in parts:
            if isinstance(current, list):
                if not part.isdigit():
                    return None
                idx = int(part)
                if idx < 0 or idx >= len(current):
                    return None
                current = current[idx]
            elif isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            else:
                return None
        return current

    def _resolve_placeholder(self, expression: str) -> Any:
        expr = expression.strip()

        if expr == "input":
            return self.initial_input
        if expr.startswith("input."):
            return self._resolve_path(self.initial_input, expr[6:])

        if expr.startswith("outputs."):
            return self._resolve_path(self._outputs, expr[8:])

        if expr == "prev.output":
            return self.get_latest_output()
        if expr.startswith("prev.output."):
            latest = self.get_latest_output()
            return self._resolve_path(latest, expr[len("prev.output."):])

        if ".output" in expr:
            node_ref, _, suffix = expr.partition(".output")
            base_output = self.get_output(node_ref)
            if suffix.startswith("."):
                return self._resolve_path(base_output, suffix[1:])
            return base_output

        return None

    def resolve_template(self, template: str) -> Any:
        """
        解析模板表达式
        
        支持:
          {{start.output}}         -> start 节点的完整输出
          {{node_2.output.text}}   -> node_2 输出中的 text 字段
          {{prev.output}}          -> 最后一个节点的完整输出
          {{prev.output.text}}     -> 最后一个节点输出中的 text 字段
          {{input.task}}           -> 初始输入 task 字段
        """
        if not isinstance(template, str) or "{{" not in template:
            return template

        pattern = r'\{\{([^{}]+)\}\}'
        matches = list(re.finditer(pattern, template))
        if not matches:
            return template

        if len(matches) == 1 and matches[0].span() == (0, len(template)):
            value = self._resolve_placeholder(matches[0].group(1))
            return template if value is None else value

        result = template
        for match in matches:
            full_match = match.group(0)
            expression = match.group(1)
            value = self._resolve_placeholder(expression)
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                replacement = str(value)
            else:
                replacement = str(value)
            result = result.replace(full_match, replacement)
        return result

    def get_final_result(self) -> Dict[str, Any]:
        """获取最终结果（最后一个有输出的节点）"""
        final_node_id = self._output_order[-1] if self._output_order else None
        return {
            "outputs": self._outputs,
            "errors": self._errors,
            "final_node_id": final_node_id,
            "final_output": self._outputs.get(final_node_id) if final_node_id else None,
            "loop_iterations": self._loop_iterations,
        }
