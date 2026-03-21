# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Interactions API for Deep Research Agent and other advanced features.

基于官方 google.genai.Client.interactions API 的兼容层实现。
直接使用官方 SDK 的 interactions API，而不是自定义的 _interactions 实现。
"""

from typing import Optional, Dict, Any, Union, List
import logging
from .common import BaseModel

logger = logging.getLogger(__name__)


class Interaction(BaseModel):
    """Represents an interaction with an agent (compatibility wrapper).
    
    兼容性包装类，用于将官方 SDK 的 Interaction 对象转换为我们的格式。
    """
    
    id: str
    status: str  # 'in_progress', 'requires_action', 'completed', 'failed', 'cancelled'
    outputs: Optional[list] = None
    error: Optional[str] = None
    
    @classmethod
    def from_official(cls, official_interaction) -> 'Interaction':
        """Convert official Interaction to compatibility wrapper.
        
        Args:
            official_interaction: Official SDK Interaction object
            
        Returns:
            Interaction compatibility wrapper
        """
        # Convert outputs - extract all available content
        outputs = []
        if hasattr(official_interaction, 'outputs') and official_interaction.outputs:
            for output in official_interaction.outputs:
                # Handle different Content types
                output_dict = {}
                
                # Check content type
                if hasattr(output, 'type'):
                    output_dict['type'] = output.type
                
                # Extract text content from various sources
                text_content = None
                
                # Method 1: Direct text attribute
                if hasattr(output, 'text') and output.text:
                    text_content = output.text
                
                # Method 2: TextContent with parts
                elif hasattr(output, 'parts') and output.parts:
                    text_parts = []
                    for part in output.parts:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                        elif hasattr(part, 'type') and part.type == 'text':
                            if hasattr(part, 'text'):
                                text_parts.append(part.text)
                    if text_parts:
                        text_content = ''.join(text_parts)
                
                # Method 3: Check if output itself is a string
                elif isinstance(output, str):
                    text_content = output
                
                # Method 4: Try to extract from content attribute
                elif hasattr(output, 'content'):
                    content = output.content
                    if isinstance(content, str):
                        text_content = content
                    elif hasattr(content, 'text'):
                        text_content = content.text
                    elif isinstance(content, list):
                        # Handle list of content items
                        text_parts = []
                        for item in content:
                            if isinstance(item, str):
                                text_parts.append(item)
                            elif hasattr(item, 'text'):
                                text_parts.append(item.text)
                        if text_parts:
                            text_content = ''.join(text_parts)
                
                if text_content:
                    output_dict['text'] = text_content
                
                # Extract role if present
                if hasattr(output, 'role'):
                    output_dict['role'] = output.role
                
                # Extract other metadata
                if hasattr(output, 'created'):
                    output_dict['created'] = str(output.created) if output.created else None
                
                # Only add if we have some content
                if output_dict:
                    outputs.append(output_dict)
        
        # Extract error if present
        error = None
        if hasattr(official_interaction, 'error') and official_interaction.error:
            error = str(official_interaction.error)
        
        return cls(
            id=official_interaction.id,
            status=official_interaction.status,
            outputs=outputs if outputs else None,
            error=error
        )


class InteractionsResource:
    """Synchronous Interactions API.
    
    基于官方 google.genai.Client.interactions API 的同步包装。
    """
    
    def __init__(self, client):
        """Initialize interactions resource.
        
        Args:
            client: Official google.genai.Client instance
        """
        self._client = client
    
    def create(
        self,
        *,
        input: Union[str, List[Dict[str, Any]]],
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_config: Optional[Dict[str, Any]] = None,
        previous_interaction_id: Optional[str] = None
    ) -> Interaction:
        """Create a new interaction with an agent.
        
        Args:
            input: The input query for the agent (string or list of content)
            agent: The agent to use (default: Deep Research Agent)
            background: Whether to run in background mode
            config: Optional configuration (agent_config) - deprecated, use agent_config
            system_instruction: Optional system instruction
            tools: Optional list of tools
            agent_config: Optional agent configuration (preferred over config)
            previous_interaction_id: Optional previous interaction ID for context
            
        Returns:
            Interaction object with ID and status
        """
        # Use agent_config if provided, otherwise use config
        final_agent_config = agent_config or config
        
        # Build parameters for official SDK
        create_params = {
            'agent': agent,
            'input': input,
            'background': background,
        }
        
        if final_agent_config:
            create_params['agent_config'] = final_agent_config
        if system_instruction:
            create_params['system_instruction'] = system_instruction
        if tools:
            create_params['tools'] = tools
        if previous_interaction_id:
            create_params['previous_interaction_id'] = previous_interaction_id
        
        # Create interaction using official SDK
        try:
            logger.debug(f"[InteractionsResource.create] Creating interaction with params: agent={agent}, background={background}, has_agent_config={bool(final_agent_config)}, has_tools={bool(tools)}")
            official_interaction = self._client.interactions.create(**create_params)
            logger.debug(f"[InteractionsResource.create] Successfully created interaction: id={official_interaction.id if hasattr(official_interaction, 'id') else 'N/A'}, status={official_interaction.status if hasattr(official_interaction, 'status') else 'N/A'}")
        except Exception as e:
            logger.error(f"[InteractionsResource.create] Failed to create interaction: {type(e).__name__}: {str(e)}", exc_info=True)
            raise
        
        # Convert to compatibility format
        try:
            return Interaction.from_official(official_interaction)
        except Exception as e:
            logger.error(f"[InteractionsResource.create] Failed to convert interaction: {type(e).__name__}: {str(e)}", exc_info=True)
            logger.error(f"[InteractionsResource.create] Official interaction type: {type(official_interaction)}, attributes: {dir(official_interaction) if hasattr(official_interaction, '__dict__') else 'N/A'}")
            raise
    
    def get(self, id: str, stream: bool = False, last_event_id: Optional[str] = None) -> Interaction:
        """Get an interaction by ID.
        
        Args:
            id: The ID of the interaction
            stream: Whether to stream events (returns a stream object)
            last_event_id: Last event ID for resuming stream
            
        Returns:
            Interaction object with current status, or stream object if stream=True
        """
        get_params = {'id': id}
        if stream:
            get_params['stream'] = True
        if last_event_id:
            get_params['last_event_id'] = last_event_id
        
        # Get interaction using official SDK
        result = self._client.interactions.get(**get_params)
        
        if stream:
            # Return stream directly
            return result
        else:
            # Convert to compatibility format
            return Interaction.from_official(result)
    
    def delete(self, id: str) -> None:
        """Delete an interaction by ID.
        
        Args:
            id: The ID of the interaction to delete
        """
        self._client.interactions.delete(id=id)
    
    def cancel(self, id: str) -> Interaction:
        """Cancel a running interaction by ID.
        
        This only applies to background interactions that are still running.
        
        Args:
            id: The ID of the interaction to cancel
            
        Returns:
            Interaction object with updated status
        """
        # Cancel interaction using official SDK
        official_interaction = self._client.interactions.cancel(id=id)
        
        # Convert to compatibility format
        return Interaction.from_official(official_interaction)


class AsyncInteractionsResource:
    """Asynchronous Interactions API.
    
    基于官方 google.genai.Client.interactions API 的异步包装。
    """
    
    def __init__(self, client):
        """Initialize async interactions resource.
        
        Args:
            client: Official google.genai.Client instance
        """
        self._client = client
    
    async def create(
        self,
        *,
        input: Union[str, List[Dict[str, Any]]],
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_config: Optional[Dict[str, Any]] = None,
        previous_interaction_id: Optional[str] = None,
        stream: bool = False
    ) -> Interaction:
        """Async version of create.
        
        Args:
            input: The input query for the agent
            agent: The agent to use
            background: Whether to run in background mode
            config: Optional configuration (agent_config) - deprecated, use agent_config
            system_instruction: Optional system instruction
            tools: Optional list of tools
            agent_config: Optional agent configuration (preferred over config)
            previous_interaction_id: Optional previous interaction ID for context
            stream: Whether to stream the response
            
        Returns:
            Interaction object or stream
        """
        # Use agent_config if provided, otherwise use config
        final_agent_config = agent_config or config
        
        # Build parameters for official SDK
        create_params = {
            'agent': agent,
            'input': input,
            'background': background,
        }
        
        if final_agent_config:
            create_params['agent_config'] = final_agent_config
        if system_instruction:
            create_params['system_instruction'] = system_instruction
        if tools:
            create_params['tools'] = tools
        if previous_interaction_id:
            create_params['previous_interaction_id'] = previous_interaction_id
        if stream:
            create_params['stream'] = True
        
        # Create interaction using official async SDK
        if stream:
            # ✅ stream=True 时，create() 返回 Stream 对象，不能 await，直接返回
            return self._client.interactions.create(**create_params)
        else:
            official_interaction = await self._client.interactions.create(**create_params)
            # Convert to compatibility format
            return Interaction.from_official(official_interaction)
    
    async def get(self, id: str, stream: bool = False, last_event_id: Optional[str] = None) -> Interaction:
        """Async version of get."""
        get_params = {'id': id}
        if stream:
            get_params['stream'] = True
        if last_event_id:
            get_params['last_event_id'] = last_event_id
        
        # Get interaction using official async SDK
        result = await self._client.interactions.get(**get_params)
        
        if stream:
            # Return stream directly
            return result
        else:
            # Convert to compatibility format
            return Interaction.from_official(result)
    
    async def delete(self, id: str) -> None:
        """Async version of delete.
        
        Args:
            id: The ID of the interaction to delete
        """
        await self._client.interactions.delete(id=id)
    
    async def cancel(self, id: str) -> Interaction:
        """Cancel a running interaction by ID (async).
        
        This only applies to background interactions that are still running.
        
        Args:
            id: The ID of the interaction to cancel
            
        Returns:
            Interaction object with updated status
        """
        # Cancel interaction using official async SDK
        official_interaction = await self._client.interactions.cancel(id=id)
        
        # Convert to compatibility format
        return Interaction.from_official(official_interaction)
