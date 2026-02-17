from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JOB_FETCH_INTERVAL: int = 3600  # seconds (not used if scheduler removed)
    REMOTIVE_API_URL: str = "https://remotive.com/api/remote-jobs"
    LOCAL_HTML_PATH: str = "app/data/careers.html"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]  # for dev

    class Config:
        env_file = ".env"

settings = Settings()