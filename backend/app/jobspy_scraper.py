# backend/app/jobspy_scraper.py

import asyncio
import logging
from typing import List, Dict, Any, Optional

import pandas as pd
from jobspy import scrape_jobs

from app.settings import settings
from app.scrapers import normalize_job

logger = logging.getLogger(__name__)

# Map our internal source names to JobSpy's site_name
JOBSPY_SITE_MAP = {
    "indeed": "indeed",
    "linkedin": "linkedin",
    "glassdoor": "glassdoor",
    "google_jobs": "google",
}

async def scrape_with_jobspy(
    sources: List[str],
    keywords: List[str],
    proxies: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Run JobSpy scrapers for each source individually.
    `proxies` must be a list of proxy URLs (strings), e.g.:
        ["http://user:pass@proxy1:port", "http://user:pass@proxy2:port"]
    """
    if not sources or not keywords:
        return []

    search_term = " ".join(keywords)
    all_jobs = []

    for source in sources:
        site = JOBSPY_SITE_MAP.get(source)
        if not site:
            logger.warning(f"Unknown JobSpy source: {source}")
            continue

        loop = asyncio.get_event_loop()
        try:
            df: pd.DataFrame = await loop.run_in_executor(
                None,
                lambda: scrape_jobs(
                    site_name=[site],
                    search_term=search_term,
                    results_wanted=settings.JOBSPY_RESULTS_WANTED,
                    hours_old=settings.JOBSPY_HOURS_OLD,
                    proxies=proxies,  # ✅ list of strings, as required
                )
            )
        except Exception as e:
            logger.error(f"JobSpy scraping failed for {source}: {e}")
            continue  # try next source

        if df is None or df.empty:
            logger.info(f"No jobs from {source}")
            continue

        # Convert each row to our normalized format
        for _, row in df.iterrows():
            raw = {
                "title": row.get("title"),
                "company": row.get("company_name"),
                "location": row.get("location"),
                "description": row.get("description"),
                "url": row.get("job_url"),
                "posted_date": row.get("date_posted"),
                "source": source,  # use our internal source name
            }
            normalized = normalize_job(raw, source=source)
            all_jobs.append(normalized)

        logger.info(f"{source} returned {len(df)} jobs")

    logger.info(f"JobSpy total: {len(all_jobs)} jobs from {sources}")
    return all_jobs