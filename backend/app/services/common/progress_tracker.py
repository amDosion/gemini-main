"""
Progress tracking system for browser operations.

This module provides a way to track and broadcast progress updates
for long-running browser operations to the frontend.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict


class ProgressTracker:
    """
    Tracks progress of browser operations and allows clients to subscribe to updates.
    """
    
    def __init__(self):
        # Store active operations: {operation_id: [queue1, queue2, ...]}
        self.subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        
    async def subscribe(self, operation_id: str) -> asyncio.Queue:
        """
        Subscribe to progress updates for a specific operation.
        
        Args:
            operation_id: Unique identifier for the operation
            
        Returns:
            Queue that will receive progress updates
        """
        queue = asyncio.Queue()
        self.subscribers[operation_id].append(queue)
        return queue
    
    async def unsubscribe(self, operation_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from progress updates.
        
        Args:
            operation_id: Operation identifier
            queue: Queue to remove
        """
        if operation_id in self.subscribers:
            try:
                self.subscribers[operation_id].remove(queue)
            except ValueError:
                pass
            
            # Clean up if no more subscribers
            if not self.subscribers[operation_id]:
                del self.subscribers[operation_id]
    
    async def send_progress(
        self,
        operation_id: str,
        step: str,
        status: str = "in_progress",
        details: Optional[str] = None,
        progress: Optional[int] = None
    ):
        """
        Send a progress update to all subscribers of an operation.
        
        Args:
            operation_id: Operation identifier
            step: Description of current step (e.g., "Initializing browser")
            status: Status of the step ("in_progress", "completed", "error")
            details: Additional details about the step
            progress: Progress percentage (0-100)
        """
        if operation_id not in self.subscribers:
            return
        
        message = {
            "operation_id": operation_id,
            "step": step,
            "status": status,
            "details": details,
            "progress": progress,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all subscribers
        dead_queues = []
        for queue in self.subscribers[operation_id]:
            try:
                await queue.put(message)
            except Exception:
                dead_queues.append(queue)
        
        # Clean up dead queues
        for queue in dead_queues:
            await self.unsubscribe(operation_id, queue)
    
    async def send_complete(self, operation_id: str, result: Any = None):
        """
        Send completion message and clean up.
        
        Args:
            operation_id: Operation identifier
            result: Optional result data
        """
        await self.send_progress(
            operation_id,
            step="Complete",
            status="completed",
            details="Operation completed successfully",
            progress=100
        )
        
        # Give clients time to receive the message
        await asyncio.sleep(0.1)
        
        # Clean up
        if operation_id in self.subscribers:
            del self.subscribers[operation_id]
    
    async def send_error(self, operation_id: str, error: str):
        """
        Send error message and clean up.
        
        Args:
            operation_id: Operation identifier
            error: Error message
        """
        await self.send_progress(
            operation_id,
            step="Error",
            status="error",
            details=error,
            progress=None
        )
        
        # Give clients time to receive the message
        await asyncio.sleep(0.1)
        
        # Clean up
        if operation_id in self.subscribers:
            del self.subscribers[operation_id]


# Global progress tracker instance
progress_tracker = ProgressTracker()
