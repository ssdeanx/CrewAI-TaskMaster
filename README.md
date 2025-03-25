# CrewAI TaskMaster

A sophisticated multi-agent AI system powered by [crewAI](https://crewai.com), featuring advanced workflow management with the TaskMaster agent and MLflow integration for performance tracking and optimization.

## 🌟 Features

- **TaskMaster Agent** - Advanced autonomous workflow manager with dynamic scheduling and self-optimization capabilities
- **MLflow Integration** - Comprehensive tracking and visualization of agent performance and task metrics
- **Reinforcement Learning** - Continuous improvement of agent decision-making through performance data
- **Secure Configuration** - Environment variable support for sensitive credentials
- **PostgreSQL Backend** - Robust database storage for MLflow tracking server

## 📦 Project Structure

``````mermaid
graph TB
    User((External User))

    subgraph "TaskMaster System"
        subgraph "Core Services"
            CrewAI["CrewAI Service<br>Python CrewAI"]
            MLflow["MLflow Server<br>MLflow"]
            TaskMaster["TaskMaster Crew<br>Python"]

            subgraph "Agent Components"
                TaskMasterAgent["Task Master Agent<br>LLM Agent"]
                ResearchAgent["Research Agent<br>LLM Agent"]
                WriterAgent["Writer Agent<br>LLM Agent"]
                DocumentorAgent["Documentor Agent<br>LLM Agent"]
                FactCheckerAgent["Fact Checker Agent<br>LLM Agent"]
                SynthesisAgent["Synthesis Agent<br>LLM Agent"]
            end

            subgraph "Task Management"
                TaskRouter["Task Router<br>Python"]
                WorkflowManager["Workflow Manager<br>Python"]
                TaskExecutor["Task Executor<br>Python"]
            end

            subgraph "Monitoring Components"
                MetricsCollector["Metrics Collector<br>MLflow"]
                PerformanceTracker["Performance Tracker<br>MLflow"]
                ExperimentTracker["Experiment Tracker<br>MLflow"]
            end
        end

        subgraph "Data Storage"
            PostgresDB[("MLflow Database<br>PostgreSQL")]
            ArtifactStore["Artifact Storage<br>Local FileSystem"]
            KnowledgeBase["Knowledge Base<br>YAML/JSON"]
        end

        subgraph "Configuration Management"
            AgentConfig["Agent Configuration<br>YAML"]
            TaskConfig["Task Configuration<br>YAML"]
            MLflowConfig["MLflow Configuration<br>YAML"]
        end
    end

    %% Relationships
    User -->|"Submits Request"| TaskMaster

    %% Core Service Relationships
    TaskMaster -->|"Creates"| CrewAI
    TaskMaster -->|"Monitors"| MLflow
    CrewAI -->|"Manages"| TaskMasterAgent

    %% Agent Relationships
    TaskMasterAgent -->|"Delegates to"| ResearchAgent
    TaskMasterAgent -->|"Delegates to"| WriterAgent
    TaskMasterAgent -->|"Delegates to"| DocumentorAgent
    TaskMasterAgent -->|"Delegates to"| FactCheckerAgent
    TaskMasterAgent -->|"Delegates to"| SynthesisAgent

    %% Task Management Relationships
    TaskMaster -->|"Uses"| TaskRouter
    TaskRouter -->|"Coordinates"| WorkflowManager
    WorkflowManager -->|"Executes"| TaskExecutor

    %% Monitoring Relationships
    MLflow -->|"Collects"| MetricsCollector
    MLflow -->|"Tracks"| PerformanceTracker
    MLflow -->|"Manages"| ExperimentTracker

    %% Data Storage Relationships
    MLflow -->|"Stores Data"| PostgresDB
    MLflow -->|"Stores Artifacts"| ArtifactStore
    CrewAI -->|"Reads"| KnowledgeBase

    %% Configuration Relationships
    TaskMaster -->|"Configures"| AgentConfig
    TaskMaster -->|"Configures"| TaskConfig
    MLflow -->|"Configures"| MLflowConfig

    %% Metric Collection
    MetricsCollector -->|"Logs to"| PostgresDB
    PerformanceTracker -->|"Stores in"| PostgresDB
    ExperimentTracker -->|"Records in"| PostgresDB

    %% Knowledge Base Access
    ResearchAgent -->|"Queries"| KnowledgeBase
    WriterAgent -->|"Queries"| KnowledgeBase
    DocumentorAgent -->|"Queries"| KnowledgeBase
    FactCheckerAgent -->|"Queries"| KnowledgeBase
    SynthesisAgent -->|"Queries"| KnowledgeBase
```

## 📋 Requirements

- Python >=3.10 <3.13
- PostgreSQL database
- [UV](https://docs.astral.sh/uv/) for dependency management

## 🚀 Getting Started

### Installation

First, install UV if you haven't already:

```bash
pip install uv
```

Then install the project dependencies:

```bash
crewai install
```

### Configuration

1. **Environment Setup**:
   Copy `.env.example` to `.env` and configure your environment variables:

   ```properties
   MODEL="gemini/gemini-2.0-flash"  # Or your preferred LLM
   GEMINI_API_KEY="your-api-key"    # Your Gemini API key
   MLFLOW_POSTGRES_URI="postgresql://username:password@localhost:5432/mlflow_tracking"
   ```

2. **Agent Configuration**:
   Modify `src/main/config/agents.yaml` to customize your agent properties.

3. **Task Configuration**:
   Update `src/main/config/tasks.yaml` to define your workflow tasks.

## 🔄 Running the Project

Start your CrewAI workflow:

```bash
crewai run
```

For MLflow dashboard access:

```bash
# MLflow server starts automatically with the application
# Access the dashboard at http://127.0.0.1:5000
```

## 📊 TaskMaster Workflow

The TaskMaster agent manages complex workflows through these key steps:

1. **Request Planning** - Decomposes user requests into manageable tasks
2. **Dynamic Scheduling** - Intelligently prioritizes tasks based on context
3. **Performance Tracking** - Logs execution metrics to MLflow for analysis
4. **Task Approval** - Validates task completion with configurable auto-approval thresholds
5. **Continuous Learning** - Refines decision-making through reinforcement learning

## 🔧 Advanced Configuration

### MLflow Settings

Customize MLflow behavior in `src/main/config/mlflow.yaml`:

```yaml
server:
  host: "127.0.0.1"
  port: 5000
  backend_store_uri: "${MLFLOW_POSTGRES_URI}"  # Uses environment variable
  default_artifact_root: "./mlflow-artifacts"
```

### TaskMaster Parameters

Configure TaskMaster behavior in the `rl_module` section:

```yaml
rl_module:
  hyperparameters:
    learning_rate: 0.001
    discount_factor: 0.95
    exploration_rate: 0.1
```

## 📚 Documentation

For more details on:

- [CrewAI Documentation](https://docs.crewai.com)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [TaskMaster Agent](https://github.com/ssdeanx/crewai-taskmaster) - see TaskMaster Agent.md

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [crewAI](https://github.com/joaomdmoura/crewai) for the multi-agent framework
- [MLflow](https://mlflow.org/) for the tracking and experiment management platform
