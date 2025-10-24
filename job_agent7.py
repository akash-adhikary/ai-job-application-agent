import os
import json
import time
import traceback
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
OLLAMA_MODEL = "gpt-oss:120b-cloud"
MAX_RETRIES = 3
MAX_STEPS = 20  # Maximum navigation steps
HTML_LIMIT = 40000
SCREENSHOT_DIR = "screenshots"
LOG_DIR = "ollama_logs"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
# ----------------------------

# === Your file paths ===
JOB_URL = "https://intel.wd1.myworkdayjobs.com/External/job/India-Bangalore/Senior-Data-Analytics-Engineer_JR0276446/apply?source=LinkedIn"
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
        print(f"📸 Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")
        return None

def load_resume_details(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def create_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    # opts.add_argument("--headless")  # Uncomment for headless mode
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

def call_ollama(prompt, model=OLLAMA_MODEL):
    """Call Ollama API and return response."""
    try:
        print("\n" + "="*80)
        print("🤖 AI Agent thinking...")
        print("="*80 + "\n")
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=300
        )
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        
        print("✅ AI response received\n")
        return result
    except Exception as e:
        print(f"⚠️ Ollama call failed: {e}")
        traceback.print_exc()
        return ""

def extract_comprehensive_page_info(driver):
    """Extract all useful information from the current page."""
    try:
        info = {
            "url": driver.current_url,
            "title": driver.title,
            "page_text": "",
            "buttons": [],
            "inputs": [],
            "selects": [],
            "textareas": [],
            "file_inputs": [],
            "links": [],
            "labels": [],
            "headings": [],
            "forms": []
        }
        
        # Get visible page text
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            info["page_text"] = body.text[:2000]  # First 2000 chars
        except:
            pass
        
        # Get headings
        try:
            for tag in ["h1", "h2", "h3"]:
                headings = driver.find_elements(By.TAG_NAME, tag)
                for h in headings[:10]:
                    if h.is_displayed() and h.text.strip():
                        info["headings"].append({
                            "level": tag,
                            "text": h.text.strip()
                        })
        except:
            pass
        
        # Get all buttons
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons[:30]:
                try:
                    if btn.is_displayed():
                        info["buttons"].append({
                            "text": btn.text.strip(),
                            "type": btn.get_attribute("type"),
                            "class": btn.get_attribute("class"),
                            "id": btn.get_attribute("id"),
                            "aria_label": btn.get_attribute("aria-label")
                        })
                except:
                    continue
        except:
            pass
        
        # Get all input fields with labels
        try:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs[:40]:
                try:
                    if not inp.is_displayed():
                        continue
                    
                    input_type = inp.get_attribute("type") or "text"
                    
                    # Try to find associated label
                    label_text = ""
                    try:
                        input_id = inp.get_attribute("id")
                        if input_id:
                            label = driver.find_element(By.CSS_SELECTOR, f"label[for='{input_id}']")
                            label_text = label.text.strip()
                    except:
                        pass
                    
                    if input_type == "file":
                        info["file_inputs"].append({
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "accept": inp.get_attribute("accept"),
                            "label": label_text
                        })
                    else:
                        info["inputs"].append({
                            "type": input_type,
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "placeholder": inp.get_attribute("placeholder"),
                            "value": inp.get_attribute("value"),
                            "required": inp.get_attribute("required"),
                            "label": label_text,
                            "aria_label": inp.get_attribute("aria-label")
                        })
                except:
                    continue
        except:
            pass
        
        # Get all select dropdowns
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in selects[:20]:
                try:
                    if sel.is_displayed():
                        # Get label
                        label_text = ""
                        try:
                            sel_id = sel.get_attribute("id")
                            if sel_id:
                                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{sel_id}']")
                                label_text = label.text.strip()
                        except:
                            pass
                        
                        # Get options
                        options = sel.find_elements(By.TAG_NAME, "option")
                        option_texts = [opt.text.strip() for opt in options[:15] if opt.text.strip()]
                        
                        info["selects"].append({
                            "name": sel.get_attribute("name"),
                            "id": sel.get_attribute("id"),
                            "label": label_text,
                            "options": option_texts
                        })
                except:
                    continue
        except:
            pass
        
        # Get all textareas
        try:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas[:15]:
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
                            "placeholder": ta.get_attribute("placeholder"),
                            "label": label_text
                        })
                except:
                    continue
        except:
            pass
        
        # Get important links
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            keywords = ["apply", "next", "continue", "submit", "save", "sign", "login", "register", "start"]
            for link in links:
                try:
                    if link.is_displayed() and link.text.strip():
                        link_text = link.text.strip().lower()
                        if any(kw in link_text for kw in keywords):
                            info["links"].append({
                                "text": link.text.strip(),
                                "href": link.get_attribute("href"),
                                "class": link.get_attribute("class")
                            })
                except:
                    continue
        except:
            pass
        
        return info
    except Exception as e:
        return {"error": str(e), "url": driver.current_url, "title": driver.title}

def print_page_analysis(info):
    """Print formatted page analysis."""
    print("\n" + "="*80)
    print("📊 PAGE ANALYSIS")
    print("="*80)
    print(f"URL: {info.get('url', 'N/A')}")
    print(f"Title: {info.get('title', 'N/A')}\n")
    
    if info.get('headings'):
        print("📑 Headings:")
        for h in info['headings'][:5]:
            print(f"  {h['level'].upper()}: {h['text']}")
    
    if info.get('page_text'):
        print(f"\n📄 Page Content Preview:\n{info['page_text'][:500]}...\n")
    
    if info.get('buttons'):
        print(f"🔘 Buttons ({len(info['buttons'])}):")
        for btn in info['buttons'][:8]:
            print(f"  - '{btn['text']}' (type: {btn['type']}, id: {btn['id']})")
    
    if info.get('inputs'):
        print(f"\n📝 Input Fields ({len(info['inputs'])}):")
        for inp in info['inputs'][:12]:
            label = inp.get('label') or inp.get('placeholder') or inp.get('aria_label') or 'No label'
            print(f"  - {inp['type']}: {label} (name: {inp['name']}, id: {inp['id']})")
    
    if info.get('selects'):
        print(f"\n📋 Dropdowns ({len(info['selects'])}):")
        for sel in info['selects'][:8]:
            label = sel.get('label') or 'No label'
            print(f"  - {label} ({len(sel.get('options', []))} options)")
    
    if info.get('textareas'):
        print(f"\n📄 Text Areas ({len(info['textareas'])}):")
        for ta in info['textareas'][:5]:
            label = ta.get('label') or ta.get('placeholder') or 'No label'
            print(f"  - {label}")
    
    if info.get('file_inputs'):
        print(f"\n📎 File Upload Fields ({len(info['file_inputs'])}):")
        for fi in info['file_inputs']:
            label = fi.get('label') or 'No label'
            print(f"  - {label} (accepts: {fi['accept']})")
    
    if info.get('links'):
        print(f"\n🔗 Important Links ({len(info['links'])}):")
        for link in info['links'][:8]:
            print(f"  - '{link['text']}'")
    
    print("="*80 + "\n")

def ask_ai_for_strategy(page_info, resume_data, step_num, history):
    """Ask AI to analyze the page and decide what to do."""
    prompt = f"""You are an intelligent job application automation agent. You are currently at STEP {step_num} of a multi-step job application process.

Your task is to analyze the current page and decide what action to take.

CURRENT PAGE INFORMATION:
{json.dumps(page_info, indent=2)}

CANDIDATE'S RESUME DATA (available to fill forms):
{json.dumps(resume_data, indent=2)}

AVAILABLE FILE PATHS:
- resume_pdf_path: Path to resume PDF
- resume_photo_path: Path to profile photo

NAVIGATION HISTORY (what you've done so far):
{json.dumps(history[-5:], indent=2) if history else "This is the first step"}

ANALYZE THE PAGE AND RESPOND WITH A JSON OBJECT containing your strategy:

{{
  "page_type": "login" | "signup" | "form" | "application" | "confirmation" | "unknown",
  "needs_user_input": true | false,
  "user_prompt_message": "What you need to ask user (if needs_user_input is true)",
  "action_plan": "Brief description of what you'll do",
  "can_proceed": true | false,
  "reason_if_stuck": "Explain why you can't proceed (if can_proceed is false)"
}}

EXAMPLES:
- If it's a login page but we don't have credentials: {{"page_type": "login", "needs_user_input": true, "user_prompt_message": "Please provide your login credentials (email/password) or create a new account.", "action_plan": "Wait for user credentials", "can_proceed": false, "reason_if_stuck": "Requires login credentials"}}
- If it's a form with fields to fill: {{"page_type": "form", "needs_user_input": false, "action_plan": "Fill all form fields with resume data and click Next/Continue", "can_proceed": true}}
- If you need information not in resume: {{"page_type": "form", "needs_user_input": true, "user_prompt_message": "Please provide: [list missing info]", "action_plan": "Fill available fields, ask for missing data", "can_proceed": false}}

Respond ONLY with the JSON object, no other text."""

    response = call_ollama(prompt)
    
    # Try to parse JSON
    try:
        # Clean up response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        strategy = json.loads(response)
        return strategy
    except:
        print(f"⚠️ Failed to parse AI strategy, raw response:\n{response}")
        return {
            "page_type": "unknown",
            "needs_user_input": False,
            "action_plan": "Attempt to fill any visible forms",
            "can_proceed": True
        }

def generate_automation_code(page_info, resume_data, strategy, step_num):
    """Generate Selenium code to execute the strategy."""
    
    html_snippet = ""
    try:
        # We'll pass minimal HTML since we have structured page_info
        html_snippet = f"Page has {len(page_info.get('inputs', []))} inputs, {len(page_info.get('buttons', []))} buttons, {len(page_info.get('selects', []))} dropdowns"
    except:
        pass
    
    prompt = f"""You are a Selenium automation expert. Generate Python code to execute this strategy on STEP {step_num}.

STRATEGY:
{json.dumps(strategy, indent=2)}

PAGE INFORMATION:
{json.dumps(page_info, indent=2)}

RESUME DATA:
{json.dumps(resume_data, indent=2)}

IMPORTANT INSTRUCTIONS:
1. Use WebDriverWait with explicit waits (10-15 seconds) for ALL element interactions
2. Use try-except blocks for each action to handle missing elements
3. Print what you're doing at each step (e.g., "Filling First Name field...")
4. Match form fields intelligently:
   - For name fields: split personal_info.name into first/last
   - For phone: use personal_info.phone
   - For email: use personal_info.email
   - For experience/skills: extract from relevant resume sections
   - For dropdowns: select the best matching option from available choices
5. For file uploads: use element.send_keys(resume_pdf_path) or send_keys(resume_photo_path)
6. After filling forms, click the appropriate button (Next/Continue/Submit/Apply)
7. If login is required but we don't have credentials, just print a message and return
8. Add time.sleep(1-2) after major actions to let page load
9. Handle checkboxes, radio buttons, and any special elements
10. SCROLL to elements before interacting: driver.execute_script("arguments[0].scrollIntoView(true);", element)

AVAILABLE VARIABLES:
- driver: WebDriver instance
- By: Selenium By class
- resume_data: dict with resume information
- resume_pdf_path: string path to PDF file
- resume_photo_path: string path to photo file
- time: time module
- WebDriverWait: for explicit waits
- EC: expected_conditions
- NoSuchElementException: exception class

RESPONSE FORMAT:
Generate ONLY executable Python code. No markdown fences, no explanations, just pure Python code.

EXAMPLE PATTERN:
```
try:
    print("Clicking Apply button...")
    wait = WebDriverWait(driver, 15)
    apply_btn = wait.until(EC.element_to_be_clickable((By.ID, "apply-button")))
    driver.execute_script("arguments[0].scrollIntoView(true);", apply_btn)
    time.sleep(1)
    apply_btn.click()
    print("✓ Clicked Apply button")
except Exception as e:
    print(f"Could not click Apply button: {{e}}")
```

Now generate the complete automation code:"""

    code = call_ollama(prompt)
    
    # Clean up code
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    return code.strip()

def execute_step(driver, resume_data, step_num, history):
    """Execute a single step of the application process."""
    
    print(f"\n{'='*80}")
    print(f"🎯 STEP {step_num}")
    print(f"{'='*80}\n")
    
    time.sleep(3)  # Let page stabilize
    
    # Take screenshot
    take_screenshot(driver, step_num, "before")
    
    # Extract page info
    print("📊 Analyzing page...")
    page_info = extract_comprehensive_page_info(driver)
    print_page_analysis(page_info)
    
    # Ask AI for strategy
    print("\n🤔 AI Agent deciding strategy...")
    strategy = ask_ai_for_strategy(page_info, resume_data, step_num, history)
    
    print("\n📋 AI STRATEGY:")
    print(json.dumps(strategy, indent=2))
    print()
    
    # Check if user input needed
    if strategy.get("needs_user_input"):
        print("\n" + "="*80)
        print("⚠️ USER INPUT REQUIRED")
        print("="*80)
        print(f"\n{strategy.get('user_prompt_message', 'Additional information needed')}\n")
        
        user_input = input("Enter information (or 'skip' to skip this step): ").strip()
        
        if user_input.lower() == 'skip':
            print("⏭️ Skipping this step...")
            return False, strategy
        
        # Store user input for use in code generation
        strategy['user_provided_data'] = user_input
    
    # Check if can proceed
    if not strategy.get("can_proceed"):
        reason = strategy.get("reason_if_stuck", "Unknown reason")
        print(f"\n⚠️ Cannot proceed: {reason}")
        print("\nOptions:")
        print("1. Press Enter to try manual intervention")
        print("2. Type 'continue' to force automation attempt")
        print("3. Type 'quit' to exit")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'quit':
            return False, strategy
        elif choice == 'continue':
            print("🔄 Forcing automation attempt...")
        else:
            print("\n👤 Please interact with the page manually, then press Enter when ready...")
            input()
            return True, strategy
    
    # Generate automation code
    print("\n🤖 Generating automation code...")
    code = generate_automation_code(page_info, resume_data, strategy, step_num)
    
    # Log code
    log_path = log_to_file(f"step{step_num}_code", code)
    print(f"📝 Code logged to: {log_path}")
    
    print(f"\n{'='*80}")
    print("📝 GENERATED CODE:")
    print(f"{'='*80}")
    print(code)
    print(f"{'='*80}\n")
    
    # Execute code
    current_url = driver.current_url
    success = False
    
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"\n🔄 Retry attempt {attempt}/{MAX_RETRIES}")
        
        try:
            print("⚙️ Executing automation code...\n")
            
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
            }
            
            exec(code, exec_globals)
            
            print("\n✅ Code executed successfully!")
            success = True
            break
            
        except Exception as e:
            err_text = traceback.format_exc()
            print(f"\n❌ Execution error:\n{err_text}")
            log_to_file(f"step{step_num}_attempt{attempt}_error", err_text)
            
            if attempt < MAX_RETRIES:
                print("\n🔄 Regenerating code with error feedback...")
                code = generate_automation_code(page_info, resume_data, strategy, step_num)
            else:
                print("\n❌ Max retries reached")
    
    # Take screenshot after
    time.sleep(2)
    take_screenshot(driver, step_num, "after")
    
    # Check if page changed
    new_url = driver.current_url
    page_changed = (new_url != current_url)
    
    if page_changed:
        print(f"\n✅ Navigation successful: {current_url} → {new_url}")
    else:
        print(f"\nℹ️ Still on same page")
    
    # Update history
    history.append({
        "step": step_num,
        "url": current_url,
        "page_type": strategy.get("page_type"),
        "action": strategy.get("action_plan"),
        "success": success,
        "page_changed": page_changed
    })
    
    return page_changed or success, strategy

def main():
    print("\n" + "="*80)
    print("🚀 INTELLIGENT JOB APPLICATION AGENT")
    print("="*80 + "\n")
    
    # Load resume
    print("📄 Loading resume data...")
    resume_data = load_resume_details(RESUME_JSON_PATH)
    print(f"✅ Loaded resume: {resume_data['personal_info']['name']}")
    print(f"📧 Email: {resume_data['personal_info']['email']}")
    print(f"📱 Phone: {resume_data['personal_info']['phone']}\n")
    
    # Start browser
    print("🌐 Starting Chrome browser...")
    driver = create_driver()
    
    history = []
    
    try:
        print(f"🔗 Navigating to job page...")
        driver.get(JOB_URL)
        print(f"✅ Loaded: {driver.title}\n")
        
        # Main loop - navigate through all steps
        for step in range(1, MAX_STEPS + 1):
            should_continue, strategy = execute_step(driver, resume_data, step, history)
            
            if not should_continue:
                print(f"\n🛑 Stopping at step {step}")
                break
            
            # Check if we've reached a confirmation or completion page
            page_type = strategy.get("page_type", "")
            if page_type in ["confirmation", "complete", "success"]:
                print(f"\n🎉 Application appears complete!")
                break
            
            print(f"\n➡️ Moving to next step...\n")
            time.sleep(2)
        
        print("\n" + "="*80)
        print("✅ PROCESS COMPLETED")
        print("="*80)
        print(f"\n📊 Summary: Completed {len(history)} steps")
        print(f"🌐 Final URL: {driver.current_url}")
        
        print("\n👀 Browser left open for review.")
        print("Press Enter to close...")
        input()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        print("\n🔚 Closing browser...")
        driver.quit()
        print("✅ Done!")

if __name__ == "__main__":
    main()