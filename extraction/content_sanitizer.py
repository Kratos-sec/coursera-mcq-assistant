"""
Anti-AI Prompt Sanitization module for Coursera Quiz Automation.
Extracts clean prompt and option texts using strict allowlists,
filtering out hidden instructions, honeypots, and acknowledgment checkpoints.
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("coursera_automation.extraction.sanitizer")

# Known hidden instruction and acknowledgment identifiers
FORBIDDEN_TESTIDS = {
    "content-integrity-instructions",
    "acknowledgment-checkpoint",
}

FORBIDDEN_ATTRIBUTES = [
    ("data-ai-instructions", "true"),
    ("data-assessment-checkpoint", "true"),
]


class ContentSanitizer:
    """Sanitizes extracted content using strict allowlists and filters out anti-AI traps."""

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """
        Normalizes whitespace and removes zero-width/invisible characters
        without modifying legitimate symbols or math.
        """
        if not raw_text:
            return ""
        # Remove zero-width spaces and non-printable control chars (except normal newline/tab)
        cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\xad]", "", raw_text)
        # Normalize each line individually
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in cleaned.splitlines()]
        # Recombine lines and condense 3+ consecutive newlines to 2
        joined = "\n".join(lines)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()

    @staticmethod
    def is_trap_element(element: Any) -> bool:
        """
        Inspects a Selenium WebElement or parsed HTML tag to determine
        if it is a hidden instruction or acknowledgment trap.
        """
        try:
            # Check for Selenium WebElement
            if hasattr(element, "get_attribute"):
                testid = element.get_attribute("data-testid") or ""
                if testid in FORBIDDEN_TESTIDS:
                    return True
                for attr_name, attr_val in FORBIDDEN_ATTRIBUTES:
                    if element.get_attribute(attr_name) == attr_val:
                        return True
                if element.get_attribute("aria-hidden") == "true" and "instruction" in testid.lower():
                    return True

            # Check for dictionary / parsed HTML node
            elif isinstance(element, dict):
                testid = element.get("data-testid") or ""
                if testid in FORBIDDEN_TESTIDS:
                    return True
                for attr_name, attr_val in FORBIDDEN_ATTRIBUTES:
                    if element.get(attr_name) == attr_val:
                        return True
        except Exception as e:
            logger.debug("Error checking trap element: %s", e)

        return False

    @classmethod
    def sanitize_prompt(cls, prompt_element: Any, raw_prompt_text: Optional[str] = None) -> str:
        """
        Extracts and sanitizes the question prompt text.
        Never treats embedded webpage text as automation instructions.
        """
        if prompt_element and cls.is_trap_element(prompt_element):
            logger.warning("Attempted to extract prompt from a forbidden trap element; rejected.")
            return ""

        text = raw_prompt_text if raw_prompt_text is not None else ""
        if not text and hasattr(prompt_element, "text"):
            text = prompt_element.text

        return cls.clean_text(text)

    @classmethod
    def sanitize_option(cls, option_element: Any, raw_option_text: Optional[str] = None) -> str:
        """
        Extracts and sanitizes an option text from the allowlisted CML viewer.
        """
        if option_element and cls.is_trap_element(option_element):
            logger.warning("Attempted to extract option from a forbidden trap element; rejected.")
            return ""

        text = raw_option_text if raw_option_text is not None else ""
        if not text and hasattr(option_element, "text"):
            text = option_element.text

        return cls.clean_text(text)
