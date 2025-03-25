"""
Main package initialization.
This module provides the core functionality for the AI agent system.
"""

from .crew import Main, TaskMasterCrew, CrewFactory
from .utils.mlflow_manager import MLflowManager

__version__ = '0.1.0'
__author__ = 'Your Name'

# Export key classes
__all__ = [
    'Main',
    'TaskMasterCrew',
    'CrewFactory',
    'MLflowManager'
]
