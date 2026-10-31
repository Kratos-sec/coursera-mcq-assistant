"""
Live DOM Reconnaissance Module for Coursera Quiz Automation.
Inspects the active quiz DOM dynamically without guessing selectors.
Handles multi-tab navigation, iframe detection, container hierarchy,
question text selectors, option inputs/labels, navigation controls,
submit buttons, and ARIA/data attributes.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import config
from .driver import FirefoxBrowser

logger = logging.getLogger("coursera_automation.browser.reconnaissance")


class DOMReconnaissance:
    """Performs non-invasive, comprehensive reconnaissance on a live Coursera quiz page."""

    def __init__(self, browser: FirefoxBrowser):
        self.browser = browser

    def wait_for_user_ready(self) -> None:
        """Prompts the user to log in and navigate to the target quiz before running recon."""
        print("\n" + "=" * 70)
        print("COURSERA QUIZ AUTOMATION — PHASE 1 DOM RECONNAISSANCE")
        print("=" * 70)
        print("1. Firefox has been opened.")
        print("2. Please log into Coursera in the Firefox window (if not already logged in).")
        print("3. Navigate to your target ungraded practice quiz.")
        print("4. Ensure the quiz questions are visibly loaded on the screen.")
        print("=" * 70)

        # Inform user about detected tabs
        self.browser.switch_to_active_tab()
        tabs = self.browser.get_open_tabs()
        if tabs:
            print("\nDetected open browser tabs:")
            for idx, tab in enumerate(tabs, 1):
                marker = " [ACTIVE]" if tab.get("is_current") else ""
                print(f"  {idx}. {tab.get('title', 'Untitled')} ({tab.get('url', '')}){marker}")
            print()

        input("\n>>> Press [ENTER] in this terminal when the quiz page is ready for inspection... <<< ")
        logger.info("User signaled page readiness. Resolving active quiz tab...")
        self.browser.switch_to_active_tab()

        # Display resolved target tab
        print(f"\n[*] Targeted Tab for Reconnaissance:")
        print(f"    Title: {self.browser.title}")
        print(f"    URL:   {self.browser.current_url}\n")

    def run_reconnaissance(self) -> Dict[str, Any]:
        """
        Executes JavaScript DOM inspection inside the browser,
        captures HTML snapshot, saves raw JSON data, and generates a detailed Markdown report.
        """
        # Ensure attached to active window
        self.browser.switch_to_active_tab()

        logger.info("Verifying document ready state...")
        for attempt in range(3):
            try:
                ready_state = self.browser.execute_script("return document.readyState;")
                logger.info("document.readyState = %s", ready_state)
                break
            except Exception as e:
                logger.warning("Attempt %d to check readyState failed: %s. Re-attaching tab...", attempt + 1, e)
                time.sleep(1)
                self.browser.switch_to_active_tab()

        # Current page info
        page_info = {
            "url": self.browser.current_url,
            "title": self.browser.title,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info("Inspecting page: %s (%s)", page_info["title"], page_info["url"])

        # Inject comprehensive inspection script
        inspection_js = """
        return (function() {
            function getUniqueSelector(el) {
                if (!el || el.nodeType !== Node.ELEMENT_NODE) return '';
                if (el.id) return '#' + CSS.escape(el.id);
                
                // Check if any reliable data attribute exists
                const dataAttrs = ['data-testid', 'data-test', 'data-qa', 'data-e2e', 'data-track-component'];
                for (const attr of dataAttrs) {
                    if (el.hasAttribute(attr)) {
                        return el.tagName.toLowerCase() + '[' + attr + '="' + CSS.escape(el.getAttribute(attr)) + '"]';
                    }
                }

                let path = [];
                let current = el;
                while (current && current.nodeType === Node.ELEMENT_NODE && current.tagName.toLowerCase() !== 'body') {
                    let selector = current.tagName.toLowerCase();
                    if (current.className && typeof current.className === 'string') {
                        const classes = current.className.trim().split(/\\s+/).filter(c => c && !c.includes(':') && !c.includes('/'));
                        if (classes.length > 0) {
                            selector += '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
                        }
                    }
                    let sibling = current;
                    let nth = 1;
                    while (sibling = sibling.previousElementSibling) {
                        if (sibling.tagName.toLowerCase() === current.tagName.toLowerCase()) nth++;
                    }
                    selector += ':nth-of-type(' + nth + ')';
                    path.unshift(selector);
                    current = current.parentElement;
                }
                return path.join(' > ');
            }

            function getAttributes(el) {
                const attrs = {};
                if (!el || !el.attributes) return attrs;
                for (let i = 0; i < el.attributes.length; i++) {
                    const attr = el.attributes[i];
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }

            const report = {
                questionContainers: [],
                allInputs: [],
                navigationButtons: [],
                actionButtons: [],
                paginationElements: [],
                iframes: [],
                ariaDataSummary: {
                    roles: {},
                    dataAttributes: {},
                    ariaAttributes: {}
                }
            };

            // Detect any iframes on page
            document.querySelectorAll('iframe').forEach(f => {
                report.iframes.push({
                    src: f.src || '',
                    id: f.id || '',
                    title: f.title || '',
                    selector: getUniqueSelector(f)
                });
            });

            // 1. Collect all ARIA roles and data-* attributes across the entire page
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                if (el.hasAttribute('role')) {
                    const r = el.getAttribute('role');
                    report.ariaDataSummary.roles[r] = (report.ariaDataSummary.roles[r] || 0) + 1;
                }
                for (let i = 0; i < el.attributes.length; i++) {
                    const name = el.attributes[i].name;
                    if (name.startsWith('data-')) {
                        report.ariaDataSummary.dataAttributes[name] = (report.ariaDataSummary.dataAttributes[name] || 0) + 1;
                    } else if (name.startsWith('aria-')) {
                        report.ariaDataSummary.ariaAttributes[name] = (report.ariaDataSummary.ariaAttributes[name] || 0) + 1;
                    }
                }
            });

            // 2. Locate Question Containers
            const potentialQuestionContainers = [];
            const containerSelectors = [
                'fieldset',
                '[role="radiogroup"]',
                '[role="group"]',
                '[class*="question" i]',
                '[class*="Question" i]',
                '[data-testid*="question" i]',
                '[data-track-component*="question" i]',
                '.c-question',
                '.rc-FormPartsQuestion',
                '.rc-QuizQuestion'
            ];

            const seenContainers = new Set();
            containerSelectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    if (!seenContainers.has(el) && el.querySelectorAll('input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"]').length > 0) {
                        seenContainers.add(el);
                        potentialQuestionContainers.push(el);
                    }
                });
            });

            // If no specific question classes matched, find common parent containers of radio/checkbox inputs
            if (potentialQuestionContainers.length === 0) {
                const inputs = document.querySelectorAll('input[type="radio"], input[type="checkbox"]');
                const parentGroups = new Set();
                inputs.forEach(input => {
                    let parent = input.closest('fieldset') || input.closest('[role="radiogroup"]') || input.closest('form') || input.parentElement.parentElement;
                    if (parent && !parentGroups.has(parent)) {
                        parentGroups.add(parent);
                        potentialQuestionContainers.push(parent);
                    }
                });
            }

            // Inspect each question container
            potentialQuestionContainers.forEach((container, idx) => {
                const containerInfo = {
                    index: idx + 1,
                    tagName: container.tagName.toLowerCase(),
                    id: container.id || null,
                    className: container.className || '',
                    attributes: getAttributes(container),
                    selector: getUniqueSelector(container),
                    questionTextCandidates: [],
                    options: []
                };

                // Find candidate question text elements
                const promptSelectors = [
                    'legend',
                    'h1, h2, h3, h4, h5, h6',
                    '[class*="prompt" i]',
                    '[class*="question-text" i]',
                    '[class*="questionText" i]',
                    '[class*="title" i]',
                    '[class*="content" i]',
                    '[data-testid*="prompt" i]',
                    '[data-testid*="question-text" i]',
                    '.rc-FormPartsQuestion__content',
                    '.c-question-prompt'
                ];

                const foundPrompts = new Set();
                promptSelectors.forEach(psel => {
                    container.querySelectorAll(psel).forEach(pel => {
                        const text = pel.innerText ? pel.innerText.trim() : '';
                        if (text.length > 3 && !foundPrompts.has(pel)) {
                            foundPrompts.add(pel);
                            containerInfo.questionTextCandidates.push({
                                tagName: pel.tagName.toLowerCase(),
                                className: pel.className || '',
                                textSnippet: text.slice(0, 150),
                                selector: getUniqueSelector(pel),
                                attributes: getAttributes(pel)
                            });
                        }
                    });
                });

                // Find options / inputs inside this container
                const optionInputs = container.querySelectorAll('input[type="radio"], input[type="checkbox"], [role="radio"], [role="checkbox"]');
                optionInputs.forEach((inp, optIdx) => {
                    let labelText = '';
                    let labelSelector = '';
                    let labelElement = null;

                    // Option 1: linked label via 'for'
                    if (inp.id) {
                        labelElement = container.querySelector('label[for="' + CSS.escape(inp.id) + '"]');
                    }
                    // Option 2: enclosing label
                    if (!labelElement) {
                        labelElement = inp.closest('label');
                    }
                    // Option 3: aria-labelledby
                    if (!labelElement && inp.hasAttribute('aria-labelledby')) {
                        const lblId = inp.getAttribute('aria-labelledby');
                        labelElement = document.getElementById(lblId);
                    }
                    // Option 4: parent container text
                    if (labelElement) {
                        labelText = labelElement.innerText ? labelElement.innerText.trim() : '';
                        labelSelector = getUniqueSelector(labelElement);
                    } else if (inp.parentElement) {
                        labelText = inp.parentElement.innerText ? inp.parentElement.innerText.trim() : '';
                        labelSelector = getUniqueSelector(inp.parentElement);
                    }

                    containerInfo.options.push({
                        optionIndex: optIdx + 1,
                        inputTag: inp.tagName.toLowerCase(),
                        inputType: inp.getAttribute('type') || inp.getAttribute('role') || 'unknown',
                        name: inp.getAttribute('name') || '',
                        id: inp.id || '',
                        value: inp.getAttribute('value') || '',
                        checked: inp.checked || inp.getAttribute('aria-checked') === 'true',
                        disabled: inp.disabled || inp.getAttribute('aria-disabled') === 'true',
                        inputSelector: getUniqueSelector(inp),
                        inputAttributes: getAttributes(inp),
                        labelText: labelText,
                        labelSelector: labelSelector,
                        wrapperSelector: getUniqueSelector(inp.parentElement)
                    });
                });

                report.questionContainers.push(containerInfo);
            });

            // 3. Inspect Navigation & Action Controls
            const navWords = ['next', 'previous', 'back', 'prev', 'forward', 'continue'];
            const actionWords = ['submit', 'finish', 'check', 'review', 'resume', 'save'];

            const allButtons = document.querySelectorAll('button, a[role="button"], input[type="button"], input[type="submit"]');
            allButtons.forEach(btn => {
                const text = (btn.innerText || btn.getAttribute('value') || btn.getAttribute('aria-label') || '').trim();
                const lower = text.toLowerCase();
                const btnData = {
                    text: text,
                    tagName: btn.tagName.toLowerCase(),
                    type: btn.getAttribute('type') || 'button',
                    id: btn.id || null,
                    className: btn.className || '',
                    disabled: btn.disabled || btn.getAttribute('aria-disabled') === 'true',
                    selector: getUniqueSelector(btn),
                    attributes: getAttributes(btn)
                };

                if (navWords.some(w => lower.includes(w))) {
                    report.navigationButtons.push(btnData);
                } else if (actionWords.some(w => lower.includes(w))) {
                    report.actionButtons.push(btnData);
                }
            });

            // 4. Pagination / Question Rail indicators
            const paginationSelectors = [
                '[role="tablist"]',
                '[role="navigation"]',
                '.pagination',
                '[class*="pagination" i]',
                '[class*="drawer" i]',
                '[class*="stepper" i]',
                '[data-testid*="pagination" i]',
                'nav'
            ];
            paginationSelectors.forEach(ps => {
                document.querySelectorAll(ps).forEach(pel => {
                    const text = pel.innerText ? pel.innerText.trim().replace(/\\s+/g, ' ') : '';
                    if (text.length > 0 && text.length < 200) {
                        report.paginationElements.push({
                            selector: getUniqueSelector(pel),
                            text: text,
                            attributes: getAttributes(pel)
                        });
                    }
                });
            });

            return report;
        })();
        """

        logger.info("Executing client-side DOM reconnaissance...")
        recon_data = self.browser.execute_script(inspection_js)

        # Merge page metadata
        full_data = {
            "page": page_info,
            "reconnaissance": recon_data
        }

        # 1. Save live DOM HTML snapshot
        self._save_html_snapshot()

        # 2. Save raw JSON data
        self._save_json_data(full_data)

        # 3. Generate detailed Markdown Report
        self._generate_markdown_report(full_data)

        return full_data

    def _save_html_snapshot(self) -> None:
        """Saves current page HTML to logs."""
        try:
            html = self.browser.page_source
            config.DOM_SNAPSHOT_PATH.write_text(html, encoding="utf-8")
            logger.info("Saved DOM HTML snapshot to: %s (%d bytes)", config.DOM_SNAPSHOT_PATH, len(html))
        except Exception as e:
            logger.error("Failed to save HTML snapshot: %s", e)

    def _save_json_data(self, data: Dict[str, Any]) -> None:
        """Saves parsed reconnaissance data to JSON file."""
        try:
            with open(config.RECON_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Saved reconnaissance JSON to: %s", config.RECON_DATA_PATH)
        except Exception as e:
            logger.error("Failed to save reconnaissance JSON: %s", e)

    def _generate_markdown_report(self, data: Dict[str, Any]) -> None:
        """Generates a human-readable, thorough Markdown report of the DOM inspection."""
        page = data["page"]
        recon = data["reconnaissance"]
        q_containers = recon.get("questionContainers", [])
        nav_buttons = recon.get("navigationButtons", [])
        action_buttons = recon.get("actionButtons", [])
        pagination = recon.get("paginationElements", [])
        iframes = recon.get("iframes", [])
        aria_summary = recon.get("ariaDataSummary", {})

        report_lines = [
            "# Coursera Quiz DOM Reconnaissance Report",
            "",
            f"**Generated:** {page['timestamp']}  ",
            f"**Page Title:** `{page['title']}`  ",
            f"**URL:** `{page['url']}`  ",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Question Containers Detected:** {len(q_containers)}",
            f"- **Navigation Buttons Detected:** {len(nav_buttons)}",
            f"- **Action / Submit Buttons Detected:** {len(action_buttons)}",
            f"- **Pagination / Navigation Elements:** {len(pagination)}",
            f"- **Iframes Detected:** {len(iframes)}",
            "",
            "---",
            "",
            "## 2. Question Container Hierarchy",
            "",
        ]

        if not q_containers:
            report_lines.append("> [!WARNING]\n> No question containers were automatically matched. The quiz might use an iframe or non-standard container structure. Check `quiz_dom_snapshot.html`.")
            if iframes:
                report_lines.append(f"\n> Found {len(iframes)} iframe(s) on the page. The quiz content may be hosted inside an embedded frame.")
        else:
            for qc in q_containers:
                report_lines.extend([
                    f"### Question #{qc['index']}",
                    f"- **Tag:** `<{qc['tagName']}>`",
                    f"- **Selector:** `{qc['selector']}`",
                    f"- **Classes:** `{qc['className']}`",
                    f"- **Options Count:** {len(qc['options'])}",
                    "",
                    "#### Question Text Candidate(s):",
                ])
                if qc['questionTextCandidates']:
                    for pt in qc['questionTextCandidates']:
                        report_lines.append(f"  - **Tag:** `<{pt['tagName']}>` | **Selector:** `{pt['selector']}`")
                        report_lines.append(f"    - *Snippet:* \"{pt['textSnippet']}\"")
                else:
                    report_lines.append("  - *No separate heading/legend found; text may reside directly in the container.*")

                report_lines.extend([
                    "",
                    "#### Option Elements:",
                    "| Option # | Input Type | Input Selector | Label Text | Label Selector |",
                    "| --- | --- | --- | --- | --- |"
                ])
                for opt in qc['options']:
                    lbl_snippet = (opt['labelText'][:40] + '...') if len(opt['labelText']) > 40 else opt['labelText']
                    lbl_snippet = lbl_snippet.replace('|', '\\|').replace('\n', ' ')
                    report_lines.append(
                        f"| {opt['optionIndex']} | `{opt['inputType']}` | `{opt['inputSelector']}` | {lbl_snippet} | `{opt['labelSelector']}` |"
                    )
                report_lines.append("")

        report_lines.extend([
            "---",
            "",
            "## 3. Radio Buttons & Checkboxes Summary",
            "",
            "| Container # | Radio Count | Checkbox Count | Input Name Attribute |",
            "| --- | --- | --- | --- |"
        ])
        for qc in q_containers:
            radios = sum(1 for o in qc['options'] if 'radio' in o['inputType'].lower())
            checks = sum(1 for o in qc['options'] if 'checkbox' in o['inputType'].lower())
            names = set(o['name'] for o in qc['options'] if o['name'])
            name_str = ", ".join(f"`{n}`" for n in names) if names else "*None*"
            report_lines.append(f"| #{qc['index']} | {radios} | {checks} | {name_str} |")

        report_lines.extend([
            "",
            "---",
            "",
            "## 4. Next / Previous Navigation Controls",
            "",
        ])
        if nav_buttons:
            report_lines.append("| Text | Tag | Type | Disabled | Selector |")
            report_lines.append("| --- | --- | --- | --- | --- |")
            for nb in nav_buttons:
                report_lines.append(f"| **{nb['text']}** | `{nb['tagName']}` | `{nb['type']}` | {nb['disabled']} | `{nb['selector']}` |")
        else:
            report_lines.append("*No next/previous navigation buttons found. The quiz may display all questions on a single page.*")

        report_lines.extend([
            "",
            "---",
            "",
            "## 5. Submit & Action Buttons",
            "",
        ])
        if action_buttons:
            report_lines.append("| Text | Tag | Type | Disabled | Selector |")
            report_lines.append("| --- | --- | --- | --- | --- |")
            for ab in action_buttons:
                report_lines.append(f"| **{ab['text']}** | `{ab['tagName']}` | `{ab['type']}` | {ab['disabled']} | `{ab['selector']}` |")
        else:
            report_lines.append("*No submit/action buttons detected with standard submit keywords.*")

        report_lines.extend([
            "",
            "---",
            "",
            "## 6. Pagination & Navigation Drawer Structure",
            "",
        ])
        if pagination:
            for idx, p in enumerate(pagination, 1):
                report_lines.append(f"- **Element {idx}:** `{p['selector']}`")
                report_lines.append(f"  - *Content:* `{p['text']}`")
        else:
            report_lines.append("*No dedicated pagination or navigation rail elements identified.*")

        report_lines.extend([
            "",
            "---",
            "",
            "## 7. Relevant ARIA Roles and Data Attributes",
            "",
            "### Top ARIA Roles Identified:",
        ])
        roles = aria_summary.get("roles", {})
        if roles:
            for r, count in sorted(roles.items(), key=lambda x: x[1], reverse=True)[:10]:
                report_lines.append(f"- `role=\"{r}\"`: {count} elements")
        else:
            report_lines.append("- *No explicit ARIA roles found.*")

        report_lines.extend([
            "",
            "### Top Data Attributes Identified:",
        ])
        data_attrs = aria_summary.get("dataAttributes", {})
        if data_attrs:
            for d, count in sorted(data_attrs.items(), key=lambda x: x[1], reverse=True)[:15]:
                report_lines.append(f"- `{d}`: {count} occurrences")
        else:
            report_lines.append("- *No data-* attributes found.*")

        if iframes:
            report_lines.extend([
                "",
                "---",
                "",
                "## 8. Embedded Iframes Detected",
                "",
                "| Index | ID | Title | Selector | Source |",
                "| --- | --- | --- | --- | --- |"
            ])
            for idx, ifr in enumerate(iframes, 1):
                src_snip = ifr['src'][:50] if len(ifr['src']) > 50 else ifr['src']
                report_lines.append(f"| {idx} | `{ifr['id']}` | {ifr['title']} | `{ifr['selector']}` | `{src_snip}` |")

        report_lines.extend([
            "",
            "---",
            "",
            "## 9. Concrete Selector Recommendations for Phase 2",
            "",
            "Based on the inspected live DOM:",
        ])

        if q_containers:
            sample_c = q_containers[0]
            report_lines.append(f"- **Question Container Selector Pattern:** `{sample_c['selector']}`")
            if sample_c['questionTextCandidates']:
                report_lines.append(f"- **Question Text Selector Pattern:** `{sample_c['questionTextCandidates'][0]['selector']}`")
            if sample_c['options']:
                sample_opt = sample_c['options'][0]
                report_lines.append(f"- **Option Input Selector Pattern:** `{sample_opt['inputSelector']}`")
                report_lines.append(f"- **Option Label Selector Pattern:** `{sample_opt['labelSelector']}`")
        if action_buttons:
            report_lines.append(f"- **Submit Button Selector:** `{action_buttons[0]['selector']}`")
        if nav_buttons:
            report_lines.append(f"- **Navigation Button Selector:** `{nav_buttons[0]['selector']}`")

        report_lines.extend([
            "",
            "> [!NOTE]",
            "> Review these selectors before proceeding to Phase 2 (Question & Option Extraction).",
            ""
        ])

        try:
            config.REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
            logger.info("Successfully generated DOM inspection report at: %s", config.REPORT_PATH)
        except Exception as e:
            logger.error("Failed to write Markdown report: %s", e)
