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
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
# OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_MODEL = "gpt-oss:120b-cloud"
MAX_RETRIES = 5
HTML_LIMIT = 50000  # Increased to capture more form elements
LOG_DIR = "ollama_logs"
os.makedirs(LOG_DIR, exist_ok=True)
# ----------------------------

# === Your file paths ===
JOB_URL = "https://usijobs.deloitte.com/en_US/careersUSI/ApplicationMethods?jobId=300058"
RESUME_JSON_PATH = r"D:\Workspace\jobs-apply\akash_profile.json"
RESUME_PDF_PATH = r"D:\Workspace\jobs-apply\Resume_akash_disn.pdf"

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
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])  # Reduce console spam
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
                    
                    # Check if generation is done
                    if token_data.get("done", False):
                        break
                except Exception as e:
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
    """Extract useful information about the current page."""
    try:
        # Get all buttons
        buttons = driver.find_elements(By.TAG_NAME, "button")
        button_texts = [btn.text.strip() for btn in buttons if btn.text.strip()]
        
        # Get all input fields
        inputs = driver.find_elements(By.TAG_NAME, "input")
        input_info = []
        for inp in inputs:
            input_type = inp.get_attribute("type") or "text"
            input_name = inp.get_attribute("name") or inp.get_attribute("id") or "unknown"
            input_info.append(f"{input_type}:{input_name}")
        
        # Get all links with "apply" in them
        links = driver.find_elements(By.TAG_NAME, "a")
        apply_links = [link.text.strip() for link in links if link.text.strip() and "apply" in link.text.lower()]
        
        info = f"""
PAGE ANALYSIS:
Current URL: {driver.current_url}
Page Title: {driver.title}

Buttons found: {button_texts[:10]}
Input fields: {input_info[:15]}
Apply-related links: {apply_links[:5]}
"""
        print(info)
        return info
    except Exception as e:
        return f"Error extracting page info: {e}"

def main(job_url, resume_json_path, resume_pdf_path):
    print("\n" + "="*80)
    print("🚀 STARTING RESUME AUTOFILL AGENT")
    print("="*80 + "\n")
    
    # Load resume data
    print("📄 Loading resume data...")
    resume_data = load_resume_details(resume_json_path)
    print(f"✅ Loaded resume with keys: {list(resume_data.keys())}\n")
    
    # Start browser
    print("🌐 Starting Chrome browser...")
    driver = create_driver()
    
    try:
        print(f"🔗 Navigating to: {job_url}")
        driver.get(job_url)
        time.sleep(5)
        
        # Extract and display page info
        page_info = extract_page_info(driver)
        
        # Get HTML
        print("\n📋 Extracting page HTML...")
        html = driver.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")[:HTML_LIMIT]
        print(f"✅ Captured {len(html)} characters of HTML\n")
        
        # Create prompt
        base_prompt = f"""
You are a Selenium automation expert. Analyze this job application page and write Python code to:
1. Click the "Apply" or "Continue" or "Next" button to start the application
2. Fill ALL visible form fields using the resume data
3. Upload the resume PDF if there's a file input
4. Use explicit waits (WebDriverWait) for reliability
5. Add print statements to show progress

IMPORTANT RULES:
- Use try-except blocks for each action
- Print what you're doing at each step
- Use WebDriverWait with EC.element_to_be_clickable or EC.presence_of_element_located
- Don't submit the form - just fill it out
- Handle missing elements gracefully

Current Page Info:
{page_info}

HTML Snippet (first {HTML_LIMIT} chars):
{html}

Resume Data:
{json.dumps(resume_data, indent=2)}

Available variables:
- driver: WebDriver instance
- By: Selenium By locators
- resume_data: dict with resume information
- resume_pdf_path: string path to PDF
- time: time module
- WebDriverWait: for explicit waits
- EC: expected_conditions

Generate ONLY executable Python code, no explanations.
"""
        
        last_error = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            print("\n" + "="*80)
            print(f"🔄 ATTEMPT {attempt}/{MAX_RETRIES}")
            print("="*80 + "\n")
            
            if last_error:
                base_prompt += f"\n\nPREVIOUS ERROR TO FIX:\n{last_error}\n"
            
            # Generate code
            code = run_ollama_stream(base_prompt)
            
            if not code:
                print("❌ No code generated by Ollama!")
                continue
            
            # Clean up code fences
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join([l for l in lines if not l.strip().startswith("```")])
            
            # Log the generated code
            log_to_file(f"attempt_{attempt}_code", code)
            
            print("\n" + "="*80)
            print("📝 GENERATED CODE:")
            print("="*80)
            print(code)
            print("="*80 + "\n")
            
            # Execute the code
            try:
                print("⚙️ Executing generated code...\n")
                
                exec_globals = {
                    "driver": driver,
                    "By": By,
                    "resume_data": resume_data,
                    "resume_pdf_path": resume_pdf_path,
                    "time": time,
                    "WebDriverWait": WebDriverWait,
                    "EC": EC,
                }
                
                exec(code, exec_globals)
                
                print("\n✅ Code execution completed successfully!")
                break
                
            except Exception as e:
                err_text = traceback.format_exc()
                print(f"\n❌ EXECUTION ERROR:\n{err_text}")
                log_to_file(f"attempt_{attempt}_error", err_text)
                last_error = err_text
                
                if attempt < MAX_RETRIES:
                    print(f"\n🔄 Retrying with error feedback...")
                else:
                    print(f"\n❌ Max retries reached. Manual intervention may be needed.")
        
        print("\n" + "="*80)
        print("✅ PROCESS COMPLETE")
        print("="*80)
        print("\n👀 Browser left open for review.")
        print("Press Enter to close the browser...")
        input()
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        print("\n🔚 Browser closed. Goodbye!")

if __name__ == "__main__":
    main(JOB_URL, RESUME_JSON_PATH, RESUME_PDF_PATH)