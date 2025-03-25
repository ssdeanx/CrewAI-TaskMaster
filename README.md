# CrewAI TaskMaster

A sophisticated multi-agent AI system powered by [crewAI](https://crewai.com), featuring advanced workflow management with the TaskMaster agent and MLflow integration for performance tracking and optimization.

## 🌟 Features

- **TaskMaster Agent** - Advanced autonomous workflow manager with dynamic scheduling and self-optimization capabilities
- **MLflow Integration** - Comprehensive tracking and visualization of agent performance and task metrics
- **Reinforcement Learning** - Continuous improvement of agent decision-making through performance data
- **Secure Configuration** - Environment variable support for sensitive credentials
- **PostgreSQL Backend** - Robust database storage for MLflow tracking server

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
