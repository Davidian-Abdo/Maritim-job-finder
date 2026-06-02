from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import logging
import mimetypes
import os
import tempfile
import aiofiles

from app.db import get_db
from app.models import User, UserKeyword
from app.auth import get_current_user
from app.settings import settings
from app.supabase_client import get_supabase_client  # we'll create this

router = APIRouter(tags=["Profile"])
logger = logging.getLogger(__name__)

# ---------- Schemas ----------
class ProfileResponse(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None
    default_cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    selected_sources: List[str]

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    default_cover_letter: Optional[str] = None
    selected_sources: Optional[List[str]] = None

class KeywordResponse(BaseModel):
    keyword: str

class AddKeywordRequest(BaseModel):
    keyword: str

class SourcesResponse(BaseModel):
    sources: List[str]

# ---------- Endpoints ----------
@router.get("/", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/", response_model=ProfileResponse)
async def update_profile(
    updates: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.post("/resume", response_model=dict)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate file type
    allowed_mimes = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    file_type = mimetypes.guess_type(file.filename)[0] or file.content_type
    if file_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail="Only PDF, DOC, DOCX files are allowed")

    # Read file content
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Generate a safe filename inside a folder named by user id
    folder = str(current_user.id)
    ext = os.path.splitext(file.filename)[1]
    # Example: "123/123_user@example.com.pdf"
    object_path = f"{folder}/{current_user.id}_{current_user.email}{ext}"

    supabase = get_supabase_client()
    try:
        # Upload file to the constructed path
        supabase.storage.from_(settings.SUPABASE_BUCKET_RESUMES).upload(
            path=object_path,
            file=content,
            file_options={"content-type": file_type}
        )
        # Get public URL (e.g., https://xyz.supabase.co/storage/v1/object/public/resumes/123/123_user@example.com.pdf)
        public_url = supabase.storage.from_(settings.SUPABASE_BUCKET_RESUMES).get_public_url(object_path)
    except Exception as e:
        logger.error(f"Supabase upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

    # Delete old resume if exists
    if current_user.resume_url:
        # Extract the old object path from the stored URL
        # URL format: https://<project>.supabase.co/storage/v1/object/public/<bucket>/<path>
        base_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET_RESUMES}/"
        if current_user.resume_url.startswith(base_url):
            old_object_path = current_user.resume_url[len(base_url):]
            try:
                supabase.storage.from_(settings.SUPABASE_BUCKET_RESUMES).remove([old_object_path])
            except Exception as e:
                logger.warning(f"Failed to delete old resume: {e}")
        else:
            logger.warning(f"Old resume URL does not match expected format: {current_user.resume_url}")

    # Update user record with the new public URL
    current_user.resume_url = public_url
    db.add(current_user)
    await db.commit()

    return {"resume_url": public_url}

@router.get("/keywords", response_model=List[str])
async def get_keywords(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(UserKeyword.keyword).where(UserKeyword.user_id == current_user.id).order_by(UserKeyword.keyword)
    )
    return result.scalars().all()

@router.post("/keywords", status_code=201)
async def add_keyword(
    req: AddKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check duplicate
    result = await db.execute(
        select(UserKeyword).where(
            UserKeyword.user_id == current_user.id,
            UserKeyword.keyword == req.keyword
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Keyword already exists")

    new_kw = UserKeyword(user_id=current_user.id, keyword=req.keyword)
    db.add(new_kw)
    await db.commit()
    return {"message": "Keyword added"}

@router.delete("/keywords/{keyword}")
async def delete_keyword(
    keyword: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        delete(UserKeyword).where(
            UserKeyword.user_id == current_user.id,
            UserKeyword.keyword == keyword
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"message": "Keyword deleted"}

@router.get("/sources", response_model=SourcesResponse)
async def get_available_sources():
    return SourcesResponse(sources=settings.AVAILABLE_SOURCES)