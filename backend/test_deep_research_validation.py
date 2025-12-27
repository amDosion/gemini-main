"""
Deep Research 基础功能验证脚本

验证 Deep Research 迁移后的基础功能：
1. 研究任务启动
2. 状态查询
3. 研究完成
4. 继续研究
5. 追问功能

使用方法：
    python test_deep_research_validation.py

环境变量：
    GEMINI_API_KEY: Google GenAI API Key
"""

import os
import sys
import time
import asyncio
import logging
from typing import Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.interactions_service import InteractionsService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeepResearchValidator:
    """Deep Research 功能验证器"""
    
    def __init__(self, api_key: str):
        """
        初始化验证器
        
        Args:
            api_key: Google GenAI API Key
        """
        self.api_key = api_key
        self.service = InteractionsService(api_key=api_key)
        self.test_results = []
    
    async def test_start_research(self) -> Optional[str]:
        """
        测试 1: 研究任务启动
        
        Returns:
            interaction_id if successful, None otherwise
        """
        logger.info("=" * 60)
        logger.info("测试 1: 研究任务启动")
        logger.info("=" * 60)
        
        try:
            prompt = "What are the latest developments in quantum computing?"
            
            logger.info(f"Prompt: {prompt}")
            logger.info("Creating interaction...")
            
            interaction = await self.service.create_interaction(
                agent="deep-research-pro-preview-12-2025",
                input=prompt,
                background=True,
                store=True
            )
            
            logger.info(f"✅ Interaction created: {interaction.id}")
            logger.info(f"   Status: {interaction.status}")
            
            self.test_results.append({
                "test": "start_research",
                "status": "PASS",
                "interaction_id": interaction.id
            })
            
            return interaction.id
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            self.test_results.append({
                "test": "start_research",
                "status": "FAIL",
                "error": str(e)
            })
            return None
    
    async def test_query_status(self, interaction_id: str) -> bool:
        """
        测试 2: 状态查询
        
        Args:
            interaction_id: Interaction ID to query
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("测试 2: 状态查询")
        logger.info("=" * 60)
        
        try:
            logger.info(f"Querying interaction: {interaction_id}")
            
            # 轮询状态直到完成或失败
            max_attempts = 60  # 最多等待 10 分钟
            attempt = 0
            
            while attempt < max_attempts:
                interaction = await self.service.get_interaction(interaction_id)
                
                logger.info(f"   Attempt {attempt + 1}: Status = {interaction.status}")
                
                if interaction.status == "completed":
                    logger.info("✅ Research completed")
                    
                    # 提取结果
                    result_text = ""
                    for output in interaction.outputs:
                        if hasattr(output, 'text') and output.type == 'text':
                            result_text += output.text
                    
                    logger.info(f"   Result length: {len(result_text)} characters")
                    logger.info(f"   Result preview: {result_text[:200]}...")
                    
                    self.test_results.append({
                        "test": "query_status",
                        "status": "PASS",
                        "result_length": len(result_text)
                    })
                    
                    return True
                
                elif interaction.status == "failed":
                    logger.error(f"❌ Research failed")
                    self.test_results.append({
                        "test": "query_status",
                        "status": "FAIL",
                        "error": "Research task failed"
                    })
                    return False
                
                # 等待 10 秒后重试
                await asyncio.sleep(10)
                attempt += 1
            
            logger.error(f"❌ Timeout: Research did not complete in {max_attempts * 10} seconds")
            self.test_results.append({
                "test": "query_status",
                "status": "FAIL",
                "error": "Timeout"
            })
            return False
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            self.test_results.append({
                "test": "query_status",
                "status": "FAIL",
                "error": str(e)
            })
            return False
    
    async def test_continue_research(self, previous_interaction_id: str) -> Optional[str]:
        """
        测试 3: 继续研究
        
        Args:
            previous_interaction_id: Previous interaction ID
            
        Returns:
            new interaction_id if successful, None otherwise
        """
        logger.info("=" * 60)
        logger.info("测试 3: 继续研究")
        logger.info("=" * 60)
        
        try:
            prompt = "Can you provide more details about quantum error correction?"
            
            logger.info(f"Previous interaction: {previous_interaction_id}")
            logger.info(f"Continue prompt: {prompt}")
            logger.info("Creating continue interaction...")
            
            interaction = await self.service.create_interaction(
                agent="deep-research-pro-preview-12-2025",
                input=prompt,
                previous_interaction_id=previous_interaction_id,
                background=True,
                store=True
            )
            
            logger.info(f"✅ Continue interaction created: {interaction.id}")
            logger.info(f"   Status: {interaction.status}")
            
            self.test_results.append({
                "test": "continue_research",
                "status": "PASS",
                "interaction_id": interaction.id
            })
            
            return interaction.id
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            self.test_results.append({
                "test": "continue_research",
                "status": "FAIL",
                "error": str(e)
            })
            return None
    
    async def test_followup_question(self, previous_interaction_id: str) -> Optional[str]:
        """
        测试 4: 追问功能
        
        Args:
            previous_interaction_id: Previous interaction ID
            
        Returns:
            new interaction_id if successful, None otherwise
        """
        logger.info("=" * 60)
        logger.info("测试 4: 追问功能")
        logger.info("=" * 60)
        
        try:
            question = "What are the main challenges in quantum computing?"
            
            logger.info(f"Previous interaction: {previous_interaction_id}")
            logger.info(f"Follow-up question: {question}")
            logger.info("Creating followup interaction...")
            
            interaction = await self.service.create_interaction(
                model="gemini-2.5-flash",
                input=question,
                previous_interaction_id=previous_interaction_id,
                background=False,
                store=True
            )
            
            logger.info(f"✅ Follow-up interaction created: {interaction.id}")
            logger.info(f"   Status: {interaction.status}")
            
            # 提取回答
            answer_text = ""
            for output in interaction.outputs:
                if hasattr(output, 'text') and output.type == 'text':
                    answer_text += output.text
            
            logger.info(f"   Answer length: {len(answer_text)} characters")
            logger.info(f"   Answer preview: {answer_text[:200]}...")
            
            self.test_results.append({
                "test": "followup_question",
                "status": "PASS",
                "interaction_id": interaction.id,
                "answer_length": len(answer_text)
            })
            
            return interaction.id
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            self.test_results.append({
                "test": "followup_question",
                "status": "FAIL",
                "error": str(e)
            })
            return None
    
    def print_summary(self):
        """打印测试结果摘要"""
        logger.info("=" * 60)
        logger.info("测试结果摘要")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["status"] == "PASS")
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info("")
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            logger.info(f"{status_icon} {result['test']}: {result['status']}")
            if result["status"] == "FAIL":
                logger.info(f"   Error: {result.get('error', 'Unknown error')}")
        
        logger.info("=" * 60)
        
        return passed_tests == total_tests


async def main():
    """主函数"""
    # 获取 API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY environment variable not set")
        logger.error("   Please set it with: export GEMINI_API_KEY=your_api_key")
        sys.exit(1)
    
    logger.info("Starting Deep Research validation...")
    logger.info("")
    
    # 创建验证器
    validator = DeepResearchValidator(api_key)
    
    # 测试 1: 启动研究
    interaction_id = await validator.test_start_research()
    if not interaction_id:
        logger.error("❌ Failed to start research, aborting tests")
        validator.print_summary()
        sys.exit(1)
    
    logger.info("")
    
    # 测试 2: 查询状态
    success = await validator.test_query_status(interaction_id)
    if not success:
        logger.error("❌ Failed to query status, aborting tests")
        validator.print_summary()
        sys.exit(1)
    
    logger.info("")
    
    # 测试 3: 继续研究
    continue_id = await validator.test_continue_research(interaction_id)
    if continue_id:
        # 等待继续研究完成
        await validator.test_query_status(continue_id)
    
    logger.info("")
    
    # 测试 4: 追问功能
    await validator.test_followup_question(interaction_id)
    
    logger.info("")
    
    # 打印摘要
    all_passed = validator.print_summary()
    
    if all_passed:
        logger.info("✅ All tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
