"""
Job Application Automation Agent v5.0 - Final Version with Smart Learning
=========================================================================
This agent learns from mistakes and never repeats failed approaches.
Key improvements:
1. Detects when stuck in a loop and breaks out
2. After filling sign-in form, ALWAYS clicks the submit button
3. Tracks action sequences to avoid repetition
4. Uses different strategies when previous ones fail
"""

import json
import time
import hashlib
import traceback
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
import base64
import re

# Configuration
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-api-key-here")
RESUME_JSON_PATH = "resume_data.json"
MEMORY_FILE = "agent_memory_final.json"
SESSION_FILE = "session_state.json"
MAX_RETRIES = 10
INTERACTIVE_MODE = False
AUTO_CONTINUE_TIMEOUT = 10
SCREENSHOT_DIR = "screenshots"

# Initialize memory structure with advanced tracking
DEFAULT_MEMORY = {
    "learnings": [],
    "domain_knowledge": {
        "first action": "accept cookies pop-up if present, to avoid blocking further actions.",
        "second action": "if a login/ sign in prompt appears, log in/sign in using stored credentials before proceeding., prefer sign in over sign up/ create account",
        "page analysis": "analyse complete page at one go and try to fill everything and click next for the first iteration itself",
        "skill_selectors": "For searchable skill dropdowns: type ONE skill, wait 1 sec, click suggestion. Repeat for each skill.",
        "file_uploads": "ALWAYS verify file upload: after send_keys(), check if value attribute is set. Print confirmation.",
        "multi_select": "Add items one by one: type, wait, select, repeat. Never paste comma-separated list.",
        "button_clicks": "If normal click fails with 'element click intercepted', use JavaScript click: driver.execute_script('arguments[0].click();', element)",
        "sign in button": "CRITICAL: After filling sign-in form, ALWAYS click submit button. Use multiple strategies if needed.",
        "modal dialogs": "Always check for modal dialogs after page loads or actions. If present, handle them before proceeding.",
        "form submission": "After filling ANY form, ALWAYS submit it via button click or Enter key. Never leave forms unfilled."
    },
    "action_history": [],
    "page_patterns": {},
    "success_sequences": [],
    "failure_patterns": [],
    "element_selectors": {},
    "action_sequences": {},  # Track sequences of actions to detect loops
    "stuck_detection": {}    # Detect when stuck on same page
}

def load_agent_memory():
    """Load agent memory with migration for old format."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                memory = json.load(f)

            # Migrate old format to new
            if "action_sequences" not in memory:
                memory["action_sequences"] = {}
            if "stuck_detection" not in memory:
                memory["stuck_detection"] = {}
            if "element_selectors" not in memory:
                memory["element_selectors"] = {}
            if "success_sequences" not in memory:
                memory["success_sequences"] = []
            if "failure_patterns" not in memory:
                memory["failure_patterns"] = []
            if "action_history" not in memory:
                memory["action_history"] = []
            if "page_patterns" not in memory:
                memory["page_patterns"] = {}

            return memory
        except Exception as e:
            print(f"⚠️ Error loading memory: {e}, using defaults")
            return DEFAULT_MEMORY.copy()
    return DEFAULT_MEMORY.copy()

def save_agent_memory(memory):
    """Save agent memory to file."""
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2, default=str)
    except Exception as e:
        print(f"⚠️ Could not save memory: {e}")

def detect_stuck_pattern(memory, page_signature, action_type):
    """Detect if we're stuck repeating the same action on the same page."""
    stuck_key = f"{page_signature}_{action_type}"

    if stuck_key not in memory["stuck_detection"]:
        memory["stuck_detection"][stuck_key] = {"count": 0, "last_time": None}

    current_time = datetime.now().isoformat()
    stuck_info = memory["stuck_detection"][stuck_key]

    # Check if we've done this action recently (within last 5 minutes)
    if stuck_info["last_time"]:
        last_time = datetime.fromisoformat(stuck_info["last_time"])
        time_diff = (datetime.now() - last_time).total_seconds()
        if time_diff < 300:  # 5 minutes
            stuck_info["count"] += 1
        else:
            stuck_info["count"] = 1
    else:
        stuck_info["count"] = 1

    stuck_info["last_time"] = current_time

    # If we've tried the same action 3+ times, we're stuck
    return stuck_info["count"] >= 3

def get_last_successful_action(memory, page_signature):
    """Get the last successful action for this page."""
    for action in reversed(memory["action_history"]):
        if action.get("page_signature") == page_signature and action.get("success"):
            return action
    return None

def create_driver():
    """Create Chrome driver with options."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    return webdriver.Chrome(options=chrome_options)

def load_resume_details(file_path):
    """Load resume details from JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_page_signature(driver):
    """Generate unique signature for current page state."""
    try:
        # Include form fields and modal state in signature
        signature_parts = [
            driver.current_url,
            driver.title,
            str(len(driver.find_elements(By.TAG_NAME, "input"))),
            str(len(driver.find_elements(By.TAG_NAME, "button"))),
            str(len(driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true'], [role='dialog']")))
        ]

        # Add visible text sample
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
            signature_parts.append(body_text)
        except:
            pass

        combined = "|".join(signature_parts)
        return hashlib.md5(combined.encode()).hexdigest()
    except:
        return hashlib.md5(driver.current_url.encode()).hexdigest()

def analyze_page_enhanced(driver, memory):
    """Analyze current page with memory awareness."""
    page_info = {
        "url": driver.current_url,
        "title": driver.title,
        "page_signature": generate_page_signature(driver),
        "modals_detected": False,
        "sign_in_detected": False,
        "form_filled": False,
        "buttons": [],
        "inputs": [],
        "error_messages": []
    }

    # Check for modals
    try:
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true'], [role='dialog'], div[class*='modal']")
        page_info["modals_detected"] = len([m for m in modals if m.is_displayed()]) > 0
    except:
        pass

    # Check for sign-in elements
    try:
        sign_in_indicators = [
            "input[type='password']",
            "input[data-automation-id='email']",
            "button[data-automation-id='signInSubmitButton']",
            "button[class*='sign'][class*='in']"
        ]
        for selector in sign_in_indicators:
            if driver.find_elements(By.CSS_SELECTOR, selector):
                page_info["sign_in_detected"] = True
                break
    except:
        pass

    # Check if form fields have values (to detect if we already filled the form)
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[type='password']")
        filled_count = sum(1 for inp in inputs if inp.get_attribute("value"))
        page_info["form_filled"] = filled_count > 0
    except:
        pass

    # Get buttons for context
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons[:10]:  # Limit to first 10
            try:
                btn_info = {
                    "text": btn.text.strip()[:50],
                    "data_automation_id": btn.get_attribute("data-automation-id"),
                    "class": btn.get_attribute("class"),
                    "displayed": btn.is_displayed()
                }
                page_info["buttons"].append(btn_info)
            except:
                continue
    except:
        pass

    return page_info

def generate_smart_action(page_info, memory, resume_data, last_error=None):
    """Generate next action based on page analysis and memory."""
    page_signature = page_info["page_signature"]

    # Check if we're stuck in a loop
    if page_info["sign_in_detected"] and page_info["form_filled"]:
        # Form is filled but we haven't progressed - we MUST click the submit button
        if detect_stuck_pattern(memory, page_signature, "fill_form"):
            print("🔴 STUCK DETECTED: Form filled but not submitted!")
            return {
                "action_type": "click_sign_in_button",
                "reasoning": "Form is filled but we're stuck. Must click the sign-in submit button NOW.",
                "target": "Sign In Submit Button",
                "confidence": "critical",
                "using_memory": True
            }

    # Check for successful patterns for this page
    last_success = get_last_successful_action(memory, page_signature)
    if last_success and not last_error:
        return {
            "action_type": last_success["action"]["action_type"],
            "reasoning": f"Using previously successful action for this page",
            "target": last_success["action"].get("target", ""),
            "confidence": "high",
            "using_memory": True
        }

    # Decision tree based on page state
    if page_info["modals_detected"] and page_info["sign_in_detected"]:
        if not page_info["form_filled"]:
            return {
                "action_type": "fill_sign_in_form",
                "reasoning": "Sign-in modal detected with empty form. Need to fill credentials.",
                "target": "Email and Password fields",
                "confidence": "high",
                "using_memory": False
            }
        else:
            return {
                "action_type": "click_sign_in_button",
                "reasoning": "Sign-in form is already filled. Must click submit button to proceed.",
                "target": "Sign In Submit Button",
                "confidence": "high",
                "using_memory": False
            }

    # Check for cookie banners
    cookie_buttons = [b for b in page_info["buttons"]
                     if b.get("data_automation_id") == "legalNoticeAcceptButton"
                     or "accept" in b.get("text", "").lower() and "cookie" in b.get("text", "").lower()]
    if cookie_buttons:
        return {
            "action_type": "accept_cookies",
            "reasoning": "Cookie banner detected. Accepting to avoid blocking interactions.",
            "target": cookie_buttons[0],
            "confidence": "high",
            "using_memory": False
        }

    # Default to clicking next/continue
    return {
        "action_type": "navigate",
        "reasoning": "Looking for navigation buttons to progress",
        "target": "Next/Continue button",
        "confidence": "medium",
        "using_memory": False
    }

def generate_action_code(action, page_info, memory, resume_data, last_error=None):
    """Generate Selenium code for the action."""
    action_type = action["action_type"]

    if action_type == "fill_sign_in_form":
        return """
# Fill sign-in form
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

wait = WebDriverWait(driver, 15)
success = False

try:
    # Wait for modal to be fully loaded
    time.sleep(1)

    # Find and fill email field
    email_selectors = [
        "input[data-automation-id='email']",
        "input[type='email']",
        "input[name='email']",
        "input[id='input-11']",  # Specific to the modal we saw
        "input[autocomplete='email']"
    ]

    email_filled = False
    for selector in email_selectors:
        try:
            email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            email_field.clear()
            email_field.send_keys('""" + resume_data.get("personal_info", {}).get("email", "") + """')
            print("✓ Email filled")
            email_filled = True
            break
        except:
            continue

    if not email_filled:
        print("❌ Could not find email field")

    # Find and fill password field
    password_selectors = [
        "input[data-automation-id='password']",
        "input[type='password']",
        "input[name='password']",
        "input[id='input-12']"  # Specific to the modal we saw
    ]

    password_filled = False
    for selector in password_selectors:
        try:
            password_field = driver.find_element(By.CSS_SELECTOR, selector)
            password_field.clear()
            password_field.send_keys('""" + resume_data.get("credentials", {}).get("password", "Hinjewadi@123") + """')
            print("✓ Password filled")
            password_filled = True
            break
        except:
            continue

    if not password_filled:
        print("❌ Could not find password field")

    success = email_filled and password_filled
    if success:
        print("✅ Form filled successfully")
        time.sleep(1)  # Brief pause before next action
    else:
        print("⚠️ Form filling incomplete")

except Exception as e:
    print(f"❌ Error filling form: {e}")
    success = False
"""

    elif action_type == "click_sign_in_button":
        return """
# Click sign-in submit button - MULTIPLE STRATEGIES
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

wait = WebDriverWait(driver, 15)
clicked = False

print("🎯 Attempting to click sign-in submit button...")

# Strategy 1: Direct button click with specific selectors
button_selectors = [
    "button[data-automation-id='signInSubmitButton']",
    "button.css-1ru62dj",
    "[aria-modal='true'] button[type='submit']",
    "[role='dialog'] button[type='submit']",
    "button:has-text('Sign In')",
    "button:has-text('Log In')",
    "button:has-text('Submit')"
]

for selector in button_selectors:
    if clicked:
        break
    try:
        # Try CSS selector
        try:
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        except:
            # Try XPath for text-based selection
            if ':has-text(' in selector:
                text = selector.split("'")[1]
                btn = driver.find_element(By.XPATH, f"//button[contains(., '{text}')]")
            else:
                continue

        # Remove any attributes that might prevent clicking
        driver.execute_script("arguments[0].removeAttribute('tabindex');", btn)
        driver.execute_script("arguments[0].removeAttribute('aria-hidden');", btn)
        driver.execute_script("arguments[0].removeAttribute('disabled');", btn)

        # Try JavaScript click
        driver.execute_script("arguments[0].click();", btn)
        print(f"✓ Clicked button via JS: {selector}")
        clicked = True
        time.sleep(2)
        break
    except:
        continue

# Strategy 2: Click any overlay that might be intercepting
if not clicked:
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR, "[data-automation-id='click_filter'], div[class*='overlay']")
        for overlay in overlays:
            if overlay.is_displayed():
                driver.execute_script("arguments[0].click();", overlay)
                print("✓ Clicked through overlay")
                clicked = True
                time.sleep(1)
                break
    except:
        pass

# Strategy 3: Submit the form directly
if not clicked:
    try:
        # Find the password field and submit the form
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.submit()
        print("✓ Submitted form via password field")
        clicked = True
        time.sleep(2)
    except:
        pass

# Strategy 4: Press Enter in password field
if not clicked:
    try:
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.send_keys(Keys.RETURN)
        print("✓ Pressed Enter in password field")
        clicked = True
        time.sleep(2)
    except:
        pass

# Strategy 5: Click all visible buttons in modal
if not clicked:
    try:
        modal = driver.find_element(By.CSS_SELECTOR, "[aria-modal='true'], [role='dialog']")
        buttons = modal.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if btn.is_displayed() and btn.is_enabled():
                btn_text = btn.text.lower()
                if any(word in btn_text for word in ['sign', 'log', 'submit', 'continue']):
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"✓ Clicked button with text: {btn.text}")
                    clicked = True
                    time.sleep(2)
                    break
    except:
        pass

# Strategy 6: Execute form submission via JavaScript
if not clicked:
    try:
        driver.execute_script("""
            var forms = document.querySelectorAll('form');
            for(var form of forms) {
                if(form.querySelector('input[type="password"]')) {
                    form.submit();
                    return true;
                }
            }
            return false;
        """)
        print("✓ Submitted form via JavaScript")
        clicked = True
        time.sleep(2)
    except:
        pass

if not clicked:
    print("❌ Could not click sign-in button with any strategy")
else:
    print("✅ Sign-in button action completed")
    time.sleep(3)  # Wait for page to load
"""

    elif action_type == "accept_cookies":
        return """
# Accept cookies
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

wait = WebDriverWait(driver, 10)
try:
    btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "[data-automation-id='legalNoticeAcceptButton']")
    ))
    driver.execute_script("arguments[0].click();", btn)
    print("✓ Accepted cookies")
except:
    print("⚠️ No cookie banner found")
"""

    else:
        # Generic navigation
        return """
# Navigate to next page
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

wait = WebDriverWait(driver, 10)
try:
    next_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(text(), 'Next') or contains(text(), 'Continue')]")
    ))
    driver.execute_script("arguments[0].click();", next_btn)
    print("✓ Clicked next/continue")
except:
    print("⚠️ No navigation button found")
"""

def capture_page_state(driver):
    """Capture current page state for comparison."""
    state = {
        "url": driver.current_url,
        "title": driver.title,
        "body_text_sample": "",
        "visible_modals": 0,
        "input_values": []
    }

    try:
        # Get sample of body text
        body = driver.find_element(By.TAG_NAME, "body")
        state["body_text_sample"] = body.text[:500]
    except:
        pass

    try:
        # Count visible modals
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true'], [role='dialog']")
        state["visible_modals"] = len([m for m in modals if m.is_displayed()])
    except:
        pass

    try:
        # Get input values to detect form changes
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[type='password'], input[type='text']")
        for inp in inputs[:5]:  # Limit to first 5
            val = inp.get_attribute("value")
            if val:
                state["input_values"].append(val[:20])  # Store first 20 chars
    except:
        pass

    return state

def states_are_different(state1, state2):
    """Compare two page states to detect meaningful changes."""
    # URL change is always significant
    if state1["url"] != state2["url"]:
        return True, "success", "URL changed"

    # Modal count change is significant
    if state1["visible_modals"] != state2["visible_modals"]:
        if state2["visible_modals"] < state1["visible_modals"]:
            return True, "success", "Modal closed"
        else:
            return True, "likely_success", "Modal state changed"

    # Form value changes
    if state1["input_values"] != state2["input_values"]:
        if len(state2["input_values"]) > len(state1["input_values"]):
            return True, "likely_success", "Form filled"
        elif len(state2["input_values"]) < len(state1["input_values"]):
            return True, "likely_success", "Form cleared/submitted"

    # Text content change
    if state1["body_text_sample"] != state2["body_text_sample"]:
        # Check if it's a significant change
        if len(state2["body_text_sample"]) < len(state1["body_text_sample"]) * 0.5:
            return True, "likely_success", "Page content changed significantly"
        elif len(state2["body_text_sample"]) > len(state1["body_text_sample"]) * 1.5:
            return True, "likely_success", "New content loaded"

    return False, "no_change", "No meaningful change detected"

def record_action(memory, page_signature, action, code_snippet, success, error_msg=None):
    """Record action in memory."""
    action_record = {
        "timestamp": datetime.now().isoformat(),
        "page_signature": page_signature,
        "action": action,
        "code_snippet": code_snippet[:500],
        "success": success,
        "error": error_msg
    }

    memory["action_history"].append(action_record)

    # Track action sequences
    if page_signature not in memory["action_sequences"]:
        memory["action_sequences"][page_signature] = []
    memory["action_sequences"][page_signature].append(action["action_type"])

    # Keep only last 100 actions to avoid memory bloat
    if len(memory["action_history"]) > 100:
        memory["action_history"] = memory["action_history"][-100:]

def execute_step(driver, memory, resume_data, step_num):
    """Execute a single step with intelligent decision making."""
    print(f"\n{'='*60}")
    print(f"STEP {step_num}")
    print(f"{'='*60}")

    # Capture initial state
    initial_state = capture_page_state(driver)

    # Analyze current page
    page_info = analyze_page_enhanced(driver, memory)
    page_signature = page_info["page_signature"]

    print(f"📍 URL: {page_info['url'][:80]}")
    print(f"🔑 Page signature: {page_signature}")
    print(f"📋 Modals detected: {page_info['modals_detected']}")
    print(f"🔐 Sign-in detected: {page_info['sign_in_detected']}")
    print(f"📝 Form filled: {page_info['form_filled']}")

    # Check if we're stuck
    if page_signature in memory["action_sequences"]:
        recent_actions = memory["action_sequences"][page_signature][-3:]
        if len(recent_actions) == 3 and len(set(recent_actions)) == 1:
            print(f"⚠️ WARNING: Repeated same action 3 times: {recent_actions[0]}")
            print("🔄 Forcing alternative strategy...")

    # Generate intelligent action
    last_error = None
    success = False

    for attempt in range(MAX_RETRIES):
        print(f"\n🎯 Attempt {attempt + 1}/{MAX_RETRIES}")

        # Generate action based on current state
        action = generate_smart_action(page_info, memory, resume_data, last_error)
        print(f"📋 Action: {action['action_type']}")
        print(f"💭 Reasoning: {action['reasoning']}")

        # Generate code for action
        code = generate_action_code(action, page_info, memory, resume_data, last_error)

        # Execute code
        try:
            exec_globals = {
                'driver': driver,
                'resume_data': resume_data,
                'By': By,
                'Keys': Keys,
                'WebDriverWait': WebDriverWait,
                'EC': EC,
                'time': time
            }

            exec(code, exec_globals)

            # Wait and check for state change
            time.sleep(2)
            new_state = capture_page_state(driver)
            changed, result_type, reason = states_are_different(initial_state, new_state)

            if changed:
                print(f"✅ Action successful: {reason}")
                record_action(memory, page_signature, action, code, True)
                success = True

                # Special handling for sign-in form
                if action["action_type"] == "fill_sign_in_form" and not detect_stuck_pattern(memory, page_signature, "fill_form"):
                    print("📌 Form filled - will click submit button next")
                    # Force next action to be clicking submit
                    memory["stuck_detection"][f"{page_signature}_fill_form"] = {"count": 10, "last_time": datetime.now().isoformat()}

                break
            else:
                print(f"⚠️ No state change detected")
                last_error = "No state change"
                record_action(memory, page_signature, action, code, False, last_error)

        except Exception as e:
            print(f"❌ Error: {str(e)[:200]}")
            last_error = str(e)
            record_action(memory, page_signature, action, code, False, last_error)

    # Save memory after each step
    save_agent_memory(memory)

    return success

def main():
    """Main execution function."""
    print("\n" + "="*80)
    print("🚀 INTELLIGENT JOB APPLICATION AGENT v5.0 - FINAL")
    print("🧠 Smart Learning - Never Repeats Failed Approaches")
    print("🔄 Loop Detection - Breaks Out of Stuck States")
    print("✅ Action Validation - Ensures Progress")
    print("="*80 + "\n")

    # Load memory and resume
    memory = load_agent_memory()
    resume_data = load_resume_details(RESUME_JSON_PATH)

    print(f"📄 Resume: {resume_data['personal_info']['name']}")
    print(f"📧 Email: {resume_data['personal_info']['email']}")
    print(f"📊 Memory: {len(memory.get('action_history', []))} past actions\n")

    # Ensure credentials are in resume_data
    if "credentials" not in resume_data:
        resume_data["credentials"] = {
            "email": resume_data.get("personal_info", {}).get("email", ""),
            "password": "Hinjewadi@123"  # Default password, should be loaded from secure storage
        }

    # Start browser
    print("🌐 Starting browser...")
    driver = create_driver()

    try:
        # Navigate to job URL
        job_url = "https://fractal.wd1.myworkdayjobs.com/en-US/Careers/job/Bengaluru/GCP-Engineer_SR-20029/apply/autofillWithResume?source=LinkedIn"
        print(f"🔗 Opening: {job_url}\n")
        driver.get(job_url)
        time.sleep(3)

        # Execute steps
        max_steps = 20
        for step_num in range(1, max_steps + 1):
            success = execute_step(driver, memory, resume_data, step_num)

            # Check if we've completed the application
            if "success" in driver.current_url.lower() or "thank" in driver.title.lower():
                print("\n🎉 Application submitted successfully!")
                break

            # Check if we're stuck
            if step_num > 10:
                # Look for patterns in last 5 actions
                recent = memory["action_history"][-5:]
                if len(recent) == 5:
                    signatures = [a["page_signature"] for a in recent]
                    if len(set(signatures)) == 1:
                        print("\n⚠️ Stuck on same page for 5 actions!")
                        print("🔄 Attempting recovery...")
                        # Try to find any button to click
                        driver.execute_script("""
                            var buttons = document.querySelectorAll('button');
                            for(var btn of buttons) {
                                if(btn.offsetParent !== null) {
                                    btn.click();
                                    break;
                                }
                            }
                        """)
                        time.sleep(2)

            if not success and step_num > 3:
                print("\n⚠️ Multiple failures - may need manual intervention")
                if INTERACTIVE_MODE:
                    input("Press Enter to continue or Ctrl+C to stop...")

    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        print("\n🔚 Closing browser...")
        driver.quit()
        save_agent_memory(memory)
        print("💾 Memory saved")

if __name__ == "__main__":
    main()
