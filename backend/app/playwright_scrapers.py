import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page

from app.scrapers import normalize_job  # reuse the normalizer

logger = logging.getLogger(__name__)

# Common selectors – adjust after inspecting the actual site
MARINEINSIGHT_SELECTORS = {
    'job_card': 'div.job-listing',  # example, change accordingly
    'title': 'h2.job-title',
    'company': 'div.company',
    'location': 'div.location',
    'description': 'div.description',
    'url': 'a.apply-link@href',
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
]

async def fetch_marineinsight_jobs(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Scrape marineinsight.com/jobs using Playwright, filter by keywords.
    """
    jobs = []
    browser = None
    try:
        async with async_playwright() as p:
            # Launch browser (headless by default)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS)
            )
            page = await context.new_page()

            # Navigate to the jobs page
            url = "https://www.marineinsight.com/jobs/"  # example URL
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for job cards to appear (adjust selector)
            await page.wait_for_selector(MARINEINSIGHT_SELECTORS['job_card'], timeout=10000)

            # Extract job data
            job_cards = await page.query_selector_all(MARINEINSIGHT_SELECTORS['job_card'])
            for card in job_cards:
                try:
                    title_elem = await card.query_selector(MARINEINSIGHT_SELECTORS['title'])
                    title = await title_elem.inner_text() if title_elem else ""

                    company_elem = await card.query_selector(MARINEINSIGHT_SELECTORS['company'])
                    company = await company_elem.inner_text() if company_elem else ""

                    location_elem = await card.query_selector(MARINEINSIGHT_SELECTORS['location'])
                    location = await location_elem.inner_text() if location_elem else ""

                    desc_elem = await card.query_selector(MARINEINSIGHT_SELECTORS['description'])
                    description = await desc_elem.inner_text() if desc_elem else ""

                    url_elem = await card.query_selector(MARINEINSIGHT_SELECTORS['url'].split('@')[0])
                    job_url = await url_elem.get_attribute('href') if url_elem else ""

                    # Build raw dict for normalizer
                    raw_job = {
                        'title': title,
                        'company': company,
                        'location': location,
                        'description': description,
                        'url': job_url,
                        'source': 'marineinsight',
                        # no posted_date here – you may need to extract separately
                    }

                    # Keyword filtering (case‑insensitive)
                    text = (title + " " + description).lower()
                    if any(kw.lower() in text for kw in keywords):
                        # Add small delay to be polite
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        norm = normalize_job(raw_job, 'marineinsight')
                        jobs.append(norm)
                except Exception as e:
                    logger.warning(f"Error parsing a job card: {e}")
                    continue

            logger.info(f"Extracted {len(jobs)} jobs from marineinsight")
    except Exception as e:
        logger.error(f"Marineinsight scraping failed: {e}")
    finally:
        if browser:
            await browser.close()
    return jobs


# Future scrapers for other sites (gcaptain, etc.) can be added here.
# backend/app/playwright_scrapers.py (add this function)

async def fetch_gcaptain_jobs(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Example Playwright scraper for gCaptain jobs page.
    Replace with actual implementation based on site structure.
    """
    jobs = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Navigate to gCaptain job board (adjust URL)
            await page.goto("https://gcaptain.com/jobs/", timeout=30000)

            # Wait for job listings – update selector to match the site
            await page.wait_for_selector(".job-listing", timeout=5000)

            # Extract job data – these selectors are examples; inspect the real page
            titles = await page.locator(".job-title").all_text_contents()
            companies = await page.locator(".company").all_text_contents()
            locations = await page.locator(".location").all_text_contents()
            links = await page.locator("a.apply-link").all()
            urls = [await link.get_attribute("href") for link in links if link]

            # Build raw job dicts
            for i in range(min(len(titles), len(urls))):
                raw = {
                    "title": titles[i],
                    "company": companies[i] if i < len(companies) else "",
                    "location": locations[i] if i < len(locations) else "",
                    "description": "",  # may need to fetch detail page
                    "url": urls[i],
                    "posted_date": None,
                }
                # Apply keyword filtering
                text = (raw["title"] + " " + raw["company"]).lower()
                if any(kw.lower() in text for kw in keywords):
                    norm = normalize_job(raw, source="gcaptain")
                    jobs.append(norm)

            await browser.close()
    except Exception as e:
        logger.error(f"gCaptain scraper error: {e}")

    logger.info(f"gCaptain returned {len(jobs)} jobs")
    return jobs

# Dispatcher map
SCRAPER_DISPATCH = {
    'remotive': None,  # special case – we'll keep using fetch_remotive_jobs
    'marineinsight': fetch_marineinsight_jobs,
    'gcaptain':fetch_gcaptain_jobs
}