"""
Coursera Quiz Automation — Main Orchestration Script.
Executes Phases 1 through 5:
- Phase 1: Browser Initialization & Dynamic Quiz Tab Detection
- Phase 2: Dynamic Question & Option Extraction (Anti-AI Sanitized)
- Phase 3: Terminal Handoff to ChatGPT & Strict Answer Parsing
- Phase 4: Native Selenium Option Selection with Verification
- Phase 5: Pre-submission Review Table & Confirmed Submission Guard
"""

import argparse
import logging
import sys
from pathlib import Path

import config
from browser.driver import FirefoxBrowser
from browser.reconnaissance import DOMReconnaissance
from browser.security_monitor import SecurityMonitor
from extraction.questions import QuestionExtractor
from handoff.parser import TerminalHandoff
from interaction.selector import QuizInteractor


def setup_logging():
    """Configures multi-destination logging to console and log file."""
    logger = logging.getLogger("coursera_automation")
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S"
    )

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def prompt_multiline_answers() -> str:
    """Collects multi-line answer input from the user in the terminal."""
    print("\n" + "=" * 70)
    print("PASTE CHATGPT'S ANSWERS BELOW")
    print("=" * 70)
    print("Format examples:")
    print("  1: A")
    print("  2: D")
    print("  3: B, C (for multi-choice)")
    print("  4: 1 (numeric 1-based format)")
    print("-" * 70)
    print("Paste your lines, then press [ENTER] (or type 'DONE'):")

    lines = []
    while True:
        try:
            line = input()
            # If explicit DONE, finish immediately
            if line.strip().upper() == "DONE":
                break
            # If empty line after answers entered, finish automatically
            if not line.strip() and lines:
                break
            if line.strip():
                lines.append(line)
        except EOFError:
            break

    return "\n".join(lines)


def run_quiz_workflow(browser: FirefoxBrowser, logger: logging.Logger, is_initial: bool = True) -> bool:
    """Runs a single quiz workflow (Phases 1-5) on the active tab."""
    # Ensure attached to active quiz tab
    browser.switch_to_active_tab()

    if is_initial:
        # Phase 1: Wait for user navigation & active quiz tab
        recon = DOMReconnaissance(browser)
        recon.wait_for_user_ready()
        print("\n[*] Inspecting live DOM...")
        recon.run_reconnaissance()

    # Security check before extraction
    SecurityMonitor.handle_if_challenged(browser.driver)

    # Phase 2: Dynamic Question Extraction
    print("\n" + "=" * 70)
    print("PHASE 2: EXTRACTING QUIZ QUESTIONS & OPTIONS")
    print("=" * 70)
    extractor = QuestionExtractor(browser)
    questions = extractor.extract_all()

    if not questions:
        print("[!] No questions could be extracted from the active page.")
        print("    Please verify the quiz is open and questions are visible in Firefox.")
        return False

    print(f"[OK] Successfully extracted {len(questions)} logical question(s).")

    # Phase 3: Format for ChatGPT & Ingest Answers
    print("\n" + "=" * 70)
    print("PHASE 3: CHATGPT PROMPT & ANSWER HANDOFF")
    print("=" * 70)
    chatgpt_prompt = TerminalHandoff.format_questions_for_chatgpt(questions)

    # Auto-copy to Windows clipboard
    copied = TerminalHandoff.copy_to_clipboard(chatgpt_prompt)
    if copied:
        print("\n[OK] Prompt automatically copied to your clipboard! (Press Ctrl+V in ChatGPT)")
    else:
        print("\nCopy the text block below and paste it into ChatGPT:\n")

    print("-" * 70)
    print(chatgpt_prompt)
    print("-" * 70)

    # Answer ingestion loop with validation
    parsed_result = None
    while True:
        raw_input_text = prompt_multiline_answers()
        if not raw_input_text.strip():
            print("[!] No input received. Please paste your answers.")
            continue

        parsed_result = TerminalHandoff.parse_answers(raw_input_text, questions)

        if parsed_result.is_valid:
            print("\n[OK] Answers successfully parsed and validated!")
            break
        else:
            print("\n" + "!" * 70)
            print("VALIDATION ERRORS ENCOUNTERED:")
            print("!" * 70)
            for err in parsed_result.errors:
                print(f"  • {err}")
            print("\nPlease re-paste the corrected answers.\n")

    # Phase 4: Option Selection
    print("\n" + "=" * 70)
    print("PHASE 4: LIVE OPTION SELECTION")
    print("=" * 70)
    interactor = QuizInteractor(browser)
    interactor.apply_selections(parsed_result.answers, questions)

    # Phase 5: Review & Confirmed Submission
    print("\n" + "=" * 70)
    print("PHASE 5: PRE-SUBMISSION REVIEW")
    print("=" * 70)
    interactor.display_review_table(parsed_result.answers, questions)

    confirm = input("Press [ENTER] to confirm and submit quiz (or type 'n' to cancel): ").strip().lower()

    if confirm in ["n", "no", "cancel"]:
        print("[*] Submission cancelled. Firefox remains open for your review.")
    else:
        interactor.submit_quiz_guarded(explicit_confirmation=True)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Coursera Quiz Automation — End-to-End Workflow"
    )
    parser.add_argument(
        "--clean-profile",
        action="store_true",
        help="Launch Firefox with a temporary profile instead of the persistent profile."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Direct URL to the practice quiz"
    )
    parser.add_argument(
        "--recon-only",
        action="store_true",
        help="Only run Phase 1 DOM reconnaissance without extracting or answering."
    )
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("Starting Coursera Quiz Automation...")

    use_persistent = not args.clean_profile and config.USE_PERSISTENT_PROFILE
    browser = None

    try:
        # Launch browser
        browser = FirefoxBrowser(persistent_profile=use_persistent)
        logger.info("Browser successfully launched.")

        target_url = args.url or "https://www.coursera.org"
        logger.info("Opening URL: %s", target_url)
        browser.get(target_url)

        # Security check
        SecurityMonitor.handle_if_challenged(browser.driver)

        if args.recon_only:
            recon = DOMReconnaissance(browser)
            recon.wait_for_user_ready()
            print("\n[*] Inspecting live DOM...")
            recon.run_reconnaissance()
            print("\n[OK] Recon-only mode complete. Report saved to logs/dom_inspection_report.md.")
            return

        is_initial = True
        while True:
            run_quiz_workflow(browser, logger, is_initial=is_initial)
            is_initial = False

            # Interactive multi-quiz loop — Firefox stays open across quizzes!
            print("\n" + "=" * 70)
            print("FIREFOX REMAINS OPEN — READY FOR NEXT QUIZ")
            print("=" * 70)
            print("Options:")
            print("  [Enter] or [1] -> Solve next quiz (open or switch to the new quiz in Firefox, then press Enter)")
            print("  [2]            -> Re-run on current page")
            print("  [q]            -> Close Firefox and exit")
            print("-" * 70)
            choice = input("Enter choice ([Enter] for next quiz, [q] to exit): ").strip().lower()

            if choice == "q":
                logger.info("User requested exit.")
                break

            print("\n[*] Switching to active quiz tab in Firefox...")
            browser.switch_to_active_tab()

    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
    except Exception as e:
        logger.exception("An error occurred during execution: %s", e)
    finally:
        if browser:
            browser.quit()
        logger.info("Session finished.")


if __name__ == "__main__":
    main()
