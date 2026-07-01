"""Run this ONCE to clean the raw catalog JSON: python scripts/fix_catalog.py"""
import json, re, os

src = os.path.join("data", "shl_product_catalog.json")
dst = os.path.join("data", "catalog_clean.json")

raw = open(src, encoding="utf-8").read()
data = json.loads(raw, strict=False)

SOLUTION_RE = re.compile(r"\bSolution\b", re.IGNORECASE)
EXCLUDE = {"universal competency framework job profiling guide"}
filtered = [
    d for d in data
    if d.get("name", "").lower() not in EXCLUDE
    and not SOLUTION_RE.search(d.get("name", ""))
]

json.dump(filtered, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Written {len(filtered)} items to {dst}  (excluded {len(data)-len(filtered)} bundles)")
