import logging
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def is_location_match(location_str: str, target_locations: List[str]) -> bool:
    if not target_locations:
        return True
    loc_lower = (location_str or "").lower()
    return any(target.lower() in loc_lower for target in target_locations) or "remote" in loc_lower

def fetch_greenhouse(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    company = entry["company"]
    board_token = entry["board_token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                loc = item.get("location", {}).get("name", "")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": company,
                        "title": item.get("title"),
                        "location": loc,
                        "url": item.get("absolute_url"),
                        "ats": "Greenhouse",
                        "date_posted": item.get("updated_at")
                    })
    except Exception as e:
        logging.error(f"Error scraping Greenhouse for {company}: {e}")
    return jobs

def fetch_lever(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    company = entry["company"]
    board_token = entry["board_token"]
    url = f"https://api.lever.co/v0/postings/{board_token}"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json():
                loc = item.get("categories", {}).get("location", "")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": company,
                        "title": item.get("text"),
                        "location": loc,
                        "url": item.get("hostedUrl"),
                        "ats": "Lever",
                        "date_posted": str(item.get("createdAt", ""))
                    })
    except Exception as e:
        logging.error(f"Error scraping Lever for {company}: {e}")
    return jobs

def fetch_personio(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    company = entry["company"]
    company_id = entry["company_id"]
    url = f"https://{company_id}.jobs.personio.de/xml"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for position in root.findall(".//position"):
                title = position.findtext("name", "")
                office = position.findtext("office", "")
                job_id = position.findtext("id", "")
                if is_location_match(office, target_locations):
                    jobs.append({
                        "company": company,
                        "title": title,
                        "location": office,
                        "url": f"https://{company_id}.jobs.personio.de/job/{job_id}",
                        "ats": "Personio",
                        "date_posted": None
                    })
    except Exception as e:
        logging.error(f"Error scraping Personio for {company}: {e}")
    return jobs

def fetch_smartrecruiters(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    company = entry["company"]
    company_id = entry["company_id"]
    url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json().get("content", []):
                city = item.get("location", {}).get("city", "")
                country = item.get("location", {}).get("country", "")
                loc = f"{city}, {country}".strip(", ")
                if is_location_match(loc, target_locations):
                    jobs.append({
                        "company": company,
                        "title": item.get("name"),
                        "location": loc,
                        "url": f"https://jobs.smartrecruiters.com/{company_id}/{item.get('id')}",
                        "ats": "SmartRecruiters",
                        "date_posted": item.get("releasedDate")
                    })
    except Exception as e:
        logging.error(f"Error scraping SmartRecruiters for {company}: {e}")
    return jobs

def fetch_workday(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    company = entry["company"]
    domain = entry["domain"]
    client_site = entry.get("client_site", "External")
    tenant = domain.split(".")[0]
    url = f"https://{domain}/wday/cxs/{tenant}/{client_site}/jobs"
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    jobs = []
    try:
        res = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobPostings", []):
                loc = item.get("location", "")
                if is_location_match(loc, target_locations):
                    external_path = item.get("externalPath", "")
                    jobs.append({
                        "company": company,
                        "title": item.get("title"),
                        "location": loc,
                        "url": f"https://{domain}/en-US/{client_site}{external_path}",
                        "ats": "Workday",
                        "date_posted": item.get("postedOn")
                    })
    except Exception as e:
        logging.error(f"Error scraping Workday for {company}: {e}")
    return jobs

SCRAPER_MAP = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "personio": fetch_personio,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday
}

def scrape_company_entry(entry: Dict[str, Any], target_locations: List[str]) -> List[Dict[str, Any]]:
    ats = entry.get("ats", "").lower()
    scraper_fn = SCRAPER_MAP.get(ats)
    return scraper_fn(entry, target_locations) if scraper_fn else []

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
                logging.error(f"Task generated an exception: {e}")

    logging.info(f"Successfully scraped {len(all_jobs)} total matching job listings.")
    return all_jobs
