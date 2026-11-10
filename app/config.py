import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

class Settings:
    # Project Info
    APP_NAME: str = "AI-Powered Business Assistant"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = BASE_DIR

    # Gemini AI
    GEMINI_AI_API_KEY: str = os.getenv("GEMINI_AI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

    # REST API for Existing Application (Passenger Service)
    PASSENGER_API_BASE_URL: str = os.getenv("PASSENGER_API_BASE_URL", "https://staging.limoground.com/api/v1/passenger").rstrip("/")
    DEFAULT_USER_EMAIL: str = os.getenv("DEFAULT_USER_EMAIL", "zentixsoftsamsu@gmail.com")
    DEFAULT_USER_PASSWORD: str = os.getenv("DEFAULT_USER_PASSWORD", "Test?123")
    DEFAULT_COMPANY_ID: str = os.getenv("DEFAULT_COMPANY_ID", "limoground2")

    # Policy Document Path
    POLICY_PDF_PATH: Path = BASE_DIR / "service_policy.pdf"

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

settings = Settings()
