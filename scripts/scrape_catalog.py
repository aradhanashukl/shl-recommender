"""
Fallback: scrape https://www.shl.com/solutions/products/product-catalog/
directly if data/catalog.json (from the provided JSON link) is missing,
malformed, or doesn't contain Individual Test Solutions cleanly.

Run locally (NOT in a network-restricted sandbox):
    python scripts/scrape_catalog.py

It paginates through the "Individual Test Solutions" type=1 catalog pages,
visits each product detail page, and pulls name/url/test_type/description/
remote_testing/adaptive_irt. Writes data/catalog.json in the schema
app/catalog.py expects.
"""
import json
import time
import sys
import os

import requests
from bs4 import BeautifulSoup

BASE = "https://www.shl.com"
CATALOG_URL = BASE + "/solutions/products/product-catalog/"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "catalog.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SHL-Assignment-Scraper/1.0)"}


def get_soup(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def list_individual_test_solutions():
    """Paginate the catalog filtered to Individual Test Solutions (type=1 on SHL's site)."""
    items = []
    start = 0
    page_size = 12
    while True:
        params = {"start": start, "type": 1}
        soup = get_soup(CATALOG_URL, params=params)
        rows = soup.select("table tr") or soup.select(".product-catalogue__row")
        links = soup.select("a[href*='/product-catalog/view/']")
        if not links:
            break
        found_new = False
        for a in links:
            href = a.get("href")
            name = a.get_text(strip=True)
            if not href or not name:
                continue
            full_url = href if href.startswith("http") else BASE + href
            if not any(it["url"] == full_url for it in items):
                items.append({"name": name, "url": full_url})
                found_new = True
        if not found_new:
            break
        start += page_size
        time.sleep(0.5)
        if start > 2000:  # safety cap
            break
    return items


def enrich(item):
    try:
        soup = get_soup(item["url"])
        desc_el = soup.select_one(".product-catalogue-training-calendar__desc, .description, p")
        item["description"] = desc_el.get_text(strip=True) if desc_el else ""
        text = soup.get_text(" ", strip=True)
        item["remote_testing"] = "Remote Testing" in text
        item["adaptive_irt"] = "Adaptive" in text or "IRT" in text
        # test type letters often shown as badges like "K", "P", "A", "B", "S", "C", "D", "E"
        badges = [b.get_text(strip=True) for b in soup.select(".product-catalogue__key, .test-type")]
        item["test_type"] = ",".join(sorted(set(b for b in badges if len(b) <= 2))) or "Unknown"
    except Exception as e:
        print(f"  ! failed to enrich {item['url']}: {e}", file=sys.stderr)
        item.setdefault("description", "")
        item.setdefault("test_type", "Unknown")
    return item


def main():
    print("Listing Individual Test Solutions...")
    items = list_individual_test_solutions()
    print(f"Found {len(items)} candidate items. Enriching each (this hits each page)...")
    enriched = []
    for i, it in enumerate(items):
        print(f"  [{i+1}/{len(items)}] {it['name']}")
        enriched.append(enrich(it))
        time.sleep(0.3)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"individual_test_solutions": enriched}, f, indent=2)
    print(f"Wrote {len(enriched)} items to {OUT_PATH}")


if __name__ == "__main__":
    main()
