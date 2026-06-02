# app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, JSON, Boolean
from sqlalchemy.orm import relationship, backref
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # New columns
    phone = Column(String, nullable=True)
    default_cover_letter = Column(Text, nullable=True)
    resume_url = Column(String, nullable=True)
    selected_sources = Column(JSON, nullable=True, default=["remotive"])

    saved_jobs = relationship("SavedJob", back_populates="user", cascade="all, delete-orphan")
    keywords = relationship("UserKeyword", back_populates="user", cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String)
    location = Column(String)
    description = Column(Text)
    url = Column(String, unique=True, index=True, nullable=False)
    posted_date = Column(DateTime)
    source = Column(String)
    rank = Column(String, nullable=True)
    vessel_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # New columns for quick apply
    contact_email = Column(String, nullable=True)
    application_type = Column(String, nullable=True, default="url")  # "email" or "url"

    saved_by = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")

class UserKeyword(Base):
    __tablename__ = "user_keywords"
    __table_args__ = (UniqueConstraint("user_id", "keyword", name="unique_user_keyword"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    keyword = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="keywords")

# ... SavedJob remains unchanged ...
class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="unique_user_saved_job"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    saved_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="saved_jobs")
    job = relationship("Job", back_populates="saved_by")

# Add these imports at the top if not present
# from sqlalchemy import UniqueConstraint, Boolean

class UserJob(Base):
    __tablename__ = "user_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="unique_user_job"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    is_new = Column(Boolean, default=False, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref=backref("user_jobs", cascade="all, delete-orphan"))
    job = relationship("Job", backref=backref("user_jobs", cascade="all, delete-orphan"))


class ScrapeSchedule(Base):
    __tablename__ = "scrape_schedules"
    __table_args__ = (UniqueConstraint("user_id", name="unique_user_schedule"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    is_active = Column(Boolean, default=False, nullable=False)
    cron_expression = Column(String, nullable=True)  # e.g. "0 9 * * *"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref=backref("scrape_schedule", uselist=False, cascade="all, delete-orphan"))
