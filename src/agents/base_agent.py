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


class AgentLLMClientWrapper:
    def __init__(self, client: LLMClient, agent_name: str):
        self.client = client
        self.agent_name = agent_name

    def complete(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        instructions_dir = os.path.join(os.path.dirname(__file__), "instructions")
        os.makedirs(instructions_dir, exist_ok=True)
        skills_file = os.path.join(instructions_dir, f"{self.agent_name}_skills.txt")
        
        skills_text = ""
        if os.path.exists(skills_file):
            with open(skills_file, "r", encoding="utf-8") as f:
                skills_text = f.read().strip()
                
        if skills_text:
            injection = f"\n\n--- [USER CUSTOM SKILLS & INSTRUCTIONS] ---\n{skills_text}\n------------------------------------------\n"
            if system_prompt:
                system_prompt += injection
            else:
                system_prompt = injection
                
        return self.client.complete(prompt=prompt, system_prompt=system_prompt, **kwargs)


class BaseAgent(ABC):
    """
    Abstract Base Class for Enterprise Agents.
    Provides database access, LLM client integration, and standardized execution lifecycle.
    """

    def __init__(self, name: str, db_path: str = DEFAULT_DB_PATH):
        self.name = name
        self.db_path = db_path
        self._raw_llm_client = LLMClient()
        self.llm_client = AgentLLMClientWrapper(self._raw_llm_client, self.name)
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
