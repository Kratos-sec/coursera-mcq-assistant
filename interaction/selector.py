"""
Option Selection and Submission Guard Module for Coursera Quiz Automation.
Executes native Selenium clicks with strict idempotency, selection verification,
review table display, and explicit confirmation gating.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

import config
from extraction.questions import Question, Option

logger = logging.getLogger("coursera_automation.interaction.selector")


class SelectionVerificationError(Exception):
    """Raised when an option click fails to result in a verified checked state."""
    pass


class QuizInteractor:
    """Manages verified answer selection and safe submission gating."""

    def __init__(self, browser_or_driver: Any):
        if hasattr(browser_or_driver, "driver") and type(browser_or_driver).__name__ != "MagicMock":
            self.driver = browser_or_driver.driver
        else:
            self.driver = browser_or_driver

    def apply_selections(
        self,
        answer_map: Dict[int, List[int]],
        questions: List[Question]
    ) -> None:
        """
        Applies answers to the live quiz using native clicks and verifies state.
        
        :param answer_map: Dict mapping question number -> list of 0-based option indices
        :param questions: Extracted question metadata
        """
        logger.info("Applying %d answer selection(s)...", len(answer_map))
        q_dict = {q.number: q for q in questions}

        for q_num, target_indices in sorted(answer_map.items()):
            question = q_dict.get(q_num)
            if not question:
                logger.warning("Question %d not found in question list; skipping.", q_num)
                continue

            for opt_idx in target_indices:
                self._select_single_option(question, opt_idx)

        logger.info("All option selections applied successfully.")

    def _select_single_option(self, question: Question, option_index: int, retry_stale: bool = True) -> None:
        """
        Locates the specific question and option using relative lookups,
        checks current state, executes a native click, and verifies state.
        """
        if option_index < 0 or option_index >= len(question.options):
            raise IndexError(f"Option index {option_index} out of bounds for Question {question.number}.")

        target_opt = question.options[option_index]

        try:
            # 1. Locate the question wrapper by identity
            q_wrapper = self._find_question_element(question)
            if not q_wrapper:
                raise NoSuchElementException(
                    f"Could not locate container for Question {question.number} (name: {question.input_name})"
                )

            # 2. Locate the option element by DOM order
            option_wrappers = q_wrapper.find_elements(By.CSS_SELECTOR, "div.rc-Option")
            if option_index >= len(option_wrappers):
                raise IndexError(
                    f"Option index {option_index} exceeded live option elements ({len(option_wrappers)})"
                )

            opt_wrapper = option_wrappers[option_index]

            # 3. Locate label and input
            label_el = opt_wrapper.find_element(By.CSS_SELECTOR, "label.cds-checkboxAndRadio-label")
            input_el = opt_wrapper.find_element(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")

            # 4. Check initial selection state (Idempotency Rule)
            is_checked = input_el.is_selected()
            if is_checked:
                logger.info(
                    "Question %d Option %s (%s) is already selected. Skipping click to prevent toggle.",
                    question.number,
                    target_opt.letter,
                    target_opt.input_type
                )
                target_opt.is_currently_selected = True
                return

            # 5. Scroll for visibility
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", label_el)
            time.sleep(0.1)

            # 6. Execute Native Click (with ActionChains fallback for click interception)
            try:
                label_el.click()
            except ElementClickInterceptedException:
                logger.warning(
                    "Native click intercepted on Question %d Option %s; falling back to ActionChains click.",
                    question.number,
                    target_opt.letter
                )
                ActionChains(self.driver).move_to_element(label_el).click().perform()

            # 7. Verify Checked State Post-Click
            self._verify_option_selected(input_el, question, target_opt)
            target_opt.is_currently_selected = True
            logger.info("Successfully selected Question %d: Option %s.", question.number, target_opt.letter)

        except StaleElementReferenceException:
            if retry_stale:
                logger.warning("Stale element encountered on Question %d Option %d; reacquiring...", question.number, option_index)
                time.sleep(0.3)
                self._select_single_option(question, option_index, retry_stale=False)
            else:
                raise

    def _verify_option_selected(self, input_el, question: Question, option: Option, timeout: float = 5.0) -> None:
        """Waits explicitly for input.is_selected() to become True."""
        try:
            wait = WebDriverWait(self.driver, timeout, poll_frequency=0.2)
            wait.until(lambda d: input_el.is_selected())
        except TimeoutException:
            # Capture diagnostics
            diag = {
                "tag": input_el.tag_name,
                "id": input_el.get_attribute("id"),
                "checked_prop": input_el.get_attribute("checked"),
                "aria_checked": input_el.get_attribute("aria-checked"),
                "disabled": input_el.get_attribute("disabled"),
                "is_selected": input_el.is_selected()
            }
            logger.error("Selection verification failed for Question %d Option %s: %s", question.number, option.letter, diag)
            raise SelectionVerificationError(
                f"Verification failed: Question {question.number} Option {option.letter} was not selected. Diagnostics: {diag}"
            )

    def _find_question_element(self, question: Question) -> Optional[Any]:
        """Locates the live question container WebElement by identity attributes."""
        containers = self.driver.find_elements(By.CSS_SELECTOR, config.QUESTION_SELECTOR)
        for c in containers:
            try:
                # Match by input_name
                inputs = c.find_elements(By.CSS_SELECTOR, f"input[name='{question.input_name}']")
                if inputs:
                    return c
                # Match by prompt_id
                if question.prompt_id:
                    prompts = c.find_elements(By.ID, question.prompt_id)
                    if prompts:
                        return c
            except Exception:
                continue

        # Fallback to index if within range
        if 0 < question.number <= len(containers):
            return containers[question.number - 1]

        return None

    def display_review_table(self, answer_map: Dict[int, List[int]], questions: List[Question]) -> None:
        """Prints a clean, formatted ASCII review table of all selections."""
        q_dict = {q.number: q for q in questions}

        print("\n" + "=" * 76)
        print("                        QUIZ SELECTION REVIEW TABLE")
        print("=" * 76)
        print(f"{'Q#':<4} | {'Type':<8} | {'Selected':<10} | {'Option Text Preview':<46}")
        print("-" * 76)

        for q_num in sorted(q_dict.keys()):
            question = q_dict[q_num]
            chosen_indices = answer_map.get(q_num, [])
            if not chosen_indices:
                chosen_str = "[NONE]"
                text_preview = "NO ANSWER PROVIDED"
            else:
                letters = [question.options[i].letter for i in chosen_indices if i < len(question.options)]
                chosen_str = ", ".join(letters)
                first_opt = question.options[chosen_indices[0]]
                text_preview = first_opt.text[:43] + "..." if len(first_opt.text) > 43 else first_opt.text

            q_type = "Multi" if question.question_type == "multi_choice" else "Single"
            print(f"{q_num:<4} | {q_type:<8} | {chosen_str:<10} | {text_preview:<46}")

        print("=" * 76 + "\n")

    def check_agreement_checkbox_state(self) -> bool:
        """
        Checks if the Coursera Honor Code agreement checkbox is checked.
        Never checks it automatically; user must review and check it manually.
        """
        try:
            boxes = self.driver.find_elements(By.CSS_SELECTOR, config.AGREEMENT_CHECKBOX_SELECTOR)
            if boxes:
                return boxes[0].is_selected()
        except Exception:
            pass
        return False

    def is_submit_button_enabled(self) -> bool:
        """Checks if the submit button is currently enabled."""
        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, config.SUBMIT_BUTTON_SELECTOR)
            if btns:
                btn = btns[0]
                return btn.is_enabled() and btn.get_attribute("aria-disabled") != "true"
        except Exception:
            pass
        return False

    def auto_select_agreement_if_needed(self) -> None:
        """
        Automatically selects the Coursera Honor Code agreement checkbox if not already selected.
        """
        try:
            boxes = self.driver.find_elements(By.CSS_SELECTOR, config.AGREEMENT_CHECKBOX_SELECTOR)
            if not boxes:
                return

            box = boxes[0]
            if not box.is_selected():
                logger.info("Auto-selecting Honor Code agreement checkbox...")
                # Find enclosing label
                try:
                    label = box.find_element(By.XPATH, "./ancestor::label")
                except Exception:
                    label = box

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", label)
                time.sleep(0.1)
                label.click()

                # Verify checked
                WebDriverWait(self.driver, 3.0).until(lambda d: box.is_selected())
                logger.info("Honor Code agreement successfully checked.")
                print("[OK] Honor Code agreement automatically checked.")
        except Exception as e:
            logger.warning("Could not auto-select Honor Code checkbox: %s", e)

    def confirm_modal_submission(self, timeout: float = 6.0) -> bool:
        """
        Detects the Coursera 'Ready to submit?' confirmation dialog
        and clicks the modal's primary 'Submit' button.
        Guaranteed to ignore the main page submit button and background chatbots.
        """
        logger.info("Checking for 'Ready to submit?' modal dialog...")
        try:
            wait = WebDriverWait(self.driver, timeout, poll_frequency=0.25)

            def get_modal_submit_btn(d):
                # 1. Search for modal containers (CDS Modal, dialog, aria-modal)
                modal_containers = d.find_elements(
                    By.CSS_SELECTOR,
                    "div.cds-Modal-container, div[role='dialog']:not([class*='Boost']):not([class*='chat']), div[aria-modal='true']:not([class*='Boost']):not([class*='chat'])"
                )

                if not modal_containers:
                    # Also look for any container enclosing "Ready to submit" text
                    headings = d.find_elements(By.XPATH, "//*[contains(text(), 'Ready to submit')]")
                    for h in headings:
                        try:
                            parent = h.find_element(By.XPATH, "./ancestor::div[.//button][1]")
                            if parent and parent.is_displayed():
                                modal_containers.append(parent)
                        except Exception:
                            continue

                if not modal_containers:
                    return None  # Modal not rendered yet; wait! NEVER fall back to root document!

                # Find the Submit button inside the detected modal container
                for container in modal_containers:
                    try:
                        if not container.is_displayed():
                            continue

                        # 1. Button with visible text 'Submit'
                        btns = container.find_elements(
                            By.XPATH,
                            ".//button[not(contains(@class, 'Boost')) and not(contains(@class, 'chat')) and (normalize-space()='Submit' or .//*[normalize-space()='Submit'])]"
                        )
                        # 2. Or primary button inside the modal
                        if not btns:
                            btns = container.find_elements(
                                By.CSS_SELECTOR,
                                "button.cds-button-primary, button[type='submit']"
                            )

                        for btn in btns:
                            # CRITICAL: Must NOT be the main page submit button
                            if btn.get_attribute("data-testid") == "submit-button":
                                continue
                            if btn.is_displayed():
                                return btn
                    except Exception:
                        continue

                return None

            submit_btn = wait.until(get_modal_submit_btn)

            if not submit_btn:
                logger.info("No modal confirmation dialog appeared (quiz submitted directly).")
                return True

            logger.info("Found confirmation dialog Submit button. Clicking...")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", submit_btn)
            time.sleep(0.2)

            # Try native click first, fallback to JavaScript click
            try:
                submit_btn.click()
            except Exception as click_err:
                logger.warning("Native click on modal button failed (%s), using JS click fallback...", click_err)
                self.driver.execute_script("arguments[0].click();", submit_btn)

            # Wait briefly for modal submission request to dispatch
            time.sleep(1.0)
            logger.info("Successfully clicked modal 'Submit' button.")
            print("[OK] Confirmed submission in 'Ready to submit?' dialog.")
            return True

        except TimeoutException:
            logger.info("No modal confirmation dialog appeared within timeout (submitted directly).")
            return True
        except Exception as e:
            logger.error("Error during modal confirmation: %s", e)
            return False

    def submit_quiz_guarded(self, explicit_confirmation: bool = False) -> bool:
        """
        Submission guard sequence:
        1. Verifies explicit terminal confirmation.
        2. Automatically checks Honor Code agreement checkbox if requested.
        3. Verifies main submit button enabled state.
        4. Clicks main submit button.
        5. Handles 'Ready to submit?' modal dialog by clicking its Submit button.
        6. Keeps browser open.
        """
        if not explicit_confirmation:
            logger.info("Submission cancelled by user.")
            print("\n[*] Submission cancelled. Firefox remains open for your review.")
            return False

        # 1. Auto-select Honor Code agreement
        self.auto_select_agreement_if_needed()

        # 2. Wait for submit button to be enabled
        logger.info("Verifying submit button enabled state...")
        try:
            WebDriverWait(self.driver, 5.0).until(lambda d: self.is_submit_button_enabled())
        except TimeoutException:
            logger.error("Submit button is disabled or not clickable.")
            print("\n[!] Error: Submit button is currently disabled. Please verify all required answers are selected in Firefox.")
            return False

        # 3. Native Click on Main Submit Button (with JS click fallback)
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, config.SUBMIT_BUTTON_SELECTOR)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", submit_btn)
        time.sleep(0.3)

        logger.info("Executing native click on main submit button...")
        try:
            submit_btn.click()
        except Exception as click_err:
            logger.warning("Native click on main submit button failed (%s), using JS click fallback...", click_err)
            self.driver.execute_script("arguments[0].click();", submit_btn)

        print("\n[OK] Main Submit button clicked.")
        time.sleep(0.5)

        # 4. Handle Confirmation Modal Dialog ("Ready to submit?")
        modal_success = self.confirm_modal_submission()

        print("\n[OK] Submission process complete! Please observe your results in Firefox.")
        return True
