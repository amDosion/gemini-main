"""
Safe AST-based expression evaluator.

This module intentionally avoids Python ``eval`` and only supports a
whitelisted subset of expression syntax.
"""

from __future__ import annotations

import ast
import operator
from typing import Any, Callable, Dict, Mapping, Optional


class SafeExpressionError(ValueError):
    """Raised when expression contains unsupported or unsafe constructs."""


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

_ALLOWED_STR_METHODS = {
    "startswith",
    "endswith",
    "lower",
    "upper",
    "strip",
    "lstrip",
    "rstrip",
    "replace",
    "split",
    "find",
    "count",
}
_ALLOWED_SEQUENCE_METHODS = {"count", "index"}
_ALLOWED_MAPPING_METHODS = {"get", "keys", "values", "items"}


def _resolve_method_allowlist(target: Any) -> set[str]:
    if isinstance(target, str):
        return _ALLOWED_STR_METHODS
    if isinstance(target, (list, tuple)):
        return _ALLOWED_SEQUENCE_METHODS
    if isinstance(target, dict):
        return _ALLOWED_MAPPING_METHODS
    return set()


class _SafeExpressionEvaluator(ast.NodeVisitor):
    def __init__(
        self,
        *,
        variables: Optional[Mapping[str, Any]] = None,
        functions: Optional[Mapping[str, Callable[..., Any]]] = None,
        max_depth: int = 32,
    ) -> None:
        self._variables = dict(variables or {})
        self._functions = dict(functions or {})
        self._max_depth = max(8, int(max_depth))
        self._depth = 0

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        self._depth += 1
        if self._depth > self._max_depth:
            self._depth -= 1
            raise SafeExpressionError("Expression nesting is too deep")
        try:
            return super().visit(node)
        finally:
            self._depth -= 1

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        identifier = str(node.id or "").strip()
        if identifier in self._variables:
            return self._variables[identifier]
        raise SafeExpressionError(f"Unknown identifier: {identifier}")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            current: Any = True
            for value in node.values:
                current = self.visit(value)
                if not current:
                    return current
            return current
        if isinstance(node.op, ast.Or):
            current = False
            for value in node.values:
                current = self.visit(value)
                if current:
                    return current
            return current
        raise SafeExpressionError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = _BINARY_OPERATORS.get(type(node.op))
        if op is None:
            raise SafeExpressionError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return op(left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = _UNARY_OPERATORS.get(type(node.op))
        if op is None:
            raise SafeExpressionError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(self.visit(node.operand))

    def visit_Compare(self, node: ast.Compare) -> bool:
        left = self.visit(node.left)
        for comparator_node, right_node in zip(node.ops, node.comparators):
            op = _COMPARATORS.get(type(comparator_node))
            if op is None:
                raise SafeExpressionError(f"Unsupported comparator: {type(comparator_node).__name__}")
            right = self.visit(right_node)
            if not op(left, right):
                return False
            left = right
        return True

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        return self.visit(node.body if self.visit(node.test) else node.orelse)

    def visit_List(self, node: ast.List) -> Any:
        return [self.visit(element) for element in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return tuple(self.visit(element) for element in node.elts)

    def visit_Set(self, node: ast.Set) -> Any:
        return {self.visit(element) for element in node.elts}

    def visit_Dict(self, node: ast.Dict) -> Dict[Any, Any]:
        output: Dict[Any, Any] = {}
        for key, value in zip(node.keys, node.values):
            resolved_key = self.visit(key) if key is not None else None
            output[resolved_key] = self.visit(value)
        return output

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        attr = str(node.attr or "").strip()
        if not attr or attr.startswith("_"):
            raise SafeExpressionError("Private/invalid attribute access is not allowed")

        target = self.visit(node.value)
        if isinstance(target, Mapping):
            if attr in target:
                return target[attr]
            raise SafeExpressionError(f"Missing key on mapping: {attr}")

        if hasattr(target, attr):
            value = getattr(target, attr)
            if callable(value):
                raise SafeExpressionError("Direct callable attribute access is not allowed")
            return value

        raise SafeExpressionError(f"Unsupported attribute access: {attr}")

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        target = self.visit(node.value)
        index = self.visit(node.slice)
        try:
            return target[index]
        except Exception as exc:
            raise SafeExpressionError(f"Subscript access failed: {exc}") from exc

    def visit_Slice(self, node: ast.Slice) -> slice:
        lower = self.visit(node.lower) if node.lower is not None else None
        upper = self.visit(node.upper) if node.upper is not None else None
        step = self.visit(node.step) if node.step is not None else None
        return slice(lower, upper, step)

    def visit_Call(self, node: ast.Call) -> Any:
        args = [self.visit(arg) for arg in node.args]
        kwargs: Dict[str, Any] = {}
        for kw in node.keywords:
            if kw.arg is None:
                raise SafeExpressionError("**kwargs is not allowed")
            kwargs[kw.arg] = self.visit(kw.value)

        if isinstance(node.func, ast.Name):
            function_name = str(node.func.id or "").strip()
            function = self._functions.get(function_name)
            if function is None:
                raise SafeExpressionError(f"Function not allowed: {function_name}")
            return function(*args, **kwargs)

        if isinstance(node.func, ast.Attribute):
            method_name = str(node.func.attr or "").strip()
            if not method_name or method_name.startswith("_"):
                raise SafeExpressionError("Private/invalid method call is not allowed")
            target = self.visit(node.func.value)
            allowlist = _resolve_method_allowlist(target)
            if method_name not in allowlist:
                raise SafeExpressionError(f"Method not allowed: {method_name}")
            method = getattr(target, method_name, None)
            if not callable(method):
                raise SafeExpressionError(f"Target method is not callable: {method_name}")
            return method(*args, **kwargs)

        raise SafeExpressionError("Only direct function/method calls are allowed")

    def generic_visit(self, node: ast.AST) -> Any:
        raise SafeExpressionError(f"Unsupported expression syntax: {type(node).__name__}")


def safe_eval_expression(
    expression: str,
    *,
    variables: Optional[Mapping[str, Any]] = None,
    functions: Optional[Mapping[str, Callable[..., Any]]] = None,
    max_depth: int = 32,
    max_nodes: int = 256,
) -> Any:
    expression_text = str(expression or "").strip()
    if not expression_text:
        raise SafeExpressionError("Expression cannot be empty")
    if len(expression_text) > 4000:
        raise SafeExpressionError("Expression is too long")

    try:
        tree = ast.parse(expression_text, mode="eval")
    except SyntaxError as exc:
        raise SafeExpressionError(f"Invalid expression syntax: {exc.msg}") from exc

    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > max_nodes:
        raise SafeExpressionError("Expression is too complex")

    evaluator = _SafeExpressionEvaluator(
        variables=variables,
        functions=functions,
        max_depth=max_depth,
    )
    return evaluator.visit(tree)

