"""
Execution Graph - 执行图（DAG）管理

提供：
- 拓扑排序
- 循环依赖检测
- 层级分组
- 依赖关系管理
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict, deque

from .task_decomposer import SubTask

logger = logging.getLogger(__name__)


class ExecutionGraph:
    """
    执行图（有向无环图）
    
    管理子任务之间的依赖关系，提供拓扑排序和执行顺序
    """
    
    def __init__(self, subtasks: List[SubTask]):
        """
        初始化执行图
        
        Args:
            subtasks: 子任务列表
        """
        self.subtasks = subtasks
        self.task_map: Dict[str, SubTask] = {task.id: task for task in subtasks if task.id}
        self.edges: List[Tuple[str, str]] = self._build_edges()
        self.adjacency_list: Dict[str, List[str]] = self._build_adjacency_list()
        self.reverse_adjacency_list: Dict[str, List[str]] = self._build_reverse_adjacency_list()
        
        logger.info(f"[ExecutionGraph] Initialized with {len(subtasks)} nodes and {len(self.edges)} edges")
    
    def _build_edges(self) -> List[Tuple[str, str]]:
        """
        构建边列表（依赖关系）
        
        Returns:
            边列表，每个边是 (source_id, target_id) 元组
        """
        edges = []
        for task in self.subtasks:
            if not task.id:
                continue
            
            for dep_id in task.dependencies:
                if dep_id in self.task_map:
                    edges.append((dep_id, task.id))  # dep_id -> task.id (依赖 -> 被依赖)
        
        return edges
    
    def _build_adjacency_list(self) -> Dict[str, List[str]]:
        """
        构建邻接表（正向：从节点到其依赖的节点）
        
        Returns:
            邻接表字典
        """
        adj_list = defaultdict(list)
        for source, target in self.edges:
            adj_list[source].append(target)
        return dict(adj_list)
    
    def _build_reverse_adjacency_list(self) -> Dict[str, List[str]]:
        """
        构建反向邻接表（反向：从节点到依赖它的节点）
        
        Returns:
            反向邻接表字典
        """
        rev_adj_list = defaultdict(list)
        for source, target in self.edges:
            rev_adj_list[target].append(source)
        return dict(rev_adj_list)
    
    def has_cycle(self) -> bool:
        """
        检测是否存在循环依赖
        
        Returns:
            True 如果存在循环，False 否则
        """
        # 使用 DFS 检测循环
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def dfs(node_id: str) -> bool:
            """DFS 检测循环"""
            if node_id in rec_stack:
                return True  # 发现循环
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            # 检查所有依赖的节点
            for dep_id in self.task_map.get(node_id, SubTask("", id="")).dependencies:
                if dep_id in self.task_map and dfs(dep_id):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # 检查所有节点
        for task_id in self.task_map.keys():
            if task_id not in visited:
                if dfs(task_id):
                    return True
        
        return False
    
    def get_execution_levels(self) -> List[List[SubTask]]:
        """
        获取拓扑排序的执行层级
        
        使用 Kahn 算法进行拓扑排序，按层级分组
        
        Returns:
            List[List[SubTask]]: 按层级分组的子任务列表
            
        Raises:
            ValueError: 如果存在循环依赖
        """
        if self.has_cycle():
            raise ValueError("Execution graph contains cycles")
        
        # 计算入度（每个节点有多少依赖）
        in_degree: Dict[str, int] = {task_id: 0 for task_id in self.task_map.keys()}
        for source, target in self.edges:
            in_degree[target] += 1
        
        # 使用队列进行拓扑排序
        queue = deque()
        for task_id, degree in in_degree.items():
            if degree == 0:
                queue.append(task_id)
        
        levels: List[List[SubTask]] = []
        remaining = set(self.task_map.keys())
        
        while queue or remaining:
            # 当前层级的所有节点
            current_level_ids: List[str] = []
            
            # 处理队列中的所有节点（入度为 0）
            while queue:
                node_id = queue.popleft()
                if node_id in remaining:
                    current_level_ids.append(node_id)
                    remaining.remove(node_id)
            
            if not current_level_ids:
                # 如果还有剩余节点但没有入度为 0 的节点，说明有循环
                if remaining:
                    raise ValueError(f"Circular dependency detected. Remaining nodes: {remaining}")
                break
            
            # 转换为 SubTask 对象
            current_level = [self.task_map[task_id] for task_id in current_level_ids]
            levels.append(current_level)
            
            # 更新入度：移除当前层级节点后，更新依赖它们的节点的入度
            for node_id in current_level_ids:
                # 找到所有依赖当前节点的节点
                dependent_nodes = self.adjacency_list.get(node_id, [])
                for dep_node_id in dependent_nodes:
                    if dep_node_id in in_degree:
                        in_degree[dep_node_id] -= 1
                        if in_degree[dep_node_id] == 0 and dep_node_id in remaining:
                            queue.append(dep_node_id)
        
        logger.info(f"[ExecutionGraph] Generated {len(levels)} execution levels")
        return levels
    
    def get_execution_order(self) -> List[SubTask]:
        """
        获取拓扑排序的执行顺序（扁平列表）
        
        Returns:
            List[SubTask]: 按执行顺序排列的子任务列表
            
        Raises:
            ValueError: 如果存在循环依赖
        """
        levels = self.get_execution_levels()
        # 展平层级列表
        return [task for level in levels for task in level]
    
    def get_dependencies(self, task_id: str) -> List[str]:
        """
        获取指定任务的所有依赖（直接依赖）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            依赖的任务 ID 列表
        """
        task = self.task_map.get(task_id)
        if not task:
            return []
        return task.dependencies.copy()
    
    def get_dependents(self, task_id: str) -> List[str]:
        """
        获取依赖指定任务的所有任务（反向依赖）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            依赖此任务的任务 ID 列表
        """
        return self.reverse_adjacency_list.get(task_id, []).copy()
    
    def get_all_dependencies(self, task_id: str) -> Set[str]:
        """
        获取指定任务的所有依赖（包括间接依赖）
        
        使用 DFS 递归获取所有依赖
        
        Args:
            task_id: 任务 ID
            
        Returns:
            所有依赖的任务 ID 集合（包括间接依赖）
        """
        all_deps: Set[str] = set()
        visited: Set[str] = set()
        
        def dfs(node_id: str):
            """DFS 收集所有依赖"""
            if node_id in visited:
                return
            visited.add(node_id)
            
            task = self.task_map.get(node_id)
            if not task:
                return
            
            for dep_id in task.dependencies:
                if dep_id in self.task_map:
                    all_deps.add(dep_id)
                    dfs(dep_id)
        
        dfs(task_id)
        return all_deps
    
    def get_all_dependents(self, task_id: str) -> Set[str]:
        """
        获取依赖指定任务的所有任务（包括间接依赖）
        
        使用 DFS 递归获取所有依赖此任务的任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            所有依赖此任务的任务 ID 集合（包括间接依赖）
        """
        all_dependents: Set[str] = set()
        visited: Set[str] = set()
        
        def dfs(node_id: str):
            """DFS 收集所有依赖此节点的节点"""
            if node_id in visited:
                return
            visited.add(node_id)
            
            dependents = self.reverse_adjacency_list.get(node_id, [])
            for dep_node_id in dependents:
                if dep_node_id in self.task_map:
                    all_dependents.add(dep_node_id)
                    dfs(dep_node_id)
        
        dfs(task_id)
        return all_dependents
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        验证执行图的有效性
        
        Returns:
            (is_valid, error_message) 元组
        """
        # 检查是否有循环依赖
        if self.has_cycle():
            return False, "Execution graph contains cycles"
        
        # 检查是否有孤立节点（没有依赖也没有被依赖）
        all_referenced = set()
        for source, target in self.edges:
            all_referenced.add(source)
            all_referenced.add(target)
        
        isolated = set(self.task_map.keys()) - all_referenced
        if isolated and len(self.task_map) > 1:
            # 如果有多个节点但存在孤立节点，可能是配置错误
            logger.warning(f"[ExecutionGraph] Found isolated nodes: {isolated}")
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（用于序列化）
        
        Returns:
            字典表示
        """
        return {
            "nodes": [task.to_dict() for task in self.subtasks],
            "edges": [{"source": source, "target": target} for source, target in self.edges],
            "levels": [
                [task.id for task in level]
                for level in self.get_execution_levels()
            ]
        }
