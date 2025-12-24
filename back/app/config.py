"""
Application configuration module.
Loads environment variables and provides centralized config access.
"""
import os

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required if env vars are set

# API Keys
LLM_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
EXA_API_KEY = os.getenv("EXA_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Database
DB_PATH = "tmp/agno.db"

# CORS Origins
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "https://127.0.0.1:5173",
]

# Agent settings
AGENT_ID = "crypto-analyst-agent"
AGENT_NAME = "CryptoAnalyst"
