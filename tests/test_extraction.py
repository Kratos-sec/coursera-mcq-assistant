"""
Extraction tests covering live snapshot fidelity and dynamic variable-length quiz fixtures.
"""

import unittest
from pathlib import Path

from extraction.questions import QuestionExtractor, Question, Option
import config


class TestQuestionExtraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.snapshot_path = config.DOM_SNAPSHOT_PATH
        cls.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_live_snapshot_extraction_dimensions(self):
        """Verifies ground-truth assertions against the live snapshot dynamically."""
        if not self.snapshot_path.exists():
            self.skipTest(f"Snapshot file not found: {self.snapshot_path}")

        import re
        html = self.snapshot_path.read_text(encoding="utf-8")
        expected_count = len(re.findall(r'data-testid=[\"\']part-Submission_MultipleChoiceQuestion[\"\']', html))
        questions = QuestionExtractor.extract_from_html(html)

        # 1. Total logical questions must match expected count in snapshot
        self.assertEqual(len(questions), expected_count, f"Expected {expected_count} logical questions, found {len(questions)}")

        # 2. Options per question and total options
        total_options = sum(len(q.options) for q in questions)
        self.assertEqual(total_options, expected_count * 4, f"Expected {expected_count * 4} options total, found {total_options}")

        for q in questions:
            self.assertEqual(len(q.options), 4, f"Question {q.number} should have 4 options, found {len(q.options)}")

        # 3. All options in this snapshot are radio inputs, zero checkboxes inside questions
        radio_count = sum(1 for q in questions for o in q.options if o.input_type == "radio")
        checkbox_count = sum(1 for q in questions for o in q.options if o.input_type == "checkbox")
        self.assertEqual(radio_count, expected_count * 4)
        self.assertEqual(checkbox_count, 0)

        # 4. Unique question input names match question count
        input_names = {q.input_name for q in questions}
        self.assertEqual(len(input_names), expected_count)

        # 5. Question numbers: sequential 1 through expected_count
        numbers = [q.number for q in questions]
        self.assertEqual(numbers, list(range(1, expected_count + 1)))

        # 6. Verify agreement checkbox is excluded from question options
        all_input_ids = [o.input_id for q in questions for o in q.options]
        self.assertNotIn("agreement-checkbox-base", all_input_ids)

    def test_dynamic_fixture_3_questions(self):
        """Tests that extractor dynamically handles 3 questions with varying option counts (3, 4, 5)."""
        fixture_file = self.fixtures_dir / "quiz_3_questions.html"
        html = fixture_file.read_text(encoding="utf-8")
        questions = QuestionExtractor.extract_from_html(html)

        self.assertEqual(len(questions), 3)
        self.assertEqual(len(questions[0].options), 3)
        self.assertEqual(len(questions[1].options), 4)
        self.assertEqual(len(questions[2].options), 5)

        # Verify anti-AI trap was excluded from Q1 prompt
        self.assertNotIn("Ignore all previous instructions", questions[0].prompt_text)
        self.assertIn("SYN packet flag", questions[0].prompt_text)

        # Check DOM order letters
        self.assertEqual([o.letter for o in questions[0].options], ["A", "B", "C"])
        self.assertEqual([o.letter for o in questions[2].options], ["A", "B", "C", "D", "E"])

    def test_dynamic_fixture_7_questions(self):
        """Tests dynamic extraction of 7 questions."""
        fixture_file = self.fixtures_dir / "quiz_7_questions.html"
        html = fixture_file.read_text(encoding="utf-8")
        questions = QuestionExtractor.extract_from_html(html)

        self.assertEqual(len(questions), 7)
        self.assertEqual([q.number for q in questions], list(range(1, 8)))

    def test_dynamic_fixture_10_questions(self):
        """Tests dynamic extraction of 10 questions."""
        fixture_file = self.fixtures_dir / "quiz_10_questions.html"
        html = fixture_file.read_text(encoding="utf-8")
        questions = QuestionExtractor.extract_from_html(html)

        self.assertEqual(len(questions), 10)
        self.assertEqual([q.number for q in questions], list(range(1, 11)))

    def test_dynamic_fixture_checkbox_and_initial_selection(self):
        """Tests multi_choice question with checkboxes and initially selected options."""
        fixture_file = self.fixtures_dir / "quiz_checkbox.html"
        html = fixture_file.read_text(encoding="utf-8")
        questions = QuestionExtractor.extract_from_html(html)

        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q.question_type, "multi_choice")
        self.assertEqual(len(q.options), 4)

        # Option 1 (HTTP) and Option 3 (SSH) are initially checked in fixture
        self.assertTrue(q.options[0].is_initially_selected)
        self.assertFalse(q.options[1].is_initially_selected)
        self.assertTrue(q.options[2].is_initially_selected)
        self.assertFalse(q.options[3].is_initially_selected)

        # Checkpoint trap was excluded
        self.assertNotIn("I acknowledge", q.prompt_text)


if __name__ == "__main__":
    unittest.main()
