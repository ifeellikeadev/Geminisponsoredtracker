import yaml
import re
from typing import Dict, Any, Tuple, Union

def load_cv_profile(path: str = "config/cv_profile.yaml") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def extract_location_snippet(job_or_text: Any, max_len: int = 100) -> str:
    if isinstance(job_or_text, dict):
        loc = job_or_text.get("location") or job_or_text.get("city") or ""
    else:
        loc = str(job_or_text or "")
    return loc[:max_len]

def resolve_city_for_job(job: Dict[str, Any], default_city: str = "") -> str:
    loc = (job.get("location") or "").lower()
    if any(c in loc for c in ["munich", "münchen"]):
        return "Munich"
    if any(c in loc for c in ["zurich", "zürich", "switzerland", "schweiz"]):
        return "Zurich"
    return default_city if default_city else (job.get("location") or "Other")

def filter_by_title_only(job_or_title: Union[Dict[str, Any], str], cv_profile: Dict[str, Any] = None) -> Tuple[bool, str]:
    if isinstance(job_or_title, dict):
        title = job_or_title.get("title", "")
    else:
        title = str(job_or_title or "")

    if not cv_profile:
        return True, "No CV profile provided"

    title_lower = title.lower()
    exclude_keywords = [k.lower() for k in cv_profile.get("exclude_keywords", []) if k]
    for ex in exclude_keywords:
        if ex in title_lower:
            return False, f"Excluded keyword matched: {ex}"

    keywords = [k.lower() for k in cv_profile.get("keywords", []) if k]
    if not keywords:
        return True, "No target keywords specified"

    matched = [k for k in keywords if k in title_lower]
    if matched:
        return True, f"Title matched keywords: {', '.join(matched)}"

    generic_tech = [
        "engineer", "developer", "software", "data", "product", "manager", 
        "lead", "architect", "analyst", "specialist", "consultant", "intern", 
        "working student", "werkstudent"
    ]
    if any(term in title_lower for term in generic_tech):
        return True, "Generic tech title match"

    return True, "Default pass"

def score_job(job: Dict[str, Any], cv_profile: Dict[str, Any]) -> Tuple[int, str]:
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = f"{title} {desc}"

    if not cv_profile:
        return 75, "No CV profile provided"

    keywords = [k.lower() for k in cv_profile.get("keywords", []) if k]
    exclude_keywords = [k.lower() for k in cv_profile.get("exclude_keywords", []) if k]

    for ex in exclude_keywords:
        if ex in text:
            return 0, f"Excluded keyword matched: {ex}"

    matched = [k for k in keywords if k in text]
    if matched:
        score = min(100, 60 + (len(matched) * 10))
        return score, f"Matched keywords: {', '.join(matched)}"

    generic_tech = ["engineer", "developer", "software", "data", "product", "manager", "lead", "architect", "analyst"]
    if any(term in title for term in generic_tech):
        return 70, "Generic tech title match"

    return 50, "General listing pass"

def match_job(job: Dict[str, Any], cv_profile: Dict[str, Any]) -> Tuple[int, str]:
    return score_job(job, cv_profile)

def calculate_match_score(job: Dict[str, Any], cv_profile: Dict[str, Any]) -> Tuple[int, str]:
    return score_job(job, cv_profile)
