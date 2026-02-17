import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
import re
import logging
import os

from app.settings import settings

logger = logging.getLogger(__name__)

# ----- Date parsing -----
def parse_date(date_str: Any) -> datetime | None:
    if not date_str:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    # Fallback: return None (will be handled by caller)
    logger.warning(f"Could not parse date: {date_str}")
    return None

# ----- Rank detection -----
def extract_rank(title: str, description: str) -> str | None:
    text = (title + " " + description).lower()
    # Priority patterns (more specific first)
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

# ----- Vessel type extraction -----
def extract_vessel_type(title: str, description: str) -> str | None:
    text = (title + " " + description).lower()
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

# ----- Normalization -----
def normalize_job(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    title = raw.get("title", "").strip()
    description = raw.get("description", "") or raw.get("content", "") or ""
    return {
        "title": title,
        "company": raw.get("company", "").strip() or raw.get("company_name", ""),
        "location": raw.get("location", "").strip() or raw.get("candidate_required_location", ""),
        "description": description[:5000],
        "url": raw.get("url", "") or raw.get("apply_url", ""),
        "posted_date": parse_date(raw.get("posted_date") or raw.get("publication_date")),
        "source": source,
        "rank": extract_rank(title, description),
        "vessel_type": extract_vessel_type(title, description),
    }

# ----- Source 1: Remotive API -----
async def fetch_remotive_jobs() -> List[Dict[str, Any]]:
    jobs = []
    maritime_keywords = ["marine", "maritime", "engineer", "naval", "ship", "vessel", "3rd", "third", "4th", "fourth", "cadet"]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.REMOTIVE_API_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for job in data.get("jobs", []):
                title = job.get("title", "").lower()
                desc = job.get("description", "").lower()
                if any(kw in title or kw in desc for kw in maritime_keywords):
                    await asyncio.sleep(0.1)  # rate limiting
                    norm = normalize_job(job, "remotive")
                    jobs.append(norm)
    except Exception as e:
        logger.error(f"Remotive fetch error: {e}")
    return jobs

# ----- Source 2: Local HTML -----
async def fetch_local_html_jobs() -> List[Dict[str, Any]]:
    jobs = []
    if not os.path.exists(settings.LOCAL_HTML_PATH):
        logger.warning(f"Local HTML file not found: {settings.LOCAL_HTML_PATH}")
        return jobs
    try:
        with open(settings.LOCAL_HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        job_cards = soup.select(".job-listing")
        for card in job_cards:
            title_elem = card.select_one(".job-title")
            company_elem = card.select_one(".company")
            location_elem = card.select_one(".location")
            desc_elem = card.select_one(".description")
            url_elem = card.select_one("a.apply-link")

            job = {
                "title": title_elem.get_text(strip=True) if title_elem else "Unknown",
                "company": company_elem.get_text(strip=True) if company_elem else "Unknown",
                "location": location_elem.get_text(strip=True) if location_elem else "Unknown",
                "description": desc_elem.get_text(strip=True) if desc_elem else "",
                "url": url_elem.get("href") if url_elem else "",
                "posted_date": datetime.utcnow().isoformat(),  # local HTML has no date
            }
            if job["url"]:
                jobs.append(normalize_job(job, "local_html"))
    except Exception as e:
        logger.error(f"Local HTML fetch error: {e}")
    return jobs

# ----- Source 3: Mock (only in DEBUG) -----
async def fetch_mock_jobs() -> List[Dict[str, Any]]:
    if not settings.DEBUG:
        return []
    return [
        {
            "title": "3rd Marine Engineer",
            "company": "Oceania Shipping Co.",
            "location": "Singapore",
            "description": "We are looking for a 3rd Engineer for our new container vessel. Experience with MAN B&W engines preferred.",
            "url": "https://example.com/apply/3rd-engineer",
            "posted_date": datetime.utcnow().isoformat(),
            "source": "mock",
            "rank": "3rd Engineer",
            "vessel_type": "Container"
        },
        # ... other mock jobs
    ]

# ----- Aggregator with isolated failures -----
async def fetch_all_jobs() -> List[Dict[str, Any]]:
    tasks = [
        fetch_remotive_jobs(),
        fetch_local_html_jobs(),
        fetch_mock_jobs(),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    jobs = []
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Scraper failed: {res}")
        else:
            jobs.extend(res)
    return jobs