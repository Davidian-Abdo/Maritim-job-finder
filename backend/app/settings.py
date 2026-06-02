from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    API_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JOB_FETCH_INTERVAL: int = 3600  # seconds (not used if scheduler removed)
    REMOTIVE_API_URL: str = "https://remotive.com/api/remote-jobs"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]  # for dev
   
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@maritimjobs.duckdns.org"

    # Supabase Storage
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None          # anon or service role key
    SUPABASE_BUCKET_RESUMES: str = "resumes"

    # Available sources (used in profile)
    AVAILABLE_SOURCES: List[str] = [
       "remotive",
       "indeed",
       "linkedin",
       "glassdoor",
       "google_jobs",
       "marineinsight",
       "gcaptain"
    ]
     # Proxy configuration for LinkedIn and other sites
    PROXY_LIST: Optional[List[str]] = None  # e.g. ["http://user:pass@proxy:port", ...]

    # JobSpy configuration
    JOBSPY_RESULTS_WANTED: int = 50          # number of jobs to fetch per source
    JOBSPY_HOURS_OLD: int = 168  
    class Config:
        env_file = ".env"

settings = Settings()