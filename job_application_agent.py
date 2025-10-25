"""
AI-Powered Job Application Agent
Automatically fills job applications using Selenium and AI
"""

import json
import logging
import time
import os
import re
import pickle
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import base64

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)

import openai
from anthropic import Anthropic
import google.generativeai as genai
import requests


@dataclass
class UserProfile:
    """Stores user information for job applications"""
    email: str
    password: str
    first_name: str
    last_name: str
    phone: str
    address: str
    city: str
    state: str
    zip_code: str
    country: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    current_company: str
    current_title: str
    years_experience: int
    education: List[Dict[str, str]]
    skills: List[str]
    resume_path: str
    photo_path: str
    cover_letter_template: str
    additional_info: Dict[str, Any]


class AIProvider:
    """Abstraction for different AI providers"""

    def __init__(self, provider: str = "openai", api_key: str = None, base_url: str = None, model: str = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model

        if provider == "openai":
            openai.api_key = api_key
            self.client = openai
        elif provider == "anthropic":
            self.client = Anthropic(api_key=api_key)
        elif provider == "gemini":
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        elif provider == "ollama":
            self.base_url = base_url or "http://localhost:11434"
            self.model_name = model or "gpt-oss:120B-cloud"

    def analyze_page(self, html: str, task: str) -> Dict:
        """Analyze page HTML and return structured insights"""
        prompt = f"""
        Analyze this HTML and {task}:

        HTML: {html[:5000]}

        Return a JSON response with:
        1. Page type (login, signup, application_form, etc.)
        2. Relevant form fields found
        3. Required actions
        4. Any error messages or warnings
        """

        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            return json.loads(response.content[0].text)

        elif self.provider == "gemini":
            response = self.model.generate_content(prompt)
            return json.loads(response.text)

        elif self.provider == "ollama":
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt + "\nRespond ONLY with valid JSON, no additional text.",
                    "stream": False,
                    "format": "json"
                }
            )
            if response.status_code == 200:
                result = response.json()
                try:
                    return json.loads(result.get("response", "{}"))
                except json.JSONDecodeError:
                    # Fallback parsing if response isn't clean JSON
                    text = result.get("response", "{}")
                    # Try to extract JSON from the response
                    import re
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    return {}
            return {}

    def map_fields(self, form_fields: List, user_data: Dict) -> Dict:
        """Map form fields to user data intelligently"""
        prompt = f"""
        Map these form fields to user data:

        Form Fields: {json.dumps(form_fields)}
        User Data: {json.dumps(user_data)}

        Return JSON mapping of field_id/name to the appropriate user data value.
        Handle variations in field naming intelligently.
        """

        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

        elif self.provider == "ollama":
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt + "\nRespond ONLY with valid JSON mapping, no additional text.",
                    "stream": False,
                    "format": "json"
                }
            )
            if response.status_code == 200:
                result = response.json()
                try:
                    return json.loads(result.get("response", "{}"))
                except json.JSONDecodeError:
                    text = result.get("response", "{}")
                    import re
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    return {}

        return {}


class LearningMemory:
    """Persistent memory system for learning from past interactions"""

    def __init__(self, memory_file: str = "agent_memory.json"):
        self.memory_file = memory_file
        self.memory = self._load_memory()

    def _load_memory(self) -> Dict:
        """Load memory from file"""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        return {
            "successful_patterns": {},
            "failed_patterns": {},
            "field_mappings": {},
            "portal_signatures": {},
            "retry_strategies": []
        }

    def save_memory(self):
        """Persist memory to file"""
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)

    def record_success(self, url: str, strategy: Dict):
        """Record successful application strategy"""
        domain = self._extract_domain(url)
        if domain not in self.memory["successful_patterns"]:
            self.memory["successful_patterns"][domain] = []
        self.memory["successful_patterns"][domain].append({
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy
        })
        self.save_memory()

    def record_failure(self, url: str, error: str, context: Dict):
        """Record failed attempt for learning"""
        domain = self._extract_domain(url)
        if domain not in self.memory["failed_patterns"]:
            self.memory["failed_patterns"][domain] = []
        self.memory["failed_patterns"][domain].append({
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "context": context
        })
        self.save_memory()

    def get_portal_strategy(self, url: str) -> Optional[Dict]:
        """Retrieve successful strategies for a portal"""
        domain = self._extract_domain(url)
        if domain in self.memory["successful_patterns"]:
            return self.memory["successful_patterns"][domain][-1]["strategy"]
        return None

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        return urlparse(url).netloc


class JobApplicationAgent:
    """Main agent for automated job applications"""

    def __init__(self, user_profile: UserProfile, ai_provider: AIProvider,
                 headless: bool = False, debug: bool = True):
        self.profile = user_profile
        self.ai = ai_provider
        self.memory = LearningMemory()
        self.debug = debug
        self.setup_logging()
        self.driver = self.setup_driver(headless)
        self.wait = WebDriverWait(self.driver, 10)
        self.max_retries = 3
        self.current_attempt = 0

    def setup_logging(self):
        """Configure logging"""
        log_dir = Path("agent_logs")
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.DEBUG if self.debug else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f"agent_{datetime.now():%Y%m%d_%H%M%S}.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_driver(self, headless: bool) -> webdriver.Chrome:
        """Setup Chrome driver with options"""
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Add user agent to appear more human-like
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def apply_to_job(self, job_url: str) -> bool:
        """Main method to apply to a job"""
        self.logger.info(f"Starting application for: {job_url}")

        try:
            # Check if we have a successful strategy for this portal
            existing_strategy = self.memory.get_portal_strategy(job_url)
            if existing_strategy:
                self.logger.info("Using learned strategy from previous successful application")
                return self._execute_strategy(job_url, existing_strategy)

            # Navigate to job URL
            self.driver.get(job_url)
            time.sleep(3)  # Wait for page load

            # Analyze the page
            page_analysis = self._analyze_current_page()

            # Determine action based on page type
            if page_analysis["page_type"] == "login":
                self._handle_login(page_analysis)
            elif page_analysis["page_type"] == "signup":
                self._handle_signup(page_analysis)
            elif page_analysis["page_type"] == "application_form":
                self._fill_application_form(page_analysis)

            # Record success
            self.memory.record_success(job_url, {
                "steps": self._get_recorded_steps(),
                "page_analysis": page_analysis
            })

            self.logger.info("Application submitted successfully!")
            return True

        except Exception as e:
            self.logger.error(f"Application failed: {str(e)}")
            self.memory.record_failure(job_url, str(e), {
                "current_url": self.driver.current_url,
                "page_source_snippet": self.driver.page_source[:1000]
            })

            if self.current_attempt < self.max_retries:
                self.current_attempt += 1
                self.logger.info(f"Retrying... Attempt {self.current_attempt}/{self.max_retries}")
                time.sleep(5)
                return self.apply_to_job(job_url)

            return False

    def _analyze_current_page(self) -> Dict:
        """Analyze current page using AI"""
        page_html = self.driver.page_source

        # Use AI to understand the page
        analysis = self.ai.analyze_page(
            page_html,
            "identify the page type and form fields for job application"
        )

        # Enhance with Selenium detection
        analysis["detected_elements"] = self._detect_form_elements()

        return analysis

    def _detect_form_elements(self) -> Dict:
        """Detect form elements on the page"""
        elements = {
            "inputs": [],
            "selects": [],
            "textareas": [],
            "buttons": [],
            "file_uploads": []
        }

        # Find all input elements
        for input_elem in self.driver.find_elements(By.TAG_NAME, "input"):
            elem_info = {
                "id": input_elem.get_attribute("id"),
                "name": input_elem.get_attribute("name"),
                "type": input_elem.get_attribute("type"),
                "placeholder": input_elem.get_attribute("placeholder"),
                "required": input_elem.get_attribute("required"),
                "visible": input_elem.is_displayed()
            }

            if elem_info["type"] == "file":
                elements["file_uploads"].append(elem_info)
            else:
                elements["inputs"].append(elem_info)

        # Find select elements
        for select_elem in self.driver.find_elements(By.TAG_NAME, "select"):
            elements["selects"].append({
                "id": select_elem.get_attribute("id"),
                "name": select_elem.get_attribute("name"),
                "visible": select_elem.is_displayed()
            })

        # Find textareas
        for textarea in self.driver.find_elements(By.TAG_NAME, "textarea"):
            elements["textareas"].append({
                "id": textarea.get_attribute("id"),
                "name": textarea.get_attribute("name"),
                "placeholder": textarea.get_attribute("placeholder"),
                "visible": textarea.is_displayed()
            })

        # Find buttons
        for button in self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']"):
            elements["buttons"].append({
                "text": button.text,
                "type": button.get_attribute("type"),
                "visible": button.is_displayed()
            })

        return elements

    def _handle_login(self, page_analysis: Dict):
        """Handle login page"""
        self.logger.info("Handling login page")

        # Map fields using AI
        field_mapping = self.ai.map_fields(
            page_analysis["detected_elements"]["inputs"],
            {"email": self.profile.email, "password": self.profile.password}
        )

        # Fill login form
        for field_id, value in field_mapping.items():
            try:
                element = self._find_element_smart(field_id)
                self._safe_send_keys(element, value)
            except Exception as e:
                self.logger.warning(f"Could not fill field {field_id}: {e}")

        # Submit form
        self._submit_form()
        time.sleep(3)

    def _handle_signup(self, page_analysis: Dict):
        """Handle signup page"""
        self.logger.info("Handling signup page")

        user_data = {
            "email": self.profile.email,
            "password": self.profile.password,
            "first_name": self.profile.first_name,
            "last_name": self.profile.last_name,
            "phone": self.profile.phone
        }

        # Map and fill fields
        field_mapping = self.ai.map_fields(
            page_analysis["detected_elements"]["inputs"],
            user_data
        )

        for field_id, value in field_mapping.items():
            try:
                element = self._find_element_smart(field_id)
                self._safe_send_keys(element, value)
            except Exception as e:
                self.logger.warning(f"Could not fill field {field_id}: {e}")

        # Handle checkboxes (terms, privacy policy, etc.)
        self._handle_checkboxes()

        # Submit form
        self._submit_form()
        time.sleep(3)

    def _fill_application_form(self, page_analysis: Dict):
        """Fill the main application form"""
        self.logger.info("Filling application form")

        # Prepare comprehensive user data
        user_data = asdict(self.profile)

        # Map fields using AI
        all_fields = (
            page_analysis["detected_elements"]["inputs"] +
            page_analysis["detected_elements"]["textareas"] +
            page_analysis["detected_elements"]["selects"]
        )

        field_mapping = self.ai.map_fields(all_fields, user_data)

        # Fill text fields
        for field_id, value in field_mapping.items():
            try:
                element = self._find_element_smart(field_id)

                # Check if it's a select element
                if element.tag_name == "select":
                    self._handle_select(element, value)
                else:
                    self._safe_send_keys(element, value)

            except Exception as e:
                self.logger.warning(f"Could not fill field {field_id}: {e}")

        # Handle file uploads
        self._handle_file_uploads(page_analysis["detected_elements"]["file_uploads"])

        # Handle checkboxes
        self._handle_checkboxes()

        # Submit application
        self._submit_form()

    def _find_element_smart(self, identifier: str):
        """Smart element finder using multiple strategies"""
        strategies = [
            (By.ID, identifier),
            (By.NAME, identifier),
            (By.CSS_SELECTOR, f"[name='{identifier}']"),
            (By.CSS_SELECTOR, f"[id='{identifier}']"),
            (By.XPATH, f"//input[@name='{identifier}']"),
            (By.XPATH, f"//input[@id='{identifier}']"),
            (By.XPATH, f"//textarea[@name='{identifier}']"),
            (By.XPATH, f"//select[@name='{identifier}']")
        ]

        for by, value in strategies:
            try:
                element = self.wait.until(EC.presence_of_element_located((by, value)))
                if element.is_displayed():
                    return element
            except:
                continue

        raise NoSuchElementException(f"Could not find element: {identifier}")

    def _safe_send_keys(self, element, value):
        """Safely send keys to element with retry logic"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Clear field first
                element.clear()
                time.sleep(0.5)

                # Type character by character to appear more human
                for char in str(value):
                    element.send_keys(char)
                    time.sleep(0.05)  # Small delay between keystrokes

                return
            except StaleElementReferenceException:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    element = self._find_element_smart(element.get_attribute("id") or element.get_attribute("name"))
                else:
                    raise

    def _handle_select(self, element, value):
        """Handle select dropdown"""
        select = Select(element)

        # Try different strategies to select the right option
        try:
            select.select_by_value(str(value))
        except:
            try:
                select.select_by_visible_text(str(value))
            except:
                # Select first matching option
                for option in select.options:
                    if str(value).lower() in option.text.lower():
                        select.select_by_visible_text(option.text)
                        break

    def _handle_file_uploads(self, file_fields: List[Dict]):
        """Handle file upload fields"""
        for field in file_fields:
            if not field["visible"]:
                continue

            # Determine file type from field attributes
            field_text = (field.get("name", "") + field.get("id", "")).lower()

            if "resume" in field_text or "cv" in field_text:
                file_path = self.profile.resume_path
            elif "photo" in field_text or "picture" in field_text or "image" in field_text:
                file_path = self.profile.photo_path
            else:
                continue

            if file_path and os.path.exists(file_path):
                try:
                    element = self._find_element_smart(field["id"] or field["name"])
                    element.send_keys(os.path.abspath(file_path))
                    self.logger.info(f"Uploaded file: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Could not upload file: {e}")

    def _handle_checkboxes(self):
        """Handle checkboxes (agree to terms, etc.)"""
        checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")

        for checkbox in checkboxes:
            try:
                # Check if it's a required checkbox or terms agreement
                parent_text = checkbox.find_element(By.XPATH, "..").text.lower()
                if any(term in parent_text for term in ["agree", "terms", "privacy", "consent"]):
                    if not checkbox.is_selected():
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        self.logger.info("Checked agreement checkbox")
            except:
                pass

    def _submit_form(self):
        """Submit the current form"""
        # Try different methods to submit
        submit_buttons = self.driver.find_elements(By.CSS_SELECTOR,
            "button[type='submit'], input[type='submit'], button:contains('Submit'), button:contains('Apply')")

        for button in submit_buttons:
            if button.is_displayed():
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                    self.logger.info("Form submitted")
                    return
                except:
                    pass

        # Fallback: submit using Enter key
        active_element = self.driver.switch_to.active_element
        active_element.send_keys(Keys.RETURN)

    def _execute_strategy(self, job_url: str, strategy: Dict) -> bool:
        """Execute a learned strategy"""
        try:
            self.driver.get(job_url)
            time.sleep(3)

            for step in strategy.get("steps", []):
                self._execute_step(step)

            return True
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {e}")
            return False

    def _execute_step(self, step: Dict):
        """Execute a single step from strategy"""
        action = step.get("action")

        if action == "fill_field":
            element = self._find_element_smart(step["field_id"])
            self._safe_send_keys(element, step["value"])
        elif action == "click":
            element = self._find_element_smart(step["element_id"])
            element.click()
        elif action == "wait":
            time.sleep(step.get("duration", 2))

    def _get_recorded_steps(self) -> List[Dict]:
        """Get recorded steps for learning (simplified)"""
        # This would be enhanced to actually track all actions
        return [{"action": "automated_fill", "timestamp": datetime.now().isoformat()}]

    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        self.memory.save_memory()


def main():
    """Example usage"""
    # Load user profile
    profile = UserProfile(
        email="your.email@example.com",
        password="your_password",
        first_name="John",
        last_name="Doe",
        phone="+1234567890",
        address="123 Main St",
        city="San Francisco",
        state="CA",
        zip_code="94105",
        country="USA",
        linkedin_url="https://linkedin.com/in/johndoe",
        github_url="https://github.com/johndoe",
        portfolio_url="https://johndoe.com",
        current_company="Tech Corp",
        current_title="Software Engineer",
        years_experience=5,
        education=[
            {
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "school": "University of California",
                "year": "2018"
            }
        ],
        skills=["Python", "JavaScript", "React", "AWS", "Docker"],
        resume_path="/path/to/resume.pdf",
        photo_path="/path/to/photo.jpg",
        cover_letter_template="I am excited to apply for this position...",
        additional_info={}
    )

    # Initialize AI provider
    ai_provider = AIProvider(provider="openai", api_key="your-api-key")

    # Create agent
    agent = JobApplicationAgent(profile, ai_provider, headless=False, debug=True)

    try:
        # Apply to job
        job_url = "https://example.com/careers/software-engineer"
        success = agent.apply_to_job(job_url)

        if success:
            print("Application submitted successfully!")
        else:
            print("Application failed. Check logs for details.")

    finally:
        agent.close()


if __name__ == "__main__":
    main()
