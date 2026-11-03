"""HTTP client with timeouts, retries and pauses between requests.

Replaces browser.py: Phase 1 showed that all data is present in the initial
HTML, so Playwright is not needed.
"""

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

logger = logging.getLogger(__name__)


class HttpClient:
    """Polite HTTP session: enforces a minimum pause between requests."""

    def __init__(
        self,
        timeout: float = config.REQUEST_TIMEOUT,
        delay: float = config.REQUEST_DELAY,
        max_retries: int = config.MAX_RETRIES,
    ) -> None:
        self.timeout = timeout
        self.delay = delay
        self._last_request = 0.0

        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=2,  # 2s, 4s, 8s...
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def get(self, url: str) -> requests.Response:
        """GET with timeout. Raises requests.RequestException on failure.

        Callers must catch the exception so that one failing ETF does not
        stop the check of the others.
        """
        self._wait()
        logger.debug("GET %s", url)
        try:
            response = self.session.get(url, timeout=self.timeout)
        finally:
            self._last_request = time.monotonic()
        logger.info("GET %s -> HTTP %s (%d bytes)", url, response.status_code, len(response.content))
        response.raise_for_status()
        return response

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
