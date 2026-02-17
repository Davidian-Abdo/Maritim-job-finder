from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from sqlalchemy import text

from app.db import engine
from app.settings import settings
from app.routes import auth, jobs
from app.middleware import add_exception_handlers

# Configure logging
logging.basicConfig(  
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    yield
    # Shutdown: close DB engine
    await engine.dispose()

app = FastAPI(
    title="Maritime Jobs Aggregator",
    version="1.0.0",
    lifespan=lifespan,
   #  root_path="/api/v1"
)


# CORS (Production Ready)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://maritimjobs.duckdns.org",
        "https://www.maritimjobs.duckdns.org",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Global exception handlers
add_exception_handlers(app)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Maritime Jobs API is running"}
