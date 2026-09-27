"""
Base Agent Abstract Class inspired by Hermes agent framework.

All 6 enterprise agents inherit from BaseAgent and communicate EXCLUSIVELY
by reading and updating rows in SQLite pipeline.db. No agent sends network emails.
"""

from abc import ABC, abstractmethod
import sqlite3
import os
import logging
from typing import Dict, Any, Optional

from database import get_db_connection, DEFAULT_DB_PATH
from src.llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


class BaseAgent(ABC):
    """
    Abstract Base Class for Enterprise Agents.
    Provides database access, LLM client integration, and standardized execution lifecycle.
    """

    def __init__(self, name: str, db_path: str = DEFAULT_DB_PATH):
        self.name = name
        self.db_path = db_path
        self.llm_client = LLMClient()
        self.logger = logging.getLogger(self.name)

    def get_db(self) -> sqlite3.Connection:
        """Returns a thread-safe connection to pipeline.db."""
        return get_db_connection(self.db_path)

    def log(self, message: str, level: str = "info") -> None:
        """Standardized formatted logging."""
        formatted_msg = f"[{self.name}] {message}"
        if level == "error":
            self.logger.error(formatted_msg)
        elif level == "warning":
            self.logger.warning(formatted_msg)
        else:
            self.logger.info(formatted_msg)

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Executes the agent's core operational task.
        Must return a status dictionary describing actions taken and row mutations.
        """
        pass
