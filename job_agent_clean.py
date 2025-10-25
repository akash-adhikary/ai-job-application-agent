
"""
Job Application Automation Agent - Clean Architecture
=====================================================
A simple, robust, and efficient job application automation system.
"""

import json
import time
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# ============= Configuration =============
class Config:
    RESUME_FILE = "resume_data.json"
    MEMORY_FILE = "agent_memory.json"
    MAX_WAIT = 10
    PAGE_LOAD_WAIT = 3
    MAX_STEPS = 30
    STUCK_THRESHOLD = 3


# ============= Data Models =============
class PageType(Enum):
    UNKNOWN = "unknown"
    SIGN_IN = "sign_in"
    APPLICATION_FORM = "application_form"
    CONFIRMATION = "confirmation"
    ERROR = "error"


@dataclass
class PageElements:
    """Holds analyzed page elements"""
    email_fields: List = field(default_factory=list)
    password_fields: List = field(default_factory=list)
    text_inputs: List = field(default_factory=list)
    buttons: List = field(default_factory=list)
    forms: List = field(default_factory=list)
    error_messages: List = field(default_factory=list)


@dataclass
class PageState:
    """Current page state"""
    url: str
    type: PageType
    elements: PageElements
    has_modal: bool = False
    form_filled: bool = False


# ============= Core Components =============
class ResumeManager:
    """Manages resume data"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        try:
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except:
            return {}

    @property
    def email(self) -> str:
        return self.data.get("personal_info", {}).get("email", "")

    @property
    def password(self) -> str:
        return self.data.get("credentials", {}).get("password", "Hinjewadi@123")

    @property
    def name(self) -> str:
        return self.data.get("personal_info", {}).get("name", "")

    @property
    def phone(self) -> str:
        return self.data.get("personal_info", {}).get("phone", "")

    def get_field_value(self, field_name: str) -> str:
        """Get value for a field based on its name"""
        field_lower = field_name.lower() if field_name else ""
        personal = self.data.get("personal_info", {})

        # Smart field mapping
        if "email" in field_lower:
            return self.email
        elif "phone" in field_lower or "mobile" in field_lower:
            return self.phone
        elif "first" in field_lower and "name" in field_lower:
            return self.name.split()[0] if self.name else ""
        elif "last" in field_lower and "name" in field_lower:
            return self.name.split()[-1] if self.name else ""
        elif "name" in field_lower:
            return self.name
        elif "address" in field_lower:
            return personal.get("address", "")
        elif "city" in field_lower:
            return personal.get("city", "")
        elif "linkedin" in field_lower:
            return personal.get("linkedin", "")

        return ""


class MemoryManager:
    """Manages agent memory for learning"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        try:
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except:
            return {
                "pages_seen": {},
                "successful_actions": [],
                "failed_actions": [],
                "signed_in": False
            }

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass

    def remember_page(self, url: str, action: str, success: bool):
        if url not in self.data["pages_seen"]:
            self.data["pages_seen"][url] = []
        self.data["pages_seen"][url].append({
            "action": action,
            "success": success
        })
        self.save()

    def set_signed_in(self):
        self.data["signed_in"] = True
        self.save()

    @property
    def is_signed_in(self) -> bool:
        return self.data.get("signed_in", False)


class PageAnalyzer:
    """Analyzes web pages to understand their structure"""

    def __init__(self, driver):
        self.driver = driver

    def analyze(self) -> PageState:
        """Analyze current page and return its state"""
        elements = self._get_elements()
        page_type = self._determine_type(elements)
        has_modal = self._check_modal()
        form_filled = self._check_form_filled(elements)

        return PageState(
            url=self.driver.current_url,
            type=page_type,
            elements=elements,
            has_modal=has_modal,
            form_filled=form_filled
        )

    def _get_elements(self) -> PageElements:
        """Extract all relevant elements from page"""
        elements = PageElements()

        try:
            # Email fields
            elements.email_fields = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='email'], input[name*='email'], input[id*='email']"
            )

            # Password fields
            elements.password_fields = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='password']"
            )

            # Text inputs
            elements.text_inputs = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='text'], textarea, select"
            )

            # Buttons
            all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
            elements.buttons = [btn for btn in all_buttons if btn.is_displayed()]

            # Forms
            elements.forms = self.driver.find_elements(By.TAG_NAME, "form")

        except:
            pass

        return elements

    def _determine_type(self, elements: PageElements) -> PageType:
        """Determine what type of page this is"""
        # Sign-in page detection
        if elements.password_fields and any(p.is_displayed() for p in elements.password_fields):
            return PageType.SIGN_IN

        # Application form detection
        if len(elements.text_inputs) > 3:
            return PageType.APPLICATION_FORM

        # Confirmation page
        if "success" in self.driver.current_url.lower() or "thank" in self.driver.title.lower():
            return PageType.CONFIRMATION

        return PageType.UNKNOWN

    def _check_modal(self) -> bool:
        """Check if there's a modal dialog"""
        try:
            modals = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[role='dialog'], [aria-modal='true'], .modal"
            )
            return any(m.is_displayed() for m in modals)
        except:
            return False

    def _check_form_filled(self, elements: PageElements) -> bool:
        """Check if form fields have values"""
        if elements.email_fields:
            for field in elements.email_fields:
                if field.get_attribute("value"):
                    return True
        return False


class ActionExecutor:
    """Executes actions on web pages"""

    def __init__(self, driver, resume: ResumeManager):
        self.driver = driver
        self.resume = resume
        self.wait = WebDriverWait(driver, Config.MAX_WAIT)

    def sign_in(self, state: PageState) -> bool:
        """Handle sign-in process"""
        print("🔐 Signing in...")

        # Fill email
        for field in state.elements.email_fields:
            try:
                field.clear()
                field.send_keys(self.resume.email)
                print(f"  ✓ Email entered: {self.resume.email}")
                break
            except:
                continue

        # Fill password
        for field in state.elements.password_fields:
            try:
                field.clear()
                field.send_keys(self.resume.password)
                print("  ✓ Password entered")

                # Submit immediately after filling password
                field.send_keys(Keys.RETURN)
                print("  ✓ Submitted with Enter key")
                time.sleep(3)
                return True
            except:
                continue

        # Fallback: click submit button
        return self._click_button(["sign in", "log in", "submit"])

    def fill_form(self, state: PageState) -> bool:
        """Fill application form fields"""
        print("📝 Filling application form...")
        filled_any = False

        for field in state.elements.text_inputs:
            try:
                if not field.is_displayed() or field.get_attribute("value"):
                    continue

                field_name = field.get_attribute("name") or field.get_attribute("id") or ""
                value = self.resume.get_field_value(field_name)

                if value:
                    field.clear()
                    field.send_keys(value)
                    print(f"  ✓ Filled {field_name}: {value[:30]}")
                    filled_any = True
            except:
                continue

        return filled_any

    def click_next(self) -> bool:
        """Click next/continue/submit button"""
        priority_texts = [
            ["apply", "start application"],
            ["next", "continue", "proceed"],
            ["submit", "send", "finish"],
            ["save", "review"]
        ]

        for button_texts in priority_texts:
            if self._click_button(button_texts):
                return True

        # Fallback: click any visible button
        return self._click_any_button()

    def _click_button(self, target_texts: List[str]) -> bool:
        """Click button with specific text"""
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")

            for btn in buttons:
                if not btn.is_displayed():
                    continue

                btn_text = (btn.text or btn.get_attribute("value") or "").lower()

                for target in target_texts:
                    if target in btn_text:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        self.driver.execute_script("arguments[0].click();", btn)
                        print(f"  ✓ Clicked: {btn.text or 'button'}")
                        time.sleep(2)
                        return True
        except:
            pass

        return False

    def _click_any_button(self) -> bool:
        """Click any visible button as last resort"""
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if btn.is_displayed() and btn.text:
                    self.driver.execute_script("arguments[0].click();", btn)
                    print(f"  ✓ Clicked: {btn.text[:30]}")
                    return True
        except:
            pass
        return False


class JobApplicationAgent:
    """Main agent that orchestrates the application process"""

    def __init__(self):
        self.resume = ResumeManager(Config.RESUME_FILE)
        self.memory = MemoryManager(Config.MEMORY_FILE)
        self.driver = self._create_driver()
        self.analyzer = PageAnalyzer(self.driver)
        self.executor = ActionExecutor(self.driver, self.resume)
        self.stuck_counter = 0
        self.last_url = ""

    def _create_driver(self):
        """Create Chrome driver with optimal settings"""
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Disable images for faster loading (optional)
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        return webdriver.Chrome(options=options)

    def apply_to_job(self, job_url: str):
        """Main method to apply to a job"""
        print(f"\n🚀 Starting application for: {self.resume.name}")
        print(f"📧 Email: {self.resume.email}\n")

        try:
            # Navigate to job
            self.driver.get(job_url)
            time.sleep(Config.PAGE_LOAD_WAIT)

            # Main application loop
            for step in range(1, Config.MAX_STEPS + 1):
                print(f"\n{'='*50}")
                print(f"Step {step}")
                print(f"{'='*50}")

                # Check if stuck
                if self._is_stuck():
                    if not self._recover_from_stuck():
                        print("❌ Unable to recover from stuck state")
                        break

                # Analyze current page
                state = self.analyzer.analyze()
                print(f"📍 Page type: {state.type.value}")
                print(f"🔗 URL: {state.url[:80]}")

                # Execute appropriate action
                success = self._execute_step(state)

                # Record in memory
                self.memory.remember_page(state.url, state.type.value, success)

                # Check if complete
                if state.type == PageType.CONFIRMATION:
                    print("\n🎉 Application submitted successfully!")
                    break

                # Brief pause
                time.sleep(1)

        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            self.cleanup()

    def _execute_step(self, state: PageState) -> bool:
        """Execute appropriate action based on page state"""

        # Priority 1: Handle sign-in
        if state.type == PageType.SIGN_IN:
            if not state.form_filled:
                return self.executor.sign_in(state)
            else:
                # Form filled, force submit
                print("⚠️ Form filled but not submitted, forcing submit...")
                return self.executor._click_button(["sign", "submit", "continue"])

        # Priority 2: Handle application form
        if state.type == PageType.APPLICATION_FORM:
            # First fill the form
            if self.executor.fill_form(state):
                time.sleep(1)
            # Then try to progress
            return self.executor.click_next()

        # Priority 3: Try to find next action
        return self.executor.click_next()

    def _is_stuck(self) -> bool:
        """Check if we're stuck on the same page"""
        current_url = self.driver.current_url

        if current_url == self.last_url:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
            self.last_url = current_url

        return self.stuck_counter >= Config.STUCK_THRESHOLD

    def _recover_from_stuck(self) -> bool:
        """Try to recover from being stuck"""
        print("🔄 Attempting recovery...")

        # Try clicking any button
        if self.executor._click_any_button():
            self.stuck_counter = 0
            return True

        # Try pressing Escape to close modals
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
            return True
        except:
            pass

        return False

    def cleanup(self):
        """Clean up resources"""
        try:
            self.memory.save()
            self.driver.quit()
            print("\n✅ Session ended cleanly")
        except:
            pass


# ============= Main Entry Point =============
def main():
    """Main entry point"""
    print("\n" + "="*60)
    print(" JOB APPLICATION AUTOMATION - Clean Architecture")
    print("="*60)

    # Job URL (can be passed as parameter or configured)
    job_url = "https://fractal.wd1.myworkdayjobs.com/en-US/Careers/job/Bengaluru/GCP-Engineer_SR-20029/apply/autofillWithResume?source=LinkedIn"

    # Create and run agent
    agent = JobApplicationAgent()
    agent.apply_to_job(job_url)


if __name__ == "__main__":
    main()
