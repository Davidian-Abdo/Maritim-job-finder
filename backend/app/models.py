from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    saved_jobs = relationship("SavedJob", back_populates="user", cascade="all, delete-orphan")

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
    saved_by = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")

class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="unique_user_job"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    saved_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="saved_jobs")
    job = relationship("Job", back_populates="saved_by")
