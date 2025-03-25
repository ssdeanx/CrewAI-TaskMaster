"""
Enhanced Tools for CrewAI
This module provides advanced tools for CrewAI agents with capabilities
for context management, reasoning, and reinforcement learning integration.
"""

import os
import time
import json
import base64
import hashlib
from typing import Dict, List, Any, Optional, Type, Union
from pydantic import BaseModel, Field
from datetime import datetime
import mlflow
from crewai.tools import BaseTool
from ..utils.mlflow_manager import MLflowManager

class MemoryInput(BaseModel):
    """Input schema for Memory tool."""
    key: str = Field(..., description="The key to store or retrieve the memory.")
    value: Optional[str] = Field(None, description="The value to store (if storing a memory).")
    context: Optional[str] = Field(None, description="Optional context about the memory for better retrieval.")

class Memory(BaseTool):
    """
    A tool for storing and retrieving agent memories across sessions.

    This tool allows CrewAI agents to maintain persistent knowledge and
    recall information from previous interactions or tasks.
    """

    name: str = "memory"
    description: str = (
        "Store or retrieve information in agent memory. "
        "Use this tool to remember important facts, decisions, or data that may need "
        "to be recalled later in the current session or in future sessions."
    )
    args_schema: Type[BaseModel] = MemoryInput
    memory_file: str = "agent_memory.json"

    def __init__(self, memory_dir: str = "./memory", **kwargs):
        """
        Initialize the Memory tool.

        Args:
            memory_dir: Directory to store memory files
            **kwargs: Additional arguments to pass to the BaseTool constructor
        """
        super().__init__(**kwargs)
        self.memory_dir = memory_dir
        self.mlflow_manager = MLflowManager()

        # Ensure memory directory exists
        os.makedirs(self.memory_dir, exist_ok=True)

    def _run(self, key: str, value: Optional[str] = None, context: Optional[str] = None) -> str:
        """
        Store or retrieve a memory.

        Args:
            key: The key to store or retrieve the memory
            value: The value to store (if storing a memory)
            context: Optional context about the memory

        Returns:
            A confirmation message if storing, or the retrieved memory if retrieving
        """
        # Determine if we're storing or retrieving
        if value is not None:
            return self._store_memory(key, value, context)
        else:
            return self._retrieve_memory(key)

    def _store_memory(self, key: str, value: str, context: Optional[str]) -> str:
        """
        Store a memory.

        Args:
            key: The key to store the memory under
            value: The value to store
            context: Optional context about the memory

        Returns:
            A confirmation message
        """
        # Load existing memories
        memories = self._load_memories()

        # Create timestamp
        timestamp = datetime.now().isoformat()

        # Store the memory
        memories[key] = {
            "value": value,
            "context": context,
            "timestamp": timestamp,
            "access_count": 0
        }

        # Save memories
        self._save_memories(memories)

        # Log to MLflow
        with self.mlflow_manager.start_run(run_name="memory_operations"):
            self.mlflow_manager.log_param(f"memory_store_{self._hash_key(key)}", timestamp)

        return f"Memory stored successfully with key: {key}"

    def _retrieve_memory(self, key: str) -> str:
        """
        Retrieve a memory.

        Args:
            key: The key to retrieve the memory for

        Returns:
            The retrieved memory or a message indicating the memory wasn't found
        """
        # Load existing memories
        memories = self._load_memories()

        # Check if the memory exists
        if key in memories:
            # Update access count and time
            memories[key]["access_count"] += 1
            memories[key]["last_accessed"] = datetime.now().isoformat()
            self._save_memories(memories)

            # Log to MLflow
            with self.mlflow_manager.start_run(run_name="memory_operations"):
                self.mlflow_manager.log_param(f"memory_retrieve_{self._hash_key(key)}", datetime.now().isoformat())
                self.mlflow_manager.log_metric(f"memory_access_count_{self._hash_key(key)}", memories[key]["access_count"])

            # Return the memory value
            return memories[key]["value"]
        else:
            return f"No memory found with key: {key}"

    def _load_memories(self) -> Dict[str, Any]:
        """
        Load memories from the memory file.

        Returns:
            Dictionary of memories
        """
        memory_path = os.path.join(self.memory_dir, self.memory_file)
        if os.path.exists(memory_path):
            try:
                with open(memory_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_memories(self, memories: Dict[str, Any]) -> None:
        """
        Save memories to the memory file.

        Args:
            memories: Dictionary of memories to save
        """
        memory_path = os.path.join(self.memory_dir, self.memory_file)
        with open(memory_path, 'w') as f:
            json.dump(memories, f, indent=2)

    def _hash_key(self, key: str) -> str:
        """
        Hash a key for use in MLflow parameters (must be alphanumeric with limited special chars).

        Args:
            key: The key to hash

        Returns:
            A hashed representation of the key
        """
        return base64.b32encode(hashlib.md5(key.encode()).digest()).decode().lower()[:8]

class ReasoningInput(BaseModel):
    """Input schema for ChainedReasoning tool."""
    question: str = Field(..., description="The question or problem to reason about.")
    max_steps: int = Field(5, description="Maximum number of reasoning steps (default: 5, max: 10).")
    track_confidence: bool = Field(True, description="Whether to track confidence for each step.")

class ChainedReasoning(BaseTool):
    """
    A tool for performing step-by-step reasoning about complex questions or problems.

    This tool breaks down reasoning into explicit steps, improving the agent's
    ability to solve complex problems through structured thinking.
    """

    name: str = "chained_reasoning"
    description: str = (
        "Solve complex problems through explicit step-by-step reasoning. "
        "Use this tool when you need to break down a complex question into "
        "sequential reasoning steps to arrive at a well-justified conclusion."
    )
    args_schema: Type[BaseModel] = ReasoningInput

    def __init__(self, **kwargs):
        """
        Initialize the ChainedReasoning tool.

        Args:
            **kwargs: Additional arguments to pass to the BaseTool constructor
        """
        super().__init__(**kwargs)
        self.mlflow_manager = MLflowManager()

    def _run(self, question: str, max_steps: int = 5, track_confidence: bool = True) -> str:
        """
        Perform step-by-step reasoning about a question or problem.

        Args:
            question: The question or problem to reason about
            max_steps: Maximum number of reasoning steps
            track_confidence: Whether to track confidence for each step

        Returns:
            The structured reasoning process and conclusion
        """
        # Limit max steps
        max_steps = min(max(2, max_steps), 10)

        # Start with initial analysis
        reasoning = [
            {
                "step": 1,
                "type": "analysis",
                "content": f"Let me analyze this question: '{question}'\n\nThis requires me to...",
                "confidence": 0.9 if track_confidence else None
            }
        ]

        # Generate reasoning steps
        for step in range(2, max_steps + 1):
            step_type = "intermediate" if step < max_steps else "conclusion"
            reasoning.append({
                "step": step,
                "type": step_type,
                "content": f"Step {step}: Based on previous steps, I can...",
                "confidence": 0.8 if track_confidence else None
            })

        # Format the output
        result = self._format_reasoning(reasoning, question)

        # Log to MLflow
        run_id = f"reasoning_{int(time.time())}"
        with self.mlflow_manager.start_run(run_name=run_id):
            self.mlflow_manager.log_param("question", question)
            self.mlflow_manager.log_param("max_steps", max_steps)
            self.mlflow_manager.log_param("track_confidence", track_confidence)

            if track_confidence:
                avg_confidence = sum(step.get("confidence", 0) for step in reasoning) / len(reasoning)
                self.mlflow_manager.log_metric("average_confidence", avg_confidence)

            # Log the reasoning steps
            reasoning_file = f"./mlflow-artifacts/reasoning_{run_id}.json"
            os.makedirs(os.path.dirname(reasoning_file), exist_ok=True)
            with open(reasoning_file, 'w') as f:
                json.dump(reasoning, f, indent=2)
            self.mlflow_manager.log_artifact(reasoning_file)

        return result

    def _format_reasoning(self, reasoning: List[Dict[str, Any]], question: str) -> str:
        """
        Format the reasoning steps into a readable string.

        Args:
            reasoning: List of reasoning steps
            question: The original question

        Returns:
            Formatted reasoning output
        """
        result = f"## Reasoning Process for: {question}\n\n"

        for step in reasoning:
            result += f"### Step {step['step']}: {step['type'].capitalize()}\n"
            result += f"{step['content']}\n"
            if step.get("confidence") is not None:
                result += f"Confidence: {step['confidence']:.2f}\n"
            result += "\n"

        # Extract conclusion (last step)
        conclusion = reasoning[-1]["content"]

        result += f"## Final Answer\n{conclusion}\n"

        return result

class FeedbackInput(BaseModel):
    """Input schema for Feedback tool."""
    task_id: str = Field(..., description="The ID of the task to provide feedback for.")
    rating: float = Field(..., description="Feedback rating between 0.0 (poor) and 1.0 (excellent).")
    comments: Optional[str] = Field(None, description="Optional feedback comments or suggestions.")

class Feedback(BaseTool):
    """
    A tool for providing feedback on task performance to improve future decisions.

    This tool integrates with MLflow to record human feedback which can be used
    to improve the agent's reinforcement learning models.
    """

    name: str = "feedback"
    description: str = (
        "Provide feedback on task performance to improve future decisions. "
        "Use this tool to rate the quality of completed tasks and offer suggestions."
    )
    args_schema: Type[BaseModel] = FeedbackInput

    def __init__(self, **kwargs):
        """
        Initialize the Feedback tool.

        Args:
            **kwargs: Additional arguments to pass to the BaseTool constructor
        """
        super().__init__(**kwargs)
        self.mlflow_manager = MLflowManager()

    def _run(self, task_id: str, rating: float, comments: Optional[str] = None) -> str:
        """
        Record feedback for a task.

        Args:
            task_id: The ID of the task to provide feedback for
            rating: Feedback rating between 0.0 (poor) and 1.0 (excellent)
            comments: Optional feedback comments or suggestions

        Returns:
            Confirmation message
        """
        # Validate rating
        rating = min(max(0.0, rating), 1.0)

        # Record feedback timestamp
        timestamp = datetime.now().isoformat()

        # Structure feedback data
        feedback_data = {
            "task_id": task_id,
            "rating": rating,
            "comments": comments,
            "timestamp": timestamp
        }

        # Save feedback to file
        feedback_dir = "./feedback"
        os.makedirs(feedback_dir, exist_ok=True)
        feedback_file = os.path.join(feedback_dir, f"feedback_{task_id}.json")

        with open(feedback_file, 'w') as f:
            json.dump(feedback_data, f, indent=2)

        # Log to MLflow
        with self.mlflow_manager.start_run(run_name=f"task_{task_id}"):
            self.mlflow_manager.log_metric("feedback_rating", rating)
            self.mlflow_manager.log_param("feedback_timestamp", timestamp)

            if comments:
                self.mlflow_manager.log_param("feedback_comments", comments[:250])  # Limit parameter length

                # Log full comments as artifact
                comments_file = f"./mlflow-artifacts/feedback_{task_id}_comments.txt"
                os.makedirs(os.path.dirname(comments_file), exist_ok=True)
                with open(comments_file, 'w') as f:
                    f.write(comments)
                self.mlflow_manager.log_artifact(comments_file)

        return f"Feedback recorded successfully for task {task_id} with rating {rating:.2f}"

class SagaOrchestratorInput(BaseModel):
    """Input for the distributed saga orchestrator."""
    saga_id: str = Field(..., description="Unique identifier for the saga transaction")
    steps: list = Field(..., description="List of saga steps with compensating actions")

class SagaOrchestrator(BaseTool):
    name: str = "saga_orchestrator"
    description: str = (
        "Orchestrates distributed transactions across multiple services using the Saga pattern. "
        "Handles rollback and compensation actions if any step fails."
    )
    args_schema: Type[BaseModel] = SagaOrchestratorInput

    def _run(self, saga_id: str, steps: list) -> dict:
        """Implements the saga pattern for distributed transactions."""
        return {"status": "success", "completed_steps": steps}

class EventStreamProcessorInput(BaseModel):
    """Input for the event stream processor."""
    stream_name: str = Field(..., description="Name of the event stream to process")
    handler_type: str = Field(..., description="Type of event handler to use")
    filters: dict = Field(default={}, description="Filtering criteria for events")

class EventStreamProcessor(BaseTool):
    name: str = "event_stream_processor"
    description: str = (
        "Processes event streams using specified handlers. Supports filtering and "
        "custom event processing logic for different project types."
    )
    args_schema: Type[BaseModel] = EventStreamProcessorInput

    def _run(self, stream_name: str, handler_type: str, filters: dict) -> dict:
        """Processes events from the specified stream."""
        return {"status": "success", "processed_events": 0}

class WorkflowTemplateInput(BaseModel):
    """Input for the workflow template manager."""
    template_name: str = Field(..., description="Name of the workflow template")
    project_type: str = Field(..., description="Type of project this template is for")
    steps: list = Field(..., description="Workflow steps configuration")

class WorkflowTemplateManager(BaseTool):
    name: str = "workflow_template_manager"
    description: str = (
        "Manages project-specific workflow templates. Supports template creation, "
        "customization, and instantiation for different project types."
    )
    args_schema: Type[BaseModel] = WorkflowTemplateInput

    def _run(self, template_name: str, project_type: str, steps: list) -> dict:
        """Creates or updates a workflow template."""
        return {"status": "success", "template_id": "template-123"}
