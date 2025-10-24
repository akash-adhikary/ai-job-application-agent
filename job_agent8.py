import os
import json
import time
import traceback
import datetime
import requests
import sys
import select
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
OLLAMA_MODEL = "gpt-oss:120b-cloud"
MAX_RETRIES = 3
MAX_STEPS = 20
HTML_LIMIT = 40000
SCREENSHOT_DIR = "screenshots"
LOG_DIR = "ollama_logs"
MEMORY_FILE = "agent_memory.json"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Interactive mode settings
INTERACTIVE_MODE = True  # Set to False for fully automated mode
AUTO_CONTINUE_TIMEOUT = 2  # Seconds to wait before auto-continuing (0 = wait forever)
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

def load_agent_memory():
    """Load past learnings."""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memory = json.load(f)
                print(f"🧠 Memory loaded: {len(memory.get('learnings', []))} learnings")
                return memory
    except Exception as e:
        print(f"⚠️ Could not load memory: {e}")
    
    return {
        "learnings": [],
        "domain_knowledge": {
            "skill_selectors": "For searchable skill dropdowns: type ONE skill, wait 1 sec, click suggestion. Repeat for each skill.",
            "file_uploads": "ALWAYS verify file upload: after send_keys(), check if value attribute is set. Print confirmation.",
            "multi_select": "Add items one by one: type, wait, select, repeat. Never paste comma-separated list.",
            "button_clicks": "If normal click fails with 'element click intercepted', use JavaScript click: driver.execute_script('arguments[0].click();', element)"
        }
    }

def save_agent_memory(memory):
    """Save learnings."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, indent=2, fp=f)
        print(f"🧠 Memory saved")
    except Exception as e:
        print(f"⚠️ Could not save memory: {e}")

def add_learning(memory, context, lesson):
    """Add learning to memory."""
    memory["learnings"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "context": context,
        "lesson": lesson
    })
    print(f"📚 Learned: {lesson}")

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
    """
    Windows-compatible timed input.
    Returns None if timeout, otherwise returns user input.
    """
    if not INTERACTIVE_MODE:
        return None
    
    if timeout_seconds <= 0:
        # No timeout, wait forever
        return input().strip().lower()
    
    print(prompt_text)
    print(f"⏱️  Auto-continuing in {timeout_seconds} seconds...")
    print("    Press any key to interact, or wait to auto-continue...")
    
    start_time = time.time()
    
    # Import msvcrt for Windows keyboard detection
    try:
        import msvcrt
        
        while True:
            if msvcrt.kbhit():
                # Key was pressed, get the full input
                print("\n⏸️  Input detected, waiting for your command...")
                user_input = input().strip().lower()
                return user_input
            
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                print("\n⏩ Auto-continuing...\n")
                return None
            
            time.sleep(0.1)
    
    except ImportError:
        # Fallback for non-Windows (Unix/Linux/Mac)
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
        # Wait a bit for any dynamic content to load
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
            "modal_content": ""
        }
        
        # Check for modals/popups/dialogs
        try:
            modals = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'], div[class*='modal'], div[class*='popup'], div[class*='overlay']")
            visible_modals = [m for m in modals if m.is_displayed()]
            
            if visible_modals:
                info["modals_detected"] = True
                # Get text from the first visible modal
                try:
                    info["modal_content"] = visible_modals[0].text[:1000]
                except:
                    pass
        except:
            pass
        
        # Page text preview (prioritize modal if present)
        try:
            if info["modals_detected"]:
                info["page_text"] = info["modal_content"]
            else:
                body = driver.find_element(By.TAG_NAME, "body")
                info["page_text"] = body.text[:1500]
        except:
            pass
        
        # Buttons (check modals first, then page)
        try:
            # If modal is present, prioritize buttons inside modal
            if info.get("modals_detected"):
                modal_buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] button, div[class*='modal'] button")
                for btn in modal_buttons[:20]:
                    try:
                        if btn.is_displayed() and btn.text.strip():
                            info["buttons"].append({
                                "text": btn.text.strip(),
                                "type": btn.get_attribute("type"),
                                "id": btn.get_attribute("id"),
                                "class": btn.get_attribute("class"),
                                "aria_label": btn.get_attribute("aria-label"),
                                "in_modal": True
                            })
                    except:
                        continue
            
            # Regular page buttons
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons[:25]:
                try:
                    if btn.is_displayed() and btn.text.strip():
                        info["buttons"].append({
                            "text": btn.text.strip(),
                            "type": btn.get_attribute("type"),
                            "id": btn.get_attribute("id"),
                            "class": btn.get_attribute("class"),
                            "aria_label": btn.get_attribute("aria-label"),
                            "in_modal": False
                        })
                except:
                    continue
        except:
            pass
        
        # Also check for divs acting as buttons (in modals and page)
        try:
            if info.get("modals_detected"):
                modal_div_buttons = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] div[role='button'], div[class*='modal'] div[data-automation-id*='button']")
                for div in modal_div_buttons[:10]:
                    try:
                        if div.is_displayed() and div.text.strip():
                            info["buttons"].append({
                                "text": div.text.strip(),
                                "type": "div-button",
                                "id": div.get_attribute("id"),
                                "class": div.get_attribute("class"),
                                "aria_label": div.get_attribute("aria-label"),
                                "data_automation_id": div.get_attribute("data-automation-id"),
                                "in_modal": True
                            })
                    except:
                        continue
            
            clickable_divs = driver.find_elements(By.CSS_SELECTOR, "div[role='button'], div[data-automation-id*='button']")
            for div in clickable_divs[:15]:
                try:
                    if div.is_displayed() and div.text.strip():
                        info["buttons"].append({
                            "text": div.text.strip(),
                            "type": "div-button",
                            "id": div.get_attribute("id"),
                            "class": div.get_attribute("class"),
                            "aria_label": div.get_attribute("aria-label"),
                            "data_automation_id": div.get_attribute("data-automation-id"),
                            "in_modal": False
                        })
                except:
                    continue
        except:
            pass
        
        # Also check for <a> tags acting as buttons (in modals and page)
        try:
            if info.get("modals_detected"):
                modal_links = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] a[role='button'], div[class*='modal'] a[data-automation-id*='apply']")
                for link in modal_links[:10]:
                    try:
                        if link.is_displayed() and link.text.strip():
                            info["buttons"].append({
                                "text": link.text.strip(),
                                "type": "link-button",
                                "id": link.get_attribute("id"),
                                "class": link.get_attribute("class"),
                                "aria_label": link.get_attribute("aria-label"),
                                "data_automation_id": link.get_attribute("data-automation-id"),
                                "href": link.get_attribute("href"),
                                "in_modal": True
                            })
                    except:
                        continue
            
            action_links = driver.find_elements(By.CSS_SELECTOR, "a[role='button'], a[data-automation-id*='Apply'], a[data-automation-id*='apply'], a[data-automation-id*='Button']")
            for link in action_links[:15]:
                try:
                    if link.is_displayed() and link.text.strip():
                        info["buttons"].append({
                            "text": link.text.strip(),
                            "type": "link-button",
                            "id": link.get_attribute("id"),
                            "class": link.get_attribute("class"),
                            "aria_label": link.get_attribute("aria-label"),
                            "data_automation_id": link.get_attribute("data-automation-id"),
                            "href": link.get_attribute("href"),
                            "in_modal": False
                        })
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
        
        # Dropdowns
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in selects[:20]:
                try:
                    if sel.is_displayed():
                        label_text = ""
                        try:
                            sel_id = sel.get_attribute("id")
                            if sel_id:
                                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{sel_id}']")
                                label_text = label.text.strip()
                        except:
                            pass
                        
                        options = sel.find_elements(By.TAG_NAME, "option")
                        option_texts = [opt.text.strip() for opt in options[:12] if opt.text.strip()]
                        
                        info["selects"].append({
                            "name": sel.get_attribute("name"),
                            "id": sel.get_attribute("id"),
                            "label": label_text,
                            "options": option_texts,
                            "current_value": sel.get_attribute("value"),
                            "is_filled": bool(sel.get_attribute("value"))
                        })
                except:
                    continue
        except:
            pass
        
        # Textareas
        try:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas[:12]:
                try:
                    if ta.is_displayed():
                        label_text = ""
                        try:
                            ta_id = ta.get_attribute("id")
                            if ta_id:
                                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{ta_id}']")
                                label_text = label.text.strip()
                        except:
                            pass
                        
                        info["textareas"].append({
                            "name": ta.get_attribute("name"),
                            "id": ta.get_attribute("id"),
                            "label": label_text or ta.get_attribute("placeholder"),
                            "placeholder": ta.get_attribute("placeholder"),
                            "value": ta.get_attribute("value"),
                            "is_filled": bool(ta.get_attribute("value"))
                        })
                except:
                    continue
        except:
            pass
        
        return info
    except Exception as e:
        return {"error": str(e), "url": driver.current_url}

def print_page_summary(info):
    """Print concise page summary."""
    print("\n" + "="*80)
    print("📊 CURRENT PAGE")
    print("="*80)
    print(f"URL: {info.get('url', 'N/A')}")
    print(f"Title: {info.get('title', 'N/A')}")
    
    # Alert if modal detected
    if info.get("modals_detected"):
        print("\n🔔 MODAL/POPUP DETECTED!")
        if info.get("modal_content"):
            print(f"Modal content preview: {info.get('modal_content')[:200]}...")
    
    # Count filled vs unfilled
    inputs = info.get('inputs', [])
    filled_inputs = [i for i in inputs if i.get('is_filled')]
    
    selects = info.get('selects', [])
    filled_selects = [s for s in selects if s.get('is_filled')]
    
    textareas = info.get('textareas', [])
    filled_textareas = [t for t in textareas if t.get('is_filled')]
    
    file_inputs = info.get('file_inputs', [])
    filled_files = [f for f in file_inputs if f.get('is_filled')]
    
    print(f"\n📝 Inputs: {len(filled_inputs)}/{len(inputs)} filled")
    print(f"📋 Dropdowns: {len(filled_selects)}/{len(selects)} selected")
    print(f"📄 Textareas: {len(filled_textareas)}/{len(textareas)} filled")
    print(f"📎 Files: {len(filled_files)}/{len(file_inputs)} uploaded")
    print(f"🔘 Buttons: {len(info.get('buttons', []))}")
    
    # Show buttons (prioritize modal buttons)
    buttons = info.get('buttons', [])
    modal_buttons = [b for b in buttons if b.get('in_modal')]
    page_buttons = [b for b in buttons if not b.get('in_modal')]
    
    if modal_buttons:
        print(f"\n🔘 MODAL BUTTONS ({len(modal_buttons)}):")
        for btn in modal_buttons[:8]:
            print(f"  - '{btn['text']}' ({btn.get('type', 'button')})")
    
    if page_buttons:
        print(f"\n🔘 Page Buttons ({len(page_buttons)}):")
        for btn in page_buttons[:8]:
            print(f"  - '{btn['text']}' ({btn.get('type', 'button')})")
    
    # Show unfilled critical fields
    unfilled = []
    for inp in inputs:
        if not inp.get('is_filled') and inp.get('required'):
            unfilled.append(f"  ⚠️ {inp.get('label', inp.get('name', 'Unnamed'))} (REQUIRED)")
    
    for fi in file_inputs:
        if not fi.get('is_filled'):
            unfilled.append(f"  ⚠️ {fi.get('label', 'File upload')} (NOT UPLOADED)")
    
    if unfilled:
        print("\n⚠️ UNFILLED CRITICAL FIELDS:")
        for u in unfilled:
            print(u)
    
    print("="*80 + "\n")

def decide_action(page_info, resume_data, memory, user_guidance=None):
    """AI decides what SINGLE action to take on THIS page."""
    
    domain_knowledge = memory.get("domain_knowledge", {})
    recent_learnings = [l.get("lesson", "") for l in memory.get("learnings", [])[-5:]]
    
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
{guidance_text}

RULES:
1. Analyze ONLY what you see on THIS page
2. Decide ONE action: fill form, click button, upload file, or ask user
3. Do NOT predict future pages
4. Do NOT plan multiple steps ahead
5. Focus on completing THIS page's requirements

Respond with JSON:
{{
  "action_type": "fill_form" | "click_button" | "upload_file" | "needs_user_input" | "done",
  "reasoning": "why you chose this action",
  "target": "what element you'll interact with",
  "needs_guidance": true | false,
  "guidance_request": "what you need from user if needs_guidance=true"
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
        return action
    except:
        print(f"⚠️ Failed to parse action:\n{response[:200]}")
        return {
            "action_type": "fill_form",
            "reasoning": "Default action",
            "target": "available fields",
            "needs_guidance": False
        }

def generate_code_for_action(page_info, resume_data, action, memory, user_guidance=None, retry_attempt=0):
    """Generate code for ONE specific action on THIS page."""
    
    domain_knowledge = memory.get("domain_knowledge", {})
    guidance_text = f"\n\nUSER GUIDANCE: {user_guidance}\n" if user_guidance else ""
    retry_text = f"\n\nThis is RETRY ATTEMPT {retry_attempt}. Previous attempts failed.\n" if retry_attempt > 0 else ""
    
    prompt = f"""Generate Selenium code for THIS SPECIFIC ACTION on the current page.

ACTION TO TAKE:
{json.dumps(action, indent=2)}

PAGE INFO:
{json.dumps(page_info, indent=2)}

RESUME DATA:
{json.dumps(resume_data, indent=2)}

DOMAIN KNOWLEDGE:
{json.dumps(domain_knowledge, indent=2)}
{guidance_text}
{retry_text}

CRITICAL RULES:

1. **CLICKING BUTTONS/LINKS** - Modern web apps use multiple strategies:
```python
# For "Apply" or action buttons - try multiple selectors
wait = WebDriverWait(driver, 15)
clicked = False

# Strategy 1: Try <a> tags with role or data-automation-id (common in Workday, etc.)
try:
    apply_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-automation-id*='Apply'], a[data-automation-id*='apply'], a[role='button']")))
    driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", apply_link)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", apply_link)
    print("✓ Clicked Apply link (JavaScript)")
    clicked = True
except:
    pass

# Strategy 2: Try visible buttons with text
if not clicked:
    try:
        button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Apply') or contains(text(), 'Next') or contains(text(), 'Continue')]")))
        driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", button)
        time.sleep(0.5)
        try:
            button.click()
            print("✓ Clicked button (normal click)")
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", button)
            print("✓ Clicked button (JavaScript click)")
        clicked = True
    except:
        pass

# Strategy 3: Try divs with role=button
if not clicked:
    try:
        div_button = driver.find_element(By.CSS_SELECTOR, "div[role='button'][data-automation-id*='button']")
        driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", div_button)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", div_button)
        print("✓ Clicked div button (JavaScript)")
        clicked = True
    except:
        pass

# Strategy 4: Last resort - find by text in any clickable element
if not clicked:
    try:
        element = driver.find_element(By.XPATH, "//*[contains(text(), 'Apply') or contains(text(), 'Next')][1]")
        driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", element)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", element)
        print("✓ Clicked element by text (JavaScript)")
        clicked = True
    except Exception as e:
        print(f"✗ Could not click any button: {{e}}")
```

2. **SKILL SELECTORS** (search/autocomplete multi-select):
```python
skills = ["Python", "Spark", "SQL"]
for skill in skills[:5]:
    try:
        skill_input.clear()
        skill_input.send_keys(skill)
        time.sleep(1.5)
        suggestion = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[contains(@class, 'suggestion') and contains(text(), '{{skill}}')]")))
        suggestion.click()
        print(f"✓ Added skill: {{skill}}")
        time.sleep(0.5)
    except:
        print(f"✗ Could not add: {{skill}}")
```

3. **FILE UPLOADS** - VERIFY:
```python
file_input.send_keys(resume_pdf_path)
time.sleep(2)
uploaded_value = file_input.get_attribute("value")
if uploaded_value:
    print(f"✓ File uploaded: {{uploaded_value}}")
else:
    print("⚠️ FILE UPLOAD MAY HAVE FAILED!")
```

4. **GENERAL RULES:**
- ALWAYS use JavaScript click (driver.execute_script("arguments[0].click();", element)) for modern web apps
- Use WebDriverWait(driver, 15) for ALL element interactions
- Scroll to center: `driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", element)`
- Print progress for each action
- Use try-except for each element
- Add time.sleep(1) after important actions
- For Workday and similar portals, prefer CSS selectors with data-automation-id

5. **FIELD MAPPING:**
- Name fields: Split `resume_data["personal_info"]["name"]` into first/last
- Email: `resume_data["personal_info"]["email"]`
- Phone: `resume_data["personal_info"]["phone"]`
- Skills: Extract from `resume_data["technical_skills"]`
- Experience: Calculate from work_experience

Available variables:
- driver, By, resume_data, resume_pdf_path, resume_photo_path
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

def execute_single_step(driver, resume_data, step_num, memory):
    """Execute ONE action on the CURRENT page with retries."""
    
    print(f"\n{'='*80}")
    print(f"🎯 STEP {step_num} - ANALYZING CURRENT PAGE")
    print(f"{'='*80}\n")
    
    time.sleep(2)
    take_screenshot(driver, step_num, "before")
    
    # Extract current page
    print("📊 Reading page...")
    page_info = extract_page_info(driver)
    print_page_summary(page_info)
    
    # Checkpoint - before decision
    user_input = interactive_checkpoint(step_num, "BEFORE ACTION")
    
    if user_input:
        if user_input.get("action") == "quit":
            return False, "User quit"
        elif user_input.get("action") == "manual":
            return True, "Manual intervention"
    
    user_guidance = user_input.get("message") if user_input and user_input.get("action") == "guidance" else None
    
    # Decide action
    print("🤔 Deciding action for THIS page...")
    action = decide_action(page_info, resume_data, memory, user_guidance)
    
    print("\n📋 ACTION DECIDED:")
    print(f"  Type: {action.get('action_type')}")
    print(f"  Reasoning: {action.get('reasoning')}")
    print(f"  Target: {action.get('target')}\n")
    
    # Check if needs guidance
    if action.get("needs_guidance"):
        print(f"\n⚠️ {action.get('guidance_request', 'Need input')}")
        user_response = input("Your input: ").strip()
        user_guidance = (user_guidance or "") + "\n" + user_response
    
    # Try executing with retries
    current_url = driver.current_url
    success = False
    last_error = None
    
    for retry_attempt in range(MAX_RETRIES):
        if retry_attempt > 0:
            print(f"\n🔄 RETRY ATTEMPT {retry_attempt + 1}/{MAX_RETRIES}")
            time.sleep(2)
        
        # Generate code (with retry context if retrying)
        print(f"🤖 Generating code for this action... (attempt {retry_attempt + 1})")
        code = generate_code_for_action(page_info, resume_data, action, memory, user_guidance, retry_attempt)
        
        if last_error:
            code = f"# Previous error: {last_error[:200]}\n\n" + code
        
        log_to_file(f"step{step_num}_attempt{retry_attempt + 1}_code", code)
        
        print(f"\n{'='*80}")
        print(f"📝 GENERATED CODE (Attempt {retry_attempt + 1}):")
        print(f"{'='*80}")
        print(code)
        print(f"{'='*80}\n")
        
        # Checkpoint - before execution (only on first attempt)
        if retry_attempt == 0 and INTERACTIVE_MODE:
            print("⚠️ About to execute. Review code above.")
            choice = timed_input_windows("Press Enter to execute (or 'g' for guidance, 'q' to quit): ", AUTO_CONTINUE_TIMEOUT)
            
            if choice == 'q':
                return False, "User quit"
            elif choice == 'g':
                print("💬 Additional guidance:")
                extra_guidance = input(">>> ").strip()
                user_guidance = (user_guidance or "") + "\n" + extra_guidance
                print("\n🔄 Regenerating with guidance...")
                code = generate_code_for_action(page_info, resume_data, action, memory, user_guidance, retry_attempt)
                print(f"\n{'='*80}")
                print("📝 NEW CODE:")
                print(f"{'='*80}")
                print(code)
                print(f"{'='*80}\n")
        
        # Execute
        try:
            print(f"⚙️ EXECUTING (Attempt {retry_attempt + 1})...\n")
            
            exec_globals = {
                "driver": driver,
                "By": By,
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
            
            print(f"\n✅ Execution completed successfully!")
            success = True
            break  # Success, exit retry loop
            
        except Exception as e:
            error_msg = traceback.format_exc()
            last_error = str(e)
            print(f"\n❌ Execution error (attempt {retry_attempt + 1}):\n{error_msg}")
            log_to_file(f"step{step_num}_attempt{retry_attempt + 1}_error", error_msg)
            
            if retry_attempt < MAX_RETRIES - 1:
                print(f"\n🔄 Will retry with error feedback...")
                add_learning(memory, page_info.get("url", ""), f"Error (will retry): {str(e)[:100]}")
            else:
                print(f"\n❌ Max retries ({MAX_RETRIES}) reached")
                add_learning(memory, page_info.get("url", ""), f"Failed after {MAX_RETRIES} attempts: {str(e)[:100]}")
    
    time.sleep(2)
    take_screenshot(driver, step_num, "after")
    
    # Check if page changed
    new_url = driver.current_url
    page_changed = (new_url != current_url)
    
    if page_changed:
        print(f"\n✅ Page changed!")
        print(f"   From: {current_url}")
        print(f"   To:   {new_url}")
    else:
        print(f"\nℹ️  Still on same page")
        if not success:
            print("   ⚠️  Action may have failed - page didn't change")
    
    # Checkpoint - after execution
    if INTERACTIVE_MODE:
        user_input2 = interactive_checkpoint(step_num, "AFTER ACTION")
        
        if user_input2:
            if user_input2.get("action") == "quit":
                return False, "User quit"
            elif user_input2.get("action") == "guidance":
                lesson = user_input2.get("message", "")
                add_learning(memory, page_info.get("url", ""), lesson)
    
    return success or page_changed, "Success" if success else "Completed with issues"

def main():
    print("\n" + "="*80)
    print("🚀 REACTIVE JOB APPLICATION AGENT v3.1")
    print("📖 Read → Decide → Act → Repeat")
    print("🔧 Fixed: Input handling, button clicks, retries")
    print("="*80 + "\n")
    
    # Load memory
    memory = load_agent_memory()
    
    # Load resume
    print("📄 Loading resume...")
    resume_data = load_resume_details(RESUME_JSON_PATH)
    print(f"✅ {resume_data['personal_info']['name']}")
    print(f"📧 {resume_data['personal_info']['email']}\n")
    
    print(f"⚙️  Interactive Mode: {'ON' if INTERACTIVE_MODE else 'OFF'}")
    if INTERACTIVE_MODE and AUTO_CONTINUE_TIMEOUT > 0:
        print(f"⏱️  Auto-continue timeout: {AUTO_CONTINUE_TIMEOUT} seconds")
    print(f"🔄 Max retries per step: {MAX_RETRIES}")
    print()
    
    # Start browser
    print("🌐 Starting browser...")
    driver = create_driver()
    
    try:
        print(f"🔗 Navigating to job...")
        driver.get(JOB_URL)
        print(f"✅ {driver.title}\n")
        
        # Main loop: read → decide → act
        for step in range(1, MAX_STEPS + 1):
            should_continue, reason = execute_single_step(driver, resume_data, step, memory)
            
            if not should_continue:
                print(f"\n🛑 Stopped: {reason}")
                break
            
            # Small pause between steps
            print(f"\n{'='*80}")
            print(f"✓ Step {step} complete. Moving to next...")
            print(f"{'='*80}\n")
            time.sleep(2)
        
        # Save memory
        save_agent_memory(memory)
        
        print("\n" + "="*80)
        print("✅ PROCESS COMPLETED")
        print("="*80)
        print(f"🌐 Final URL: {driver.current_url}\n")
        
        print("Press Enter to close browser...")
        input()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        save_agent_memory(memory)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        print("\n✅ Done!")

if __name__ == "__main__":
    main()