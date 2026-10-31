"""
DOM Stability Detection Module for Coursera Quiz Automation.
Ensures the quiz DOM is fully loaded and structurally stable before extraction begins.
"""

import logging
import time
from typing import Any, List, Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait

import config

logger = logging.getLogger("coursera_automation.extraction.stability")


class DOMStabilityTimeoutException(Exception):
    """Raised when the quiz DOM fails to achieve structural stability within the timeout."""
    pass


class QuizDOMStabilityCondition:
    """
    Explicit wait condition for Selenium WebDriverWait.
    Verifies that:
    1. QUIZ_ROOT and SUBMISSION_BOUNDARY are present.
    2. All discovered question containers are structurally complete.
    3. The structural signature remains unchanged for >= stability_duration seconds.
    """

    def __init__(self, stability_duration: float = config.DOM_STABILITY_TIME):
        self.stability_duration = stability_duration
        self.last_signature: Optional[Tuple[Any, ...]] = None
        self.last_change_time: float = 0.0
        self.last_diagnostics: dict = {
            "question_count": 0,
            "incomplete_questions": [],
            "boundary_found": False
        }

    def __call__(self, driver) -> bool:
        try:
            # 1. Check for submission boundary
            boundaries = driver.find_elements(By.CSS_SELECTOR, config.SUBMISSION_BOUNDARY)
            self.last_diagnostics["boundary_found"] = len(boundaries) > 0
            if not self.last_diagnostics["boundary_found"]:
                self._record_change(None)
                return False

            # 2. Enumerate question containers
            containers = driver.find_elements(By.CSS_SELECTOR, config.QUESTION_SELECTOR)
            self.last_diagnostics["question_count"] = len(containers)
            self.last_diagnostics["incomplete_questions"] = []

            if not containers:
                self._record_change(None)
                return False

            # 3. Build structural signature
            current_signature = []
            for idx, c in enumerate(containers, 1):
                inputs = c.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")
                prompt_els = c.find_elements(By.CSS_SELECTOR, "div[id^='prompt-']")

                if not inputs or not prompt_els:
                    # Incomplete container
                    self.last_diagnostics["incomplete_questions"].append({
                        "container_index": idx,
                        "has_prompt": len(prompt_els) > 0,
                        "has_inputs": len(inputs) > 0
                    })
                    self._record_change(None)
                    return False

                prompt_id = prompt_els[0].get_attribute("id") or ""
                input_name = inputs[0].get_attribute("name") or ""
                opt_ids = tuple(i.get_attribute("id") or "" for i in inputs)
                current_signature.append((prompt_id, input_name, len(inputs), opt_ids))

            current_sig_tuple = tuple(current_signature)
            now = time.monotonic()

            if current_sig_tuple != self.last_signature:
                self.last_signature = current_sig_tuple
                self.last_change_time = now
                return False

            # Signature has remained unchanged: check if duration elapsed
            elapsed = now - self.last_change_time
            if elapsed >= self.stability_duration:
                logger.info(
                    "DOM structural stability achieved for %d questions (stable for %.2fs).",
                    len(current_signature),
                    elapsed
                )
                return True

            return False

        except StaleElementReferenceException:
            self._record_change(None)
            return False
        except Exception as e:
            logger.debug("Exception in DOM stability check: %s", e)
            self._record_change(None)
            return False

    def _record_change(self, sig: Any) -> None:
        self.last_signature = sig
        self.last_change_time = time.monotonic()


def wait_for_dom_stability(
    driver,
    timeout: float = config.DOM_STABILITY_TIMEOUT,
    stability_duration: float = config.DOM_STABILITY_TIME
) -> None:
    """
    Waits explicitly for the quiz DOM to stabilize.
    If it fails to stabilize within timeout, saves a diagnostic DOM snapshot and raises DOMStabilityTimeoutException.
    """
    logger.info("Waiting for quiz DOM to achieve structural stability (timeout=%.1fs)...", timeout)
    condition = QuizDOMStabilityCondition(stability_duration=stability_duration)

    try:
        WebDriverWait(driver, timeout, poll_frequency=0.1).until(condition)
    except Exception as exc:
        diag = condition.last_diagnostics
        logger.error(
            "DOM stability timeout! Boundary found: %s, Questions found: %d, Incomplete: %s",
            diag.get("boundary_found"),
            diag.get("question_count"),
            diag.get("incomplete_questions")
        )
        try:
            html = driver.page_source
            config.DIAGNOSTIC_DOM_PATH.write_text(html, encoding="utf-8")
            logger.info("Saved diagnostic DOM snapshot to: %s", config.DIAGNOSTIC_DOM_PATH)
        except Exception as save_err:
            logger.error("Failed to save diagnostic DOM snapshot: %s", save_err)

        raise DOMStabilityTimeoutException(
            f"DOM failed to achieve structural stability within {timeout}s. "
            f"Discovered {diag.get('question_count')} questions, "
            f"Boundary present: {diag.get('boundary_found')}."
        ) from exc
