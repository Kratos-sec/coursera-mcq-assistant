"""
Unit tests for TerminalHandoff and AnswerParser.
"""

import unittest
from extraction.questions import Question, Option
from handoff.parser import TerminalHandoff, ParseResult


def create_mock_questions() -> list:
    """Creates a sample list of 3 questions (2 single_choice, 1 multi_choice)."""
    q1 = Question(
        number=1,
        container_testid="test",
        container_id=None,
        prompt_id="p1",
        input_name="name1",
        question_type="single_choice",
        prompt_text="What is Wireshark?",
        options=[
            Option(index=0, letter="A", text="Packet analyzer", input_id="1", input_name="n1", input_type="radio", input_value="1"),
            Option(index=1, letter="B", text="Compiler", input_id="2", input_name="n1", input_type="radio", input_value="2"),
            Option(index=2, letter="C", text="Database", input_id="3", input_name="n1", input_type="radio", input_value="3"),
            Option(index=3, letter="D", text="Game", input_id="4", input_name="n1", input_type="radio", input_value="4"),
        ]
    )
    q2 = Question(
        number=2,
        container_testid="test",
        container_id=None,
        prompt_id="p2",
        input_name="name2",
        question_type="single_choice",
        prompt_text="Default HTTPS port?",
        options=[
            Option(index=0, letter="A", text="80", input_id="5", input_name="n2", input_type="radio", input_value="1"),
            Option(index=1, letter="B", text="22", input_id="6", input_name="n2", input_type="radio", input_value="2"),
            Option(index=2, letter="C", text="443", input_id="7", input_name="n2", input_type="radio", input_value="3"),
            Option(index=3, letter="D", text="21", input_id="8", input_name="n2", input_type="radio", input_value="4"),
        ]
    )
    q3 = Question(
        number=3,
        container_testid="test",
        container_id=None,
        prompt_id="p3",
        input_name="name3",
        question_type="multi_choice",
        prompt_text="Select all secure protocols.",
        options=[
            Option(index=0, letter="A", text="SSH", input_id="9", input_name="n3", input_type="checkbox", input_value="1"),
            Option(index=1, letter="B", text="Telnet", input_id="10", input_name="n3", input_type="checkbox", input_value="2"),
            Option(index=2, letter="C", text="HTTPS", input_id="11", input_name="n3", input_type="checkbox", input_value="3"),
            Option(index=3, letter="D", text="FTP", input_id="12", input_name="n3", input_type="checkbox", input_value="4"),
        ]
    )
    return [q1, q2, q3]


class TestAnswerParser(unittest.TestCase):

    def setUp(self):
        self.questions = create_mock_questions()

    def test_format_questions_for_chatgpt(self):
        formatted = TerminalHandoff.format_questions_for_chatgpt(self.questions)
        self.assertIn("Question 1: What is Wireshark?", formatted)
        self.assertIn("A) Packet analyzer", formatted)
        self.assertIn("Question 3: Select all secure protocols. (Select all that apply)", formatted)

    def test_parse_valid_letter_answers(self):
        raw_text = """
        1: A
        2: C
        3: A, C
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.answers[1], [0])
        self.assertEqual(result.answers[2], [2])
        self.assertEqual(result.answers[3], [0, 2])

    def test_parse_valid_numeric_answers(self):
        # 1-based converted to 0-based: 1->0, 3->2, 1 and 3 -> [0, 2]
        raw_text = """
        1: 1
        2: 3
        3: 1, 3
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.answers[1], [0])
        self.assertEqual(result.answers[2], [2])
        self.assertEqual(result.answers[3], [0, 2])

    def test_parse_mixed_prefixes(self):
        raw_text = """
        Question 1 - A
        Q2: C
        3) A, C
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.answers[1], [0])
        self.assertEqual(result.answers[2], [2])
        self.assertEqual(result.answers[3], [0, 2])

    def test_reject_out_of_bounds_letter(self):
        raw_text = """
        1: E
        2: C
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("out-of-bounds" in err.lower() for err in result.errors))

    def test_reject_out_of_bounds_number(self):
        raw_text = """
        1: 5
        2: C
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("out-of-bounds" in err.lower() for err in result.errors))

    def test_reject_multiple_options_for_single_choice(self):
        raw_text = """
        1: A, B
        2: C
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("multiple options" in err.lower() for err in result.errors))

    def test_reject_duplicate_question_number(self):
        raw_text = """
        1: A
        1: B
        2: C
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicate answer" in err.lower() for err in result.errors))

    def test_reject_duplicate_option_tokens(self):
        raw_text = """
        1: A
        2: C
        3: A, A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicate option" in err.lower() for err in result.errors))

    def test_reject_unknown_question_number(self):
        raw_text = """
        1: A
        2: C
        99: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("unknown question" in err.lower() for err in result.errors))

    def test_detect_missing_questions(self):
        # Q2 missing
        raw_text = """
        1: A
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_questions, [2])

    def test_copy_to_clipboard(self):
        """Tests that copy_to_clipboard runs without raising exceptions."""
        result = TerminalHandoff.copy_to_clipboard("Sample Clipboard Test Text")
        # On Windows environments where clip is available, result will be True
        self.assertIsInstance(result, bool)

    def test_reject_malformed_lines(self):
        raw_text = """
        1: A
        this is just random gibberish
        3: A
        """
        result = TerminalHandoff.parse_answers(raw_text, self.questions)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("malformed" in err.lower() for err in result.errors))


if __name__ == "__main__":
    unittest.main()
