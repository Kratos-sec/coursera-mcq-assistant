"""
Configuration module for Coursera Quiz Automation.
Centralizes paths, timeouts, browser profile settings, selectors, and reporting targets.
"""

from pathlib import Path
import os
import sys

# Base project paths
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Logging configuration
LOG_FILE = LOG_DIR / "coursera_automation.log"
LOG_LEVEL = "INFO"

# Reconnaissance & Diagnostic output artifacts
DOM_SNAPSHOT_PATH = LOG_DIR / "quiz_dom_snapshot.html"
RECON_DATA_PATH = LOG_DIR / "recon_data.json"
REPORT_PATH = LOG_DIR / "dom_inspection_report.md"
DIAGNOSTIC_DOM_PATH = LOG_DIR / "diagnostic_stability_dom.html"

# Browser Configuration
# Check common Windows Firefox installation paths
DEFAULT_FIREFOX_PATHS = [
    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Mozilla Firefox" / "firefox.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Mozilla Firefox" / "firefox.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla Firefox" / "firefox.exe"
]

FIREFOX_BINARY: str | None = None
for p in DEFAULT_FIREFOX_PATHS:
    if p.exists():
        FIREFOX_BINARY = str(p)
        break

# Profile directory (set USE_PERSISTENT_PROFILE = True to retain cookies/session)
USE_PERSISTENT_PROFILE = True
PROFILE_DIR = BASE_DIR / "firefox_profile"

# Explicit Wait Timeouts (seconds)
EXPLICIT_WAIT_TIMEOUT = 25.0
POLL_FREQUENCY = 0.5
PAGE_LOAD_TIMEOUT = 45.0

# Dynamic Quiz Discovery & Boundary Selectors (Ground Truth)
QUIZ_ROOT = '[data-testid="tunnel-vision-content"]'
QUESTION_SELECTOR = 'div[data-testid="part-Submission_MultipleChoiceQuestion"]'
SUBMISSION_BOUNDARY = '[data-e2e="AttemptSubmitControls"]'
SUBMIT_BUTTON_SELECTOR = 'button[data-testid="submit-button"]'
AGREEMENT_CHECKBOX_SELECTOR = '#agreement-checkbox-base'

# DOM Stability Detection
DOM_STABILITY_TIME = 0.85        # Window in seconds signature must remain unchanged
DOM_STABILITY_TIMEOUT = 15.0     # Max wait for DOM stability before aborting
