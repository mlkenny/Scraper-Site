#!/usr/bin/env python3
"""
Dynamic, parallel quote scraper.

Features:
- Discovers URLs with Google (via SerpAPI)
- Scrapes top-N results in parallel
- Static HTML first (requests+BS4), optional Selenium fallback for JS pages
- Simple site-specific handlers where helpful; generic extractor otherwise
- Outputs CSV: source_url, quote

"""

from pathlib import Path
import re
import csv
import time
import html
import argparse
import threading
from urllib.parse import urlparse

from django.conf import settings

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------
# Config
# ---------------------------

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; UniversalQuoteScraper/1.0; +https://example.com/bot)"
DEFAULT_TIMEOUT = 20
DEFAULT_WORKERS = 8
DEFAULT_MAX_URLS = 30
SERPAPI_KEY = settings.SERPAPI_KEY

# Domains that frequently require JS rendering
LIKELY_JS_DOMAINS = {
    "ranker.com", "buzzfeed.com", "thethings.com", "screenrant.com", "cbr.com"
}

# ---------------------------
# Utilities
# ---------------------------

def fetch(url, timeout=DEFAULT_TIMEOUT, headers=None):
    """GET with sensible defaults."""
    h = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h, timeout=timeout)
    resp.raise_for_status()
    return resp

def fetch_soup(url, **kwargs):
    """Return BeautifulSoup of the URL (static)."""
    resp = fetch(url, **kwargs)
    return BeautifulSoup(resp.text, "html.parser")

def is_probably_js(url, html_text=None):
    """Heuristic: JS-rendered if domain is known or HTML is script-heavy/short."""
    host = urlparse(url).netloc.lower()
    if any(host.endswith(d) for d in LIKELY_JS_DOMAINS):
        return True
    if html_text is None:
        try:
            html_text = fetch(url).text
        except Exception:
            return True
    return (html_text.count("<script") > 10 and len(html_text) < 80000)

# ---------------------------
# Selenium (dynamic)
# ---------------------------

_browser_lock = threading.Lock()  # to avoid spinning up too many browsers at once

def fetch_dynamic_html(url, scroll_selector=None, max_wait_loops=3, pause=1.0):
    """
    Faster text-only dynamic fetch with Selenium.
    Keeps error output visible but disables heavy resources.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import time

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1600,900")
    # 🚀 speed tweaks
    opts.add_argument("--disable-gpu")
    opts.add_argument("--blink-settings=imagesEnabled=false")   # no images
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-notifications")
    # block unnecessary content types
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.plugins": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.notifications": 2,
    }
    opts.add_experimental_option("prefs", prefs)

    with _browser_lock:
        driver = webdriver.Chrome(options=opts)

    try:
        start = time.time()
        driver.get(url)

        selector = scroll_selector or "blockquote, q, p"
        last_count, same = 0, 0
        while True:
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            if elems:
                driver.execute_script("arguments[0].scrollIntoView({block:'end'});", elems[-1])
            else:
                driver.execute_script("window.scrollBy(0, 1000);")

            time.sleep(pause)
            new_count = len(driver.find_elements(By.CSS_SELECTOR, selector))
            same = same + 1 if new_count == last_count else 0
            last_count = new_count
            if same >= max_wait_loops or (time.time() - start) > 15:
                break

        html_source = driver.page_source
        return html_source
    finally:
        driver.quit()

# ---------------------------
# SerpAPI Search
# ---------------------------

def google_search_serpapi(query, max_results=DEFAULT_MAX_URLS, country="us", lang="en"):
    """
    Return a list of organic result URLs using SerpAPI.
    Set env SERPAPI_KEY.
    """
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY environment variable not set. Get one at https://serpapi.com")

    params = {
        "engine": "google",
        "q": query,
        "num": max_results,
        "hl": lang,
        "gl": country,
        "api_key": SERPAPI_KEY
    }
    resp = requests.get("https://serpapi.com/search", params=params, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    urls = []
    for item in data.get("organic_results", []):
        url = item.get("link")
        if url and url.startswith("http"):
            urls.append(url)
    return urls[:max_results]

def build_query(character):
    # Bias toward quote pages; include exact or typographic quotes
    base = f'{character} quotes'
    extras = ['"best quotes"', '"quotes"', 'site:ranker.com OR site:cbr.com OR site:epicquotes.com OR site:sportskeeda.com OR site:scatteredquotes.com OR site:animemotivation.com OR site:goodreads.com']
    return f"{base} " + " ".join(extras)

# ---------------------------
# Extraction helpers
# ---------------------------

def clean_text(t):
    t = html.unescape(t).strip()
    t = t.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", t)

QUOTE_LIKE = re.compile(r"[\"“”'«»‘’].{6,}")

def generic_extract(html_text, base_url, character=None):
    """
    Generic quote extraction from blockquote, q, p, li.
    Stricter heuristics to keep only real character quotes and ignore site junk.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    candidates = soup.select("blockquote, q, li, p")
    out = []

    # Lowercase character name for matching
    char_name = character.lower() if character else None

    for c in candidates:
        txt = clean_text(c.get_text(" ", strip=True))
        if len(txt) < 12:
            continue

        # skip obvious junk text
        junk_words = ["vote", "photo", "ranker", "comment", "episode", "great quote", "quotes list"]
        if any(j in txt.lower() for j in junk_words):
            continue

        # must look quote-ish (starts with a quote mark or contains the character’s name)
        looks_like_quote = QUOTE_LIKE.search(txt)
        mentions_character = char_name and char_name in txt.lower()

        if looks_like_quote or mentions_character:
            # limit excessively long blocks of text
            if len(txt) > 350:
                continue
            out.append((base_url, txt))

    return out

# --- Site-specific (improve precision where possible) ---

def extract_ranker(soup, base_url):
    quotes = []
    for div in soup.select("div.richText_container__Kvtj0"):
        p = div.find("p")
        if not p:
            continue
        txt = clean_text(p.get_text(" ", strip=True))
        if txt and (txt.startswith('"') or txt.startswith("“") or txt.startswith("'")):
            quotes.append((base_url, txt))
    return quotes

def extract_scatteredquotes(soup, base_url):
    return [(base_url, clean_text(bq.get_text(" ", strip=True)))
            for bq in soup.select("blockquote.quote") if clean_text(bq.get_text(" ", strip=True))]

def extract_epicquotes(soup, base_url):
    out = []
    for p in soup.select("div.entry-content p"):
        txt = clean_text(p.get_text(" ", strip=True))
        if len(txt.split()) > 4:
            out.append((base_url, txt))
    return out

def site_specific_extract(html_text, url):
    """Try site-known patterns first; else None."""
    host = urlparse(url).netloc.lower()
    soup = BeautifulSoup(html_text, "html.parser")
    if "ranker.com" in host:
        q = extract_ranker(soup, url)
        if q:
            return q
    if "scatteredquotes.com" in host:
        q = extract_scatteredquotes(soup, url)
        if q:
            return q
    if "epicquotes.com" in host:
        q = extract_epicquotes(soup, url)
        if q:
            return q
    # add other per-site extractors here as needed
    return None

# ---------------------------
# Scrape single URL
# ---------------------------

def scrape_url(url, character=None, use_browser_fallback=False):
    """
    Scrape quotes from a single URL.
    Strategy:
      1) Fetch static HTML
      2) Try site-specific extractors
      3) Generic extractor
      4) If nothing & allowed, dynamic (Selenium) fallback then retry
    """
    results = []
    try:
        resp = fetch(url)
        html_text = resp.text
        specific = site_specific_extract(html_text, url)
        if specific:
            results.extend(specific)
        else:
            generic = generic_extract(html_text, url, character=character)
            results.extend(generic)

        # If we got good results, return
        if results:
            return results

        # If empty and looks JS-y, optionally do dynamic
        if use_browser_fallback or is_probably_js(url, html_text):
            try:
                dyn_html = fetch_dynamic_html(
                    url,
                    scroll_selector="div.richText_container__Kvtj0, blockquote, q, p"
                )
                specific = site_specific_extract(dyn_html, url)
                if specific:
                    return specific
                return generic_extract(dyn_html, url, character=character)
            except Exception as e:
                print(f"[dynamic fallback failed] {url}: {e}")
                return results
        return results
    except Exception as e:
        print(f"[scrape error] {url}: {e}")
        return results

# ---------------------------
# Search → Scrape (Parallel)
# ---------------------------

def discover_urls(character, max_urls=DEFAULT_MAX_URLS):
    query = build_query(character)
    urls = google_search_serpapi(query, max_results=max_urls)
    # light filtering: avoid PDFs / login / obvious non-content
    filtered = []
    seen = set()
    for u in urls:
        if any(u.lower().endswith(ext) for ext in (".pdf", ".ppt", ".doc", ".zip")):
            continue
        if "login" in u.lower() or "signup" in u.lower():
            continue
        if u in seen:
            continue
        seen.add(u)
        filtered.append(u)
    return filtered[:max_urls]

def scrape_many(urls, character=None, max_workers=DEFAULT_WORKERS, use_browser_fallback=False):
    all_quotes = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scrape_url, u, character, use_browser_fallback): u for u in urls}
        for fut in as_completed(futures):
            u = futures[fut]
            try:
                results = fut.result()
                all_quotes.extend(results)
            except Exception as e:
                print(f"✖ error {u}: {e}")
    return all_quotes

# ---------------------------
# Main
# ---------------------------

def dedupe(quotes):
    """quotes: list[(url, quote_text)]"""
    seen = set()
    out = []
    for src, q in quotes:
        cq = clean_text(q)
        # drop super-short / noisy lines
        if len(cq) < 10:
            continue
        if cq not in seen:
            seen.add(cq)
            out.append((src, cq))
    return out

def save_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_url", "quote"])
        for r in rows:
            w.writerow(r)

# ---------------------------
# OpenAI Moderation Checks on jsonl
# ---------------------------

from openai import OpenAI
client = OpenAI(api_key=settings.OPENAI_KEY)
def normalize_quote(text: str) -> str:
    """Strip HTML, normalize spacing, and remove common junk."""
    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)        # remove HTML tags
    text = re.sub(r"\s+", " ", text).strip() # normalize whitespace
    text = re.sub(r"\b\d+\s+votes?\b", "", text, flags=re.I)
    text = re.sub(r"Photo:.*", "", text, flags=re.I)
    text = re.sub(r"Great quote\??", "", text, flags=re.I)
    return text.strip()

def is_safe_quote(text: str) -> bool:
    """Return True if the quote passes moderation."""
    try:
        result = client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        return not result.results[0].flagged
    except Exception as e:
        print(f"⚠️ Moderation check failed: {e}")
        return False
    

def clean_dataset(csv_path, character_name):
    """
    Clean a scraped CSV by removing unsafe, duplicate, or junk quotes.
    Overwrites the original CSV file with a cleaned version.
    """
    csv_path = Path(csv_path)
    temp_path = csv_path.with_name(f"{csv_path.stem}_temp.csv")

    seen = set()
    kept = removed = 0

    with open(csv_path, encoding="utf-8", errors="ignore") as infile, \
         open(temp_path, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=["source_url", "quote"])
        writer.writeheader()

        for row in reader:
            quote = normalize_quote(row.get("quote", ""))
            if not quote or len(quote) < 10 or quote.lower() in seen:
                continue

            seen.add(quote.lower())

            if is_safe_quote(quote):
                writer.writerow({
                    "source_url": row.get("source_url", ""),
                    "quote": quote
                })
                kept += 1
            else:
                removed += 1

    new_path = temp_path.replace(csv_path)
    print(f"✅ Cleaned dataset for {character_name}: {csv_path}")
    print(f"Kept: {kept} | Removed: {removed}")
    return new_path