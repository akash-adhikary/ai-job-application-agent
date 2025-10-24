# job_agent_stream_retry.py
import time
import json
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import ollama

# === File paths ===
RESUME_JSON_PATH = r"akash_profile.json"
RESUME_PDF_PATH = r"Resume_akash_disn.pdf"

# Load JSON from file
with open(RESUME_JSON_PATH, 'r', encoding='utf-8') as f:
    MY_JSON = json.load(f)

# === Job URL ===
JOB_URL = "https://usijobs.deloitte.com/en_US/careersUSI/ApplicationMethods?jobId=300058"

# === Start Browser ===
options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Navigate to job URL
driver.get(JOB_URL)
time.sleep(5)

# Extract HTML
html = driver.page_source

# === Initial Prompt for Llama ===
base_prompt = f"""
You are an expert Selenium automation engineer.
You are automating a job application on Deloitte's site.
Here is the job page HTML (truncated to 5000 chars):
{html[:5000]}

Resume info (JSON):
{json.dumps(MY_JSON)}

Resume PDF path: {RESUME_PDF_PATH}

Generate **Python code only** that:
1. Detects which "Application Method" button to click (like “Default Apply”, “Copy & Paste”, or “From Device”, or “Next” etc.).
2. Clicks that button using Selenium.
3. Uploads the resume file or fills details from JSON where required.
4. Does not auto-submit at the end—pause for manual review.
5. Assume variables `driver`, `MY_JSON`, and `RESUME_PDF_PATH` already exist.
"""

def stream_llama(prompt):
    """Stream live output from Llama while generating code"""
    print("\n🤖 Generating code from Llama... (streaming live)\n")
    code_output = ""
    for chunk in ollama.chat(
        model="llama3.2:latest",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    ):
        part = chunk.get("message", {}).get("content", "")
        if part:
            print(part, end="", flush=True)
            code_output += part
    print("\n\n✅ Code generation complete.\n")
    return code_output

def try_exec_code(code):
    """Try executing generated code, and retry if it fails"""
    attempt = 1
    while attempt <= 3:
        try:
            print(f"\n🚀 Attempt {attempt}: Executing generated code...\n")
            exec(code, {"driver": driver, "time": time, "MY_JSON": MY_JSON, "RESUME_PDF_PATH": RESUME_PDF_PATH})
            print("\n✅ Code executed successfully.")
            return True
        except Exception as e:
            print(f"\n⚠️ Error on attempt {attempt}:\n{e}")
            traceback.print_exc()
            error_prompt = f"""
The following Python Selenium code caused this error:
{code}

Error:
{traceback.format_exc()}

Please fix the issue and regenerate only the corrected Python code.
Do not repeat explanations.
"""
            code = stream_llama(error_prompt)
            attempt += 1
    print("\n❌ All attempts failed. Please review manually.")
    return False

# === Generate and execute AI code ===
generated_code = stream_llama(base_prompt)
success = try_exec_code(generated_code)

print("\n✅ Process paused for manual review. Browser remains open.")
input("Press Enter to quit…")

driver.quit()
