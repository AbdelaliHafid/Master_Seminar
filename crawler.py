"""
AI-Powered Crawler
------------------------
Crawls the web based on a search prompt, extracts text and images, 
takes full-page screenshots, and uses a local LLM (Ollama/Mistral) 
to rank, summarize, and classify the findings.
"""

import os
import glob
import re
import hashlib
import sqlite3
import requests
from collections import deque
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Any
from datetime import datetime


from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page
from ddgs import DDGS
from ollama import chat

# --- Configuration & Timestamping ---
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DB_NAME = f"crawler_{TIMESTAMP}.db"
IMAGE_DIR = f"images_{TIMESTAMP}"
SCREENSHOT_DIR = f"screenshots_{TIMESTAMP}"
MAX_QUEUE = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

BAD_DOMAINS = [
    "tiktok.com", "facebook.com", "instagram.com", "twitter.com", 
    "youtube.com", "mp3", "shazam.com", "cloudflare.com", 
    "dash.cloudflare.com", "x.ai", "x.com", "linkedin.com"
]

BAD_IMAGE_KEYWORDS = [
    "icon", "logo", "arrow", "gradient", "sprite",
    "facebook", "instagram", "twitter", "youtube", "banner", "flag", "language"
]

# --- Database Setup ---
def setup_database() -> sqlite3.Connection:
    """Initializes the SQLite database and creates the necessary tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        text TEXT,
        score INTEGER,
        summary TEXT,
        label TEXT
    )
    """)
    conn.commit()
    return conn

def save_page(conn: sqlite3.Connection, page_data: Dict[str, Any]):
    """Saves evaluated page data to the SQLite database."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO pages 
        (url, title, text, score, summary, label)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        page_data.get("url", ""),
        page_data.get("title", ""),
        page_data.get("text", ""),
        page_data.get("score", 0),
        page_data.get("summary", ""),
        page_data.get("label", "")
    ))
    conn.commit()

# --- File System Management ---
def initialize_directories():
    """Creates required directories and clears out old files."""
    for directory in [IMAGE_DIR, SCREENSHOT_DIR]:
        os.makedirs(directory, exist_ok=True)
        # Clear existing files
        for f in glob.glob(f"{directory}/*"):
            try:
                os.remove(f)
            except OSError as e:
                print(f"Error removing file {f}: {e}")

# --- AI & LLM Functions ---
def clean_text(text: str) -> str:
    """Removes null bytes, control characters, and normalizes whitespace."""
    if not text:
        return ""
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def ai_rank(prompt: str, text: str) -> int:
    """Uses the local LLM to score the page relevance from 0 to 10."""
    result = ""
    text = clean_text(text)
    try:
        response = chat(
            model="mistral",
            messages=[
                {
                    "role": "system",
                    "content": "Return ONLY ONE integer between 0 and 10. No words. No explanation. No extra digits."
                },
                {
                    "role": "user",
                    "content": f"Query: {prompt}\nDocument: {text[:1500]}"
                }
            ]
        )
        result = response["message"]["content"].strip()
        score = int(result)
        return max(0, min(10, score))
    except Exception as e:
        print(f"[WARN] AI Rank failed: {e}. Analyzing raw response: {result[:50]}")
        match = re.search(r"\b(10|[0-9])\b", result if 'result' in locals() else "")
        return int(match.group()) if match else 0

def summarize(text: str) -> str:
    """Generates a 5-bullet-point cybersecurity-focused summary."""
    text = clean_text(text)
    response = chat(
        model="mistral",
        messages=[
            {"role": "system", "content": "Summarize in 5 bullet points. Cybersecurity focus."},
            {"role": "user", "content": text[:2000]}
        ]
    )
    return response["message"]["content"]

def classify(text: str) -> str:
    """Classifies the text into JSON format outlining attack types and TTPs."""
    text = clean_text(text)
    response = chat(
        model="mistral",
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON with attack_type, malware_family, ttp."},
            {"role": "user", "content": text[:2000]}
        ]
    )
    return response["message"]["content"]

# --- Crawler Utilities ---
def get_seed_urls(prompt: str, max_results: int) -> List[str]:
    """Fetches initial seed URLs using DuckDuckGo Search."""
    urls = []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(prompt, max_results=max_results)
        for r in results:
            url = r.get("href") or r.get("url") or r.get("link")
            if url:
                urls.append(url)
        return urls
    except Exception as e:
        print("Search failed:", repr(e))
        return []

def safe_goto(page: Page, url: str) -> bool:
    """Safely navigates a Playwright page to a URL with fallbacks."""
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        return True
    except:
        try:
            page.goto(url, timeout=30000, wait_until="load")
            return True
        except:
            return False

def is_valid_page(url: str) -> bool:
    """Filters out bad schemes, domains, and extensions."""
    if not url:
        return False

    bad_schemes = ("mailto:", "javascript:", "tel:")
    if url.startswith(bad_schemes):
        return False

    bad_keywords = [
        "play.google.com", "youtube.com", "gstatic.com", "fonts.gstatic.com",
        "mobileNavBar", "post_page", "referrer=", "/store/", "/apps/",
        "/watch", "login", "signin", "signup", "auth", "authentication",
        "subscribe", "cookie", "consent", "popup", "modal", "notification-banner"
    ]

    if any(k in url for k in bad_keywords):
        return False

    bad_ext = (".jpg", ".png", ".pdf", ".zip", ".mp4", ".mp3")
    path = urlparse(url).path.lower()
    if path.endswith(bad_ext):
        return False

    return True

def is_real_image(url: str) -> bool:
    """Validates if a URL points to an actual image file."""
    path = urlparse(url).path.lower()
    valid_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")
    return path.endswith(valid_ext)

# --- Main Crawler Logic ---
def run_crawler(prompt: str, initial_urls: List[str], db_conn: sqlite3.Connection):
    """Executes the main crawling loop using Requests and Playwright."""
    urls_to_visit = deque(initial_urls)
    visited_urls = set()
    downloaded_images = set()
    crawl_count = 0
    
    # Initialize Playwright ONCE for the whole crawling session
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        while urls_to_visit and crawl_count < MAX_QUEUE:
            current_url = urls_to_visit.popleft() # Fast O(1) removal from queue
            
            if current_url in visited_urls:
                continue

            visited_urls.add(current_url)
            crawl_count += 1
            print(f"\n[CRAWL] {crawl_count}/{MAX_QUEUE} -> {current_url}")

            if not is_valid_page(current_url) or any(domain in current_url for domain in BAD_DOMAINS):
                continue

            # 1. Fetch HTML (Try Requests first, fallback to Playwright)
            html = ""
            try:
                response = requests.get(current_url, headers=HEADERS, timeout=15)
                response.raise_for_status()
                html = response.text
            except Exception:
                print(f"Requests failed, switching to Playwright: {current_url}")
                page = browser.new_page()
                if safe_goto(page, current_url):
                    html = page.content()
                page.close()

            if not html:
                continue

            # 2. Parse HTML
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            if len(text) < 200:
                continue

            title = soup.title.string if soup.title and soup.title.string else "No title"
            
            # 3. AI Evaluation
            score = ai_rank(prompt, text)
            print(f"[AI] Score={score} for {current_url}")

            page_data = {
                "url": current_url,
                "title": title,
                "text": text,
                "score": score,
                "summary": "",
                "label": ""
            }

            if score >= 3:
                print("[AI] Score high enough. Summarizing and classifying...")
                page_data["summary"] = summarize(text)
                page_data["label"] = classify(text)
            
            save_page(db_conn, page_data)

            # 4. Handle Images
            raw_images = [img for img in soup.select("img") if not str(img.get("src")).startswith("data:")]
            image_urls = []
            
            for img in raw_images:
                src = img.get("src") or img.get("data-src") or img.get("data-original")
                if not src or src.startswith("data:"):
                    continue

                abs_img_url = urljoin(current_url, src)
                if any(b in abs_img_url for b in BAD_DOMAINS) or any(k in abs_img_url.lower() for k in BAD_IMAGE_KEYWORDS):
                    continue
                if not is_real_image(abs_img_url):
                    continue

                image_urls.append(abs_img_url)

            for img_url in set(image_urls):
                if img_url in downloaded_images:
                    continue
                
                downloaded_images.add(img_url)
                filename = hashlib.md5(img_url.encode()).hexdigest() + ".jpg"
                filepath = os.path.join(IMAGE_DIR, filename)

                if os.path.exists(filepath):
                    continue

                try:
                    r = requests.get(img_url, headers=HEADERS, timeout=10)
                    if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                        with open(filepath, "wb") as f:
                            f.write(r.content)
                        print(f"[DOWNLOAD] Saved image: {filename}")
                except Exception as e:
                    print(f"Failed to download image {img_url}: {e}")

            # 5. Extract New Links
            for link in soup.select("a[href]"):
                url = link["href"]
                if is_valid_page(url):
                    abs_url = urljoin(current_url, url)
                    if abs_url not in urls_to_visit and abs_url not in visited_urls and len(urls_to_visit) < MAX_QUEUE:
                        urls_to_visit.append(abs_url)

            # 6. Take Screenshot (Reusing the open browser instance)
            print("[CAPTURE] Taking full-page screenshot...")
            screenshot_page = browser.new_page()
            if safe_goto(screenshot_page, current_url):
                filename = hashlib.md5(current_url.encode()).hexdigest() + ".png"
                path = os.path.join(SCREENSHOT_DIR, filename)
                screenshot_page.screenshot(path=path, full_page=True)
            screenshot_page.close()

if __name__ == "__main__":
    print("--- AI Crawler ---")
    initialize_directories()
    db_connection = setup_database()
    
    search_prompt = input("Enter search prompt: ")
    print("Fetching initial URLs...")
    seeds = get_seed_urls(search_prompt, MAX_QUEUE)
    
    if seeds:
        print(f"Found {len(seeds)} seed URLs. Starting crawl...")
        run_crawler(search_prompt, seeds, db_connection)
    else:
        print("No seed URLs found. Exiting.")
        
    db_connection.close()
    print("\nCrawl complete!")