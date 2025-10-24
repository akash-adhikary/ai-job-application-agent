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
MAX_FORM_STEPS = 10  # Maximum number of form pages to handle
HTML_LIMIT = 30000
LOG_DIR = "ollama_logs"
os.makedirs(LOG_DIR, exist_ok=True)
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
    print(f"📝 Logged to: {filepath}")

def load_resume_details(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def create_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

def run_ollama_stream(prompt):
    """Stream generation from Ollama and show live output."""
    try:
        with requests.post(
            "http://localhost:11434/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
            stream=True,
            timeout=300
        ) as r:
            r.raise_for_status()
            result = ""
            print("\n" + "="*80)
            print("🤖 Llama generating code...")
            print("="*80 + "\n")
            
            for line in r.iter_lines(decode_unicode=True):
                if not line.strip():
                    continue
                try:
                    token_data = json.loads(line)
                    token = token_data.get("response", "")
                    print(token, end="", flush=True)
                    result += token
                    
                    if token_data.get("done", False):
                        break
                except:
                    continue
            
            print("\n\n" + "="*80)
            print("✅ Generation complete")
            print("="*80 + "\n")
            return result.strip()
    except Exception as e:
        print(f"⚠️ Ollama streaming failed: {e}")
        traceback.print_exc()
        return ""

def extract_page_info(driver):
    """Extract detailed information about the current page for better analysis."""
    try:
        info = {
            "url": driver.current_url,
            "title": driver.title,
            "buttons": [],
            "inputs": [],
            "selects": [],
            "textareas": [],
            "file_inputs": [],
            "links": []
        }
        
        # Get all buttons
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            info["buttons"] = [
                {
                    "text": btn.text.strip(),
                    "type": btn.get_attribute("type"),
                    "class": btn.get_attribute("class"),
                    "id": btn.get_attribute("id"),
                    "visible": btn.is_displayed()
                }
                for btn in buttons[:20]
            ]
        except:
            pass
        
        # Get all input fields
        try:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs[:30]:
                try:
                    input_type = inp.get_attribute("type") or "text"
                    if input_type == "file":
                        info["file_inputs"].append({
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "accept": inp.get_attribute("accept"),
                            "visible": inp.is_displayed()
                        })
                    else:
                        info["inputs"].append({
                            "type": input_type,
                            "name": inp.get_attribute("name"),
                            "id": inp.get_attribute("id"),
                            "placeholder": inp.get_attribute("placeholder"),
                            "value": inp.get_attribute("value"),
                            "required": inp.get_attribute("required"),
                            "visible": inp.is_displayed()
                        })
                except:
                    continue
        except:
            pass
        
        # Get all select dropdowns
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            info["selects"] = [
                {
                    "name": sel.get_attribute("name"),
                    "id": sel.get_attribute("id"),
                    "options_count": len(sel.find_elements(By.TAG_NAME, "option")),
                    "visible": sel.is_displayed()
                }
                for sel in selects[:15]
            ]
        except:
            pass
        
        # Get all textareas
        try:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            info["textareas"] = [
                {
                    "name": ta.get_attribute("name"),
                    "id": ta.get_attribute("id"),
                    "placeholder": ta.get_attribute("placeholder"),
                    "visible": ta.is_displayed()
                }
                for ta in textareas[:10]
            ]
        except:
            pass
        
        # Get links with keywords
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            keywords = ["apply", "next", "continue", "submit", "save"]
            info["links"] = [
                {
                    "text": link.text.strip(),
                    "href": link.get_attribute("href"),
                    "visible": link.is_displayed()
                }
                for link in links
                if link.text.strip() and any(kw in link.text.lower() for kw in keywords)
            ][:10]
        except:
            pass
        
        return info
    except Exception as e:
        return {"error": str(e)}

def print_page_analysis(info):
    """Print a formatted analysis of the page."""
    print("\n" + "="*80)
    print("📊 PAGE ANALYSIS")
    print("="*80)
    print(f"URL: {info.get('url', 'N/A')}")
    print(f"Title: {info.get('title', 'N/A')}")
    
    if info.get('buttons'):
        print(f"\n🔘 Buttons ({len(info['buttons'])}):")
        for btn in info['buttons'][:10]:
            if btn.get('visible'):
                print(f"  - '{btn['text']}' (type: {btn['type']}, id: {btn['id']})")
    
    if info.get('inputs'):
        print(f"\n📝 Input Fields ({len(info['inputs'])}):")
        for inp in info['inputs'][:15]:
            if inp.get('visible'):
                req = "REQUIRED" if inp.get('required') else ""
                print(f"  - {inp['type']}: {inp['name'] or inp['id']} {req}")
    
    if info.get('selects'):
        print(f"\n📋 Dropdowns ({len(info['selects'])}):")
        for sel in info['selects'][:10]:
            if sel.get('visible'):
                print(f"  - {sel['name'] or sel['id']} ({sel['options_count']} options)")
    
    if info.get('textareas'):
        print(f"\n📄 Text Areas ({len(info['textareas'])}):")
        for ta in info['textareas']:
            if ta.get('visible'):
                print(f"  - {ta['name'] or ta['id']}")
    
    if info.get('file_inputs'):
        print(f"\n📎 File Upload Fields ({len(info['file_inputs'])}):")
        for fi in info['file_inputs']:
            if fi.get('visible'):
                print(f"  - {fi['name'] or fi['id']} (accepts: {fi['accept']})")
    
    if info.get('links'):
        print(f"\n🔗 Action Links ({len(info['links'])}):")
        for link in info['links']:
            if link.get('visible'):
                print(f"  - '{link['text']}'")
    
    print("="*80 + "\n")

def handle_form_step(driver, resume_data, resume_pdf_path, step_num):
    """Handle a single step of the multi-step form."""
    print(f"\n{'='*80}")
    print(f"📋 FORM STEP {step_num}")
    print(f"{'='*80}\n")
    
    time.sleep(3)  # Let page load
    
    # Extract page information
    page_info = extract_page_info(driver)
    print_page_analysis(page_info)
    
    # Get HTML
    html = driver.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")[:HTML_LIMIT]
    
    # Create prompt
    prompt = f"""
You are a Selenium automation expert. This is STEP {step_num} of a multi-step job application form.

TASK:
1. Fill ALL visible input fields, dropdowns, and textareas using the resume_data
2. Upload the resume PDF if there's a file input (use send_keys with resume_pdf_path)
3. Click "Next" / "Continue" / "Save and Continue" button (DO NOT click "Submit" or "Finish")
4. Use WebDriverWait for reliability
5. Add print statements showing what you're filling

CRITICAL RULES:
- Map resume_data fields intelligently to form fields (e.g., personal_info.name → First Name + Last Name)
- For dropdowns: select the most appropriate option from available choices
- Handle fields gracefully with try-except blocks
- Print each action: "Filling field X with value Y"
- Use explicit waits (WebDriverWait with EC.element_to_be_clickable)
- DO NOT submit the form - only click Next/Continue to go to next step
- If no Next button exists, just fill the form and don't click anything

Page Information:
{json.dumps(page_info, indent=2)}

HTML Snippet (first {HTML_LIMIT} chars):
{html[:HTML_LIMIT]}

Resume Data:
{json.dumps(resume_data, indent=2)}

Available variables:
- driver: WebDriver instance
- By: Selenium By class
- resume_data: dict with resume info
- resume_pdf_path: string path to PDF file
- time: time module
- WebDriverWait: for explicit waits
- EC: expected_conditions from selenium.webdriver.support
- NoSuchElementException: exception class

Generate ONLY Python code, no markdown, no explanations.
"""
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n{'='*80}")
        print(f"🔄 ATTEMPT {attempt}/{MAX_RETRIES} for Step {step_num}")
        print(f"{'='*80}\n")
        
        if last_error:
            prompt += f"\n\nPREVIOUS ERROR TO FIX:\n{last_error}\n"
        
        # Generate code
        code = run_ollama_stream(prompt)
        
        if not code:
            print("❌ No code generated!")
            continue
        
        # Clean up code
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join([l for l in lines if not l.strip().startswith("```")])
        
        # Log code
        log_to_file(f"step{step_num}_attempt{attempt}_code", code)
        
        print(f"\n{'='*80}")
        print("📝 GENERATED CODE:")
        print(f"{'='*80}")
        print(code)
        print(f"{'='*80}\n")
        
        # Execute code
        try:
            print("⚙️ Executing code...\n")
            
            current_url = driver.current_url
            
            exec_globals = {
                "driver": driver,
                "By": By,
                "resume_data": resume_data,
                "resume_pdf_path": resume_pdf_path,
                "time": time,
                "WebDriverWait": WebDriverWait,
                "EC": EC,
                "NoSuchElementException": NoSuchElementException,
            }
            
            exec(code, exec_globals)
            
            print("\n✅ Code executed successfully!")
            
            # Check if URL changed (next page loaded)
            time.sleep(2)
            new_url = driver.current_url
            
            if new_url != current_url:
                print(f"✅ Page changed: {current_url} → {new_url}")
                return True  # Move to next step
            else:
                print(f"ℹ️ Still on same page - form filled but no navigation")
                return False  # No more steps
            
        except Exception as e:
            err_text = traceback.format_exc()
            print(f"\n❌ EXECUTION ERROR:\n{err_text}")
            log_to_file(f"step{step_num}_attempt{attempt}_error", err_text)
            last_error = err_text
            
            if attempt < MAX_RETRIES:
                print(f"\n🔄 Retrying with error feedback...")
            else:
                print(f"\n❌ Max retries reached for this step")
                return False
    
    return False

def main(job_url, resume_json_path, resume_pdf_path):
    print("\n" + "="*80)
    print("🚀 MULTI-STEP RESUME AUTOFILL AGENT")
    print("="*80 + "\n")
    
    # Load resume
    print("📄 Loading resume data...")
    resume_data = load_resume_details(resume_json_path)
    print(f"✅ Loaded resume: {resume_data['personal_info']['name']}\n")
    
    # Start browser
    print("🌐 Starting Chrome...")
    driver = create_driver()
    
    try:
        print(f"🔗 Navigating to: {job_url}")
        driver.get(job_url)
        
        # Handle multiple form steps
        for step in range(1, MAX_FORM_STEPS + 1):
            has_next_step = handle_form_step(driver, resume_data, resume_pdf_path, step)
            
            if not has_next_step:
                print(f"\n✅ Form filling complete (no more steps detected)")
                break
            
            print(f"\n➡️ Moving to next form step...\n")
        
        print("\n" + "="*80)
        print("✅ ALL STEPS COMPLETED")
        print("="*80)
        print("\n👀 Browser left open for review.")
        print("Press Enter to close...")
        input()
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        print("\n🔚 Browser closed!")

if __name__ == "__main__":
    main(JOB_URL, RESUME_JSON_PATH, RESUME_PDF_PATH)