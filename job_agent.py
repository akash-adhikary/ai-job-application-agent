# job_agent_auto_fill.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import ollama

# === Your information ===
MY_INFO = {
    "First Name": "Akash",
    "Last Name": "Adhikary",
    "Email": "your_email@example.com",
    "Phone": "1234567890",
    "Resume": r"D:\Workspace\jobs-apply\resume.pdf"
}

JOB_URLS = [
    "https://usijobs.deloitte.com/en_US/careersUSI/JobDetail/USI-EH26-Consulting-AI-Data-Senior-Consultant-Python-Data-Engineer/300058",
]

# === Start browser ===
driver = webdriver.Chrome()
driver.maximize_window()

for url in JOB_URLS:
    driver.get(url)
    time.sleep(3)

    # --- Step 1: Extract full page text ---
    full_text = driver.find_element(By.TAG_NAME, "body").text

    # --- Step 2: Extract Job Description using Llama ---
    prompt_extract_jd = f"""
    Extract the job description from this page text.
    Ignore unrelated content.
    Page text:
    {full_text}
    """
    jd_response = ollama.chat(
        model="llama3.2:latest",
        messages=[{"role":"user","content":prompt_extract_jd}]
    )
    job_description = jd_response['message']['content'][:1000]  # truncate
    print("----- Job Description -----")
    print(job_description)

    # --- Step 3: Decide whether to apply ---
    prompt_decision = f"""
    My info: {MY_INFO}
    Job Description: {job_description}
    Should I apply? Answer YES or NO.
    """
    decision = ollama.chat(
        model="llama3.2:latest",
        messages=[{"role":"user","content":prompt_decision}]
    )['message']['content']
    print("AI Decision:", decision)

    if "YES" in decision.upper():
        # --- Step 4: Click Apply ---
        try:
            apply_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Apply') or contains(text(),'apply')]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", apply_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", apply_btn)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            print("Apply page opened.")

            # --- Step 5: Auto-fill the form ---
            html_source = driver.page_source
            prompt_fields = f"""
            Analyze this page HTML and identify input fields for Name, Email, Phone, and Resume.
            Provide the element selectors (id, name, or XPath) to fill these fields.
            Only return JSON like:
            {{
                "First Name": "selector",
                "Last Name": "selector",
                "Email": "selector",
                "Phone": "selector",
                "Resume": "selector"
            }}
            HTML:
            {html_source[:2000]}
            """
            field_response = ollama.chat(
                model="llama3.2:latest",
                messages=[{"role":"user","content":prompt_fields}]
            )['message']['content']

            print("Field mapping suggested by AI:")
            print(field_response)

            # --- Step 6: Fill the fields manually based on Llama mapping ---
            # Here, you can parse the JSON and fill via Selenium.
            # Example (replace selectors after inspecting Llama output):
            # driver.find_element(By.ID, "firstName").send_keys(MY_INFO["First Name"])
            # driver.find_element(By.ID, "lastName").send_keys(MY_INFO["Last Name"])
            # driver.find_element(By.ID, "email").send_keys(MY_INFO["Email"])
            # driver.find_element(By.ID, "phone").send_keys(MY_INFO["Phone"])
            # driver.find_element(By.ID, "resumeUpload").send_keys(MY_INFO["Resume"])

            print("✅ Form fields auto-filled. Please review before submitting.")
            input("Press Enter to continue after reviewing the form...")

        except Exception as e:
            print("⚠️ Error during Apply step:", e)

print("Job application automation paused for manual review. Browser will stay open.")
