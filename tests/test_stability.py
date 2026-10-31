"""
Unit tests for QuizDOMStabilityCondition and wait_for_dom_stability.
"""

import time
import unittest
from unittest.mock import MagicMock
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

from extraction.dom_stability import (
    QuizDOMStabilityCondition,
    wait_for_dom_stability,
    DOMStabilityTimeoutException
)
import config


class DummyWebElement:
    def __init__(self, tag_name="div", attrs=None, children=None):
        self.tag_name = tag_name
        self._attrs = attrs or {}
        self._children = children or []

    def get_attribute(self, name):
        return self._attrs.get(name)

    def find_elements(self, by, value):
        res = []
        for c in self._children:
            if "prompt-" in value and c._attrs.get("id", "").startswith("prompt-"):
                res.append(c)
            elif "input" in value and c.tag_name == "input":
                res.append(c)
        return res


class TestDOMStability(unittest.TestCase):

    def test_missing_boundary_returns_false(self):
        driver = MagicMock()
        # Find submission boundary returns empty
        driver.find_elements.side_effect = lambda by, val: [] if val == config.SUBMISSION_BOUNDARY else [DummyWebElement()]
        condition = QuizDOMStabilityCondition(stability_duration=0.1)

        result = condition(driver)
        self.assertFalse(result)
        self.assertFalse(condition.last_diagnostics["boundary_found"])

    def test_incomplete_question_returns_false(self):
        driver = MagicMock()
        boundary = DummyWebElement()
        # Container with prompt but no inputs
        prompt = DummyWebElement(attrs={"id": "prompt-1"})
        incomplete_q = DummyWebElement(children=[prompt])

        def mock_find(by, val):
            if val == config.SUBMISSION_BOUNDARY:
                return [boundary]
            if val == config.QUESTION_SELECTOR:
                return [incomplete_q]
            return []

        driver.find_elements.side_effect = mock_find
        condition = QuizDOMStabilityCondition(stability_duration=0.1)

        result = condition(driver)
        self.assertFalse(result)
        self.assertEqual(len(condition.last_diagnostics["incomplete_questions"]), 1)

    def test_stability_achieved_after_duration(self):
        driver = MagicMock()
        boundary = DummyWebElement()

        # Complete question with prompt and 2 inputs
        prompt = DummyWebElement(attrs={"id": "prompt-1"})
        inp1 = DummyWebElement(tag_name="input", attrs={"id": "o1", "name": "g1"})
        inp2 = DummyWebElement(tag_name="input", attrs={"id": "o2", "name": "g1"})
        complete_q = DummyWebElement(children=[prompt, inp1, inp2])

        def mock_find(by, val):
            if val == config.SUBMISSION_BOUNDARY:
                return [boundary]
            if val == config.QUESTION_SELECTOR:
                return [complete_q]
            return []

        driver.find_elements.side_effect = mock_find
        condition = QuizDOMStabilityCondition(stability_duration=0.1)

        # First call establishes signature
        first_call = condition(driver)
        self.assertFalse(first_call)

        # Wait duration
        time.sleep(0.12)

        # Second call with identical signature succeeds
        second_call = condition(driver)
        self.assertTrue(second_call)

    def test_stale_element_returns_false_safely(self):
        driver = MagicMock()
        driver.find_elements.side_effect = StaleElementReferenceException("Stale")
        condition = QuizDOMStabilityCondition(stability_duration=0.1)

        result = condition(driver)
        self.assertFalse(result)

    def test_wait_for_dom_stability_timeout_raises_and_saves_snapshot(self):
        driver = MagicMock()
        driver.find_elements.return_value = []
        driver.page_source = "<html><body>Incomplete page</body></html>"

        with self.assertRaises(DOMStabilityTimeoutException):
            wait_for_dom_stability(driver, timeout=0.2, stability_duration=0.1)

        # Verify diagnostic snapshot was written
        self.assertTrue(config.DIAGNOSTIC_DOM_PATH.exists())


if __name__ == "__main__":
    unittest.main()
