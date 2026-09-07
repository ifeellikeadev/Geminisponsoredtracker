import logging
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

def reset_headless_budget():
    pass

def fetch_description_fallback(url: str, ats_type: str = "") -> str:
    try:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            return soup.get_text(separator=" ", strip=True)[:1000]
    except Exception:
        pass
    return ""

def is_location_match(location_str: str, target_locs: List[str]) -> bool:
    if not location_str:
        return True
    loc_lower = location_str.lower()
    
    if target_locs:
        for t in target_locs:
            if t and t.lower() in loc_lower:
                return True
                
    broad_regional = ["remote", "switzerland", "schweiz", "germany", "deutschland", "dach", "munich", "münchen", "zurich", "zürich"]
    return any(keyword in loc_lower for keyword in broad_regional)

def make_request(url: str, method: str = "GET", json_payload: Dict = None) -> requests.Response:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if method == "POST":
        return session.post(url, json=json_payload, timeout=12)
    return session.get(url, timeout=12)

def fetch_greenhouse(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{entry['board_token']}/jobs?content=true"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                loc = item.get("location", {}).get("name", "")
                title = item.get("title", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": item.get("absolute_url"),
                        "ats": "Greenhouse",
                        "date_posted": item.get("updated_at"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Greenhouse error for {entry.get('name')}: {e}")
    return jobs

def fetch_lever(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://api.lever.co/v0/postings/{entry['board_token']}"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json():
                loc = item.get("categories", {}).get("location", "")
                title = item.get("text", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": item.get("hostedUrl"),
                        "ats": "Lever",
                        "date_posted": str(item.get("createdAt", "")),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Lever error for {entry.get('name')}: {e}")
    return jobs

def fetch_personio(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://{entry['company_id']}.jobs.personio.de/xml"
        res = make_request(url)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for position in root.findall(".//position"):
                office = position.findtext("office", "")
                title = position.findtext("name", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(office, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": office,
                        "url": f"https://{entry['company_id']}.jobs.personio.de/job/{position.findtext('id', '')}",
                        "ats": "Personio",
                        "date_posted": None,
                        "description": f"{title} position at {comp} in {office}"
                    })
    except Exception as e:
        logging.error(f"Personio error for {entry.get('name')}: {e}")
    return jobs

def fetch_smartrecruiters(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://api.smartrecruiters.com/v1/companies/{entry['company_id']}/postings"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("content", []):
                city = item.get("location", {}).get("city", "")
                country = item.get("location", {}).get("country", "")
                loc = f"{city}, {country}".strip(", ")
                title = item.get("name", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": f"https://jobs.smartrecruiters.com/{entry['company_id']}/{item.get('id')}",
                        "ats": "SmartRecruiters",
                        "date_posted": item.get("releasedDate"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"SmartRecruiters error for {entry.get('name')}: {e}")
    return jobs

def fetch_workday(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        domain = entry["domain"]
        client_site = entry.get("client_site", "External")
        tenant = domain.split(".")[0]
        url = f"https://{domain}/wday/cxs/{tenant}/{client_site}/jobs"
        payload = {"appliedFacets": {}, "limit": 50, "offset": 0, "searchText": ""}
        res = make_request(url, method="POST", json_payload=payload)
        if res.status_code == 200:
            for item in res.json().get("jobPostings", []):
                loc = item.get("location", "")
                title = item.get("title", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": f"https://{domain}/en-US/{client_site}{item.get('externalPath', '')}",
                        "ats": "Workday",
                        "date_posted": item.get("postedOn"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Workday error for {entry.get('name')}: {e}")
    return jobs

def fetch_ashby(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{entry['board_token']}"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                loc = item.get("locationName", "")
                title = item.get("title", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": item.get("jobUrl"),
                        "ats": "Ashby",
                        "date_posted": item.get("publishedAt"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Ashby error for {entry.get('name')}: {e}")
    return jobs

def fetch_recruitee(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://{entry['company_id']}.recruitee.com/api/offers"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("offers", []):
                loc = item.get("location", "")
                title = item.get("title", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": item.get("careers_url"),
                        "ats": "Recruitee",
                        "date_posted": item.get("created_at"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Recruitee error for {entry.get('name')}: {e}")
    return jobs

def fetch_teamtailor(entry: Dict[str, Any], target_locs: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    try:
        url = f"https://{entry['company_id']}.teamtailor.com/jobs.json"
        res = make_request(url)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                attrs = item.get("attributes", {})
                loc = attrs.get("location-name", "") or attrs.get("city", "")
                title = attrs.get("title", "")
                comp = entry.get("name", "Unknown")
                if is_location_match(loc, target_locs):
                    jobs.append({
                        "company": comp,
                        "title": title,
                        "location": loc,
                        "url": attrs.get("url"),
                        "ats": "Teamtailor",
                        "date_posted": attrs.get("created-at"),
                        "description": f"{title} position at {comp} in {loc}"
                    })
    except Exception as e:
        logging.error(f"Teamtailor error for {entry.get('name')}: {e}")
    return jobs

SCRAPER_MAP = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "personio": fetch_personio,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
    "ashby": fetch_ashby,
    "recruitee": fetch_recruitee,
    "teamtailor": fetch_teamtailor
}

def scrape_company(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    ats = entry.get("ats", "").lower()
    target_locs = [entry.get("location")] if entry.get("location") else ["Munich", "München", "Zurich", "Zürich", "Switzerland"]
    scraper_fn = SCRAPER_MAP.get(ats)
    return scraper_fn(entry, target_locs) if scraper_fn else []
