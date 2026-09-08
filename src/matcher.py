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
    if not cv_profile:
        return jobs
        
    must_match = [k.lower() for k in cv_profile.get("title_must_match", [])]
    must_not_match = [k.lower() for k in cv_profile.get("title_must_not_match", [])]
    
    filtered = []
    for job in jobs:
        title = job.get("title", "").lower()
        
        # 1. Reject if it matches any exclusion word
        if must_not_match and any(ex in title for ex in must_not_match):
            continue
            
        # 2. Accept if it matches any required word
        if must_match:
            if any(req in title for req in must_match):
                filtered.append(job)
        else:
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
    scoring_keywords = cv_profile.get("scoring_keywords", [])
    score_ceiling = cv_profile.get("score_ceiling", 20)
    
    for job in jobs:
        if job.get("date_posted"):
            raw_date = str(job["date_posted"])
            match = re.search(r'\d{4}-\d{2}-\d{2}', raw_date)
            job["posted_date"] = match.group(0) if match else raw_date
            
        text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        
        raw_score = 0
        for sk in scoring_keywords:
            term = sk.get("term", "").lower()
            weight = sk.get("weight", 0)
            if term and term in text:
                raw_score += weight
                
        if raw_score > 0:
            scaled_score = min(10, max(1, round((raw_score / score_ceiling) * 10)))
        else:
            scaled_score = 1
            
        job["relevance_score"] = scaled_score
