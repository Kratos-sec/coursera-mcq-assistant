"""
Unit tests for SecurityMonitor.
"""

import unittest
from unittest.mock import MagicMock
from browser.security_monitor import SecurityMonitor, SecurityChallengeStatus


class TestSecurityMonitor(unittest.TestCase):

    def test_clean_page_returns_no_challenge(self):
        driver = MagicMock()
        driver.find_elements.return_value = []
        driver.title = "Practice Quiz: Network Traffic Analysis | Coursera"
        driver.page_source = "<html><body>Standard quiz page content</body></html>"

        status = SecurityMonitor.inspect_page(driver)
        self.assertFalse(status.has_challenge)
        self.assertIsNone(status.challenge_type)

    def test_detects_captcha_element(self):
        driver = MagicMock()
        mock_el = MagicMock()
        mock_el.is_displayed.return_value = True

        def mock_find(by, val):
            if "recaptcha" in val:
                return [mock_el]
            return []

        driver.find_elements.side_effect = mock_find
        driver.title = "Quiz"
        driver.page_source = "<html><body></body></html>"

        status = SecurityMonitor.inspect_page(driver)
        self.assertTrue(status.has_challenge)
        self.assertEqual(status.challenge_type, "CAPTCHA_OR_TURNSTILE")

    def test_detects_access_denied_or_429_title(self):
        driver = MagicMock()
        driver.find_elements.return_value = []
        driver.title = "429 Too Many Requests"
        driver.page_source = "<html><body></body></html>"

        status = SecurityMonitor.inspect_page(driver)
        self.assertTrue(status.has_challenge)
        self.assertEqual(status.challenge_type, "ACCESS_DENIED_OR_RATE_LIMIT")

    def test_detects_access_denied_body(self):
        driver = MagicMock()
        driver.find_elements.return_value = []
        driver.title = "Error"
        driver.page_source = "<html><body>Attention Required! | Cloudflare - Please verify you are a human</body></html>"

        status = SecurityMonitor.inspect_page(driver)
        self.assertTrue(status.has_challenge)
        self.assertEqual(status.challenge_type, "ACCESS_DENIED_OR_RATE_LIMIT")


if __name__ == "__main__":
    unittest.main()
