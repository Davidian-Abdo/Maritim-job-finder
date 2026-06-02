from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, or_, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from app.db import get_db
from app.models import Job, SavedJob, User, UserJob 
from app.auth import get_current_user
from app.supabase_client import get_supabase_client
from app.models import UserKeyword
from app.settings import settings


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
    contact_email: Optional[str]          # added
    application_type: Optional[str]       # added
    is_new: bool = False                   # added

    class Config:
        from_attributes = True

class JobSaveRequest(BaseModel):
    job_id: int

class QuickApplyRequest(BaseModel):
    cover_letter: Optional[str] = None
    use_default: bool = False


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
    title: Optional[str] = Query(None, description="Filter by job title"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    keywords: Optional[str] = Query(None, description="Comma‑separated keywords override"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Base query with left join to UserJob to get is_new
    query = (
        select(Job, UserJob.is_new)
        .outerjoin(UserJob, and_(UserJob.job_id == Job.id, UserJob.user_id == current_user.id))
    )

    # Keyword filtering
    if keywords:
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    else:
        result = await db.execute(
            select(UserKeyword.keyword).where(UserKeyword.user_id == current_user.id)
        )
        kw_list = result.scalars().all()

    if kw_list:
        conditions = []
        for kw in kw_list:
            conditions.append(Job.title.ilike(f"%{kw}%"))
            conditions.append(Job.description.ilike(f"%{kw}%"))
        query = query.where(or_(*conditions))

    if rank:
        query = query.where(Job.rank.ilike(f"%{rank}%"))
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if vessel_type:
        query = query.where(Job.vessel_type.ilike(f"%{vessel_type}%"))
    if title:
        query = query.where(Job.title.ilike(f"%{title}%"))
    if company:
        query = query.where(Job.company.ilike(f"%{company}%"))
    if current_user.selected_sources:
        query = query.where(Job.source.in_(current_user.selected_sources))

    query = query.order_by(desc(Job.posted_date)).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Build response
    jobs = []
    for job, is_new in rows:
        job_dict = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "url": job.url,
            "posted_date": job.posted_date,
            "source": job.source,
            "rank": job.rank,
            "vessel_type": job.vessel_type,
            "contact_email": job.contact_email,
            "application_type": job.application_type,
            "is_new": is_new or False,   # if no UserJob, is_new is None -> False
        }
        jobs.append(JobResponse(**job_dict))
    return jobs

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


@router.post("/{job_id}/apply")
async def quick_apply(
    job_id: int,
    req: QuickApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch job
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if application via email is possible
    if job.application_type != "email" or not job.contact_email:
        raise HTTPException(status_code=400, detail="This job does not support email application")

    # Ensure user has resume
    if not current_user.resume_url:
        raise HTTPException(status_code=400, detail="Please upload a resume first")

    # Determine cover letter
    cover_letter = req.cover_letter
    if req.use_default:
        cover_letter = current_user.default_cover_letter or ""
    if not cover_letter:
        raise HTTPException(status_code=400, detail="Cover letter is required")

    # Download resume from Supabase
    supabase = get_supabase_client()
    try:
        # Extract filename from URL (assuming public URL)
        filename = current_user.resume_url.split("/")[-1]
        resume_data = supabase.storage.from_(settings.SUPABASE_BUCKET_RESUMES).download(filename)
    except Exception as e:
        logger.error(f"Failed to download resume: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve resume")

    # Prepare email
    subject = f"Application for {job.title} at {job.company}"
    body = f"""
    Dear Hiring Team,

    {cover_letter}

    ---
    Applicant: {current_user.full_name or current_user.email}
    Email: {current_user.email}
    Phone: {current_user.phone or "Not provided"}
    ---
    This application was sent via Maritime Jobs Aggregator.
    """

    # Send email using SMTP (run in thread to avoid blocking)
    try:
        import asyncio
        from app.email_sender import send_email  # we'll create this helper
        await asyncio.to_thread(
            send_email,
            to_email=job.contact_email,
            subject=subject,
            body=body,
            reply_to=current_user.email,
            attachment_data=resume_data,
            attachment_name=filename,
        )
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send application email")

    return {"message": "Application sent successfully"}
