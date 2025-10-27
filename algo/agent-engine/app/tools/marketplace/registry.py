"""
Tool Registry Management
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Tool information"""
    id: str
    name: str
    version: str
    author: str
    description: str
    category: str
    tags: List[str]
    registered_at: datetime
    usage_count: int
    last_used: Optional[datetime]
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "registered_at": self.registered_at.isoformat(),
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


class ToolRegistry:
    """Tool registry for managing tool metadata"""
    
    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {}
        
    def register(self, tool_info: ToolInfo):
        """Register a tool"""
        self.tools[tool_info.id] = tool_info
        logger.info(f"Registered tool: {tool_info.name} ({tool_info.id})")
        
    def unregister(self, tool_id: str) -> bool:
        """Unregister a tool"""
        if tool_id in self.tools:
            tool_name = self.tools[tool_id].name
            del self.tools[tool_id]
            logger.info(f"Unregistered tool: {tool_name} ({tool_id})")
            return True
        return False
        
    def get(self, tool_id: str) -> Optional[ToolInfo]:
        """Get tool information"""
        return self.tools.get(tool_id)
        
    def list_all(self) -> List[ToolInfo]:
        """List all tools"""
        return list(self.tools.values())
        
    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[ToolInfo]:
        """Search tools"""
        results = []
        
        for tool in self.tools.values():
            # Category filter
            if category and tool.category != category:
                continue
                
            # Tags filter
            if tags and not set(tags).intersection(set(tool.tags)):
                continue
                
            # Query filter
            if query:
                searchable = f"{tool.name} {tool.description}".lower()
                if query.lower() not in searchable:
                    continue
                    
            results.append(tool)
            
        return results
        
    def update_usage(self, tool_id: str):
        """Update tool usage statistics"""
        if tool_id in self.tools:
            self.tools[tool_id].usage_count += 1
            self.tools[tool_id].last_used = datetime.utcnow()
            
    def get_statistics(self) -> Dict:
        """Get registry statistics"""
        total = len(self.tools)
        total_usage = sum(t.usage_count for t in self.tools.values())
        
        categories = {}
        for tool in self.tools.values():
            categories[tool.category] = categories.get(tool.category, 0) + 1
            
        return {
            "total_tools": total,
            "total_usage": total_usage,
            "categories": categories,
            "avg_usage": total_usage / total if total > 0 else 0
        }

