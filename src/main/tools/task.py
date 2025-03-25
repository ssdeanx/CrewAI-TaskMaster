# File: src/main/tools/task.py
import time
import uuid
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import json
import mlflow
from ..utils.mlflow_manager import MLflowManager

# Enums
class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Status(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Event(Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ApprovalRole(Enum):
    AUTO = "AUTO"
    AGENT = "AGENT"
    MANAGER = "MANAGER"

class TaskMasterTools:
    """Implementation of the TaskMaster tools with MLflow integration."""

    def __init__(self):
        self.mlflow_manager = MLflowManager()
        self.requests = {}
        self.tasks = {}
        self.subtasks = {}
        # Configuration for auto-approval
        self.auto_decision_threshold = 0.75
        # Error handling settings
        self.max_retries = 3
        self.backoff_factor = 2
        self.jitter = 0.1

    def request_planning(self, original_request: str, tasks: List[Dict],
                         split_details: str = None,
                         priority: str = "MEDIUM",
                         due_date: str = None) -> Dict:
        """Register a new user request and plan its associated tasks."""
        request_id = f"req-{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now().isoformat()

        # Create request object
        request = {
            "id": request_id,
            "original_request": original_request,
            "split_details": split_details,
            "priority": priority,
            "due_date": due_date,
            "created_at": timestamp,
            "status": Status.PENDING.value,
            "tasks": []
        }

        # Create tasks
        for task_data in tasks:
            task_id = f"task-{str(uuid.uuid4())[:8]}"
            task = {
                "id": task_id,
                "request_id": request_id,
                "title": task_data["title"],
                "description": task_data["description"],
                "priority": priority,
                "due_date": due_date,
                "created_at": timestamp,
                "status": Status.PENDING.value,
                "subtasks": []
            }
            self.tasks[task_id] = task
            request["tasks"].append(task_id)

        self.requests[request_id] = request

        # Log to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_param("request_id", request_id)
            self.mlflow_manager.log_param("original_request", original_request)
            self.mlflow_manager.log_param("num_tasks", len(tasks))
            self.mlflow_manager.log_param("priority", priority)
            if due_date:
                self.mlflow_manager.log_param("due_date", due_date)

            # Save request to file for tracking
            request_file = f"./mlflow-artifacts/request_{request_id}.json"
            os.makedirs(os.path.dirname(request_file), exist_ok=True)
            with open(request_file, 'w') as f:
                json.dump(request, f, indent=2)
            self.mlflow_manager.log_artifact(request_file)

        return {
            "status": "planned",
            "requestId": request_id,
            "totalTasks": len(tasks),
            "tasks": [self._get_task_summary(task_id) for task_id in request["tasks"]],
            "message": f"Tasks have been successfully added. Please use 'get_next_task' to retrieve the first task.\n\n{self._generate_progress_table(request_id)}"
        }

    def get_next_task(self, request_id: str) -> Dict:
        """Get the next pending task for a request."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        request = self.requests[request_id]

        # Check if all tasks are completed
        all_completed = True
        for task_id in request["tasks"]:
            task = self.tasks[task_id]
            if task["status"] != Status.COMPLETED.value:
                all_completed = False
                break

        if all_completed:
            return {
                "status": "all_tasks_done",
                "message": f"All tasks for request {request_id} have been completed. Please use 'approve_request_completion' to finalize.\n\n{self._generate_progress_table(request_id)}"
            }

        # Find pending tasks
        pending_tasks = []
        for task_id in request["tasks"]:
            task = self.tasks[task_id]
            if task["status"] == Status.PENDING.value:
                pending_tasks.append(task)

        # Sort tasks by priority
        priority_values = {
            Priority.HIGH.value: 3,
            Priority.MEDIUM.value: 2,
            Priority.LOW.value: 1
        }

        if pending_tasks:
            # Sort by priority and due date
            pending_tasks.sort(
                key=lambda t: (
                    -priority_values.get(t["priority"], 0),
                    t["due_date"] or "9999-12-31"
                )
            )

            next_task = pending_tasks[0]
            next_task["status"] = Status.IN_PROGRESS.value
            self.tasks[next_task["id"]] = next_task

            # Log to MLflow
            with self.mlflow_manager.start_run(run_name=request_id):
                self.mlflow_manager.log_param(f"task_{next_task['id']}_started_at", datetime.now().isoformat())

                # Track context metrics for RL model
                context_metrics = self._get_context_metrics()
                for metric_name, value in context_metrics.items():
                    self.mlflow_manager.log_metric(f"context.{metric_name}", value)

            return {
                "status": "next_task",
                "task": self._get_task_summary(next_task["id"]),
                "message": f"Next task is ready. Task approval will be required after completion.\n\n{self._generate_progress_table(request_id)}"
            }

        # If there are no pending tasks but some are in progress
        in_progress_tasks = []
        for task_id in request["tasks"]:
            task = self.tasks[task_id]
            if task["status"] == Status.IN_PROGRESS.value:
                in_progress_tasks.append(task)

        if in_progress_tasks:
            return {
                "status": "tasks_in_progress",
                "message": f"There are {len(in_progress_tasks)} tasks in progress. Please await their completion or use 'mark_task_done'.\n\n{self._generate_progress_table(request_id)}"
            }

        # Fallback - should not reach here
        return {
            "status": "no_pending_tasks",
            "message": f"No pending tasks found for request {request_id}.\n\n{self._generate_progress_table(request_id)}"
        }

    def mark_task_done(self, request_id: str, task_id: str,
                       subtask_id: str = None,
                       status: str = Status.COMPLETED.value,
                       completed_details: str = None) -> Dict:
        """Mark a task or subtask as completed."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]

        # Handle subtask case
        if subtask_id:
            if subtask_id not in self.subtasks:
                raise ValueError(f"Subtask ID {subtask_id} not found")

            subtask = self.subtasks[subtask_id]
            subtask["status"] = status
            subtask["completed_at"] = datetime.now().isoformat()
            subtask["completed_details"] = completed_details

            # Log subtask completion metrics
            with self.mlflow_manager.start_run(run_name=request_id):
                execution_time = self._calculate_execution_time(subtask)

                self.mlflow_manager.log_task_metrics(f"{task_id}.{subtask_id}", {
                    "execution_time": execution_time,
                    "status": 1.0 if status == Status.COMPLETED.value else 0.0
                })

                if completed_details:
                    subtask_file = f"./mlflow-artifacts/subtask_{subtask_id}_details.txt"
                    os.makedirs(os.path.dirname(subtask_file), exist_ok=True)
                    with open(subtask_file, 'w') as f:
                        f.write(completed_details)
                    self.mlflow_manager.log_artifact(subtask_file)

            return {
                "status": "task_done",
                "taskId": task_id,
                "subtaskId": subtask_id,
                "message": f"Subtask marked as {status}. Approval is required.\n\n{self._generate_progress_table(request_id)}"
            }

        # Main task case
        if task["status"] not in [Status.IN_PROGRESS.value, Status.PENDING.value]:
            return {
                "status": "already_done",
                "message": f"Task is already marked {task['status']}."
            }

        task["status"] = status
        task["completed_at"] = datetime.now().isoformat()
        task["completed_details"] = completed_details

        # Log task completion metrics
        with self.mlflow_manager.start_run(run_name=request_id):
            execution_time = self._calculate_execution_time(task)

            self.mlflow_manager.log_task_metrics(task_id, {
                "execution_time": execution_time,
                "status": 1.0 if status == Status.COMPLETED.value else 0.0
            })

            if completed_details:
                task_file = f"./mlflow-artifacts/task_{task_id}_details.txt"
                os.makedirs(os.path.dirname(task_file), exist_ok=True)
                with open(task_file, 'w') as f:
                    f.write(completed_details)
                self.mlflow_manager.log_artifact(task_file)

        return {
            "status": "task_done",
            "taskId": task_id,
            "message": f"Task marked as {status}. Approval is required.\n\n{self._generate_progress_table(request_id)}"
        }

    def approve_task_completion(self, request_id: str, task_id: str, subtask_id: str = None) -> Dict:
        """Approve the completion of a task or subtask."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]

        # Handle subtask approval
        if subtask_id:
            if subtask_id not in self.subtasks:
                raise ValueError(f"Subtask ID {subtask_id} not found")

            subtask = self.subtasks[subtask_id]

            if subtask["status"] != Status.COMPLETED.value:
                return {
                    "status": "not_completed",
                    "message": f"Subtask {subtask_id} is not marked as completed. Current status: {subtask['status']}"
                }

            # Calculate confidence score for potential auto-approval
            confidence_score = self._calculate_approval_confidence(subtask)

            # Determine approval role
            approval_role = ApprovalRole.AUTO.value if confidence_score >= self.auto_decision_threshold else ApprovalRole.AGENT.value

            # Record approval
            subtask["approved"] = True
            subtask["approved_at"] = datetime.now().isoformat()
            subtask["approval_role"] = approval_role
            subtask["confidence_score"] = confidence_score

            # Log approval to MLflow
            with self.mlflow_manager.start_run(run_name=request_id):
                self.mlflow_manager.log_task_metrics(f"{task_id}.{subtask_id}", {
                    "approval_time": time.time(),
                    "confidence_score": confidence_score,
                    "auto_approved": 1.0 if approval_role == ApprovalRole.AUTO.value else 0.0
                })

            # Check if all subtasks are approved for this task
            all_subtasks_approved = True
            for stid in task["subtasks"]:
                st = self.subtasks[stid]
                if not st.get("approved", False):
                    all_subtasks_approved = False
                    break

            if all_subtasks_approved and task["subtasks"]:
                task["status"] = Status.COMPLETED.value
                task["completed_at"] = datetime.now().isoformat()

            return {
                "status": "approved",
                "taskId": task_id,
                "subtaskId": subtask_id,
                "message": f"Subtask approval completed with role {approval_role}.\n\n{self._generate_progress_table(request_id)}"
            }

        # Main task approval
        if task["status"] != Status.COMPLETED.value:
            return {
                "status": "not_completed",
                "message": f"Task {task_id} is not marked as completed. Current status: {task['status']}"
            }

        # Calculate confidence score for potential auto-approval
        confidence_score = self._calculate_approval_confidence(task)

        # Determine approval role
        approval_role = ApprovalRole.AUTO.value if confidence_score >= self.auto_decision_threshold else ApprovalRole.AGENT.value

        # Record approval
        task["approved"] = True
        task["approved_at"] = datetime.now().isoformat()
        task["approval_role"] = approval_role
        task["confidence_score"] = confidence_score

        # Log approval to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_task_metrics(task_id, {
                "approval_time": time.time(),
                "confidence_score": confidence_score,
                "auto_approved": 1.0 if approval_role == ApprovalRole.AUTO.value else 0.0
            })

        return {
            "status": "approved",
            "taskId": task_id,
            "message": f"Task approval completed with role {approval_role}.\n\n{self._generate_progress_table(request_id)}"
        }

    def approve_request_completion(self, request_id: str) -> Dict:
        """Approve the completion of an entire request."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        request = self.requests[request_id]

        # Check if all tasks are completed and approved
        all_completed_and_approved = True
        for task_id in request["tasks"]:
            task = self.tasks[task_id]
            if task["status"] != Status.COMPLETED.value or not task.get("approved", False):
                all_completed_and_approved = False
                break

        if not all_completed_and_approved:
            return {
                "status": "incomplete",
                "message": f"Not all tasks are completed and approved for request {request_id}.\n\n{self._generate_progress_table(request_id)}"
            }

        # Mark request as completed
        request["status"] = Status.COMPLETED.value
        request["completed_at"] = datetime.now().isoformat()

        # Calculate overall workflow performance metrics
        workflow_metrics = self._calculate_workflow_metrics(request)

        # Log workflow completion to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            for metric_name, value in workflow_metrics.items():
                self.mlflow_manager.log_workflow_metrics({metric_name: value})

            # Finalize the MLflow run
            self.mlflow_manager.log_param("request_status", Status.COMPLETED.value)
            self.mlflow_manager.log_param("completed_at", request["completed_at"])

            # Save final request state
            request_file = f"./mlflow-artifacts/request_{request_id}_final.json"
            os.makedirs(os.path.dirname(request_file), exist_ok=True)
            with open(request_file, 'w') as f:
                json.dump(request, f, indent=2)
            self.mlflow_manager.log_artifact(request_file)

        return {
            "status": "completed",
            "requestId": request_id,
            "message": f"Request {request_id} has been successfully completed and approved.\n\n{self._generate_progress_table(request_id)}"
        }

    def open_task_details(self, task_id: str) -> Dict:
        """Get details of a specific task."""
        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]

        # Include subtasks if any
        subtasks_details = []
        for subtask_id in task.get("subtasks", []):
            if subtask_id in self.subtasks:
                subtasks_details.append(self.subtasks[subtask_id])

        # Create comprehensive task details
        task_details = dict(task)
        if subtasks_details:
            task_details["subtasks_data"] = subtasks_details

        return task_details

    def list_requests(self) -> Dict:
        """List all requests with their status and task summaries."""
        requests_summary = []

        for request_id, request in self.requests.items():
            # Count tasks by status
            task_counts = {
                Status.PENDING.value: 0,
                Status.IN_PROGRESS.value: 0,
                Status.COMPLETED.value: 0,
                Status.FAILED.value: 0
            }

            for task_id in request["tasks"]:
                if task_id in self.tasks:
                    task_status = self.tasks[task_id]["status"]
                    task_counts[task_status] = task_counts.get(task_status, 0) + 1

            # Create request summary
            summary = {
                "id": request_id,
                "status": request["status"],
                "created_at": request["created_at"],
                "completed_at": request.get("completed_at"),
                "priority": request["priority"],
                "due_date": request["due_date"],
                "task_summary": task_counts,
                "total_tasks": len(request["tasks"])
            }

            requests_summary.append(summary)

        # Sort by created_at descending (newest first)
        requests_summary.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "requests": requests_summary,
            "total_requests": len(requests_summary)
        }

    def add_tasks_to_request(self, request_id: str, tasks: List[Dict],
                            priority: str = None, due_date: str = None) -> Dict:
        """Add new tasks to an existing request."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        request = self.requests[request_id]

        # Use request's priority/due_date if not specified
        if priority is None:
            priority = request["priority"]

        if due_date is None:
            due_date = request["due_date"]

        timestamp = datetime.now().isoformat()

        # Create new tasks
        new_task_ids = []
        for task_data in tasks:
            task_id = f"task-{str(uuid.uuid4())[:8]}"
            task = {
                "id": task_id,
                "request_id": request_id,
                "title": task_data["title"],
                "description": task_data["description"],
                "priority": priority,
                "due_date": due_date,
                "created_at": timestamp,
                "status": Status.PENDING.value,
                "subtasks": []
            }
            self.tasks[task_id] = task
            request["tasks"].append(task_id)
            new_task_ids.append(task_id)

        # Log to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_param("tasks_added_at", timestamp)
            self.mlflow_manager.log_param("tasks_added_count", len(tasks))

        return {
            "status": "tasks_added",
            "requestId": request_id,
            "addedTasks": len(new_task_ids),
            "totalTasks": len(request["tasks"]),
            "tasks": [self._get_task_summary(task_id) for task_id in new_task_ids],
            "message": f"Added {len(new_task_ids)} new tasks to request {request_id}.\n\n{self._generate_progress_table(request_id)}"
        }

    def update_task(self, request_id: str, task_id: str,
                   subtask_id: str = None, title: str = None,
                   description: str = None, priority: str = None,
                   due_date: str = None) -> Dict:
        """Update an existing task or subtask."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]

        # Handle subtask update
        if subtask_id:
            if subtask_id not in self.subtasks:
                raise ValueError(f"Subtask ID {subtask_id} not found")

            subtask = self.subtasks[subtask_id]

            # Only allow updates of non-completed subtasks
            if subtask["status"] in [Status.COMPLETED.value, Status.FAILED.value]:
                return {
                    "status": "cannot_update",
                    "message": f"Cannot update completed or failed subtask {subtask_id}."
                }

            # Update fields if provided
            if title:
                subtask["title"] = title
            if description:
                subtask["description"] = description
            if priority:
                subtask["priority"] = priority
            if due_date:
                subtask["due_date"] = due_date

            # Log update to MLflow
            with self.mlflow_manager.start_run(run_name=request_id):
                self.mlflow_manager.log_param(f"subtask_{subtask_id}_updated_at", datetime.now().isoformat())

            return {
                "status": "updated",
                "taskId": task_id,
                "subtaskId": subtask_id,
                "message": f"Subtask {subtask_id} updated successfully.\n\n{self._generate_progress_table(request_id)}"
            }

        # Main task update
        # Only allow updates of non-completed tasks
        if task["status"] in [Status.COMPLETED.value, Status.FAILED.value]:
            return {
                "status": "cannot_update",
                "message": f"Cannot update completed or failed task {task_id}."
            }

        # Update fields if provided
        if title:
            task["title"] = title
        if description:
            task["description"] = description
        if priority:
            task["priority"] = priority
        if due_date:
            task["due_date"] = due_date

        # Log update to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_param(f"task_{task_id}_updated_at", datetime.now().isoformat())

        return {
            "status": "updated",
            "taskId": task_id,
            "message": f"Task {task_id} updated successfully.\n\n{self._generate_progress_table(request_id)}"
        }

    def delete_task(self, request_id: str, task_id: str, subtask_id: str = None) -> Dict:
        """Delete an uncompleted task or subtask."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]
        request = self.requests[request_id]

        # Handle subtask deletion
        if subtask_id:
            if subtask_id not in self.subtasks:
                raise ValueError(f"Subtask ID {subtask_id} not found")

            subtask = self.subtasks[subtask_id]

            # Only allow deletion of non-completed subtasks
            if subtask["status"] in [Status.COMPLETED.value, Status.FAILED.value]:
                return {
                    "status": "cannot_delete",
                    "message": f"Cannot delete completed or failed subtask {subtask_id}."
                }

            # Remove subtask
            task["subtasks"].remove(subtask_id)
            del self.subtasks[subtask_id]

            # Log deletion to MLflow
            with self.mlflow_manager.start_run(run_name=request_id):
                self.mlflow_manager.log_param(f"subtask_{subtask_id}_deleted_at", datetime.now().isoformat())

            return {
                "status": "deleted",
                "taskId": task_id,
                "subtaskId": subtask_id,
                "message": f"Subtask {subtask_id} deleted successfully.\n\n{self._generate_progress_table(request_id)}"
            }

        # Main task deletion
        # Only allow deletion of non-completed tasks
        if task["status"] in [Status.COMPLETED.value, Status.FAILED.value]:
            return {
                "status": "cannot_delete",
                "message": f"Cannot delete completed or failed task {task_id}."
            }

        # Remove task
        request["tasks"].remove(task_id)
        del self.tasks[task_id]

        # Remove associated subtasks
        for subtask_id in task.get("subtasks", []):
            if subtask_id in self.subtasks:
                del self.subtasks[subtask_id]

        # Log deletion to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_param(f"task_{task_id}_deleted_at", datetime.now().isoformat())

        return {
            "status": "deleted",
            "taskId": task_id,
            "message": f"Task {task_id} and its subtasks deleted successfully.\n\n{self._generate_progress_table(request_id)}"
        }

    def create_subtasks(self, request_id: str, task_id: str,
                       subtasks: List[Dict], priority: str = None,
                       due_date: str = None) -> Dict:
        """Create subtasks for a task."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        task = self.tasks[task_id]

        # Use task's priority/due_date if not specified
        if priority is None:
            priority = task["priority"]

        if due_date is None:
            due_date = task["due_date"]

        timestamp = datetime.now().isoformat()

        # Create subtasks
        new_subtask_ids = []
        for subtask_data in subtasks:
            subtask_id = f"subtask-{str(uuid.uuid4())[:8]}"
            subtask = {
                "id": subtask_id,
                "task_id": task_id,
                "request_id": request_id,
                "title": subtask_data["title"],
                "description": subtask_data["description"],
                "priority": priority,
                "due_date": due_date,
                "created_at": timestamp,
                "status": Status.PENDING.value
            }
            self.subtasks[subtask_id] = subtask
            task["subtasks"].append(subtask_id)
            new_subtask_ids.append(subtask_id)

        # Log to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_param(f"task_{task_id}_subtasks_created_at", timestamp)
            self.mlflow_manager.log_param(f"task_{task_id}_subtasks_count", len(subtasks))

        return {
            "status": "subtasks_created",
            "taskId": task_id,
            "subtasks": [self._get_subtask_summary(subtask_id) for subtask_id in new_subtask_ids],
            "totalSubtasks": len(task["subtasks"]),
            "message": f"Created {len(new_subtask_ids)} subtasks for task {task_id}.\n\n{self._generate_progress_table(request_id)}"
        }

    def notify_task_event(self, request_id: str, task_id: str,
                         event: str, subtask_id: str = None,
                         completed_details: str = None) -> Dict:
        """Notify an external event for an asynchronous task."""
        if request_id not in self.requests:
            raise ValueError(f"Request ID {request_id} not found")

        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found")

        # Validate event
        if event not in [e.value for e in Event]:
            raise ValueError(f"Invalid event: {event}. Must be one of: {[e.value for e in Event]}")

        task = self.tasks[task_id]

        # Handle subtask event
        if subtask_id:
            if subtask_id not in self.subtasks:
                raise ValueError(f"Subtask ID {subtask_id} not found")

            subtask = self.subtasks[subtask_id]

            # Update subtask status based on event
            if event == Event.COMPLETED.value:
                subtask["status"] = Status.COMPLETED.value
                subtask["completed_at"] = datetime.now().isoformat()
                subtask["completed_details"] = completed_details
            elif event == Event.FAILED.value:
                subtask["status"] = Status.FAILED.value
                subtask["failed_at"] = datetime.now().isoformat()
                subtask["failure_details"] = completed_details

            # Log event to MLflow
            with self.mlflow_manager.start_run(run_name=request_id):
                self.mlflow_manager.log_task_metrics(f"{task_id}.{subtask_id}", {
                    "event_time": time.time(),
                    "event_success": 1.0 if event == Event.COMPLETED.value else 0.0
                })

                if completed_details:
                    details_file = f"./mlflow-artifacts/subtask_{subtask_id}_event_details.txt"
                    os.makedirs(os.path.dirname(details_file), exist_ok=True)
                    with open(details_file, 'w') as f:
                        f.write(completed_details)
                    self.mlflow_manager.log_artifact(details_file)

            return {
                "status": "event_processed",
                "taskId": task_id,
                "subtaskId": subtask_id,
                "event": event,
                "message": f"Event {event} processed for subtask {subtask_id}.\n\n{self._generate_progress_table(request_id)}"
            }

        # Main task event
        # Update task status based on event
        if event == Event.COMPLETED.value:
            task["status"] = Status.COMPLETED.value
            task["completed_at"] = datetime.now().isoformat()
            task["completed_details"] = completed_details
        elif event == Event.FAILED.value:
            task["status"] = Status.FAILED.value
            task["failed_at"] = datetime.now().isoformat()
            task["failure_details"] = completed_details

        # Log event to MLflow
        with self.mlflow_manager.start_run(run_name=request_id):
            self.mlflow_manager.log_task_metrics(task_id, {
                "event_time": time.time(),
                "event_success": 1.0 if event == Event.COMPLETED.value else 0.0
            })

            if completed_details:
                details_file = f"./mlflow-artifacts/task_{task_id}_event_details.txt"
                os.makedirs(os.path.dirname(details_file), exist_ok=True)
                with open(details_file, 'w') as f:
                    f.write(completed_details)
                self.mlflow_manager.log_artifact(details_file)

        return {
            "status": "event_processed",
            "taskId": task_id,
            "event": event,
            "message": f"Event {event} processed for task {task_id}.\n\n{self._generate_progress_table(request_id)}"
        }

    # Helper methods
    def _get_task_summary(self, task_id: str) -> Dict:
        """Get a summary of a task for display."""
        task = self.tasks[task_id]
        return {
            "id": task_id,
            "title": task["title"],
            "description": task["description"],
            "status": task["status"],
            "subtasks_count": len(task.get("subtasks", [])),
            "approved": task.get("approved", False)
        }

    def _get_subtask_summary(self, subtask_id: str) -> Dict:
        """Get a summary of a subtask for display."""
        subtask = self.subtasks[subtask_id]
        return {
            "id": subtask_id,
            "title": subtask["title"],
            "description": subtask["description"],
            "status": subtask["status"],
            "approved": subtask.get("approved", False)
        }

    def _calculate_execution_time(self, task_obj: Dict) -> float:
        """Calculate the execution time of a task or subtask."""
        if "completed_at" not in task_obj or "created_at" not in task_obj:
            return 0.0

        try:
            start_time = datetime.fromisoformat(task_obj["created_at"]).timestamp()
            end_time = datetime.fromisoformat(task_obj["completed_at"]).timestamp()
            return end_time - start_time
        except (ValueError, TypeError):
            return 0.0

    def _calculate_approval_confidence(self, task_obj: Dict) -> float:
        """Calculate the confidence score for auto-approval."""
        # Start with a base confidence
        base_confidence = 0.7

        # Adjust based on execution time (faster tasks might be more reliable)
        execution_time = self._calculate_execution_time(task_obj)
        # Normalize execution time: tasks under 30s get a boost, over 5 minutes get a penalty
        if execution_time < 30:
            time_factor = 0.1
        elif execution_time > 300:
            time_factor = -0.1
        else:
            time_factor = 0

        # Adjust based on task complexity (approximated by description length)
        description_len = len(task_obj.get("description", ""))
        # Penalize very short or very long descriptions
        if description_len < 50:
            complexity_factor = -0.05
        elif description_len > 1000:
            complexity_factor = -0.1
        else:
            complexity_factor = 0.05

        # Adjust based on history (placeholder for RL component)
        history_factor = 0
        # In a real implementation, this would use the RL model's prediction

        # Final confidence calculation
        confidence = base_confidence + time_factor + complexity_factor + history_factor
        # Bound between 0 and 1
        return max(0.0, min(1.0, confidence))

    def _calculate_workflow_metrics(self, request: Dict) -> Dict:
        """Calculate overall workflow performance metrics."""
        metrics = {}

        # Calculate total execution time
        if "completed_at" in request and "created_at" in request:
            try:
                start_time = datetime.fromisoformat(request["created_at"]).timestamp()
                end_time = datetime.fromisoformat(request["completed_at"]).timestamp()
                metrics["total_execution_time"] = end_time - start_time
            except (ValueError, TypeError):
                metrics["total_execution_time"] = 0.0

        # Calculate task statistics
        task_count = len(request["tasks"])
        auto_approved_count = 0
        error_count = 0

        task_times = []
        for task_id in request["tasks"]:
            task = self.tasks[task_id]

            # Track auto-approved tasks
            if task.get("approval_role") == ApprovalRole.AUTO.value:
                auto_approved_count += 1

            # Track errors
            if task.get("status") == Status.FAILED.value:
                error_count += 1

            # Track task execution times
            execution_time = self._calculate_execution_time(task)
            if execution_time > 0:
                task_times.append(execution_time)

        # Calculate metrics
        metrics["task_count"] = task_count
        metrics["auto_approval_rate"] = auto_approved_count / task_count if task_count > 0 else 0
        metrics["error_rate"] = error_count / task_count if task_count > 0 else 0
        metrics["avg_task_time"] = sum(task_times) / len(task_times) if task_times else 0
        metrics["success_rate"] = 1.0 - metrics["error_rate"]

        return metrics

    def _get_context_metrics(self) -> Dict:
        """Get real-time context metrics for RL model input."""
        # In a real implementation, these would be actual system metrics
        return {
            "system_load": 0.5,  # Example: CPU load between 0-1
            "memory_usage": 0.3,  # Example: Memory usage between 0-1
            "pending_task_count": sum(1 for t in self.tasks.values() if t["status"] == Status.PENDING.value),
            "in_progress_task_count": sum(1 for t in self.tasks.values() if t["status"] == Status.IN_PROGRESS.value)
        }

    def _generate_progress_table(self, request_id: str) -> str:
        """Generate a markdown progress table for the request."""
        if request_id not in self.requests:
            return "Request not found"

        request = self.requests[request_id]

        # Table header
        table = "Progress Status:\n"
        table += "| Task ID | Title | Description | Status | Approval |\n"
        table += "|----------|----------|------|------|----------|\n"

        # Add rows for each task
        for task_id in request["tasks"]:
            if task_id in self.tasks:
                task = self.tasks[task_id]

                # Status emoji
                status_emoji = {
                    Status.PENDING.value: "⏳ Pending",
                    Status.IN_PROGRESS.value: "🔄 In Progress",
                    Status.COMPLETED.value: "✅ Completed",
                    Status.FAILED.value: "❌ Failed"
                }.get(task["status"], task["status"])

                # Approval status
                approval_status = "✓ Approved" if task.get("approved", False) else "⏳ Pending"

                # Truncate description if too long
                description = task["description"]
                if len(description) > 50:
                    description = description[:50] + "..."

                # Add row
                table += f"| {task_id} | {task['title']} | {description} | {status_emoji} | {approval_status} |\n"

        return table
