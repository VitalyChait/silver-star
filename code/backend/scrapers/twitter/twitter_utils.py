import json
import os
import random
import time
from collections import deque
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import RequestException


class TwitterScraper:
    """
    A BeautifulSoup-based scraper that collects tweets matching keywords from
    Nitter (a lightweight Twitter front-end) and supports rotating proxies
    sourced from public lists. This avoids running Selenium while still
    providing fresh tweet content.
    """

    PROXY_SOURCE_URLS = [
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ]
    NITTER_BASE_URL = "https://nitter.net"

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        use_proxies: bool = True,
        proxy_refresh_interval: int = 1800,
    ):
        """
        Args:
            credentials_path: Optional JSON file with "username" and "password".
                              Retained for compatibility; login is not performed.
            use_proxies: Enable the proxy-rotation layer.
            proxy_refresh_interval: Seconds between proxy list refresh attempts.
        """
        self.credentials: Dict[str, str] = {}
        if credentials_path:
            try:
                self.credentials = self._load_credentials(credentials_path)
            except Exception as exc:
                print(f"Warning: Could not load credentials: {exc}")

        self.use_proxies = use_proxies
        self.proxy_refresh_interval = proxy_refresh_interval
        self.max_proxy_attempts = 2

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
        )

        self._proxies: deque[str] = deque()
        self._last_proxy_refresh = 0.0
        if self.use_proxies:
            self._ensure_proxies(force=True)

    # ------------------------------------------------------------------ #
    # Credential and proxy helpers                                       #
    # ------------------------------------------------------------------ #

    def _load_credentials(self, path: str) -> Dict[str, str]:
        """Loads credentials from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "username" not in data or "password" not in data:
            raise ValueError("Credentials JSON must contain 'username' and 'password'.")
        return data

    def _ensure_proxies(self, force: bool = False) -> None:
        """Refreshes the proxy list when needed."""
        if not self.use_proxies:
            return

        now = time.time()
        should_refresh = (
            force
            or not self._proxies
            or (now - self._last_proxy_refresh) > self.proxy_refresh_interval
        )
        if not should_refresh:
            return

        proxies = self._fetch_proxies()
        if proxies:
            random.shuffle(proxies)
            # Keep the list manageable to avoid unbounded growth.
            self._proxies = deque(proxies[:200])
            self._last_proxy_refresh = now
            print(f"Loaded {len(self._proxies)} proxies.")
        else:
            print("Warning: No proxies were loaded; proceeding without proxy rotation.")
            self._proxies.clear()

    def _fetch_proxies(self) -> List[str]:
        """Pulls a fresh list of proxies from public text endpoints."""
        print("Refreshing proxy list from public sources...")
        collected: List[str] = []
        headers = {"User-Agent": self.session.headers.get("User-Agent", "")}

        for source in self.PROXY_SOURCE_URLS:
            try:
                response = requests.get(source, timeout=10, headers=headers)
                response.raise_for_status()
            except RequestException as exc:
                print(f"Proxy source failed ({source}): {exc}")
                continue

            for line in response.text.splitlines():
                candidate = line.strip()
                if not candidate or ":" not in candidate:
                    continue
                collected.append(candidate)

            if collected:
                break  # Use the first successful source to keep results consistent.

        return collected

    def _get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Returns the next proxy configuration or None."""
        if not self.use_proxies:
            return None

        self._ensure_proxies()
        if not self._proxies:
            return None

        proxy = self._proxies[0]
        self._proxies.rotate(-1)
        proxy_uri = f"http://{proxy}"
        return {
            "http": proxy_uri,
            "https": proxy_uri,
        }

    # ------------------------------------------------------------------ #
    # HTTP helpers                                                       #
    # ------------------------------------------------------------------ #

    def _request(
        self,
        method: str,
        url: str,
        *,
        retries: Optional[int] = None,
        **kwargs,
    ) -> Response:
        """Performs an HTTP request with optional proxy rotation."""
        attempts = retries or self.max_proxy_attempts
        last_exception: Optional[Exception] = None

        proxy_attempts = attempts if self.use_proxies else 0
        total_attempts = proxy_attempts + (1 if self.use_proxies else attempts)

        for attempt in range(1, total_attempts + 1):
            request_kwargs = dict(kwargs)

            using_proxy = self.use_proxies and attempt <= proxy_attempts
            proxy = self._get_next_proxy() if using_proxy else None
            using_proxy = using_proxy and proxy is not None
            if using_proxy:
                request_kwargs["proxies"] = proxy
            else:
                request_kwargs.pop("proxies", None)

            request_kwargs.setdefault("timeout", 8 if using_proxy else 20)

            try:
                response = self.session.request(method, url, **request_kwargs)
                if response.status_code in (403, 429) and using_proxy:
                    print(
                        f"Proxy {proxy['http']} blocked with status {response.status_code}; rotating..."
                    )
                    time.sleep(1)
                    continue

                response.raise_for_status()
                return response

            except RequestException as exc:
                last_exception = exc
                if using_proxy and proxy:
                    print(f"Attempt {attempt}/{total_attempts} failed for {url}: {exc}")
                    if attempt < proxy_attempts:
                        self._ensure_proxies(force=True)
                        time.sleep(min(2 ** attempt, 10))
                    continue

                print(f"Direct request failed for {url}: {exc}")
                break  # No point retrying direct requests endlessly.

        if last_exception:
            raise RuntimeError(f"Failed to fetch {url}") from last_exception
        raise RuntimeError(f"Failed to fetch {url} due to unknown error.")

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def login(self) -> None:
        """
        Placeholder login to keep the public API compatible with the previous
        Selenium-based version. Direct login against X.com is not supported via
        static HTTP scraping due to heavy anti-bot protections.
        """
        raise RuntimeError(
            "Programmatic login is not supported without Selenium or official APIs. "
            "Provide session cookies manually if authenticated requests are required."
        )

    def query_grok(self, query_text: str) -> str:
        """
        Placeholder for Grok access.

        Grok's UI relies heavily on authenticated WebSocket traffic, which is
        not currently accessible via static HTML scraping.
        """
        raise RuntimeError(
            "Grok cannot be queried through static HTTP scraping. "
            "Consider using the official API or Selenium-based automation."
        )

    def scrape_home_feed(self, keywords: Iterable[str], scroll_limit: int = 1) -> List[str]:
        """
        Collects tweets containing any of the supplied keywords by leveraging
        Nitter's public search endpoint. The scroll_limit parameter controls the
        number of result pages fetched per keyword (first page by default).
        """
        keywords = list(keywords)
        if not keywords:
            return []

        print(f"Fetching tweets for keywords via Nitter: {keywords}")
        aggregated: List[str] = []
        seen = set()

        for keyword in keywords:
            relative_url = f"/search?f=tweets&q={quote_plus(keyword)}"
            pages_to_fetch = max(1, scroll_limit)

            for page in range(pages_to_fetch):
                url = f"{self.NITTER_BASE_URL}{relative_url}"
                response = self._request("GET", url)
                page_matches, next_relative = self._extract_matches_from_nitter(
                    response.text, keyword, seen
                )

                if page_matches:
                    aggregated.extend(page_matches)
                else:
                    print(f"No tweets found for keyword '{keyword}' on page {page + 1}.")

                if not next_relative:
                    break

                relative_url = next_relative

        return aggregated

    def close(self) -> None:
        """Closes underlying network resources."""
        print("Closing HTTP session.")
        self.session.close()

    # ------------------------------------------------------------------ #
    # Parsing helpers                                                    #
    # ------------------------------------------------------------------ #

    def _extract_matches_from_nitter(
        self,
        html: str,
        keyword: str,
        seen: set,
    ) -> Tuple[List[str], Optional[str]]:
        """
        Parses a Nitter search page, returning matching tweets and the next page
        relative URL if available.
        """
        soup = BeautifulSoup(html, "html.parser")
        timeline_items = soup.select("div.timeline-item")

        keyword_lower = keyword.lower()
        matches: List[str] = []

        for item in timeline_items:
            content = item.select_one("div.tweet-content")
            if not content:
                continue

            text = content.get_text(" ", strip=True)
            normalized = " ".join(text.split())
            if not normalized or normalized in seen:
                continue

            if keyword_lower in normalized.lower():
                matches.append(normalized)
                seen.add(normalized)

        next_relative = self._extract_next_relative(soup)
        return matches, next_relative

    @staticmethod
    def _extract_next_relative(soup: BeautifulSoup) -> Optional[str]:
        """Finds the relative URL for the next page of Nitter results, if any."""
        show_more = soup.find("div", class_="show-more")
        if not show_more:
            return None

        link = show_more.find("a", href=True)
        if not link:
            return None

        href = link["href"]
        if not href.startswith("/"):
            return None

        return href


if __name__ == "__main__":
    # --- EXAMPLE USAGE ---
    # 1. Ensure the required libraries are installed:
    #    pip install requests beautifulsoup4
    # 2. Optionally create a credentials.json file to mirror the old interface:
    #    {
    #        "username": "your_x_username",
    #        "password": "your_x_password"
    #    }

    CREDENTIALS_FILE_PATH = "credentials.json"
    credentials_argument: Optional[str] = None
    if os.path.exists(CREDENTIALS_FILE_PATH):
        credentials_argument = CREDENTIALS_FILE_PATH
    else:
        print("credentials.json not found; continuing without credentials.")

    scraper: Optional[TwitterScraper] = None

    try:
        scraper = TwitterScraper(credentials_argument)

        keywords_to_search = ["python", "AI", "data science", "FastAPI"]
        tweets = scraper.scrape_home_feed(keywords_to_search, scroll_limit=2)
        print("\n--- Keyword Search Results ---")
        if tweets:
            for idx, tweet in enumerate(tweets, start=1):
                print(f"{idx}. {tweet}\n")
        else:
            print("No tweets matched the supplied keywords.")

    except Exception as err:
        print(f"An unexpected error occurred: {err}")
    finally:
        if scraper:
            scraper.close()
