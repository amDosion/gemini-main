"""
状态管理器

负责交互的持久化和上下文加载
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging


logger = logging.getLogger(__name__)


class StorageBackend:
    """存储后端接口"""
    
    async def save(self, interaction_id: str, data: Dict[str, Any], ttl: int) -> None:
        """保存交互数据"""
        raise NotImplementedError
    
    async def load(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """加载交互数据"""
        raise NotImplementedError
    
    async def delete(self, interaction_id: str) -> None:
        """删除交互数据"""
        raise NotImplementedError


class MemoryStorage(StorageBackend):
    """内存存储后端（开发/测试用）"""
    
    def __init__(self):
        self.interactions: Dict[str, Dict[str, Any]] = {}
        self.expiry: Dict[str, datetime] = {}
    
    async def save(self, interaction_id: str, data: Dict[str, Any], ttl: int) -> None:
        """保存交互到内存"""
        self.interactions[interaction_id] = data
        self.expiry[interaction_id] = datetime.now() + timedelta(seconds=ttl)
        logger.debug(f"Saved interaction {interaction_id} to memory")
    
    async def load(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """从内存加载交互"""
        # 检查是否过期
        if interaction_id in self.expiry:
            if datetime.now() > self.expiry[interaction_id]:
                # 已过期，删除
                await self.delete(interaction_id)
                return None
        
        return self.interactions.get(interaction_id)
    
    async def delete(self, interaction_id: str) -> None:
        """从内存删除交互"""
        self.interactions.pop(interaction_id, None)
        self.expiry.pop(interaction_id, None)
        logger.debug(f"Deleted interaction {interaction_id} from memory")


class StateManager:
    """
    状态管理器
    
    负责交互的持久化和上下文加载
    """
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        """
        初始化状态管理器
        
        Args:
            storage_backend: 存储后端（默认使用内存存储）
        """
        self.storage = storage_backend or MemoryStorage()
        logger.info(f"StateManager initialized with {type(self.storage).__name__}")
    
    async def save_interaction(
        self,
        interaction: Any,
        ttl: int = 86400  # 默认 1 天
    ) -> None:
        """
        保存交互
        
        Args:
            interaction: Interaction 对象（google.genai SDK 返回的动态对象）
            ttl: 保留时间（秒），默认 1 天
        """
        try:
            # 将 Interaction 对象转换为字典
            data = {
                "id": interaction.id,
                "model": getattr(interaction, "model", None),
                "agent": getattr(interaction, "agent", None),
                "status": interaction.status,
                "input": getattr(interaction, "input", []),
                "outputs": getattr(interaction, "outputs", []),
                "previous_interaction_id": getattr(interaction, "previous_interaction_id", None),
                "created_at": datetime.now().isoformat()
            }
            
            await self.storage.save(interaction.id, data, ttl)
            logger.info(f"Saved interaction {interaction.id} with TTL {ttl}s")
            
        except Exception as e:
            logger.error(f"Failed to save interaction {interaction.id}: {e}")
            raise
    
    async def load_context(
        self,
        interaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        加载交互上下文
        
        Args:
            interaction_id: 交互 ID
            
        Returns:
            交互数据字典，如果不存在或已过期则返回 None
        """
        try:
            data = await self.storage.load(interaction_id)
            
            if not data:
                logger.warning(f"Interaction {interaction_id} not found or expired")
                return None
            
            logger.info(f"Loaded interaction {interaction_id}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load interaction {interaction_id}: {e}")
            return None
    
    async def delete_interaction(
        self,
        interaction_id: str
    ) -> None:
        """
        删除交互
        
        Args:
            interaction_id: 交互 ID
        """
        try:
            await self.storage.delete(interaction_id)
            logger.info(f"Deleted interaction {interaction_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete interaction {interaction_id}: {e}")
            raise
    
    async def build_conversation_chain(
        self,
        interaction_id: str
    ) -> List[Dict[str, Any]]:
        """
        构建完整的对话链
        
        从指定交互开始，递归加载所有 previous_interaction_id
        
        Args:
            interaction_id: 交互 ID
            
        Returns:
            按时间顺序排列的交互数据字典列表（最早的在前）
            
        Raises:
            ValueError: 检测到循环引用
            KeyError: 交互不存在
        """
        chain = []
        visited = set()  # 防止循环引用
        current_id = interaction_id
        
        while current_id:
            # 检查循环引用
            if current_id in visited:
                logger.error(f"Circular reference detected: {current_id}")
                raise ValueError(f"Circular reference detected: {current_id}")
            visited.add(current_id)
            
            # 加载当前交互
            interaction = await self.load_context(current_id)
            if not interaction:
                logger.error(f"Interaction not found: {current_id}")
                raise KeyError(f"Interaction not found: {current_id}")
            
            # 添加到链的开头（保持时间顺序）
            chain.insert(0, interaction)
            
            # 继续加载上一个交互
            current_id = interaction.get("previous_interaction_id")
        
        logger.info(f"Built conversation chain with {len(chain)} interactions")
        return chain
