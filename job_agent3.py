# job_agent_updated.py
import time
import json
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

# Prompt AI to detect application method and generate steps
prompt = f"""
I have loaded a job application method selection page (Deloitte USI) with this HTML (truncated):
{html[:5000]}

I have my resume info in JSON as:
{json.dumps(MY_JSON)}

And my PDF resume path is: {RESUME_PDF_PATH}

Please generate Python/Selenium code that:
1. Detects which application method button to click (e.g., “Default Apply”, “Copy & Paste”, “From Device”).
2. Clicks that method.
3. Follows through the subsequent form steps:
   - Uploads or pastes the resume (using the PDF path).
   - Fills required personal details from the JSON.
   - Waits for review before final submit.
Return only the Python code (no explanations).
"""

response = ollama.chat(
    model="llama3.2:latest",
    messages=[{"role": "user", "content": prompt}]
)
generated_code = response['message']['content']

print("----- Generated Code -----")
print(generated_code[:1000], "...")

# Execute the code
try:
    exec(generated_code, {"driver": driver, "time": time, "MY_JSON": MY_JSON, "RESUME_PDF_PATH": RESUME_PDF_PATH})
except Exception as e:
    print("⚠️ Error executing AI-generated code:", e)

print("✅ Process paused for review. Browser remains open.")
input("Press Enter to quit…")

driver.quit()
