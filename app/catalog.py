"""
Loads data/catalog_clean.json (369 Individual Test Solutions from SHL catalog).

Real catalog schema fields we use:
  entity_id, name, link, description, keys (list of category names),
  duration, remote, adaptive, job_levels, languages

keys examples: ["Knowledge & Skills"], ["Personality & Behavior", "Competencies"]
We map these to letter codes: A B C D E K P S
"""
import json, os, re
from functools import lru_cache
from typing import List, Optional, Dict, Any

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "catalog_clean.json")

CATEGORY_TO_CODE = {
    "Ability & Aptitude": "A",
    "Biodata & Situational Judgment": "B",
    "Biodata & Situational Judgement": "B",
    "Competencies": "C",
    "Development & 360": "D",
    "Assessment Exercises": "E",
    "Knowledge & Skills": "K",
    "Personality & Behavior": "P",
    "Personality & Behaviour": "P",
    "Simulations": "S",
}


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    categories = raw.get("keys") or []
    codes = sorted({CATEGORY_TO_CODE.get(c, "") for c in categories} - {""})
    return {
        "id": raw.get("entity_id"),
        "name": (raw.get("name") or "").strip(),
        "url": raw.get("link") or "",
        "test_type": ",".join(codes),
        "test_type_names": categories,
        "description": raw.get("description") or "",
        "duration": raw.get("duration") or "",
        "remote": raw.get("remote") == "yes",
        "adaptive": raw.get("adaptive") == "yes",
        "job_levels": raw.get("job_levels") or [],
        "languages": raw.get("languages") or [],
    }


@lru_cache(maxsize=1)
def load_catalog(path: Optional[str] = None) -> List[Dict[str, Any]]:
    p = path or DATA_PATH
    with open(p, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [_normalize(r) for r in raw_items]


if __name__ == "__main__":
    items = load_catalog()
    print(f"Loaded {len(items)} items")
    for it in items[:6]:
        print(f"  {it['name'][:50]:50s} | {it['test_type']:6s} | {it['duration']}")
