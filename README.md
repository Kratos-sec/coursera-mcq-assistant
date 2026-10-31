# Coursera MCQ Assistant (Firefox + Selenium)

A modular, fail-safe Python automation suite for Coursera quizzes (practice and graded) using Selenium 4, Firefox, and Selenium Manager.

## Features

- **Dynamic Quiz Discovery**: Zero hardcoded question counts. Automatically handles quizzes of arbitrary length (3, 5, 7, 10+ questions) and varying option counts per question.
- **Strict DOM Scoping**: Uses verified boundary controls (`QUIZ_ROOT = '[data-testid="tunnel-vision-content"]'` and `SUBMISSION_BOUNDARY = '[data-e2e="AttemptSubmitControls"]'`) to avoid duplicate question matches.
- **DOM Stability Detection**: Implements a custom explicit-wait condition verifying structural stability (prompt IDs, input names, option counts, input IDs) for $\ge$ 850 ms using `time.monotonic()`.
- **Anti-AI Prompt Sanitizer**: Strict allowlist extraction of prompt and option CML viewers, filtering out hidden instructions (`[data-testid="content-integrity-instructions"]`) and acknowledgment checkpoints (`[data-testid="acknowledgment-checkpoint"]`).
- **Strict Native Selenium Interaction**: Exclusively uses native `WebElement.click()` on labels or inputs. Includes checkbox idempotency (never unchecks an already-selected checkbox) and post-click checked state verification.
- **Strict Answer Parser**: Converts letter (`A-Z`) and 1-based numeric (`1-N`) answers to 0-based indices, validating option bounds, question numbers, duplicate entries, single-choice cardinality, and detecting missing questions.
- **Auto-Clipboard Handoff**: Formats the extracted quiz into a structured prompt and automatically copies it to your clipboard for instant pasting into ChatGPT.
- **Auto Honor Code & Modal Confirmation**: Automatically checks the Coursera Honor Code agreement checkbox and confirms the "Ready to submit?" modal dialog, excluding background AI chat widgets.
- **Continuous Multi-Quiz Workflow**: Firefox stays open across quizzes; solve multiple quizzes back-to-back in the same session without restarting the browser.
- **Security Monitor**: Detects visible CAPTCHAs, rate limiting (HTTP 429), or Cloudflare challenges and gracefully pauses automation for manual user completion.

---

## Project Structure

```
coursera-mcq-assistant/
├── main.py                  # End-to-end interactive workflow CLI
├── config.py                # Centralized paths, timeouts, and selectors
├── requirements.txt         # Dependencies (Selenium 4)
├── browser/
│   ├── driver.py            # Firefox WebDriver & multi-tab management
│   ├── reconnaissance.py    # Live DOM inspection & report generation
│   └── security_monitor.py  # CAPTCHA / rate-limit detection & graceful pause
├── extraction/
│   ├── questions.py         # Dynamic question extractor & identity models
│   ├── content_sanitizer.py # Anti-AI prompt & honeypot trap filter
│   └── dom_stability.py     # Custom explicit wait condition for DOM stability
├── handoff/
│   └── parser.py            # ChatGPT prompt formatter & strict answer parser
├── interaction/
│   └── selector.py          # Native Selenium selector & modal submission guard
└── tests/
    ├── fixtures/            # Variable-length & synthetic quiz test fixtures
    ├── test_extraction.py   # Snapshot & variable-length extraction tests
    ├── test_sanitizer.py    # Anti-AI trap filtering tests
    ├── test_stability.py    # DOM stability detection tests
    ├── test_parser.py       # Answer parsing & validation tests
    ├── test_interaction.py  # Selection idempotency & modal submission tests
    └── test_security_monitor.py # Security monitor tests
```

---

## Running the Automated Test Suite

Run all 42 unit and fixture tests:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## How to Run End-to-End

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Launch the Automation
```powershell
python main.py
```
*(Or specify a direct quiz URL with `--url <quiz_url>`)*

### 3. Workflow:
1. Firefox launches with a persistent profile (`./firefox_profile`) to retain your Coursera login.
2. In the terminal, press `[ENTER]` when the quiz questions are displayed.
3. The prompt is automatically copied to your clipboard — paste it directly into ChatGPT (`Ctrl+V`).
4. Paste ChatGPT's answers into your terminal, press `[ENTER]`, and hit `[ENTER]` again on an empty line.
5. The automation selects the answers, verifies each checked state, auto-checks the Honor Code agreement, and displays the ASCII Review Table.
6. Press `[ENTER]` to confirm and submit. The script clicks the main submit button and confirms the "Ready to submit?" modal dialog.
7. Firefox remains open! Hit `[ENTER]` to solve the next quiz or `[q]` to exit.
