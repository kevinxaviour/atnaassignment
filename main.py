import requests
import time
import json
import logging
import os
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# Configuration Set Up
quotes_url = "https://quotes.toscrape.com"
github_api = "https://api.github.com/search/repositories"
output_file = "output.json"
user_agent = "kevin-atna/1.0" # this is to identify the script

# Logging Set Up
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("atna.log")

# Retry Helper
def get_with_retry(url, headers=None, params=None, retries=3):
    wait = 1
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            if r.status_code >= 500:
                raise Exception(f"Server error {r.status_code}")
            return r
        except Exception as e:
            logger.warning(f"Retry {i+1}/{retries} failed: {e}")
            if i == retries - 1:
                raise
            time.sleep(wait)
            wait *= 2


# Web Scraping for quotes page

def scrape_quotes():
    quotes = []
    url = quotes_url
    headers = {"User-Agent": user_agent}
    while url: #Starting a loop that runs as long as there is a valid page URL.
        r = get_with_retry(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser") # fetching the html content of the page.
        for q in soup.select(".quote"): # Scraping the quote text, author, and author URL.
            quotes.append({
                "text": q.select_one(".text").get_text(strip=True),
                "author": q.select_one(".author").get_text(strip=True),
                "author_url": quotes_url + q.select_one("a")["href"]
            })
        next_btn = soup.select_one("li.next > a") # selecting the next button.
        url = quotes_url + next_btn["href"] if next_btn else None
    return quotes 


# Fetching Github Data
def fetch_github_repos():
    logger.info("Fetching GitHub repo")
    repos = []

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/vnd.github.v3+json" #requesting for a json response
    }

    params = {
        "q": "language:python", # searches for python repositories
        "sort": "stars",
        "order": "desc",
        "per_page": 30,   # setting up safe limit to avoid rate limiting
        "page": 1
    }

    try:
        resp = get_with_retry(github_api, headers=headers, params=params)
        data = resp.json()
    except Exception:
        logger.error("GitHub API request failed")
        return repos

    items = data.get("items", [])
    if not items:
        logger.warning("No GitHub repositories returned (rate limit)")
        return repos

    for repo in items:
        repos.append({
            "name": repo.get("name"),
            "owner": repo.get("owner", {}).get("login"),
            "stars": repo.get("stargazers_count", 0),
            "url": repo.get("html_url")
        })

    return repos


# Execution code
def main():
    start_time = time.time()
    failures = 0

    try:
        quotes = scrape_quotes()
    except Exception:
        logger.exception("Quotes scraping failed")
        quotes = []
        failures += 1

    try:
        repos = fetch_github_repos()
    except Exception:
        logger.exception("GitHub fetch failed")
        repos = []
        failures += 1

    output = {
        "quotes": quotes,
        "github_repos": repos,
        "meta": {
            "run_time": datetime.now(timezone.utc).isoformat(),
            "total_quotes": len(quotes),
            "total_repos": len(repos),
            "failures": failures
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - start_time
    logger.info(
        f"Completed in {elapsed:.2f}s | "
        f"Quotes: {len(quotes)} | "
        f"Repos: {len(repos)} | "
        f"Failures: {failures}"
    )

if __name__ == "__main__":
    main()
