"""
Firefox WebDriver manager for Coursera Quiz Automation.
Configures Firefox with Selenium Manager, persistent profile,
robust window/tab management, and explicit waits.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
)

import config

logger = logging.getLogger("coursera_automation.browser.driver")


class FirefoxBrowser:
    """Manages Firefox browser lifecycle, window handles, and explicit waits."""

    def __init__(self, persistent_profile: bool = config.USE_PERSISTENT_PROFILE):
        self.persistent_profile = persistent_profile
        self.driver: webdriver.Firefox | None = None
        self._init_driver()

    def _init_driver(self) -> None:
        """Initializes the Firefox WebDriver using Selenium Manager."""
        logger.info("Initializing Firefox WebDriver with Selenium Manager...")
        options = FirefoxOptions()

        if config.FIREFOX_BINARY:
            logger.info("Setting Firefox binary path: %s", config.FIREFOX_BINARY)
            options.binary_location = config.FIREFOX_BINARY

        if self.persistent_profile:
            profile_dir = Path(config.PROFILE_DIR)
            profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Using persistent Firefox profile at: %s", profile_dir)
            options.add_argument("-profile")
            options.add_argument(str(profile_dir.resolve()))

        # Preferences to optimize responsiveness
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("geo.enabled", False)

        try:
            service = FirefoxService()
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
            logger.info("Firefox WebDriver initialized successfully.")
        except WebDriverException as e:
            logger.error("Failed to initialize Firefox WebDriver: %s", e)
            raise

    def get(self, url: str) -> None:
        """Navigates to a given URL."""
        if not self.driver:
            raise RuntimeError("Browser is not running.")
        try:
            self.driver.get(url)
        except NoSuchWindowException:
            logger.warning("Browsing context discarded during get(). Recovering active tab...")
            self.switch_to_active_tab()
            self.driver.get(url)

    def switch_to_active_tab(self) -> None:
        """
        Ensures the driver is attached to the actual quiz window/tab.
        If multiple tabs are open:
        1. Prioritizes tabs containing quiz indicators (/exam/, /quiz/, assignment, attempt).
        2. Prioritizes the most recently opened tab (handles[-1]).
        3. Never stays trapped on the dashboard if a newer tab is open.
        """
        if not self.driver:
            return

        try:
            handles = self.driver.window_handles
            if not handles:
                logger.error("No open browser windows or tabs found.")
                return

            if len(handles) == 1:
                self.driver.switch_to.window(handles[0])
                return

            logger.info("Scanning %d open tab(s) to locate the quiz tab...", len(handles))

            # 1. Search for explicit quiz URL keywords
            quiz_keywords = ["/exam/", "/quiz/", "/assignment", "attempt", "submission", "/test/"]
            for handle in reversed(handles):
                try:
                    self.driver.switch_to.window(handle)
                    url = self.driver.current_url.lower()
                    title = self.driver.title
                    if any(kw in url for kw in quiz_keywords):
                        logger.info("Auto-selected quiz tab [%s]: '%s' (%s)", handle, title, self.driver.current_url)
                        return
                except Exception:
                    continue

            # 2. Search for any tab that is not the dashboard/home
            for handle in reversed(handles):
                try:
                    self.driver.switch_to.window(handle)
                    url = self.driver.current_url.lower()
                    if "coursera.org" in url and "my-learning" not in url and url != "about:blank":
                        logger.info("Selected non-dashboard Coursera tab [%s]: '%s' (%s)", handle, self.driver.title, self.driver.current_url)
                        return
                except Exception:
                    continue

            # 3. Default to the newest tab (last created)
            newest_handle = handles[-1]
            self.driver.switch_to.window(newest_handle)
            logger.info("Defaulted to newest tab [%s]: '%s' (%s)", newest_handle, self.driver.title, self.driver.current_url)

        except Exception as e:
            logger.error("Error while resolving active window: %s", e)

    def get_open_tabs(self) -> List[Dict[str, str]]:
        """Returns metadata of all open browser tabs."""
        tabs = []
        if not self.driver:
            return tabs
        current = None
        try:
            current = self.driver.current_window_handle
        except Exception:
            pass

        for handle in self.driver.window_handles:
            try:
                self.driver.switch_to.window(handle)
                tabs.append({
                    "handle": handle,
                    "title": self.driver.title,
                    "url": self.driver.current_url,
                    "is_current": (handle == current)
                })
            except Exception:
                continue

        # Restore original tab
        if current and current in self.driver.window_handles:
            try:
                self.driver.switch_to.window(current)
            except Exception:
                pass
        return tabs

    def execute_script(self, script: str, *args) -> Any:
        """Executes JavaScript with automatic discarded browsing context recovery."""
        if not self.driver:
            raise RuntimeError("Browser is not running.")
        try:
            return self.driver.execute_script(script, *args)
        except NoSuchWindowException:
            logger.warning("Browsing context discarded during execute_script. Reconnecting to active tab...")
            self.switch_to_active_tab()
            return self.driver.execute_script(script, *args)

    def wait_for_presence(self, by: str, value: str, timeout: float = config.EXPLICIT_WAIT_TIMEOUT):
        """Explicit wait for an element to be present in DOM with window recovery."""
        if not self.driver:
            raise RuntimeError("Browser is not running.")
        try:
            wait = WebDriverWait(self.driver, timeout, poll_frequency=config.POLL_FREQUENCY)
            return wait.until(EC.presence_of_element_located((by, value)))
        except NoSuchWindowException:
            self.switch_to_active_tab()
            wait = WebDriverWait(self.driver, timeout, poll_frequency=config.POLL_FREQUENCY)
            return wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logger.warning("Timed out waiting for presence of element: (%s, %s)", by, value)
            return None

    def wait_for_clickable(self, by: str, value: str, timeout: float = config.EXPLICIT_WAIT_TIMEOUT):
        """Explicit wait for an element to be clickable with window recovery."""
        if not self.driver:
            raise RuntimeError("Browser is not running.")
        try:
            wait = WebDriverWait(self.driver, timeout, poll_frequency=config.POLL_FREQUENCY)
            return wait.until(EC.element_to_be_clickable((by, value)))
        except NoSuchWindowException:
            self.switch_to_active_tab()
            wait = WebDriverWait(self.driver, timeout, poll_frequency=config.POLL_FREQUENCY)
            return wait.until(EC.element_to_be_clickable((by, value)))
        except TimeoutException:
            logger.warning("Timed out waiting for element to be clickable: (%s, %s)", by, value)
            return None

    @property
    def current_url(self) -> str:
        if not self.driver:
            return ""
        try:
            return self.driver.current_url
        except NoSuchWindowException:
            self.switch_to_active_tab()
            return self.driver.current_url

    @property
    def title(self) -> str:
        if not self.driver:
            return ""
        try:
            return self.driver.title
        except NoSuchWindowException:
            self.switch_to_active_tab()
            return self.driver.title

    @property
    def page_source(self) -> str:
        if not self.driver:
            return ""
        try:
            return self.driver.page_source
        except NoSuchWindowException:
            self.switch_to_active_tab()
            return self.driver.page_source

    def quit(self) -> None:
        """Closes the browser and terminates the WebDriver process."""
        if self.driver:
            logger.info("Closing Firefox WebDriver...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning("Error while quitting driver: %s", e)
            finally:
                self.driver = None
