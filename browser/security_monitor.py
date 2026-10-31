"""
Security Monitor module for Coursera Quiz Automation.
Monitors for CAPTCHA challenges, rate limiting (HTTP 429), or access-denied states,
and gracefully pauses automation to allow manual user resolution.
Does not attempt automated bypass or fingerprint spoofing.
"""

import logging
from dataclasses import dataclass
from typing import Any, List, Optional
from selenium.webdriver.common.by import By

logger = logging.getLogger("coursera_automation.browser.security")

CAPTCHA_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='recaptcha']",
    "iframe[src*='arkoselabs']",
    "[data-testid='captcha']",
    ".cf-turnstile",
    "#challenge-stage",
    ".g-recaptcha"
]

ACCESS_DENIED_TEXTS = [
    "429 too many requests",
    "access denied",
    "please verify you are a human",
    "attention required! | cloudflare",
    "security check"
]


@dataclass
class SecurityChallengeStatus:
    has_challenge: bool
    challenge_type: Optional[str] = None
    description: Optional[str] = None


class SecurityMonitor:
    """Monitors live browser sessions for security challenges and pauses safely."""

    @staticmethod
    def inspect_page(driver: Any) -> SecurityChallengeStatus:
        """Inspects the page for visible CAPTCHAs, Cloudflare checks, or rate limits."""
        if not driver:
            return SecurityChallengeStatus(has_challenge=False)

        # 1. Check for CAPTCHA / Challenge elements
        for selector in CAPTCHA_SELECTORS:
            try:
                matches = driver.find_elements(By.CSS_SELECTOR, selector)
                if matches and any(m.is_displayed() for m in matches):
                    return SecurityChallengeStatus(
                        has_challenge=True,
                        challenge_type="CAPTCHA_OR_TURNSTILE",
                        description=f"Detected visible challenge element matching selector: {selector}"
                    )
            except Exception:
                continue

        # 2. Check page title and visible body text for block indicators
        try:
            title = (driver.title or "").lower()
            if any(text in title for text in ACCESS_DENIED_TEXTS):
                return SecurityChallengeStatus(
                    has_challenge=True,
                    challenge_type="ACCESS_DENIED_OR_RATE_LIMIT",
                    description=f"Page title indicates access restriction: '{driver.title}'"
                )

            body_snippet = (driver.page_source[:3000] or "").lower()
            for text in ACCESS_DENIED_TEXTS:
                if text in body_snippet:
                    return SecurityChallengeStatus(
                        has_challenge=True,
                        challenge_type="ACCESS_DENIED_OR_RATE_LIMIT",
                        description=f"Page body contains security restriction notice: '{text}'"
                    )
        except Exception:
            pass

        return SecurityChallengeStatus(has_challenge=False)

    @classmethod
    def handle_if_challenged(cls, driver: Any) -> bool:
        """
        Checks for security challenges and pauses automation if detected.
        Returns True if a challenge was handled/waited on, False if clean.
        """
        status = cls.inspect_page(driver)
        if not status.has_challenge:
            return False

        logger.warning("Security Challenge Detected: %s - %s", status.challenge_type, status.description)
        print("\n" + "!" * 70)
        print("SECURITY MONITOR NOTICE: AUTOMATION PAUSED")
        print("!" * 70)
        print(f"Condition: {status.challenge_type}")
        print(f"Details:   {status.description}")
        print("A verification challenge or rate-limit notice has been detected.")
        print("Per safety policy, automated bypass is forbidden.")
        print("Please complete the challenge manually in the Firefox window if permitted.")
        print("!" * 70)
        input("\n>>> Once resolved in Firefox, press [ENTER] to resume automation... <<< ")
        logger.info("User signaled challenge resolution. Resuming automation...")
        return True
