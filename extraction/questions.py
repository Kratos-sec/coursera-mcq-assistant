"""
Question and Option Extraction Module for Coursera Quiz Automation.
Implements dynamic discovery, question identity models, and anti-AI sanitization.
"""

import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Dict, List, Literal, Optional

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By

import config
from .content_sanitizer import ContentSanitizer
from .dom_stability import wait_for_dom_stability

logger = logging.getLogger("coursera_automation.extraction.questions")


@dataclass
class Option:
    """Represents a single answer option within a quiz question."""
    index: int                          # 0-based DOM order (0, 1, 2, 3...)
    letter: str                         # 'A', 'B', 'C', 'D'...
    text: str                           # Sanitized display text
    input_id: str                       # e.g. cds-react-aria3142865275-:r7c:
    input_name: str                     # e.g. autoGradableResponseId~...
    input_type: str                     # 'radio' or 'checkbox'
    input_value: str                    # Raw server value (e.g. '4', '1')
    is_initially_selected: bool = False
    is_currently_selected: bool = False


@dataclass
class Question:
    """Represents a complete quiz question with full identity lineage."""
    number: int                         # Logical question number (1, 2, 3...)
    container_testid: str               # e.g. part-Submission_MultipleChoiceQuestion
    container_id: Optional[str]         # Nullable container id
    prompt_id: str                      # e.g. prompt-autoGradableResponseId~...
    input_name: str                     # Shared input name across options
    question_type: Literal["single_choice", "multi_choice"]
    prompt_text: str                    # Sanitized prompt text
    options: List[Option] = field(default_factory=list)


class QuestionExtractor:
    """
    Extracts structured quiz questions from the live DOM or raw HTML.
    Enforces dynamic discovery, boundary scoping, deduplication, and sanitization.
    """

    def __init__(self, browser_or_driver: Any = None):
        self.browser_or_driver = browser_or_driver

    def extract_all(self, skip_stability_wait: bool = False) -> List[Question]:
        """
        Extracts all questions from the active Selenium WebDriver session.
        Applies DOM stability detection, boundary scoping, and sanitization.
        """
        driver = getattr(self.browser_or_driver, "driver", self.browser_or_driver)
        if not driver:
            raise RuntimeError("No active WebDriver instance available.")

        if not skip_stability_wait:
            wait_for_dom_stability(driver)

        # Locate all primary question containers
        containers = driver.find_elements(By.CSS_SELECTOR, config.QUESTION_SELECTOR)
        logger.info("Located %d primary question container(s).", len(containers))

        # Fallback if primary selector returned nothing
        if not containers:
            logger.warning("Primary selector found 0 containers. Using deduplicated fallback strategy...")
            containers = self._discover_fallback_containers(driver)

        questions: List[Question] = []
        seen_prompts = set()
        seen_names = set()

        for idx, container in enumerate(containers, 1):
            q = self._extract_question_from_webelement(container, fallback_number=idx)
            if not q:
                continue

            # Deduplication safety
            if q.prompt_id and q.prompt_id in seen_prompts:
                logger.debug("Skipping duplicate prompt ID: %s", q.prompt_id)
                continue
            if q.input_name and q.input_name in seen_names:
                logger.debug("Skipping duplicate input name: %s", q.input_name)
                continue

            seen_prompts.add(q.prompt_id)
            seen_names.add(q.input_name)
            questions.append(q)

        logger.info("Successfully extracted %d unique logical question(s).", len(questions))
        return questions

    def _discover_fallback_containers(self, driver) -> List[Any]:
        """Fallback discovery for older Coursera layouts with prompt/name deduplication."""
        candidates = driver.find_elements(By.CSS_SELECTOR, "[role='radiogroup'], [role='group']")
        deduped = []
        seen_keys = set()
        for c in candidates:
            try:
                inputs = c.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")
                if not inputs:
                    continue
                name = inputs[0].get_attribute("name") or ""
                if name and name not in seen_keys:
                    seen_keys.add(name)
                    deduped.append(c)
            except Exception:
                continue
        return deduped

    def _extract_question_from_webelement(self, container: Any, fallback_number: int) -> Optional[Question]:
        """Parses a single question container WebElement into a Question object."""
        try:
            # 1. Question Number
            q_num = fallback_number
            try:
                num_els = container.find_elements(By.CSS_SELECTOR, "span.rc-A11yScreenReaderOnly")
                for el in num_els:
                    m = re.search(r"Question\s*(\d+)", el.text, re.IGNORECASE)
                    if m:
                        q_num = int(m.group(1))
                        break
            except Exception:
                pass

            # 2. Prompt Element & Text
            prompt_id = ""
            prompt_text = ""
            try:
                prompt_containers = container.find_elements(By.CSS_SELECTOR, "div[id^='prompt-']")
                if prompt_containers:
                    prompt_id = prompt_containers[0].get_attribute("id") or ""
                    cml_viewers = prompt_containers[0].find_elements(By.CSS_SELECTOR, "[data-testid='cml-viewer']")
                    if cml_viewers:
                        prompt_text = ContentSanitizer.sanitize_prompt(cml_viewers[0])
                    else:
                        prompt_text = ContentSanitizer.sanitize_prompt(prompt_containers[0])
            except Exception as e:
                logger.warning("Error extracting prompt for Question %d: %s", q_num, e)

            # 3. Option Wrappers
            option_elements = container.find_elements(By.CSS_SELECTOR, "div.rc-Option")
            options: List[Option] = []
            has_checkbox = False

            for opt_idx, opt_el in enumerate(option_elements):
                try:
                    # Ignore trap checkpoints if accidentally nested
                    if ContentSanitizer.is_trap_element(opt_el):
                        continue

                    # Input element inside option
                    input_el = opt_el.find_element(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']")
                    input_id = input_el.get_attribute("id") or ""
                    input_name = input_el.get_attribute("name") or ""
                    input_type = (input_el.get_attribute("type") or "radio").lower()
                    input_val = input_el.get_attribute("value") or ""
                    is_selected = input_el.is_selected()

                    if input_type == "checkbox":
                        has_checkbox = True

                    # Option text from label CML viewer
                    opt_text = ""
                    try:
                        cml_v = opt_el.find_elements(By.CSS_SELECTOR, ".cds-checkboxAndRadio-labelText [data-testid='cml-viewer']")
                        if cml_v:
                            opt_text = ContentSanitizer.sanitize_option(cml_v[0])
                        else:
                            lbl_span = opt_el.find_elements(By.CSS_SELECTOR, ".cds-checkboxAndRadio-labelText")
                            if lbl_span:
                                opt_text = ContentSanitizer.sanitize_option(lbl_span[0])
                    except Exception:
                        pass

                    letter = chr(ord("A") + opt_idx)
                    options.append(Option(
                        index=opt_idx,
                        letter=letter,
                        text=opt_text,
                        input_id=input_id,
                        input_name=input_name,
                        input_type=input_type,
                        input_value=input_val,
                        is_initially_selected=is_selected,
                        is_currently_selected=is_selected
                    ))
                except Exception as opt_err:
                    logger.warning("Error extracting option %d on Question %d: %s", opt_idx + 1, q_num, opt_err)

            if not options or not prompt_text:
                logger.warning("Question %d missing valid prompt or options; skipping.", q_num)
                return None

            q_type: Literal["single_choice", "multi_choice"] = "multi_choice" if has_checkbox else "single_choice"
            common_name = options[0].input_name if options else ""
            container_id = container.get_attribute("id") or None
            container_testid = container.get_attribute("data-testid") or "part-Submission_MultipleChoiceQuestion"

            return Question(
                number=q_num,
                container_testid=container_testid,
                container_id=container_id,
                prompt_id=prompt_id,
                input_name=common_name,
                question_type=q_type,
                prompt_text=prompt_text,
                options=options
            )

        except Exception as e:
            logger.error("Failed to parse question container: %s", e)
            return None

    @staticmethod
    def extract_from_html(html_content: str) -> List[Question]:
        """
        Pure Python HTML extractor for testing against snapshots and synthetic fixtures.
        Uses exact same selector hierarchy, allowlists, and deduplication logic without requiring Selenium.
        """
        # 1. Match question wrappers
        q_blocks = re.findall(
            r'<div[^>]*data-testid=[\"\']part-Submission_MultipleChoiceQuestion[\"\'].*?(?=(?:<div[^>]*data-testid=[\"\']part-Submission_MultipleChoiceQuestion[\"\']|<div[^>]*data-e2e=[\"\']AttemptSubmitControls[\"\']|<button[^>]*data-testid=[\"\']submit-button[\"\']|$))',
            html_content,
            flags=re.DOTALL
        )

        questions: List[Question] = []
        seen_prompts = set()
        seen_names = set()

        for idx, block in enumerate(q_blocks, 1):
            # Question number
            q_num = idx
            num_match = re.search(r'class=[\"\'][^\"\']*rc-A11yScreenReaderOnly[^\"\']*[\"\'][^>]*><span>Question\s*(\d+)</span>', block)
            if num_match:
                q_num = int(num_match.group(1))

            # Prompt ID
            prompt_id_match = re.search(r'id=[\"\'](prompt-[^\"\']+|p-[^\"\']+)[\"\']', block)
            prompt_id = prompt_id_match.group(1) if prompt_id_match else f"prompt-fallback-{idx}"

            # Prompt text extraction via allowlist (exclude content-integrity-instructions)
            prompt_text = ""
            # Isolate prompt section before rc-Option
            prompt_section = re.split(r'<div[^>]*class=[\"\'][^\"\']*rc-Option', block)[0]

            # Find cml-viewer inside prompt section that is NOT a trap
            cml_matches = re.finditer(r'<div[^>]*data-testid=[\"\']cml-viewer[\"\'][^>]*>(.*?)</div>', prompt_section, re.DOTALL)
            for cm in cml_matches:
                # Check if this cml viewer is inside a trap element
                start_pos = cm.start()
                context_before = prompt_section[max(0, start_pos - 300):start_pos]
                if "content-integrity-instructions" in context_before or "data-ai-instructions" in context_before:
                    continue
                raw_text = re.sub(r'<[^>]+>', ' ', cm.group(1))
                prompt_text = ContentSanitizer.clean_text(raw_text)
                if prompt_text:
                    break

            if not prompt_text:
                # Fallback to any text inside prompt div
                p_match = re.search(r'id=[\"\'](?:prompt-[^\"\']+|p-[^\"\']+)[\"\'][^>]*>(.*?)</div>', prompt_section, re.DOTALL)
                if p_match:
                    prompt_text = ContentSanitizer.clean_text(re.sub(r'<[^>]+>', ' ', p_match.group(1)))

            # 2. Extract options using rc-Option boundary splitting
            opt_parts = re.split(r'(?=<div[^>]*class=[\"\'][^\"\']*rc-Option)', block)[1:]
            options: List[Option] = []
            has_checkbox = False

            for opt_idx, opt_raw in enumerate(opt_parts):
                # Input
                inp_match = re.search(r'<input\s+([^>]+)>', opt_raw)
                if not inp_match:
                    continue
                attrs_str = inp_match.group(1)

                id_m = re.search(r'id=[\"\']([^\"\']+)[\"\']', attrs_str)
                name_m = re.search(r'name=[\"\']([^\"\']+)[\"\']', attrs_str)
                type_m = re.search(r'type=[\"\']([^\"\']+)[\"\']', attrs_str)
                val_m = re.search(r'value=[\"\']([^\"\']+)[\"\']', attrs_str)
                
                # Check checked attribute or aria-checked
                checked_m = bool(re.search(r'\bchecked\b', attrs_str) or 'aria-checked="true"' in attrs_str)

                input_id = id_m.group(1) if id_m else f"opt_{idx}_{opt_idx}"
                input_name = name_m.group(1) if name_m else f"group_{idx}"
                input_type = (type_m.group(1) if type_m else "radio").lower()
                input_val = val_m.group(1) if val_m else str(opt_idx + 1)

                if input_type == "checkbox":
                    has_checkbox = True

                # Option text
                opt_text = ""
                opt_cml = re.search(r'class=[\"\'][^\"\']*labelText[^\"\']*[\"\'].*?data-testid=[\"\']cml-viewer[\"\'][^>]*>(.*?)</div>', opt_raw, re.DOTALL)
                if opt_cml:
                    opt_text = ContentSanitizer.clean_text(re.sub(r'<[^>]+>', ' ', opt_cml.group(1)))
                else:
                    lbl_m = re.search(r'class=[\"\'][^\"\']*labelText[^\"\']*[\"\'][^>]*>(.*?)</span>', opt_raw, re.DOTALL)
                    if lbl_m:
                        opt_text = ContentSanitizer.clean_text(re.sub(r'<[^>]+>', ' ', lbl_m.group(1)))

                letter = chr(ord("A") + opt_idx)
                options.append(Option(
                    index=opt_idx,
                    letter=letter,
                    text=opt_text,
                    input_id=input_id,
                    input_name=input_name,
                    input_type=input_type,
                    input_value=input_val,
                    is_initially_selected=checked_m,
                    is_currently_selected=checked_m
                ))

            if not options or not prompt_text:
                continue

            # Deduplication
            if prompt_id in seen_prompts or (options and options[0].input_name in seen_names):
                continue

            seen_prompts.add(prompt_id)
            if options:
                seen_names.add(options[0].input_name)

            q_type: Literal["single_choice", "multi_choice"] = "multi_choice" if has_checkbox else "single_choice"
            questions.append(Question(
                number=q_num,
                container_testid="part-Submission_MultipleChoiceQuestion",
                container_id=None,
                prompt_id=prompt_id,
                input_name=options[0].input_name if options else "",
                question_type=q_type,
                prompt_text=prompt_text,
                options=options
            ))

        return questions
