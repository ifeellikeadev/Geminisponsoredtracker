import yaml
import re
from typing import Dict, Any, Tuple

def load_cv_profile(path: str = "config/cv_profile.yaml") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def score_job(job: Dict[str, Any], cv_profile: Dict[str, Any]) -> Tuple[int, str]:
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = f"{title} {desc}"

    # Target & Exclude Keywords from CV Profile
    keywords = [k.lower() for k in cv_profile.get("keywords", [])]
    exclude_keywords = [k.lower() for k in cv_profile.get("exclude_keywords", [])]

    # Exclude check
    for ex in exclude_keywords:
        if ex and ex in text:
            return 0, f"Excluded keyword matched: {ex}"

    # If no keywords configured, default pass
    if not keywords:
        return 70, "Default pass (no keyword filter)"

    # Match keywords in title or text
    matched = [k for k in keywords if k in text]
    
    if matched:
        score = min(100, 50 + (len(matched) * 15))
        return score, f"Matched keywords: {', '.join(matched)}"
    
    # Fallback score if title contains standard tech/engineering roles
    generic_tech_terms = ["engineer", "developer", "software", "data", "product", "manager", "lead", "architect", "analyst"]
    if any(term in title for term in generic_tech_terms):
        return 60, "Generic tech title match"

    return 20, "Low keyword relevance"
