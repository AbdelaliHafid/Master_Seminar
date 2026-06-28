# AI-Powered Crawler

An intelligent web crawler built in Python that searches the web, extracts data, and uses a local Large Language Model (LLM) to evaluate, summarize, and classify the findings.

## Features
* **Hybrid Scraping:** Attempts fast HTTP requests first, automatically falling back to full DOM rendering via Playwright if anti-bot protections or JavaScript walls are detected.
* **On-the-fly AI Analysis:** Uses a locally hosted `Mistral` model (via Ollama) to read webpage content and score its relevance to your search prompt (0-10).
* **Automated OSINT Summaries:** If a page ranks highly, the LLM automatically generates a 5-bullet-point cybersecurity-focused summary and a JSON classification of potential threats.
* **Media Extraction:** Intelligently filters out SEO spam, trackers, and UI icons, downloading only relevant images to a local directory.
* **Evidence Capture:** Takes a full-page, headless Chromium screenshot of every visited page for record-keeping.
* **SQLite Storage:** Saves all textual data, URLs, LLM scores, and summaries cleanly into a local timestamped SQLite database.

## Prerequisites & Installation

Before running the crawler, ensure you have **Python 3.8+** installed on your system. Setup requires three quick steps to configure the Python environment, the headless browser, and the local AI engine.

### 1. Install Python Dependencies
Create a `requirements.txt` file in your project directory (if you haven't already), then install the required packages:
```bash
pip install -r requirements.txt