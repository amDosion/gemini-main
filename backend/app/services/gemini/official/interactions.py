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

"""Interactions API for Deep Research Agent and other advanced features."""

from typing import Optional, Dict, Any
from ._common import BaseModel


class Interaction(BaseModel):
    """Represents an interaction with an agent."""
    
    id: str
    status: str  # 'running', 'completed', 'failed'
    outputs: Optional[list] = None
    error: Optional[str] = None


class InteractionsResource:
    """Synchronous Interactions API."""
    
    def __init__(self, api_client):
        self._api_client = api_client
    
    def create(
        self,
        *,
        input: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> Interaction:
        """Create a new interaction with an agent.
        
        Args:
            input: The input query for the agent
            agent: The agent to use (default: Deep Research Agent)
            background: Whether to run in background mode
            config: Optional configuration
            
        Returns:
            Interaction object with ID and status
        """
        # Mock implementation - would need actual API call
        return Interaction(
            id="mock-interaction-id",
            status="running",
            outputs=[],
            error=None
        )
    
    def get(self, interaction_id: str) -> Interaction:
        """Get an interaction by ID.
        
        Args:
            interaction_id: The ID of the interaction
            
        Returns:
            Interaction object with current status
        """
        # Mock implementation
        return Interaction(
            id=interaction_id,
            status="completed",
            outputs=[{"text": "Mock research result"}],
            error=None
        )


class AsyncInteractionsResource:
    """Asynchronous Interactions API."""
    
    def __init__(self, api_client):
        self._api_client = api_client
    
    async def create(
        self,
        *,
        input: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> Interaction:
        """Async version of create."""
        sync_interactions = InteractionsResource(self._api_client)
        return sync_interactions.create(
            input=input,
            agent=agent,
            background=background,
            config=config
        )
    
    async def get(self, interaction_id: str) -> Interaction:
        """Async version of get."""
        sync_interactions = InteractionsResource(self._api_client)
        return sync_interactions.get(interaction_id)