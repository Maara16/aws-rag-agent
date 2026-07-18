"""
Configuration management with environment variables.
"""

from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Literal

# Load .env file
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)


class Config:
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    PORT = int(os.getenv("PORT", 8000))

    # LLM Configuration
    LLM_PROVIDER: Literal["ollama", "claude"] = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Embeddings
    EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDINGS_DIM = int(os.getenv("EMBEDDINGS_DIM", 384))

    # Vector Store
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "data/chroma_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "aws_saa_docs")

    # Database
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/app.db")

    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "+1234567890")
    TWILIO_VERIFY_TOKEN = os.getenv("TWILIO_VERIFY_TOKEN", "")

    # Agent Behavior
    RAG_RETRIEVAL_TOP_K = int(os.getenv("RAG_RETRIEVAL_TOP_K", 5))
    RAG_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.3))
    RAG_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 500))

    QUIZ_QUESTIONS_PER_SESSION = int(os.getenv("QUIZ_QUESTIONS_PER_SESSION", 5))
    CHEATSHEET_MAX_LENGTH = int(os.getenv("CHEATSHEET_MAX_LENGTH", 500))

    # Document Processing
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", 100))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls):
        """Validate critical configuration."""
        if cls.LLM_PROVIDER == "ollama":
            print(f"✓ LLM: Ollama ({cls.OLLAMA_MODEL}) at {cls.OLLAMA_API_URL}")
        elif cls.LLM_PROVIDER == "claude":
            if not cls.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not set for Claude provider")
            print(f"✓ LLM: Claude (via Anthropic API)")
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {cls.LLM_PROVIDER}")

        print(f"✓ Embeddings: {cls.EMBEDDINGS_MODEL}")
        print(f"✓ Vector DB: {cls.CHROMA_DB_PATH}")
        print(f"✓ SQLite: {cls.SQLITE_DB_PATH}")

        if cls.TWILIO_ACCOUNT_SID:
            print(f"✓ Twilio: Configured ({cls.TWILIO_ACCOUNT_SID[:10]}...)")
        else:
            print("⚠ Twilio: Not configured (WhatsApp disabled)")


def get_config() -> Config:
    """Get configuration instance."""
    return Config
