"""
Multi-Agent Coordinator - Manages agent collaboration
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent role definitions"""
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"


class Message:
    """Inter-agent message"""
    def __init__(
        self,
        sender: str,
        receiver: str,
        content: str,
        message_type: str = "text",
        priority: int = 0,
        metadata: Optional[Dict] = None
    ):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.priority = priority
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.id = f"{sender}_{receiver}_{self.timestamp.timestamp()}"


class Agent:
    """Base Agent class"""
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        llm_client,
        tools: Optional[List] = None,
        max_queue_size: int = 100
    ):
        self.agent_id = agent_id
        self.role = role
        self.llm_client = llm_client
        self.tools = tools or []
        self.message_queue = asyncio.Queue(maxsize=max_queue_size)
        self.is_running = False
        self.processed_messages = []
        
    async def start(self):
        """Start agent message processing loop"""
        self.is_running = True
        logger.info(f"Agent {self.agent_id} ({self.role.value}) started")
        
    async def stop(self):
        """Stop agent"""
        self.is_running = False
        logger.info(f"Agent {self.agent_id} stopped")
        
    async def process_message(self, message: Message) -> Optional[Message]:
        """Process received message"""
        try:
            logger.info(f"Agent {self.agent_id} processing message from {message.sender}")
            
            # 1. Understand message
            understanding = await self._understand_message(message)
            
            # 2. Decide action based on role
            if self.role == AgentRole.RESEARCHER:
                response = await self._research(understanding)
            elif self.role == AgentRole.PLANNER:
                response = await self._plan(understanding)
            elif self.role == AgentRole.EXECUTOR:
                response = await self._execute(understanding)
            elif self.role == AgentRole.REVIEWER:
                response = await self._review(understanding)
            else:
                response = await self._coordinate(understanding)
                
            # 3. Create reply message
            reply = Message(
                sender=self.agent_id,
                receiver=message.sender,
                content=response,
                metadata={"in_reply_to": message.id}
            )
            
            self.processed_messages.append(message.id)
            return reply
            
        except Exception as e:
            logger.error(f"Agent {self.agent_id} failed to process message: {e}")
            return Message(
                sender=self.agent_id,
                receiver=message.sender,
                content=f"Error: {str(e)}",
                message_type="error"
            )
        
    async def _understand_message(self, message: Message) -> Dict[str, Any]:
        """Understand message intent and content"""
        prompt = f"""
        Analyze this message and extract key information:
        
        From: {message.sender}
        Content: {message.content}
        Type: {message.message_type}
        
        Return JSON with:
        - intent: what the sender wants
        - key_points: main points
        - requires_action: boolean
        - suggested_action: what action to take
        """
        
        response = await self.llm_client.chat([
            {"role": "system", "content": f"You are a {self.role.value} agent."},
            {"role": "user", "content": prompt}
        ])
        
        import json
        try:
            return json.loads(response.get("content", "{}"))
        except:
            return {"intent": "unknown", "content": message.content}
        
    async def _research(self, understanding: Dict) -> str:
        """Research role: Search and analyze information"""
        query = understanding.get("key_points", [])
        if not query:
            return "No research query provided"
            
        # Search using tools
        results = []
        for tool in self.tools:
            if hasattr(tool, 'search'):
                result = await tool.search(query)
                results.append(result)
                
        # Analyze results
        prompt = f"""
        Research Query: {query}
        
        Search Results:
        {results}
        
        Provide a comprehensive analysis with key findings and sources.
        """
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a research analyst."},
            {"role": "user", "content": prompt}
        ])
        
        return response.get("content", "Research completed")
        
    async def _plan(self, understanding: Dict) -> str:
        """Planner role: Create execution plan"""
        task = understanding.get("content", "")
        
        prompt = f"""
        Task: {task}
        
        Create a detailed execution plan with:
        1. Steps to complete the task
        2. Required resources
        3. Dependencies
        4. Estimated time
        5. Success criteria
        
        Return structured plan.
        """
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a strategic planner."},
            {"role": "user", "content": prompt}
        ])
        
        return response.get("content", "Plan created")
        
    async def _execute(self, understanding: Dict) -> str:
        """Executor role: Execute tasks"""
        action = understanding.get("suggested_action", "")
        
        # Execute using available tools
        result = f"Executed: {action}"
        
        for tool in self.tools:
            if hasattr(tool, 'execute'):
                try:
                    result = await tool.execute(action)
                    break
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    
        return result
        
    async def _review(self, understanding: Dict) -> str:
        """Reviewer role: Review and critique"""
        content = understanding.get("content", "")
        
        prompt = f"""
        Review the following work:
        
        {content}
        
        Provide:
        1. Quality assessment (1-10)
        2. Strengths
        3. Weaknesses
        4. Improvement suggestions
        5. Approval status (approved/needs_revision/rejected)
        """
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a quality reviewer."},
            {"role": "user", "content": prompt}
        ])
        
        return response.get("content", "Review completed")
        
    async def _coordinate(self, understanding: Dict) -> str:
        """Coordinator role: Coordinate agent activities"""
        return "Coordination in progress"


class MultiAgentCoordinator:
    """Multi-Agent Coordinator"""
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.message_bus = asyncio.Queue()
        self.task_results: Dict[str, Any] = {}
        self.is_running = False
        
    def register_agent(self, agent: Agent):
        """Register an agent"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id} ({agent.role.value})")
        
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            
    async def start(self):
        """Start coordinator"""
        self.is_running = True
        # Start all agents
        for agent in self.agents.values():
            await agent.start()
        logger.info("Multi-Agent Coordinator started")
        
    async def stop(self):
        """Stop coordinator"""
        self.is_running = False
        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()
        logger.info("Multi-Agent Coordinator stopped")
        
    async def execute_collaborative_task(
        self,
        task: str,
        agent_ids: List[str],
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Execute a collaborative task across multiple agents"""
        try:
            # Get coordinator agent
            coordinator = self._get_coordinator_agent()
            if not coordinator:
                return {"error": "No coordinator agent available"}
                
            # 1. Decompose task
            subtasks = await self._decompose_task(task, agent_ids, coordinator)
            
            # 2. Assign subtasks to agents
            task_assignments = {}
            for agent_id, subtask in subtasks.items():
                if agent_id in self.agents:
                    message = Message(
                        sender="coordinator",
                        receiver=agent_id,
                        content=subtask,
                        message_type="task"
                    )
                    await self.agents[agent_id].message_queue.put(message)
                    task_assignments[agent_id] = subtask
                    
            # 3. Collect results with timeout
            results = {}
            try:
                async with asyncio.timeout(timeout):
                    for agent_id in task_assignments:
                        response = await self._wait_for_response(agent_id)
                        results[agent_id] = response
            except asyncio.TimeoutError:
                logger.warning(f"Task execution timed out after {timeout}s")
                
            # 4. Merge results
            final_result = await self._merge_results(results, coordinator)
            
            return {
                "task": task,
                "agents_involved": agent_ids,
                "subtask_results": results,
                "final_result": final_result,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Collaborative task failed: {e}")
            return {"error": str(e), "status": "failed"}
            
    async def _decompose_task(
        self,
        task: str,
        agent_ids: List[str],
        coordinator: Agent
    ) -> Dict[str, str]:
        """Decompose task into subtasks"""
        agent_roles = {
            agent_id: self.agents[agent_id].role.value 
            for agent_id in agent_ids 
            if agent_id in self.agents
        }
        
        prompt = f"""
        Task: {task}
        
        Available agents and their roles:
        {agent_roles}
        
        Decompose this task into subtasks for each agent based on their roles.
        Return JSON mapping agent_id to subtask description.
        
        Example:
        {{
            "researcher_1": "Research topic X",
            "planner_1": "Create execution plan",
            "executor_1": "Execute steps A, B, C"
        }}
        """
        
        response = await coordinator.llm_client.chat([
            {"role": "system", "content": "You are a task coordinator."},
            {"role": "user", "content": prompt}
        ])
        
        import json
        try:
            return json.loads(response.get("content", "{}"))
        except:
            # Fallback: assign same task to all agents
            return {agent_id: task for agent_id in agent_ids}
            
    async def _wait_for_response(
        self,
        agent_id: str,
        timeout: int = 60
    ) -> Optional[str]:
        """Wait for agent response"""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
            
        try:
            # Get message from agent's queue
            async with asyncio.timeout(timeout):
                message = await agent.message_queue.get()
                response = await agent.process_message(message)
                return response.content if response else None
        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent_id} response timed out")
            return None
            
    async def _merge_results(
        self,
        results: Dict[str, str],
        coordinator: Agent
    ) -> str:
        """Merge agent results into final answer"""
        prompt = f"""
        Merge these agent results into a comprehensive final answer:
        
        {results}
        
        Provide a coherent synthesis that addresses the original task.
        """
        
        response = await coordinator.llm_client.chat([
            {"role": "system", "content": "You are synthesizing multiple agent outputs."},
            {"role": "user", "content": prompt}
        ])
        
        return response.get("content", "Results merged")
        
    def _get_coordinator_agent(self) -> Optional[Agent]:
        """Get coordinator agent"""
        for agent in self.agents.values():
            if agent.role == AgentRole.COORDINATOR:
                return agent
        return None
        
    async def resolve_conflict(
        self,
        agent1_id: str,
        agent2_id: str,
        conflict: str
    ) -> str:
        """Resolve conflict between agents"""
        coordinator = self._get_coordinator_agent()
        if not coordinator:
            return "No coordinator available to resolve conflict"
            
        prompt = f"""
        Conflict between {agent1_id} and {agent2_id}:
        
        {conflict}
        
        Provide a resolution that:
        1. Is fair to both agents
        2. Maintains task progress
        3. Prevents future conflicts
        """
        
        response = await coordinator.llm_client.chat([
            {"role": "system", "content": "You are mediating a conflict."},
            {"role": "user", "content": prompt}
        ])
        
        return response.get("content", "Conflict resolved")

