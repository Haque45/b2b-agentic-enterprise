"""
Global Configuration & Environment Settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if present
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv()
load_dotenv(dotenv_path=env_path, override=True)

# API Keys & Paths
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Riyan <eng@muhammadriyan.tech>").strip()
DB_PATH = os.getenv("DB_PATH", "pipeline.db")

# IMAP Settings
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "").strip()
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "").strip()

# User Grounding Context (Mechatronics Engineering Background)
FOUNDER_PROFILE = {
    "education": "Final Year Mechatronics Engineering Student at UET Faisalabad",
    "core_skills": [
        "SolidWorks DFM (Design for Manufacturability - CNC machining, injection molding, sheet metal)",
        "ROS 2 & Gazebo Simulation (URDF/Xacro modeling, Nav2 autonomous navigation)",
        "TinyML & INT8 Quantization (TFLite for Microcontrollers, ESP32, STM32)",
        "Cascade Pneumatics (Multi-cylinder electropneumatic sequence control, valve manifolds)"
    ]
}
