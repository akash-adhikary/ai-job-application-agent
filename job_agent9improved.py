import os
import json
import time
import traceback
import datetime
import requests
import sys
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
OLLAMA_MODEL = "gpt-oss:120b-cloud"
MAX_RETRIES = 10
MAX_STEPS = 50
HTML_LIMIT = 4000000
SCREENSHOT_DIR = "screenshots"
LOG_DIR = "ollama_logs"
MEMORY_FILE = "agent_memory_enhanced.json"
SESSION_FILE = "agent_session.json"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Interactive mode settings
INTERACTIVE_MODE = True  # Set to False for fully automated mode
AUTO_CONTINUE_TIMEOUT = 5  # Seconds to wait before auto-continuing (0 = wait forever)
# ----------------------------

# === Your file paths ===
JOB_URL = "https://fractal.wd1.myworkdayjobs.com/Careers/job/Bengaluru/GCP-Engineer_SR-20029?source=LinkedIn"
RESUME_JSON_PATH = r"D:\Workspace\jobs-apply\akash_profile.json"
RESUME_PDF_PATH = r"D:\Workspace\jobs-apply\Resume_akash_disn.pdf"
RESUME_PHOTO_PATH = r"D:\Workspace\jobs-apply\AkashPortrait.jpg"

def log_to_file(name, content):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(LOG_DIR, f"{ts}_{name}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def take_screenshot(driver, step_num, label=""):
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"step{step_num}_{label}_{ts}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        driver.save_screenshot(filepath)
        print(f"📸 {filepath}")
        return filepath
    except:
        return None

def load_resume_details(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def create_page_signature(page_info):
    """Create a unique signature for a page based on its structure."""
    # Get button texts for differentiation
    button_texts = []
    buttons = page_info.get('buttons', [])
    for i, b in enumerate(buttons):
        if i >= 5:  # Only take first 5 buttons
            break
        text = b.get('text', '')
        if text:
            button_texts.append(text[:20])

    sig_elements = [
        page_info.get('url', '').split('?')[0],  # Base URL without query params
        len(page_info.get('inputs', [])),
        len(page_info.get('buttons', [])),
        len(page_info.get('selects', [])),
        len(page_info.get('file_inputs', [])),
        # Include some button texts for better differentiation
        tuple(sorted(button_texts))
    ]
    sig_str = json.dumps(sig_elements, sort_keys=True)
    return hashlib.md5(sig_str.encode()).hexdigest()

def load_agent_memory():
    """Load enhanced memory with action history and success patterns."""
    default_memory = {
        "learnings": [],
        "domain_knowledge": {
            "first action": "accept cookies pop-up if present, to avoid blocking further actions.",
            "second action": "if a login/ sign in prompt appears, log in/sign in using stored credentials before proceeding., prefer sign in over sign up/ create account",
            "page analysis": "analyse complete page at one go and try to fill everything and click next for the first iteration itself",
            "skill_selectors": "For searchable skill dropdowns: type ONE skill, wait 1 sec, click suggestion. Repeat for each skill.",
            "file_uploads": "ALWAYS verify file upload: after send_keys(), check if value attribute is set. Print confirmation.",
            "multi_select": "Add items one by one: type, wait, select, repeat. Never paste comma-separated list.",
            "button_clicks": "If normal click fails with 'element click intercepted', use JavaScript click: driver.execute_script('arguments[0].click();', element)",
            "sign in button": "Use data-automation-id='signInSubmitButton' or class containing 'css-1ru62dj' for Workday sign in",
            "modal dialogs": "Always check for modal dialogs after page loads or actions. If present, handle them before proceeding."
        },
        "action_history": [],  # Records of successful actions on specific pages
        "page_patterns": {},   # Patterns for similar pages
        "success_sequences": [],  # Successful action sequences
        "failure_patterns": [],  # Patterns that lead to failures
        "element_selectors": {}  # Successful element selectors by page signature
    }

    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memory = json.load(f)

                # Migrate old memory format to new format
                if "element_selectors" not in memory:
                    memory["element_selectors"] = {}
                    print("🔄 Migrating memory: Added element_selectors")

                if "action_history" not in memory:
                    memory["action_history"] = []
                    print("🔄 Migrating memory: Added action_history")

                if "page_patterns" not in memory:
                    memory["page_patterns"] = {}
                    print("🔄 Migrating memory: Added page_patterns")

                if "success_sequences" not in memory:
                    memory["success_sequences"] = []
                    print("🔄 Migrating memory: Added success_sequences")

                if "failure_patterns" not in memory:
                    memory["failure_patterns"] = []
                    print("🔄 Migrating memory: Added failure_patterns")

                # Ensure domain_knowledge has all required fields
                if "domain_knowledge" not in memory:
                    memory["domain_knowledge"] = default_memory["domain_knowledge"]
                else:
                    # Add any missing domain knowledge keys
                    for key, value in default_memory["domain_knowledge"].items():
                        if key not in memory["domain_knowledge"]:
                            memory["domain_knowledge"][key] = value

                print(f"🧠 Memory loaded: {len(memory.get('learnings', []))} learnings, {len(memory.get('action_history', []))} action records")
                return memory
    except Exception as e:
        print(f"⚠️ Could not load memory: {e}")

    return default_memory

def save_agent_memory(memory):
    """Save enhanced memory."""
    try:
        # Ensure all required keys exist before saving
        if "learnings" not in memory:
            memory["learnings"] = []
        if "action_history" not in memory:
            memory["action_history"] = []
        if "success_sequences" not in memory:
            memory["success_sequences"] = []
        if "failure_patterns" not in memory:
            memory["failure_patterns"] = []
        if "element_selectors" not in memory:
            memory["element_selectors"] = {}
        if "page_patterns" not in memory:
            memory["page_patterns"] = {}

        # Limit memory size to prevent it from growing too large
        memory["learnings"] = memory["learnings"][-100:]  # Keep last 100 learnings
        memory["action_history"] = memory["action_history"][-200:]  # Keep last 200 actions
        memory["success_sequences"] = memory["success_sequences"][-50:]  # Keep last 50 sequences
        memory["failure_patterns"] = memory["failure_patterns"][-50:]  # Keep last 50 failure patterns

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, indent=2, fp=f)
        print(f"🧠 Memory saved with {len(memory['action_history'])} action records")
    except Exception as e:
        print(f"⚠️ Could not save memory: {e}")

def load_session_state():
    """Load session state to resume from where we left off."""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session = json.load(f)
                print(f"📂 Session restored: Step {session.get('last_step', 0)}, URL: {session.get('last_url', '')}")
                return session
    except Exception as e:
        print(f"⚠️ Could not load session: {e}")

    return {
        "session_id": datetime.datetime.now().isoformat(),
        "last_step": 0,
        "last_url": "",
        "completed_pages": [],
        "pending_actions": []
    }

def save_session_state(session):
    """Save session state for recovery."""
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, indent=2, fp=f)
    except Exception as e:
        print(f"⚠️ Could not save session: {e}")

def add_learning(memory, context, lesson, success=True):
    """Add learning to memory with success indicator."""
    memory["learnings"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "context": context,
        "lesson": lesson,
        "success": success
    })
    print(f"{'📚' if success else '⚠️'} Learned: {lesson}")

def record_action(memory, page_signature, action, code, success, error_msg=None):
    """Record an action attempt in memory."""
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "page_signature": page_signature,
        "action": action,
        "code_snippet": code[:500] if code else "",  # Store first 500 chars
        "success": success,
        "error": error_msg[:200] if error_msg else None
    }
    memory["action_history"].append(record)

    # Update success/failure patterns
    if success:
        # Record successful selector patterns
        if page_signature not in memory["element_selectors"]:
            memory["element_selectors"][page_signature] = []

        # Extract selectors from code (simplified extraction)
        if "By.CSS_SELECTOR" in code:
            import re
            selectors = re.findall(r'By\.CSS_SELECTOR,\s*["\']([^"\']+)["\']', code)
            for selector in selectors[:5]:  # Store up to 5 selectors
                if selector not in memory["element_selectors"][page_signature]:
                    memory["element_selectors"][page_signature].append(selector)
    else:
        # Record failure pattern
        failure_pattern = {
            "page_signature": page_signature,
            "action_type": action.get("action_type"),
            "error_keyword": error_msg[:50] if error_msg else "unknown"
        }
        if failure_pattern not in memory["failure_patterns"]:
            memory["failure_patterns"].append(failure_pattern)

def find_similar_page_actions(memory, page_signature):
    """Find successful actions from similar pages in history."""
    similar_actions = []
    for record in memory["action_history"][-50:]:  # Check last 50 actions
        if record["page_signature"] == page_signature and record["success"]:
            similar_actions.append(record)
    return similar_actions

def get_known_selectors(memory, page_signature):
    """Get known working selectors for this page."""
    return memory["element_selectors"].get(page_signature, [])

def create_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

def call_ollama(prompt, model=OLLAMA_MODEL):
    """Call Ollama API."""
    try:
        print("🤖 AI thinking...")

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300
        )
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        print("✅ AI responded\n")
        return result
    except Exception as e:
        print(f"⚠️ Ollama failed: {e}")
        return ""

def timed_input_windows(prompt_text, timeout_seconds):
    """Windows-compatible timed input."""
    if not INTERACTIVE_MODE:
        return None

    if timeout_seconds <= 0:
        return input().strip().lower()

    print(prompt_text)
    print(f"⏱️  Auto-continuing in {timeout_seconds} seconds...")
    print("    Press any key to interact, or wait to auto-continue...")

    start_time = time.time()

    try:
        import msvcrt

        while True:
            if msvcrt.kbhit():
                print("\n⏸️  Input detected, waiting for your command...")
                user_input = input().strip().lower()
                return user_input

            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                print("\n⏩ Auto-continuing...\n")
                return None

            time.sleep(0.1)

    except ImportError:
        # Fallback for non-Windows
        import select

        rlist, _, _ = select.select([sys.stdin], [], [], timeout_seconds)

        if rlist:
            user_input = sys.stdin.readline().strip().lower()
            return user_input
        else:
            print("\n⏩ Auto-continuing...\n")
            return None

def interactive_checkpoint(step_num, phase):
    """Optional checkpoint for user interaction."""
    if not INTERACTIVE_MODE:
        return None

    print("\n" + "="*80)
    print(f"⏸️  CHECKPOINT - Step {step_num} - {phase}")
    print("="*80)
    print("\nOptions:")
    print("  [Enter] - Continue")
    print("  g       - Give guidance")
    print("  m       - Manual (you control browser)")
    print("  q       - Quit")

    choice = timed_input_windows("\nChoice: ", AUTO_CONTINUE_TIMEOUT)

    if choice is None or choice == '':
        return {"action": "continue"}
    elif choice == 'g':
        print("\n💬 Your guidance:")
        guidance = input(">>> ").strip()
        return {"action": "guidance", "message": guidance}
    elif choice == 'm':
        print("\n👤 Manual mode - interact with page, press Enter when done...")
        input()
        return {"action": "manual"}
    elif choice == 'q':
        return {"action": "quit"}
    else:
        return {"action": "continue"}

def extract_page_info(driver):
    """Extract current page information including modals and popups."""
    try:
        time.sleep(1)

        info = {
            "url": driver.current_url,
            "title": driver.title,
            "buttons": [],
            "inputs": [],
            "selects": [],
            "textareas": [],
            "file_inputs": [],
            "page_text": "",
            "modals_detected": False,
            "modal_content": "",
            "sign_in_modal": False,
            "click_interceptors": []
        }

        # Enhanced modal detection - including aria-modal and high z-index elements
        try:
            # Check for dialogs with aria-modal
            aria_modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true'], [role='dialog']")

            # Check for common modal patterns
            css_modals = driver.find_elements(By.CSS_SELECTOR, "div[class*='modal'], div[class*='popup'], div[class*='overlay'], div[class*='dialog']")

            # Check for sign-in specific modals
            sign_in_modals = driver.find_elements(By.CSS_SELECTOR, "[data-automation-id*='signIn'], [data-automation-id*='auth']")

            all_modals = aria_modals + css_modals + sign_in_modals
            visible_modals = [m for m in all_modals if m.is_displayed()]

            if visible_modals:
                info["modals_detected"] = True
                try:
                    modal_text = visible_modals[0].text[:1000]
                    info["modal_content"] = modal_text

                    # Check if it's a sign-in modal
                    if any(keyword in modal_text.lower() for keyword in ['sign in', 'login', 'password', 'email address']):
                        info["sign_in_modal"] = True
                except:
                    pass

            # Check for click interceptors (transparent overlays)
            try:
                interceptors = driver.find_elements(By.CSS_SELECTOR, "[data-automation-id='click_filter'], div[class*='overlay'][style*='z-index']")
                for interceptor in interceptors:
                    if interceptor.is_displayed():
                        info["click_interceptors"].append({
                            "id": interceptor.get_attribute("id"),
                            "class": interceptor.get_attribute("class"),
                            "data_automation_id": interceptor.get_attribute("data-automation-id")
                        })
            except:
                pass
        except:
            pass

        # Page text preview
        try:
            if info["modals_detected"]:
                info["page_text"] = info["modal_content"]
            else:
                body = driver.find_element(By.TAG_NAME, "body")
                info["page_text"] = body.text[:1500]
        except:
            pass

        # Extract form elements (buttons, inputs, etc.)
        # [Similar extraction code as original, abbreviated for space]

        # Buttons - Enhanced detection for modals and sign-in buttons
        try:
            if info.get("modals_detected"):
                # Look for buttons specifically in modal/dialog contexts
                modal_button_selectors = [
                    "[aria-modal='true'] button",
                    "[role='dialog'] button",
                    "div[class*='modal'] button",
                    "[data-automation-id='signInSubmitButton']",
                    "button[class*='sign'][class*='in']",
                    "button[class*='login']"
                ]

                for selector in modal_button_selectors:
                    try:
                        modal_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in modal_buttons[:10]:
                            try:
                                # Check various display properties
                                is_visible = btn.is_displayed()
                                is_enabled = btn.is_enabled()

                                # Some buttons might be hidden behind overlays but still "displayed"
                                # Check if button has negative tabindex (often used to hide from keyboard nav)
                                tabindex = btn.get_attribute("tabindex")
                                aria_hidden = btn.get_attribute("aria-hidden")

                                # Include button even if it has negative tabindex (common for Workday)
                                if is_visible or (is_enabled and tabindex == "-2"):
                                    button_info = {
                                        "text": btn.text.strip() or btn.get_attribute("aria-label") or "Submit",
                                        "type": btn.get_attribute("type"),
                                        "id": btn.get_attribute("id"),
                                        "class": btn.get_attribute("class"),
                                        "aria_label": btn.get_attribute("aria-label"),
                                        "data_automation_id": btn.get_attribute("data-automation-id"),
                                        "tabindex": tabindex,
                                        "aria_hidden": aria_hidden,
                                        "in_modal": True,
                                        "selector_used": selector
                                    }

                                    # Avoid duplicates
                                    if not any(b.get('data_automation_id') == button_info['data_automation_id']
                                             and b.get('class') == button_info['class']
                                             for b in info["buttons"] if b.get('data_automation_id')):
                                        info["buttons"].append(button_info)
                            except:
                                continue
                    except:
                        continue

            # Regular page buttons
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons[:25]:
                try:
                    if btn.is_displayed() and btn.text.strip():
                        button_info = {
                            "text": btn.text.strip(),
                            "type": btn.get_attribute("type"),
                            "id": btn.get_attribute("id"),
                            "class": btn.get_attribute("class"),
                            "aria_label": btn.get_attribute("aria-label"),
                            "data_automation_id": btn.get_attribute("data-automation-id"),
                            "in_modal": False
                        }

                        # Avoid duplicates
                        if not any(b.get('data_automation_id') == button_info['data_automation_id']
                                 and b.get('class') == button_info['class']
                                 for b in info["buttons"] if b.get('data_automation_id')):
                            info["buttons"].append(button_info)
                except:
                    continue
        except:
            pass

        # Input fields
        try:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs[:35]:
                try:
                    if not inp.is_displayed():
                        continue

                    input_type = inp.get_attribute("type") or "text"

                    # Get label
                    label_text = ""
                    try:
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            label = driver.find_element(By.CSS_SELECTOR, f"label[for='{inp_id}']")
                            label_text = label.text.strip()
                    except:
                        pass

                    if input_type == "file":
                        info["file_inputs"].append({
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "label": label_text or inp.get_attribute("aria-label") or "Upload",
                            "accept": inp.get_attribute("accept"),
                            "value": inp.get_attribute("value"),
                            "is_filled": bool(inp.get_attribute("value"))
                        })
                    else:
                        info["inputs"].append({
                            "type": input_type,
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "label": label_text or inp.get_attribute("placeholder") or inp.get_attribute("aria-label"),
                            "placeholder": inp.get_attribute("placeholder"),
                            "value": inp.get_attribute("value"),
                            "required": bool(inp.get_attribute("required")),
                            "is_filled": bool(inp.get_attribute("value"))
                        })
                except:
                    continue
        except:
            pass

        return info
    except Exception as e:
        return {"error": str(e), "url": driver.current_url}

def print_page_summary(info, memory=None, page_signature=None):
    """Print concise page summary with memory insights."""
    print("\n" + "="*80)
    print("📊 CURRENT PAGE")
    print("="*80)
    print(f"URL: {info.get('url', 'N/A')}")
    print(f"Title: {info.get('title', 'N/A')}")

    # Show if we've seen this page before
    if memory and page_signature:
        similar_actions = find_similar_page_actions(memory, page_signature)
        if similar_actions:
            print(f"✨ Seen this page {len(similar_actions)} times before!")
            last_success = similar_actions[-1]
            print(f"   Last successful action: {last_success['action'].get('action_type', 'unknown')}")

    # Alert if modal detected
    if info.get("modals_detected"):
        print("\n🔔 MODAL/POPUP DETECTED!")
        if info.get("sign_in_modal"):
            print("   📝 Type: SIGN-IN MODAL")
        if info.get("modal_content"):
            print(f"   Content preview: {info.get('modal_content')[:200]}...")
        if info.get("click_interceptors"):
            print(f"   ⚠️ Click interceptors detected: {len(info['click_interceptors'])}")

    # Count filled vs unfilled
    inputs = info.get('inputs', [])
    filled_inputs = [i for i in inputs if i.get('is_filled')]

    print(f"\n📝 Inputs: {len(filled_inputs)}/{len(inputs)} filled")

    # Show buttons
    buttons = info.get('buttons', [])
    modal_buttons = [b for b in buttons if b.get('in_modal')]

    if modal_buttons:
        print(f"\n🔘 MODAL BUTTONS ({len(modal_buttons)}):")
        for btn in modal_buttons[:5]:
            print(f"  - '{btn['text']}' (id: {btn.get('id', 'none')}, automation: {btn.get('data_automation_id', 'none')})")

    print("="*80 + "\n")

def decide_action(page_info, resume_data, memory, page_signature, user_guidance=None):
    """AI decides action with memory insights."""

    domain_knowledge = memory.get("domain_knowledge", {})
    recent_learnings = [l.get("lesson", "") for l in memory.get("learnings", [])[-5:]]

    # Get insights from memory
    similar_actions = find_similar_page_actions(memory, page_signature)
    known_selectors = get_known_selectors(memory, page_signature)

    # Build memory insights
    memory_insights = ""
    if similar_actions:
        memory_insights = f"\n\nPREVIOUS SUCCESS ON THIS PAGE:\n"
        for action in similar_actions[-3:]:
            memory_insights += f"- {action['action']['action_type']}: {action['action'].get('reasoning', '')}\n"

    if known_selectors:
        memory_insights += f"\n\nKNOWN WORKING SELECTORS FOR THIS PAGE:\n"
        for selector in known_selectors[:5]:
            memory_insights += f"- {selector}\n"

    guidance_text = f"\n\nUSER GUIDANCE: {user_guidance}\n" if user_guidance else ""

    prompt = f"""You are analyzing the CURRENT page only. Decide ONE action to take right now.

CURRENT PAGE:
{json.dumps(page_info, indent=2)}

RESUME DATA AVAILABLE:
{json.dumps(resume_data, indent=2)}

DOMAIN KNOWLEDGE:
{json.dumps(domain_knowledge, indent=2)}

RECENT LEARNINGS:
{', '.join(recent_learnings)}
{memory_insights}
{guidance_text}

IMPORTANT PAST LEARNINGS:
- For Workday sign in: Use button with data-automation-id="signInSubmitButton" or class containing "css-1ru62dj"
- Always handle modals/popups before proceeding with main page actions
- Check if we've successfully interacted with this exact page before

RULES:
1. Analyze ONLY what you see on THIS page
2. If we've succeeded on this page before, prefer the same approach
3. Decide ONE action: fill_form, click_button, upload_file, needs_user_input, or done
4. Focus on completing THIS page's requirements
5. Learn from past failures - avoid patterns that previously failed

Respond with JSON:
{{
  "action_type": "fill_form" | "click_button" | "upload_file" | "needs_user_input" | "done",
  "reasoning": "why you chose this action",
  "target": "what element you'll interact with",
  "confidence": "high" | "medium" | "low",
  "using_memory": true | false
}}

ONLY JSON:"""

    response = call_ollama(prompt)

    try:
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        action = json.loads(response.strip())

        # Add memory flag if we used past experience
        if similar_actions or known_selectors:
            action["using_memory"] = True

        return action
    except:
        print(f"⚠️ Failed to parse action:\n{response[:200]}")
        return {
            "action_type": "fill_form",
            "reasoning": "Default action",
            "target": "available fields",
            "confidence": "low",
            "using_memory": False
        }

def generate_code_for_action(page_info, resume_data, action, memory, page_signature, user_guidance=None, retry_attempt=0):
    """Generate code with memory-informed strategies."""

    domain_knowledge = memory.get("domain_knowledge", {})
    guidance_text = f"\n\nUSER GUIDANCE: {user_guidance}\n" if user_guidance else ""
    retry_text = f"\n\nThis is RETRY ATTEMPT {retry_attempt}. Previous attempts failed.\n" if retry_attempt > 0 else ""

    # Get known working selectors
    known_selectors = get_known_selectors(memory, page_signature)
    selector_text = ""
    if known_selectors:
        selector_text = f"\n\nKNOWN WORKING SELECTORS FOR THIS PAGE:\n"
        for selector in known_selectors:
            selector_text += f"- {selector}\n"
        selector_text += "PREFER THESE SELECTORS IF APPLICABLE!\n"

    # Get recent failures to avoid
    failure_patterns = [f for f in memory.get("failure_patterns", []) if f["page_signature"] == page_signature]
    avoid_text = ""
    if failure_patterns:
        avoid_text = f"\n\nAVOID THESE PATTERNS (they failed before):\n"
        for pattern in failure_patterns[-3:]:
            avoid_text += f"- {pattern['error_keyword']}\n"

    # Build prompt without f-string to avoid syntax issues with code examples
    prompt = """Generate Selenium code for THIS SPECIFIC ACTION on the current page.

ACTION TO TAKE:
""" + json.dumps(action, indent=2) + """

PAGE INFO:
""" + json.dumps(page_info, indent=2) + """

RESUME DATA:
""" + json.dumps(resume_data, indent=2) + """

DOMAIN KNOWLEDGE:
""" + json.dumps(domain_knowledge, indent=2) + guidance_text + retry_text + selector_text + avoid_text + """

CRITICAL RULES BASED ON PAST EXPERIENCE:

1. **SIGN IN BUTTONS** - For Workday and modals with click interceptors:
```python
# IMPORTANT: Workday often has transparent overlays that intercept clicks
# The real button might have tabindex="-2" and aria-hidden="true"

wait = WebDriverWait(driver, 15)

# First, fill the form fields if they exist
try:
    email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-automation-id='email'], input[type='email'], input[autocomplete='email']")))
    email_field.clear()
    # Handle the nested dictionary safely
    personal_info = resume_data.get('personal_info', {}) if resume_data else {}  # type: dict
    email = personal_info.get('email', '')
    email_field.send_keys(email)
    print("✓ Filled email")

    password_field = driver.find_element(By.CSS_SELECTOR, "input[data-automation-id='password'], input[type='password']")
    password_field.clear()
    password_field.send_keys("YOUR_PASSWORD")  # You'll need to provide this
    print("✓ Filled password")
    time.sleep(1)
except:
    pass

# Now handle the sign-in button with multiple strategies
clicked = False

# Strategy 1: Try the actual button (might be hidden by overlay)
try:
    sign_in_btn = driver.find_element(By.CSS_SELECTOR, "button[data-automation-id='signInSubmitButton']")
    # Force click with JavaScript even if it has tabindex="-2"
    driver.execute_script("arguments[0].removeAttribute('tabindex');", sign_in_btn)
    driver.execute_script("arguments[0].removeAttribute('aria-hidden');", sign_in_btn)
    driver.execute_script("arguments[0].click();", sign_in_btn)
    print("✓ Clicked Sign In button directly")
    clicked = True
except:
    pass

# Strategy 2: Click the overlay/filter that might be intercepting
if not clicked:
    try:
        click_filter = driver.find_element(By.CSS_SELECTOR, "[data-automation-id='click_filter']")
        driver.execute_script("arguments[0].click();", click_filter)
        print("✓ Clicked through click filter overlay")
        clicked = True
    except:
        pass

# Strategy 3: Submit the form directly
if not clicked:
    try:
        form = driver.find_element(By.CSS_SELECTOR, "form[data-automation-id*='signIn'], form")
        driver.execute_script("arguments[0].submit();", form)
        print("✓ Submitted form directly")
        clicked = True
    except:
        pass

# Strategy 4: Press Enter in password field
if not clicked:
    try:
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.send_keys(Keys.RETURN)
        print("✓ Pressed Enter in password field")
        clicked = True
    except:
        pass
```

2. **GENERAL BUTTON CLICKING**:
```python
# Always use JavaScript click for reliability
driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
time.sleep(0.5)
driver.execute_script("arguments[0].click();", element)
```

3. **FILE UPLOADS** - ALWAYS VERIFY:
```python
file_input.send_keys(resume_pdf_path)
time.sleep(2)
uploaded_value = file_input.get_attribute("value")
if uploaded_value:
    print(f"✓ File uploaded: {uploaded_value}")
else:
    print("⚠️ FILE UPLOAD MAY HAVE FAILED!")
```

4. **SKILL INPUTS** - One at a time:
```python
for skill in skills[:5]:
    skill_input.clear()
    skill_input.send_keys(skill)
    time.sleep(1.5)
    # Click suggestion
```

Available variables:
- driver, By, Keys, resume_data, resume_pdf_path, resume_photo_path
- time, WebDriverWait, EC, NoSuchElementException, ElementClickInterceptedException

Generate ONLY Python code (no markdown, no explanations):"""

    code = call_ollama(prompt)

    # Clean code
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]

    return code.strip()

def capture_page_state(driver):
    """Capture current page state for comparison."""
    try:
        state = {
            "url": driver.current_url,
            "title": driver.title,
            "body_text_hash": hashlib.md5(driver.find_element(By.TAG_NAME, "body").text.encode()).hexdigest(),
            "input_count": len(driver.find_elements(By.TAG_NAME, "input")),
            "button_count": len(driver.find_elements(By.TAG_NAME, "button")),
            "visible_modals": len([m for m in driver.find_elements(By.CSS_SELECTOR, "[role='dialog'], [aria-modal='true']") if m.is_displayed()]),
            "error_messages": [],
            "form_values": {}
        }

        # Capture form values to detect if form was cleared/submitted
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='password']")
        for inp in inputs[:10]:  # Limit to avoid too much data
            try:
                inp_id = inp.get_attribute("id") or inp.get_attribute("name")
                if inp_id:
                    state["form_values"][inp_id] = inp.get_attribute("value") or ""
            except:
                pass

        # Check for common error indicators
        error_selectors = [
            "[class*='error']", "[class*='alert']", "[class*='warning']",
            "[data-automation-id*='error']", "[role='alert']"
        ]
        for selector in error_selectors:
            try:
                errors = driver.find_elements(By.CSS_SELECTOR, selector)
                for err in errors:
                    if err.is_displayed() and err.text.strip():
                        state["error_messages"].append(err.text.strip()[:100])
            except:
                pass

        return state
    except Exception as e:
        return {"url": driver.current_url, "error": str(e)}

def states_are_different(state1, state2, action_type):
    """Check if two page states are meaningfully different based on the action type."""

    # URL change is usually a strong success indicator
    if state1.get("url") != state2.get("url"):
        return True, "success", "URL changed - navigation successful"

    # For sign-in actions, modal closing is success
    if action_type == "click_button" and "sign" in str(action_type).lower():
        if state1.get("visible_modals", 0) > state2.get("visible_modals", 0):
            return True, "success", "Modal closed - likely signed in"

    # Check for error messages (indicates failure)
    new_errors = set(state2.get("error_messages", [])) - set(state1.get("error_messages", []))
    if new_errors:
        return True, "failure", f"Error appeared: {list(new_errors)[0]}"

    # Page content change
    if state1.get("body_text_hash") != state2.get("body_text_hash"):
        # Check if form was cleared (might indicate submission)
        form_cleared = False
        if state1.get("form_values"):
            cleared_fields = 0
            for field_id, old_value in state1.get("form_values", {}).items():
                new_value = state2.get("form_values", {}).get(field_id, "")
                if old_value and not new_value:
                    cleared_fields += 1
            if cleared_fields >= len(state1.get("form_values", {})) // 2:
                form_cleared = True

        if form_cleared:
            return True, "likely_success", "Form cleared - possibly submitted"
        return True, "partial_success", "Page content changed"

    # Modal state change
    if state1.get("visible_modals", 0) != state2.get("visible_modals", 0):
        if state2.get("visible_modals", 0) > state1.get("visible_modals", 0):
            return True, "partial", "New modal appeared"
        else:
            return True, "success", "Modal closed"

    # No meaningful change - this is usually a failure for action steps
    return False, "no_change", "No meaningful change detected - action likely failed"

def validate_action_success(driver, initial_state, action, expected_wait=5):
    """Validate if an action actually succeeded by checking state changes."""

    print(f"\n🔍 Validating action success...")

    # Wait for potential changes
    time.sleep(expected_wait)

    # Capture new state
    new_state = capture_page_state(driver)

    # Compare states
    changed, result_type, reason = states_are_different(initial_state, new_state, action.get("action_type"))

    if result_type == "success":
        print(f"✅ Action validated: {reason}")
        return True, reason
    elif result_type == "likely_success":
        print(f"🔶 Likely successful: {reason}")
        return True, reason
    elif result_type == "partial_success":
        print(f"⚠️ Partial success: {reason}")
        return True, reason  # Consider partial as success but log it
    elif result_type == "failure":
        print(f"❌ Action failed: {reason}")
        return False, reason
    elif result_type == "no_change":
        print(f"❌ Action had no effect: {reason}")
        return False, reason
    else:
        print(f"❓ Uncertain result: {reason}")
        return False, reason

def execute_single_step(driver, resume_data, step_num, memory, session):
    """Execute ONE action with memory-informed strategies."""

    print(f"\n{'='*80}")
    print(f"🎯 STEP {step_num} - ANALYZING CURRENT PAGE")
    print(f"{'='*80}\n")

    time.sleep(2)
    take_screenshot(driver, step_num, "before")

    # Extract current page
    print("📊 Reading page...")
    page_info = extract_page_info(driver)
    page_signature = create_page_signature(page_info)

    # Capture initial state for validation
    initial_state = capture_page_state(driver)

    # Check if we've been here before
    print_page_summary(page_info, memory, page_signature)

    # Update session
    session["last_step"] = step_num
    session["last_url"] = driver.current_url
    save_session_state(session)

    user_guidance = None

    # Decide action with memory insights
    print("🤔 Deciding action (checking memory for past successes)...")
    action = decide_action(page_info, resume_data, memory, page_signature, user_guidance)

    confidence_emoji = {"high": "✅", "medium": "🔶", "low": "⚠️"}
    print(f"\n📋 ACTION DECIDED ({confidence_emoji.get(action.get('confidence', 'low'), '❓')} confidence):")
    print(f"  Type: {action.get('action_type')}")
    print(f"  Reasoning: {action.get('reasoning')}")
    print(f"  Using Memory: {action.get('using_memory', False)}")

    if INTERACTIVE_MODE:
        user_input2 = interactive_checkpoint(step_num, "REVIEW ANALYSIS")
        if user_input2:
            if user_input2.get("action") == "quit":
                return False, "User quit"
            elif user_input2.get("action") == "guidance":
                lesson = user_input2.get("message", "")
                user_guidance = (user_guidance or "") + "\n" + lesson
                add_learning(memory, page_info.get("url", ""), lesson, success=True)

    # Try executing with retries
    current_url = driver.current_url
    success = False
    last_error = None

    for retry_attempt in range(MAX_RETRIES):
        if retry_attempt > 0:
            print(f"\n🔄 RETRY ATTEMPT {retry_attempt + 1}/{MAX_RETRIES}")
            time.sleep(2)

        # Generate code with memory insights
        print(f"🤖 Generating code (using past experience)... (attempt {retry_attempt + 1})")
        code = generate_code_for_action(page_info, resume_data, action, memory, page_signature, user_guidance, retry_attempt)

        if last_error:
            code = f"# Previous error: {last_error[:200]}\n# Adjusting approach...\n\n" + code

        log_to_file(f"step{step_num}_attempt{retry_attempt + 1}_code", code)

        print(f"\n{'='*80}")
        print(f"📝 GENERATED CODE (Attempt {retry_attempt + 1}):")
        print(f"{'='*80}")
        print(code[:800])  # Show first 800 chars
        if len(code) > 800:
            print("... [truncated]")
        print(f"{'='*80}\n")

        # Execute
        try:
            print(f"⚙️ EXECUTING (Attempt {retry_attempt + 1})...\n")

            exec_globals = {
                "driver": driver,
                "By": By,
                "Keys": Keys,
                "resume_data": resume_data,
                "resume_pdf_path": RESUME_PDF_PATH,
                "resume_photo_path": RESUME_PHOTO_PATH,
                "time": time,
                "WebDriverWait": WebDriverWait,
                "EC": EC,
                "NoSuchElementException": NoSuchElementException,
                "ElementClickInterceptedException": ElementClickInterceptedException,
            }

            exec(code, exec_globals)

            print(f"\n✅ Code executed without exception")

            # VALIDATE if the action actually succeeded
            actual_success, validation_reason = validate_action_success(
                driver, initial_state, action, expected_wait=3
            )

            if actual_success:
                print(f"✅ Action genuinely successful: {validation_reason}")
                success = True

                # Record successful action WITH validation reason
                record_action(memory, page_signature, action, code, success=True)
                add_learning(memory, page_info.get("url", ""),
                           f"Successful action: {action.get('action_type')} - {validation_reason}",
                           success=True)

                # Add to success sequence if page changed
                if driver.current_url != current_url:
                    if not session.get("current_sequence"):
                        session["current_sequence"] = []
                    session["current_sequence"].append({
                        "page_signature": page_signature,
                        "action": action,
                        "url": current_url,
                        "validation": validation_reason
                    })

                break  # Success, exit retry loop
            else:
                # Code executed but didn't achieve desired outcome
                print(f"⚠️ Code executed but action failed validation: {validation_reason}")
                last_error = f"Validation failed: {validation_reason}"

                # Record as failed even though code executed
                record_action(memory, page_signature, action, code, success=False,
                            error_msg=f"No state change: {validation_reason}")

                # Learn from this specific failure
                add_learning(memory, page_info.get("url", ""),
                           f"Action executed but had no effect: {action.get('action_type')} - {validation_reason}",
                           success=False)

                # Continue to retry with different approach
                if retry_attempt < MAX_RETRIES - 1:
                    print(f"\n🔄 Will retry with different approach...")
                else:
                    print(f"\n❌ Max retries reached - action consistently has no effect")

        except Exception as e:
            error_msg = traceback.format_exc()
            last_error = str(e)
            print(f"\n❌ Execution error (attempt {retry_attempt + 1}):\n{str(e)[:200]}")
            log_to_file(f"step{step_num}_attempt{retry_attempt + 1}_error", error_msg)

            # Record failed action
            record_action(memory, page_signature, action, code, success=False, error_msg=str(e))

            if retry_attempt < MAX_RETRIES - 1:
                print(f"\n🔄 Will retry with error feedback...")
                add_learning(memory, page_info.get("url", ""), f"Error on attempt {retry_attempt + 1}: {str(e)[:100]}", success=False)
            else:
                print(f"\n❌ Max retries ({MAX_RETRIES}) reached")
                add_learning(memory, page_info.get("url", ""), f"Failed after {MAX_RETRIES} attempts: {str(e)[:100]}", success=False)

    time.sleep(2)
    take_screenshot(driver, step_num, "after")

    # Check if page changed
    new_url = driver.current_url
    page_changed = (new_url != current_url)

    if page_changed:
        print(f"\n✅ Page changed!")
        print(f"   From: {current_url[:60]}...")
        print(f"   To:   {new_url[:60]}...")

        # Mark page as completed in session
        if current_url not in session["completed_pages"]:
            session["completed_pages"].append(current_url)
    else:
        print(f"\nℹ️  Still on same page")
        if not success:
            print("   ⚠️  Action may have failed - page didn't change")

    # Final validation - double check the actual outcome
    final_state = capture_page_state(driver)
    _, final_result, final_reason = states_are_different(initial_state, final_state, action.get("action_type"))

    # Save memory after each step with detailed outcome
    save_agent_memory(memory)

    # Return based on actual validation, not just code execution
    if final_result in ["success", "likely_success"]:
        return True, f"Validated success: {final_reason}"
    elif final_result == "partial_success":
        return True, f"Partial success: {final_reason}"
    else:
        return False, f"Action failed validation: {final_reason}"

def main():
    print("\n" + "="*80)
    print("🚀 INTELLIGENT JOB APPLICATION AGENT v4.0")
    print("🧠 Enhanced Memory System - Learns from Experience")
    print("📊 Pattern Recognition - Avoids Past Mistakes")
    print("✨ Adaptive Strategies - Improves with Each Run")
    print("="*80 + "\n")

    # Load memory and session
    memory = load_agent_memory()
    session = load_session_state()

    # Load resume
    print("📄 Loading resume...")
    resume_data = load_resume_details(RESUME_JSON_PATH)
    print(f"✅ {resume_data['personal_info']['name']}")
    print(f"📧 {resume_data['personal_info']['email']}\n")

    print(f"⚙️  Interactive Mode: {'ON' if INTERACTIVE_MODE else 'OFF'}")
    if INTERACTIVE_MODE and AUTO_CONTINUE_TIMEOUT > 0:
        print(f"⏱️  Auto-continue timeout: {AUTO_CONTINUE_TIMEOUT} seconds")
    print(f"🔄 Max retries per step: {MAX_RETRIES}")
    print(f"📊 Memory stats: {len(memory.get('action_history', []))} past actions")
    print()

    # Start browser
    print("🌐 Starting browser...")
    driver = create_driver()

    try:
        # Navigate to job URL or resume from last URL
        if session.get("last_url") and session["last_url"] != JOB_URL:
            print(f"📂 Resuming from: {session['last_url'][:60]}...")
            driver.get(session["last_url"])
        else:
            print(f"🔗 Navigating to job...")
            driver.get(JOB_URL)

        print(f"✅ {driver.title}\n")

        # Main loop
        start_step = session.get("last_step", 0) + 1
        for step in range(start_step, MAX_STEPS + 1):
            should_continue, reason = execute_single_step(driver, resume_data, step, memory, session)

            if not should_continue:
                print(f"\n🛑 Stopped: {reason}")
                break

            print(f"\n{'='*80}")
            print(f"✓ Step {step} complete. Moving to next...")
            print(f"{'='*80}\n")
            time.sleep(2)

        # Save final state
        save_agent_memory(memory)
        save_session_state(session)

        # Record successful sequence if completed
        if session.get("current_sequence"):
            memory["success_sequences"].append({
                "timestamp": datetime.datetime.now().isoformat(),
                "sequence": session["current_sequence"],
                "job_url": JOB_URL
            })
            save_agent_memory(memory)

        print("\n" + "="*80)
        print("✅ PROCESS COMPLETED")
        print("="*80)
        print(f"🌐 Final URL: {driver.current_url}")
        print(f"📊 Learned: {len(memory.get('learnings', []))} lessons")
        print(f"✨ Recorded: {len(memory.get('action_history', []))} actions")
        print()

        print("Press Enter to close browser...")
        input()

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        save_agent_memory(memory)
        save_session_state(session)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        save_agent_memory(memory)
        save_session_state(session)
    finally:
        driver.quit()
        print("\n✅ Done!")

if __name__ == "__main__":
    main()
