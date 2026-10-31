"""
Terminal-Based Answer Handoff and Parser for Coursera Quiz Automation.
Formats questions cleanly for ChatGPT and strictly parses/validates structured responses.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from extraction.questions import Question

logger = logging.getLogger("coursera_automation.handoff.parser")


@dataclass
class ParseResult:
    """Encapsulates the result of parsing terminal answer input."""
    is_valid: bool
    answers: Dict[int, List[int]] = field(default_factory=dict)  # question_number -> list of 0-based option indices
    errors: List[str] = field(default_factory=list)
    missing_questions: List[int] = field(default_factory=list)


class TerminalHandoff:
    """Manages question formatting for ChatGPT and strict answer ingestion."""

    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """
        Copies text to the system clipboard using Windows native clip.exe.
        Requires zero external packages.
        """
        try:
            import subprocess
            subprocess.run(["clip"], input=text.strip().encode("utf-16"), check=True)
            return True
        except Exception as e:
            logger.warning("Could not auto-copy to clipboard: %s", e)
            return False

    @staticmethod
    def format_questions_for_chatgpt(questions: List[Question]) -> str:
        """
        Formats extracted questions into a numbered, prompt-ready text block for ChatGPT.
        Excludes all anti-AI traps and hidden metadata.
        """
        lines = [
            "Please answer these practice quiz questions.",
            "",
            "Return answers in this format:",
            "",
            "1: A",
            "2: C",
            "3: B",
            "4: D",
            "5: A",
            "",
            "For multiple-choice questions, use comma-separated letters.",
            "",
            "--- QUESTIONS ---",
            ""
        ]

        for q in sorted(questions, key=lambda x: x.number):
            type_indicator = " (Select all that apply)" if q.question_type == "multi_choice" else ""
            lines.append(f"Question {q.number}: {q.prompt_text}{type_indicator}\n")
            for opt in q.options:
                lines.append(f"{opt.letter}) {opt.text}")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def parse_answers(cls, raw_input_text: str, questions: List[Question]) -> ParseResult:
        """
        Strictly parses terminal input containing answers into 0-based option indices.
        Validates question existence, option bounds, cardinality, duplicates, and missing questions.
        """
        result = ParseResult(is_valid=True)
        q_map: Dict[int, Question] = {q.number: q for q in questions}
        seen_questions: Set[int] = set()

        line_pattern = re.compile(
            r"^\s*(?:(?:Question|Q)\s*)?(\d+)\s*[:.)-]\s*(.*?)\s*$",
            re.IGNORECASE
        )

        lines = [ln.strip() for ln in raw_input_text.splitlines() if ln.strip()]

        for line_num, line in enumerate(lines, 1):
            # Ignore chatty intro lines if user pasted conversational text
            if line.startswith("---") or line.lower().startswith("here are") or line.lower().startswith("answers:"):
                continue

            match = line_pattern.match(line)
            if not match:
                result.errors.append(f"Line {line_num}: Malformed answer format: '{line}'")
                result.is_valid = False
                continue

            q_num_str, answer_part = match.groups()
            q_num = int(q_num_str)

            # 1. Validate Question Number
            if q_num not in q_map:
                result.errors.append(f"Line {line_num}: Unknown question number {q_num}. Valid numbers: {sorted(q_map.keys())}")
                result.is_valid = False
                continue

            if q_num in seen_questions:
                result.errors.append(f"Line {line_num}: Duplicate answer entry for Question {q_num}.")
                result.is_valid = False
                continue

            seen_questions.add(q_num)
            question = q_map[q_num]
            max_options = len(question.options)

            # 2. Split option tokens by commas or whitespace
            raw_tokens = [t.strip() for t in re.split(r"[,;\s]+", answer_part.strip()) if t.strip()]
            if not raw_tokens:
                result.errors.append(f"Line {line_num}: Empty answer given for Question {q_num}.")
                result.is_valid = False
                continue

            # 3. Convert tokens to 0-based indices
            opt_indices: List[int] = []
            seen_indices_in_q: Set[int] = set()
            line_has_error = False

            for token in raw_tokens:
                token_upper = token.upper()
                opt_idx: Optional[int] = None

                # Letter conversion: 'A' -> 0, 'B' -> 1...
                if len(token_upper) == 1 and "A" <= token_upper <= "Z":
                    opt_idx = ord(token_upper) - ord("A")
                # Numeric conversion: '1' -> 0, '2' -> 1... (1-based to 0-based)
                elif token.isdigit():
                    opt_idx = int(token) - 1
                else:
                    result.errors.append(
                        f"Line {line_num}: Invalid option symbol '{token}' for Question {q_num}."
                    )
                    line_has_error = True
                    break

                # Bounds check
                if opt_idx is None or opt_idx < 0 or opt_idx >= max_options:
                    result.errors.append(
                        f"Line {line_num}: Option '{token}' is out-of-bounds for Question {q_num} "
                        f"(Question has {max_options} options: A-{chr(ord('A') + max_options - 1)})."
                    )
                    line_has_error = True
                    break

                # Duplicate option selection check
                if opt_idx in seen_indices_in_q:
                    result.errors.append(
                        f"Line {line_num}: Duplicate option selection '{token}' for Question {q_num}."
                    )
                    line_has_error = True
                    break

                seen_indices_in_q.add(opt_idx)
                opt_indices.append(opt_idx)

            if line_has_error:
                result.is_valid = False
                continue

            # 4. Cardinality check for single-choice questions
            if question.question_type == "single_choice" and len(opt_indices) > 1:
                result.errors.append(
                    f"Line {line_num}: Multiple options provided for single-choice Question {q_num}: {raw_tokens}."
                )
                result.is_valid = False
                continue

            result.answers[q_num] = opt_indices

        # 5. Missing question detection
        all_expected_nums = set(q_map.keys())
        missing = sorted(all_expected_nums - seen_questions)
        if missing:
            result.missing_questions = missing
            result.errors.append(f"Missing answers for Question(s): {missing}")
            result.is_valid = False

        return result
