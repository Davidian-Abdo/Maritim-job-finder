import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
import re
import logging

from app.settings import settings

logger = logging.getLogger(__name__)

EMAIL_REGEX = r'[\w\.-]+@[\w\.-]+\.\w+'

def safe_str(value) -> str:
    """Return stripped string if value is a non‑empty string, else empty string."""
    if value and isinstance(value, str):
        return value.strip()
    return ""

def parse_date(date_str: Any) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {date_str}")
    return None

def extract_rank(title: str, description: str) -> str | None:
    text = safe_str(title) + " " + safe_str(description)
    text = text.lower()
    patterns = [
        (r"\b3rd\s+engineer\b", "3rd Engineer"),
        (r"\bthird\s+engineer\b", "3rd Engineer"),
        (r"\b4th\s+engineer\b", "4th Engineer"),
        (r"\bfourth\s+engineer\b", "4th Engineer"),
        (r"\bcadet\b", "Cadet"),
        (r"\bjunior\s+engineer\b", "Cadet"),
        (r"\btrainee\s+engineer\b", "Cadet"),
        (r"\b2nd\s+engineer\b", "2nd Engineer"),
        (r"\bsecond\s+engineer\b", "2nd Engineer"),
        (r"\bchief\s+engineer\b", "Chief Engineer"),
    ]
    for pattern, rank in patterns:
        if re.search(pattern, text):
            return rank
    return None
def extract_vessel_type(title: str, description: str) -> str | None:
    text = safe_str(title) + " " + safe_str(description)
    text = text.lower()
    keywords = {
        "tanker": "Tanker",
        "container": "Container",
        "bulk": "Bulk Carrier",
        "cargo": "Cargo",
        "offshore": "Offshore",
        "cruise": "Cruise",
        "roro": "Ro-Ro",
        "lng": "LNG",
        "lpg": "LPG",
        "chemical": "Chemical Tanker",
        "supply": "Supply Vessel",
        "psv": "PSV",
        "ahv": "AHV",
        "drillship": "Drillship",
    }
    for kw, vtype in keywords.items():
        if kw in text:
            return vtype
    return None

def normalize_job(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    title = safe_str(raw.get("title"))
    description = safe_str(raw.get("description")) or safe_str(raw.get("content"))

    emails = re.findall(EMAIL_REGEX, description)
    contact_email = emails[0] if emails else None
    application_type = "email" if contact_email else "url"

    return {
        "title": title,
        "company": safe_str(raw.get("company")) or safe_str(raw.get("company_name")),
        "location": safe_str(raw.get("location")) or safe_str(raw.get("candidate_required_location")),
        "description": description[:5000],
        "url": safe_str(raw.get("url")) or safe_str(raw.get("apply_url")),
        "posted_date": parse_date(raw.get("posted_date") or raw.get("publication_date")),
        "source": source,
        "rank": extract_rank(title, description),
        "vessel_type": extract_vessel_type(title, description),
        "contact_email": contact_email,
        "application_type": application_type,
    }

async def fetch_remotive_jobs(keywords: List[str]) -> List[Dict[str, Any]]:
    """Fetch jobs from Remotive API and filter by given keywords."""
    jobs = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.REMOTIVE_API_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for job in data.get("jobs", []):
                title = job.get("title", "").lower()
                desc = job.get("description", "").lower()
                # Check if any keyword appears in title or description
                if any(kw.lower() in title or kw.lower() in desc for kw in keywords):
                    await asyncio.sleep(0.1)  # basic rate limiting
                    norm = normalize_job(job, "remotive")
                    jobs.append(norm)
    except Exception as e:
        logger.error(f"Remotive fetch error: {e}")
    return jobs