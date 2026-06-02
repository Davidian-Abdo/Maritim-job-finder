# app/routes/scrape.py (excerpt of run_scrape_for_user)

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import asyncio

from app.db import get_db
from app.models import User, Job, UserJob, ScrapeSchedule
from app.auth import get_current_user
from app.scrapers import fetch_remotive_jobs
from app.jobspy_scraper import scrape_with_jobspy
from app.playwright_scrapers import fetch_marineinsight_jobs, fetch_gcaptain_jobs  # add others
from app.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrape", tags=["Scraping"])

# ----- Pydantic schemas -----
class ScrapeStatusResponse(BaseModel):
    last_scrape: Optional[datetime] = None
    new_jobs_count: int = 0
    is_scraping: bool = False  # placeholder, can be enhanced later

class ScrapeScheduleRequest(BaseModel):
    is_active: bool
    cron_expression: Optional[str] = None

class ScrapeScheduleResponse(BaseModel):
    is_active: bool
    cron_expression: Optional[str] = None

# ----- Background task function -----
async def run_scrape_for_user(user_id: int, db: AsyncSession):
    """Fetch jobs from all enabled sources for a user and update UserJob entries."""
    user = await db.get(User, user_id)
    if not user:
        logger.error(f"User {user_id} not found during scrape")
        return

    # Get user keywords
    from app.models import UserKeyword
    kw_result = await db.execute(
        select(UserKeyword.keyword).where(UserKeyword.user_id == user_id)
    )
    keywords = kw_result.scalars().all()
    if not keywords:
        logger.info(f"User {user_id} has no keywords, scrape skipped")
        return

    sources = user.selected_sources or ["remotive"]

    # Split sources
    MAJOR_BOARDS = {"indeed", "linkedin", "glassdoor", "google_jobs"}
    MARITIME_SITES = {"marineinsight", "gcaptain"}  # add more as needed

    major_selected = [s for s in sources if s in MAJOR_BOARDS]
    maritime_selected = [s for s in sources if s in MARITIME_SITES]

    # Build list of scraping tasks
    tasks = []

    # Remotive (existing)
    if "remotive" in sources:
        tasks.append(fetch_remotive_jobs(keywords))

    # Major boards via JobSpy
    if major_selected:
        # Prepare proxies (JobSpy expects a list of proxy URLs)
        proxies = settings.PROXY_LIST
        tasks.append(scrape_with_jobspy(major_selected, keywords, proxies))

    # Maritime sites via Playwright
    if "marineinsight" in maritime_selected:
        tasks.append(fetch_marineinsight_jobs(keywords))
    if "gcaptain" in maritime_selected:
        tasks.append(fetch_gcaptain_jobs(keywords))

    # Run all scrapers concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect jobs, handling exceptions
    all_jobs = []
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Scraper task failed: {res}")
        elif isinstance(res, list):
            all_jobs.extend(res)

    # For future sources, add elif blocks here

    if not all_jobs:
        logger.info(f"No jobs found for user {user_id}")
        return

    # Get existing job URLs
    urls = [j["url"] for j in all_jobs if j.get("url")]
    existing_jobs_result = await db.execute(
        select(Job).where(Job.url.in_(urls))
    )
    existing_jobs = {job.url: job for job in existing_jobs_result.scalars().all()}

    # Prepare new Job objects
    new_jobs_to_add = []
    for job_data in all_jobs:
        url = job_data.get("url")
        if not url:
            continue
        if url not in existing_jobs:
            job = Job(**job_data)
            db.add(job)
            new_jobs_to_add.append(job)  # will get id after flush
        else:
            job = existing_jobs[url]

    # Flush to get IDs for new jobs
    await db.flush()

    # Now create UserJob entries for all fetched jobs (new or existing)
    newly_created_user_jobs = []
    for job_data in all_jobs:
        url = job_data["url"]
        job = existing_jobs.get(url) or next((j for j in new_jobs_to_add if j.url == url), None)
        if not job:
            continue

        # Check if UserJob already exists
        uj_result = await db.execute(
            select(UserJob).where(
                and_(UserJob.user_id == user_id, UserJob.job_id == job.id)
            )
        )
        uj = uj_result.scalar_one_or_none()
        if not uj:
            uj = UserJob(user_id=user_id, job_id=job.id, is_new=True)
            db.add(uj)
            newly_created_user_jobs.append(uj)
        # else: keep existing is_new as is (no change)

    # Mark all other UserJob entries for this user as not new
    if newly_created_user_jobs:
        new_ids = [uj.id for uj in newly_created_user_jobs]
        await db.execute(
            UserJob.__table__.update()
            .where(
                and_(UserJob.user_id == user_id, UserJob.id.notin_(new_ids))
            )
            .values(is_new=False)
        )
    else:
        # No new ones, set all to False
        await db.execute(
            UserJob.__table__.update()
            .where(UserJob.user_id == user_id)
            .values(is_new=False)
        )

    await db.commit()
    logger.info(f"Scrape completed for user {user_id}, {len(newly_created_user_jobs)} new jobs")

# ----- Endpoints -----
@router.post("/trigger", status_code=202)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a background scrape for the current user."""
    background_tasks.add_task(run_scrape_for_user, current_user.id, db)
    return {"message": "Scrape started in background"}

@router.get("/status", response_model=ScrapeStatusResponse)
async def get_scrape_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return last scrape time and number of new jobs."""
    # Get the most recent added_at from UserJob for this user
    result = await db.execute(
        select(func.max(UserJob.added_at)).where(UserJob.user_id == current_user.id)
    )
    last_scrape = result.scalar()

    # Count new jobs
    count_result = await db.execute(
        select(func.count()).where(
            and_(UserJob.user_id == current_user.id, UserJob.is_new == True)
        )
    )
    new_count = count_result.scalar() or 0

    return ScrapeStatusResponse(
        last_scrape=last_scrape,
        new_jobs_count=new_count,
        is_scraping=False  # placeholder
    )

@router.put("/schedule", response_model=ScrapeScheduleResponse)
async def set_schedule(
    req: ScrapeScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update the user's scrape schedule."""
    # Check if schedule exists
    result = await db.execute(
        select(ScrapeSchedule).where(ScrapeSchedule.user_id == current_user.id)
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        schedule.is_active = req.is_active
        schedule.cron_expression = req.cron_expression
    else:
        schedule = ScrapeSchedule(
            user_id=current_user.id,
            is_active=req.is_active,
            cron_expression=req.cron_expression
        )
        db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return ScrapeScheduleResponse(
        is_active=schedule.is_active,
        cron_expression=schedule.cron_expression
    )

@router.get("/schedule", response_model=ScrapeScheduleResponse)
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the user's current scrape schedule."""
    result = await db.execute(
        select(ScrapeSchedule).where(ScrapeSchedule.user_id == current_user.id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        return ScrapeScheduleResponse(is_active=False, cron_expression=None)
    return ScrapeScheduleResponse(
        is_active=schedule.is_active,
        cron_expression=schedule.cron_expression
    )