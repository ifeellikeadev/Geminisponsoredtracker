import yaml
import re
from typing import Dict, List, Any, Optional

MAIN_LIST_CITIES = ["Munich", "Zurich"]
SWISS_CITIES = ["Basel", "Bern", "Geneva", "Lausanne", "Lucerne"]

def load_cv_profile(path: str = "config/cv_profile.yaml") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def filter_by_title_only(jobs: List[Dict[str, Any]], cv_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    exclude_keywords = [k.lower() for k in cv_profile.get("exclude_keywords", []) if k] if cv_profile else []
    keywords = [k.lower() for k in cv_profile.get("keywords", []) if k] if cv_profile else []
    
    # Ultra-strict generic tech terms: no standalone "engineer", "ai", "lead", or "manager"
    generic_tech = [
        "software", "backend", "frontend", "fullstack", "full-stack", 
        "devops", "sre", "machine learning", "data scientist", 
        "data engineer", "cloud", "platform engineer", 
        "ai engineer", "ai research"
    ]
    
    filtered = []
    for job in jobs:
        title = job.get("title", "").lower()
        
        if any(ex in title for ex in exclude_keywords):
            continue
            
        if keywords and any(k in title for k in keywords):
            filtered.append(job)
            continue
            
        if any(re.search(rf"\b{re.escape(term)}\b", title) for term in generic_tech):
            filtered.append(job)
            
    return filtered

def resolve_city_for_job(job: Dict[str, Any], search_text: Optional[str] = None) -> Optional[str]:
    loc = str(job.get("location") or job.get("city") or "").lower()
    search = str(search_text or "").lower()
    combined = f"{loc} {search}"

    matched = None
    if any(c in combined for c in ["munich", "münchen"]):
        matched = "Munich"
    elif any(c in combined for c in ["zurich", "zürich"]):
        matched = "Zurich"
    else:
        for city in SWISS_CITIES:
            if city.lower() in combined:
                matched = city
                break

    if not matched:
        if "switzerland" in combined or "schweiz" in combined:
            matched = "Zurich"
        elif "germany" in combined or "deutschland" in combined:
            matched = "Munich"

    if matched:
        job["matched_city"] = matched
        return matched
        
    return None

def extract_location_snippet(text: str, city: str) -> str:
    if not text:
        return city
    
    # Prevent anti-bot/JS warnings from bleeding into the Excel file
    text_lower = text.lower()
    if "enable javascript" in text_lower or "javascript to run" in text_lower:
        return city
        
    idx = text_lower.find(city.lower())
    if idx == -1:
        return city
        
    start = max(0, idx - 40)
    end = min(len(text), idx + 60)
    snippet = text[start:end].replace('\n', ' ').strip()
    return f"...{snippet}..." if start > 0 else f"{snippet}..."

def score_jobs(jobs: List[Dict[str, Any]], cv_profile: Dict[str, Any]) -> None:
    keywords = [k.lower() for k in cv_profile.get("keywords", []) if k] if cv_profile else []
    for job in jobs:
        # Map ATS 'date_posted' to tracker 'posted_date' and cleanly format to YYYY-MM-DD
        if job.get("date_posted"):
            raw_date = str(job["date_posted"])
            match = re.search(r'\d{4}-\d{2}-\d{2}', raw_date)
            job["posted_date"] = match.group(0) if match else raw_date
            
        text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        score = 50
        if keywords:
            matched = sum(1 for k in keywords if k in text)
            score = min(100, 60 + (matched * 10))
        job["relevance_score"] = score
