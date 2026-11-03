"""Central project configuration.

Values can be overridden with environment variables or a .env file
(see .env.example). No financial values are defined here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Provider website ---
# Base URL of the ETF provider website (required, set in .env)
BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")
LISTING_URL = f"{BASE_URL}/etfs" if BASE_URL else ""

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 etf-checker/0.1",
)

# --- HTTP behavior ---
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))  # seconds per request
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))  # minimum pause between requests
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))  # retries on transient errors

# --- Validation ---
# Maximum age (business days, weekends excluded, no holiday calendar) of the
# NAV, Market Price and holdings dates before they are reported as stale.
MAX_DATA_AGE_BUSINESS_DAYS = int(os.getenv("MAX_DATA_AGE_BUSINESS_DAYS", "3"))

# --- Output ---
REPORTS_DIR = PROJECT_ROOT / os.getenv("REPORTS_DIR", "reports")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
