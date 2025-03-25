from os import startfile
import time
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.main.utils.mlflow_manager import MLflowManager
import os
import yaml

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class Main():
    """Main crew"""

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'],
            verbose=True
        )

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['reporting_analyst'],
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
        )

    @task
    def reporting_task(self) -> Task:
        return Task(
            config=self.tasks_config['reporting_task'],
            output_file='report.md'
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Main crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )

class TaskMasterCrew:
    def __init__(self):
        # Existing initialization code
        self.mlflow_manager = MLflowManager()

    def kickoff(self, inputs):
        with self.mlflow_manager.start_run(inputs.get("request_id")):
            # Execute existing workflow
            result = self._execute_workflow(inputs)

            # Log workflow completion metrics
            self.mlflow_manager.log_workflow_metrics({
                "completion_time": time.time() - startfile,
                "success_rate": 1.0 if result["status"] == "success" else 0.0
            })

        return result

    def execute_task(self, task):
        start_time = time.time()
        try:
            # Execute task
            result = task.execute()

            # Log task performance
            self.mlflow_manager.log_task_metrics(task.id, {
                "execution_time": time.time() - start_time,
                "error_count": 0,
                "successful": 1.0
            })
            return result
        except Exception as e:
            # Log error metrics
            self.mlflow_manager.log_task_metrics(task.id, {
                "execution_time": time.time() - start_time,
                "error_count": 1,
                "successful": 0.0
            })
            raise e

class CrewFactory:
    """Factory for creating CrewAI crews with MLflow integration."""

    def __init__(self):
        self.mlflow_manager = MLflowManager()

    def load_config(self, config_path):
        """Load configuration from YAML file."""
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)

    def create_crew(self, name, agents, tasks):
        """Create a crew with MLflow tracking."""
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=os.environ.get("PROCESS", "sequential")
        )

        # Patch crew's kickoff method to add MLflow tracking
        original_kickoff = crew.kickoff

        def kickoff_with_mlflow(inputs=None):
            start_time = time.time()

            # Start MLflow run
            with self.mlflow_manager.start_run(run_name=name):
                self.mlflow_manager.log_param("crew_name", name)
                self.mlflow_manager.log_param("agents", [agent.name for agent in agents])
                self.mlflow_manager.log_param("tasks", [task.description[:50] for task in tasks])

                try:
                    # Run original kickoff method
                    result = original_kickoff(inputs)

                    # Log workflow completion metrics
                    execution_time = time.time() - start_time
                    self.mlflow_manager.log_workflow_metrics({
                        "execution_time": execution_time,
                        "success": 1.0
                    })

                    return result
                except Exception as e:
                    # Log failure
                    execution_time = time.time() - start_time
                    self.mlflow_manager.log_workflow_metrics({
                        "execution_time": execution_time,
                        "success": 0.0,
                        "error": str(e)
                    })
                    raise e

        crew.kickoff = kickoff_with_mlflow
        return crew
