#!/usr/bin/env python
import sys
import warnings
import subprocess
import os
import time

from datetime import datetime

from main.crew import Main

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def start_mlflow_server():
    """Start the MLflow tracking server with PostgreSQL backend"""
    # Get PostgreSQL URI from environment variables - no hardcoding
    postgres_uri = os.environ.get('MLFLOW_POSTGRES_URI')

    if postgres_uri is None:
        raise ValueError("MLFLOW_POSTGRES_URI environment variable must be set")

    mlflow_process = subprocess.Popen(
        ["mlflow", "server",
         "--host", "127.0.0.1",
         "--port", "5000",
         "--backend-store-uri", postgres_uri,
         "--default-artifact-root", "./mlflow-artifacts"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Wait for server to start
    time.sleep(2)
    return mlflow_process

def run():
    """
    Run the crew.
    """
    mlflow_process = start_mlflow_server()
    inputs = {
        'topic': 'AI LLMs',
        'current_year': str(datetime.now().year)
    }

    try:
        Main().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
    finally:
        # Ensure MLflow server is terminated
        mlflow_process.terminate()


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs"
    }
    try:
        Main().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        Main().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    try:
        Main().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
