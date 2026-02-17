from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from app.db import get_db
from app.models import Job, SavedJob, User
from app.auth import get_current_user
from app.scrapers import fetch_all_jobs

logger = logging.getLogger(__name__)
router = APIRouter()

class JobResponse(BaseModel):
    id: int
    title: str
    company: Optional[str]
    location: Optional[str]
    description: str
    url: str
    posted_date: Optional[datetime]
    source: str
    rank: Optional[str]
    vessel_type: Optional[str]

    class Config:
        from_attributes = True

class JobSaveRequest(BaseModel):
    job_id: int

async def store_jobs(jobs_data: List[dict], db: AsyncSession):
    if not jobs_data:
        return 0

    urls = [j["url"] for j in jobs_data if j.get("url")]
    if not urls:
        return 0

    result = await db.execute(select(Job.url).where(Job.url.in_(urls)))
    existing_urls = set(result.scalars().all())

    new_jobs = [Job(**j) for j in jobs_data if j.get("url") and j["url"] not in existing_urls]
    if not new_jobs:
        return 0

    db.add_all(new_jobs)
    try:
        await db.commit()
        return len(new_jobs)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to store jobs: {e}")
        return 0

@router.get("/", response_model=List[JobResponse])
async def get_jobs(
    rank: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    vessel_type: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Job)

    if rank:
        query = query.where(Job.rank.ilike(f"%{rank}%"))
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if vessel_type:
        query = query.where(Job.vessel_type.ilike(f"%{vessel_type}%"))

    query = query.order_by(desc(Job.posted_date)).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/fetch", status_code=202)
async def trigger_fetch_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 🔒 protect this
):
    jobs = await fetch_all_jobs()
    stored = await store_jobs(jobs, db)
    return {"message": "Fetch completed", "fetched": len(jobs), "stored": stored}

@router.post("/save", status_code=201)
async def save_job(
    request: JobSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = await db.get(Job, request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stmt = select(SavedJob).where(
        and_(SavedJob.user_id == current_user.id, SavedJob.job_id == request.job_id)
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already saved")

    db.add(SavedJob(user_id=current_user.id, job_id=request.job_id))
    await db.commit()
    return {"message": "Saved successfully"}

@router.delete("/unsave/{job_id}")
async def unsave_job(job_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        delete(SavedJob).where(and_(SavedJob.user_id == current_user.id, SavedJob.job_id == job_id))
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Saved job not found")

    return {"message": "Unsaved successfully"}

@router.get("/saved", response_model=List[JobResponse])
async def get_saved_jobs(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Job)
        .join(SavedJob)
        .where(SavedJob.user_id == current_user.id)
        .order_by(desc(Job.posted_date))
    )
    return result.scalars().all()
