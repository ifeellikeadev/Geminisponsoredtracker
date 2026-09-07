import logging
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# --- Compatibility Wrappers for src/main.py ---

def reset_headless_budget():
    """No-op function to maintain interface compatibility with main.py."""
    pass

def fetch_description_fallback(url: str, ats_type: str = "") -> str:
    """Fallback fetcher to maintain interface compatibility with main.py."""
    try:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            return soup.get_text(separator=" ", strip=True)[:1000]
    except Exception:
        pass
    return ""

def is_location_match(location_str: str, target_locations: List[str]) -> bool:
    if not target_locations:
        return True
    loc_lower = (location_str or "").lower()
    return any(target.lower() in loc_lower for target in target_locations) or "remote" in loc_lower

def make_request(url: str, method: str = "GET", json_payload: Dict = None) -> requests.Response:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if method == "POST":
        return session.post(url, json=json_payload, timeout=12)
    return session.get(url, timeout=12)

# --- ATS Handlers ---

def fetch_greenhouse(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{entry['board_token']}/jobs?content=true"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                loc = item.get("location", {}).get("name", "")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": item.get("title"),
                        "location": loc,
                        "url": item.get("absolute_url"),
                        "ats": "Greenhouse",
                        "date_posted": item.get("updated_at")
                    })
    except Exception as e:
        logging.error(f"Greenhouse error for {entry.get('company')}: {e}")
    return jobs

def fetch_lever(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://api.lever.co/v0/postings/{entry['board_token']}"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json():
                loc = item.get("categories", {}).get("location", "")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": item.get("text"),
                        "location": loc,
                        "url": item.get("hostedUrl"),
                        "ats": "Lever",
                        "date_posted": str(item.get("createdAt", ""))
                    })
    except Exception as e:
        logging.error(f"Lever error for {entry.get('company')}: {e}")
    return jobs

def fetch_personio(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://{entry['company_id']}.jobs.personio.de/xml"
        res = make_request(url)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for position in root.findall(".//position"):
                office = position.findtext("office", "")
                if is_location_match(office, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": position.findtext("name", ""),
                        "location": office,
                        "url": f"https://{entry['company_id']}.jobs.personio.de/job/{position.findtext('id', '')}",
                        "ats": "Personio",
                        "date_posted": None
                    })
    except Exception as e:
        logging.error(f"Personio error for {entry.get('company')}: {e}")
    return jobs

def fetch_smartrecruiters(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://api.smartrecruiters.com/v1/companies/{entry['company_id']}/postings"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("content", []):
                city = item.get("location", {}).get("city", "")
                country = item.get("location", {}).get("country", "")
                loc = f"{city}, {country}".strip(", ")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": item.get("name"),
                        "location": loc,
                        "url": f"https://jobs.smartrecruiters.com/{entry['company_id']}/{item.get('id')}",
                        "ats": "SmartRecruiters",
                        "date_posted": item.get("releasedDate")
                    })
    except Exception as e:
        logging.error(f"SmartRecruiters error for {entry.get('company')}: {e}")
    return jobs

def fetch_workday(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        domain = entry["domain"]
        client_site = entry.get("client_site", "External")
        tenant = domain.split(".")[0]
        url = f"https://{domain}/wday/cxs/{tenant}/{client_site}/jobs"
        payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
        res = make_request(url, method="POST", json_payload=payload)
        if res.status_code == 200:
            for item in res.json().get("jobPostings", []):
                loc = item.get("location", "")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": item.get("title"),
                        "location": loc,
                        "url": f"https://{domain}/en-US/{client_site}{item.get('externalPath', '')}",
                        "ats": "Workday",
                        "date_posted": item.get("postedOn")
                    })
    except Exception as e:
        logging.error(f"Workday error for {entry.get('company')}: {e}")
    return jobs

def fetch_custom_html(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        res = make_request(entry["url"])
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            job_cards = soup.select(entry.get("job_selector", ".job"))
            for card in job_cards:
                title_el = card.select_one(entry.get("title_selector", "a"))
                link_el = card.select_one(entry.get("link_selector", "a"))
                loc_el = card.select_one(entry.get("location_selector", ".location"))
                
                title = title_el.get_text(strip=True) if title_el else "Unknown Title"
                url = link_el.get("href", "") if link_el else entry["url"]
                loc = loc_el.get_text(strip=True) if loc_el else "Not Specified"
                
                if not url.startswith("http"):
                    base_url = "/".join(entry["url"].split("/")[:3])
                    url = f"{base_url}{url}"

                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": entry["company"],
                        "title": title,
                        "location": loc,
                        "url": url,
                        "ats": "Custom Portal",
                        "date_posted": None
                    })
    except Exception as e:
        logging.error(f"Custom HTML error for {entry.get('company')}: {e}")
    return jobs

SCRAPER_MAP = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "personio": fetch_personio,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
    "custom_html": fetch_custom_html
}

def scrape_company_entry(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    ats = entry.get("ats", "").lower()
    scraper_fn = SCRAPER_MAP.get(ats)
    return scraper_fn(entry, target_locations) if scraper_fn else []

# Export scrape_company for main.py compatibility
scrape_company = scrape_company_entry

def run_all_scrapers(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    all_jobs = []
    tasks = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        for area, target_locs in [("munich_area", ["Munich", "München"]), ("zurich_area", ["Zurich", "Zürich"])]:
            for entry in config.get(area, []):
                tasks.append(executor.submit(scrape_company_entry, entry, target_locs))

        for future in as_completed(tasks):
            try:
                all_jobs.extend(future.result())
            except Exception as e:
                logging.error(f"Task exception: {e}")

    logging.info(f"Scraped {len(all_jobs)} jobs across all systems.")
    return all_jobs
