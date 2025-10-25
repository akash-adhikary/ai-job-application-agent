"""
Job Application Automation Agent v6.0 - Focused on the Goal
===========================================================
This agent stays focused on the primary goal: completing job applications.
It doesn't get distracted by non-essential elements like cookie banners.
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
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
import re

# Configuration
RESUME_JSON_PATH = "resume_data.json"
MEMORY_FILE = "agent_memory_focused.json"
MAX_RETRIES = 3
INTERACTIVE_MODE = False
AUTO_CONTINUE_TIMEOUT = 10
SCREENSHOT_DIR = "screenshots"

# Initialize memory structure
DEFAULT_MEMORY = {
    "learnings": [],
    "domain_knowledge": {
        "primary_goal": "Complete job application by filling all required fields and submitting",
        "priorities": "1. Sign in if required, 2. Fill application form, 3. Submit application",
        "sign_in_rule": "If sign-in is required, complete it first. After filling credentials, ALWAYS click submit.",
        "form_rule": "Fill all required fields marked with * or (required). Submit when complete.",
        "navigation": "Look for Apply, Next, Continue, Submit buttons to progress through application"
    },
    "action_history": [],
    "completed_actions": {},  # Track what we've done on each page
    "application_progress": {
        "signed_in": False,
        "form_pages_completed": 0,
        "current_stage": "initial"
    }
}

def load_agent_memory():
    """Load agent memory."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                memory = json.load(f)
                # Ensure all keys exist
                for key in DEFAULT_MEMORY:
                    if key not in memory:
                        memory[key] = DEFAULT_MEMORY[key]
                return memory
        except Exception as e:
            print(f"⚠️ Error loading memory: {e}")
    return DEFAULT_MEMORY.copy()

def save_agent_memory(memory):
    """Save agent memory."""
    try:
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2, default=str)
    except Exception as e:
        print(f"⚠️ Could not save memory: {e}")

def create_driver():
    """Create Chrome driver."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    return webdriver.Chrome(options=chrome_options)

def load_resume_details(file_path):
    """Load resume details."""
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_page_signature(driver):
    """Generate unique signature for current page."""
    try:
        elements = [
            driver.current_url,
            str(len(driver.find_elements(By.CSS_SELECTOR, "input, select, textarea"))),
            str(len(driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")))
        ]
        return hashlib.md5("|".join(elements).encode()).hexdigest()
    except:
        return hashlib.md5(driver.current_url.encode()).hexdigest()

def analyze_page_for_application(driver):
    """Analyze page specifically for job application elements."""
    analysis = {
        "url": driver.current_url,
        "page_signature": generate_page_signature(driver),
        "has_sign_in": False,
        "sign_in_form_filled": False,
        "has_application_form": False,
        "required_fields": [],
        "filled_fields": [],
        "submit_buttons": [],
        "navigation_buttons": [],
        "stage": "unknown"
    }

    # Check for sign-in elements FIRST (highest priority)
    try:
        # Look for password field as indicator of sign-in
        password_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
        if password_fields and any(p.is_displayed() for p in password_fields):
            analysis["has_sign_in"] = True
            analysis["stage"] = "sign_in"

            # Check if email/username is filled
            email_fields = driver.find_elements(By.CSS_SELECTOR,
                "input[type='email'], input[name*='email'], input[name*='user'], input[id*='email']")
            for field in email_fields:
                if field.get_attribute("value"):
                    analysis["sign_in_form_filled"] = True
                    break

            # Look for sign-in submit button
            sign_in_buttons = driver.find_elements(By.CSS_SELECTOR,
                "button[type='submit'], button[data-automation-id*='sign'], button[class*='sign']")
            for btn in sign_in_buttons:
                if btn.is_displayed():
                    analysis["submit_buttons"].append({
                        "element": btn,
                        "text": btn.text,
                        "type": "sign_in"
                    })
    except Exception as e:
        print(f"Debug: Sign-in check error: {e}")

    # If not sign-in page, check for application form
    if not analysis["has_sign_in"]:
        try:
            # Look for form fields
            form_fields = driver.find_elements(By.CSS_SELECTOR,
                "input[type='text'], input[type='email'], input[type='tel'], select, textarea")

            if len(form_fields) > 2:  # More than 2 fields suggests a form
                analysis["has_application_form"] = True
                analysis["stage"] = "application_form"

                # Check required fields
                for field in form_fields:
                    try:
                        if field.is_displayed():
                            # Check if field is required
                            is_required = (
                                field.get_attribute("required") or
                                field.get_attribute("aria-required") == "true" or
                                "*" in (field.get_attribute("placeholder") or "")
                            )

                            field_info = {
                                "element": field,
                                "name": field.get_attribute("name") or field.get_attribute("id"),
                                "type": field.get_attribute("type"),
                                "value": field.get_attribute("value"),
                                "required": is_required
                            }

                            if is_required:
                                analysis["required_fields"].append(field_info)

                            if field_info["value"]:
                                analysis["filled_fields"].append(field_info)
                    except:
                        continue
        except Exception as e:
            print(f"Debug: Form check error: {e}")

    # Look for navigation/submit buttons
    try:
        all_buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit'], a[role='button']")
        for btn in all_buttons:
            try:
                if not btn.is_displayed():
                    continue

                btn_text = (btn.text or btn.get_attribute("value") or "").lower()

                # Categorize buttons
                if any(word in btn_text for word in ["submit", "apply", "send"]):
                    analysis["submit_buttons"].append({
                        "element": btn,
                        "text": btn.text,
                        "type": "submit"
                    })
                elif any(word in btn_text for word in ["next", "continue", "proceed"]):
                    analysis["navigation_buttons"].append({
                        "element": btn,
                        "text": btn.text,
                        "type": "navigation"
                    })
            except:
                continue
    except Exception as e:
        print(f"Debug: Button check error: {e}")

    return analysis

def decide_next_action(analysis, memory, resume_data):
    """Decide the next action based on page analysis and memory."""
    page_sig = analysis["page_signature"]

    # Check if we've already completed actions on this page
    if page_sig in memory.get("completed_actions", {}):
        completed = memory["completed_actions"][page_sig]
        print(f"ℹ️ Already completed on this page: {completed}")

    # PRIORITY 1: Handle sign-in if detected
    if analysis["has_sign_in"]:
        if not analysis["sign_in_form_filled"]:
            return {
                "type": "fill_sign_in",
                "reason": "Need to sign in to proceed with application"
            }
        else:
            # Form is filled, MUST click submit
            return {
                "type": "click_sign_in_submit",
                "reason": "Sign-in form filled, must submit to proceed"
            }

    # PRIORITY 2: Fill application form if present
    if analysis["has_application_form"]:
        unfilled_required = [f for f in analysis["required_fields"] if not f["value"]]
        if unfilled_required:
            return {
                "type": "fill_application_form",
                "reason": f"Need to fill {len(unfilled_required)} required fields",
                "fields": unfilled_required
            }
        elif analysis["submit_buttons"]:
            return {
                "type": "submit_application",
                "reason": "Form is complete, ready to submit"
            }
        elif analysis["navigation_buttons"]:
            return {
                "type": "navigate_next",
                "reason": "Form complete, moving to next section"
            }

    # PRIORITY 3: Look for any way to progress
    if analysis["navigation_buttons"]:
        return {
            "type": "navigate_next",
            "reason": "Click to progress through application"
        }

    if analysis["submit_buttons"]:
        return {
            "type": "click_submit",
            "reason": "Found submit button to progress"
        }

    # DEFAULT: Try to find Apply button or similar
    return {
        "type": "find_apply_button",
        "reason": "Looking for way to start/continue application"
    }

def execute_action(driver, action, analysis, resume_data):
    """Execute the decided action."""
    action_type = action["type"]
    print(f"\n🎯 Executing: {action_type}")
    print(f"📝 Reason: {action['reason']}")

    wait = WebDriverWait(driver, 10)

    try:
        if action_type == "fill_sign_in":
            # Fill sign-in form
            email = resume_data.get("personal_info", {}).get("email", "")
            password = resume_data.get("credentials", {}).get("password", "Hinjewadi@123")

            # Fill email
            email_filled = False
            for selector in ["input[type='email']", "input[name*='email']", "input[id*='email']", "input[name*='user']"]:
                try:
                    field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    field.clear()
                    field.send_keys(email)
                    print(f"✓ Email filled: {email}")
                    email_filled = True
                    break
                except:
                    continue

            # Fill password
            password_filled = False
            try:
                pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                pwd_field.clear()
                pwd_field.send_keys(password)
                print("✓ Password filled")
                password_filled = True
            except:
                print("❌ Could not fill password")

            return email_filled and password_filled

        elif action_type == "click_sign_in_submit":
            # Try multiple methods to submit sign-in
            clicked = False

            # Method 1: Click submit button
            for btn in analysis["submit_buttons"]:
                try:
                    driver.execute_script("arguments[0].click();", btn["element"])
                    print(f"✓ Clicked sign-in button: {btn['text']}")
                    clicked = True
                    break
                except:
                    continue

            # Method 2: Submit form via password field
            if not clicked:
                try:
                    pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    pwd_field.send_keys(Keys.RETURN)
                    print("✓ Submitted via Enter key")
                    clicked = True
                except:
                    pass

            # Method 3: Submit any visible form
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
                    """)
                    print("✓ Submitted form via JavaScript")
                    clicked = True
                except:
                    pass

            time.sleep(3)  # Wait for sign-in to process
            return clicked

        elif action_type == "fill_application_form":
            # Fill required fields
            filled_count = 0
            for field_info in action.get("fields", []):
                try:
                    field = field_info["element"]
                    field_name = field_info["name"] or "unknown"

                    # Determine what to fill based on field name/type
                    value = determine_field_value(field_name, field_info["type"], resume_data)
                    if value:
                        field.clear()
                        field.send_keys(value)
                        print(f"✓ Filled: {field_name} = {value[:30]}...")
                        filled_count += 1
                except:
                    continue

            return filled_count > 0

        elif action_type in ["submit_application", "click_submit"]:
            # Click submit button
            for btn in analysis["submit_buttons"]:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn["element"])
                    driver.execute_script("arguments[0].click();", btn["element"])
                    print(f"✓ Clicked submit: {btn['text']}")
                    time.sleep(2)
                    return True
                except:
                    continue
            return False

        elif action_type == "navigate_next":
            # Click navigation button
            for btn in analysis["navigation_buttons"]:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn["element"])
                    driver.execute_script("arguments[0].click();", btn["element"])
                    print(f"✓ Clicked: {btn['text']}")
                    time.sleep(2)
                    return True
                except:
                    continue
            return False

        elif action_type == "find_apply_button":
            # Look for Apply button
            try:
                apply_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Apply') or contains(text(), 'Start')]")
                ))
                driver.execute_script("arguments[0].click();", apply_btn)
                print("✓ Clicked Apply/Start button")
                return True
            except:
                print("⚠️ No Apply button found")
                return False

    except Exception as e:
        print(f"❌ Action failed: {str(e)[:100]}")
        return False

    return False

def determine_field_value(field_name, field_type, resume_data):
    """Determine appropriate value for a form field."""
    if not field_name:
        return ""

    field_lower = field_name.lower()
    personal_info = resume_data.get("personal_info", {})

    # Map field names to resume data
    if "first" in field_lower and "name" in field_lower:
        return personal_info.get("name", "").split()[0] if personal_info.get("name") else ""
    elif "last" in field_lower and "name" in field_lower:
        return personal_info.get("name", "").split()[-1] if personal_info.get("name") else ""
    elif "name" in field_lower:
        return personal_info.get("name", "")
    elif "email" in field_lower:
        return personal_info.get("email", "")
    elif "phone" in field_lower or "mobile" in field_lower:
        return personal_info.get("phone", "")
    elif "address" in field_lower or "street" in field_lower:
        return personal_info.get("address", "")
    elif "city" in field_lower:
        return personal_info.get("city", "")
    elif "state" in field_lower:
        return personal_info.get("state", "")
    elif "zip" in field_lower or "postal" in field_lower:
        return personal_info.get("zip", "")
    elif "linkedin" in field_lower:
        return personal_info.get("linkedin", "")
    elif "github" in field_lower:
        return personal_info.get("github", "")

    return ""

def record_page_action(memory, page_signature, action_type, success):
    """Record what action was taken on a page."""
    if "completed_actions" not in memory:
        memory["completed_actions"] = {}

    if page_signature not in memory["completed_actions"]:
        memory["completed_actions"][page_signature] = []

    memory["completed_actions"][page_signature].append({
        "action": action_type,
        "success": success,
        "timestamp": datetime.now().isoformat()
    })

    # Update progress
    if success:
        if action_type == "click_sign_in_submit":
            memory["application_progress"]["signed_in"] = True
        elif action_type in ["submit_application", "navigate_next"]:
            memory["application_progress"]["form_pages_completed"] += 1

def main():
    """Main execution."""
    print("\n" + "="*80)
    print("🎯 JOB APPLICATION AGENT v6.0 - FOCUSED")
    print("📋 Primary Goal: Complete Job Application")
    print("🚫 No Distractions: Ignores non-essential elements")
    print("✅ Smart Progress: Tracks application stages")
    print("="*80 + "\n")

    # Load resources
    memory = load_agent_memory()
    resume_data = load_resume_details(RESUME_JSON_PATH)

    # Add credentials if not present
    if "credentials" not in resume_data:
        resume_data["credentials"] = {
            "email": resume_data.get("personal_info", {}).get("email", ""),
            "password": "Hinjewadi@123"
        }

    print(f"👤 Applicant: {resume_data['personal_info']['name']}")
    print(f"📧 Email: {resume_data['personal_info']['email']}")
    print(f"📊 Progress: Stage {memory['application_progress']['form_pages_completed']}")
    print()

    # Start browser
    driver = create_driver()

    try:
        # Navigate to job
        job_url = "https://fractal.wd1.myworkdayjobs.com/en-US/Careers/job/Bengaluru/GCP-Engineer_SR-20029/apply/autofillWithResume?source=LinkedIn"
        print(f"🔗 Opening job application...\n")
        driver.get(job_url)
        time.sleep(3)

        # Main application loop
        max_steps = 30
        stuck_counter = 0
        last_url = ""

        for step in range(1, max_steps + 1):
            print(f"\n{'='*60}")
            print(f"STEP {step} - Focused on Application")
            print(f"{'='*60}")

            # Check if stuck
            current_url = driver.current_url
            if current_url == last_url:
                stuck_counter += 1
                if stuck_counter > 5:
                    print("⚠️ Stuck on same page - trying alternative approach")
                    # Try clicking any visible button
                    try:
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.is_displayed() and btn.text:
                                driver.execute_script("arguments[0].click();", btn)
                                print(f"🔄 Clicked: {btn.text[:30]}")
                                break
                    except:
                        pass
            else:
                stuck_counter = 0
            last_url = current_url

            # Analyze page
            analysis = analyze_page_for_application(driver)
            print(f"📍 Stage: {analysis['stage']}")
            print(f"🔐 Sign-in detected: {analysis['has_sign_in']}")
            print(f"📝 Application form: {analysis['has_application_form']}")

            # Decide action
            action = decide_next_action(analysis, memory, resume_data)

            # Execute action
            success = execute_action(driver, action, analysis, resume_data)

            # Record action
            record_page_action(memory, analysis["page_signature"], action["type"], success)
            save_agent_memory(memory)

            # Check for completion
            if "success" in current_url.lower() or "thank" in driver.title.lower():
                print("\n🎉 Application submitted successfully!")
                break

            # Brief pause between actions
            time.sleep(2)

        print(f"\n📊 Final Progress: Completed {memory['application_progress']['form_pages_completed']} pages")

    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        save_agent_memory(memory)
        print("💾 Memory saved")

if __name__ == "__main__":
    main()
