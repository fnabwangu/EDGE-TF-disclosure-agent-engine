"""
disclosure_crawler.py
Minimal crawler stub that demonstrates fetching disclosures.
"""
import json
import requests

def fetch_daily_disclosures(url: str):
    """Fetch disclosure JSON from a URL. Returns parsed JSON or raises on HTTP error."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    print("Run fetch_daily_disclosures(url) to fetch disclosures")
