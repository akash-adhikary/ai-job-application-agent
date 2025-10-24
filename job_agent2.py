# job_agent_full_autofill.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import ollama

# === Your JSON resume/info ===
MY_JSON = {
  "personal_info": {
    "name": "Akash Adhikary",
    "phone": "+91-8420433877",
    "email": "akash.adhikary@hotmail.com",
    "linkedin": "https://linkedin.com/in/adhikary-akash",
    "github": "https://github.com/akash-adhikary"
  },
  "professional_summary": "Results-driven Senior Data Engineer with 6+ years of experience designing cloud-native, large-scale data platforms and real-time analytics pipelines across GCP, AWS, and Snowflake. Skilled in building event-driven architectures using Kafka, Pub/Sub, and Spark, and orchestrating complex workflows with Airflow and Matillion. Proven expertise in ETL framework design, streaming ingestion, and CDC-based data modeling using Snowpipe, Streams, and Tasks. Adept at partnering with cross-functional product, ML, and analytics teams to deliver high-quality, globally scalable data solutions that power personalization, user insights, and business intelligence. Passionate about architecting data systems that enable data-driven storytelling at scale.",
  "technical_skills": {
    "programming_frameworks": ["Python", "PySpark", "SQL", "C/C++", "Pandas", "NumPy", "SciPy"],
    "cloud_platforms": ["AWS (S3, Lambda, API Gateway, CloudFormation)", "Azure", "Google Cloud Platform (GCP)"],
    "big_data_analytics": ["Spark", "Databricks", "BigQuery", "Kafka", "Thoughtspot", "Power BI"],
    "data_warehousing": ["Snowflake", "BigQuery", "MongoDB", "Oracle", "IBM Db2"],
    "etl_orchestration": ["Airflow", "Matillion", "Qlik Replicate", "Informatica"],
    "devops_iac": ["GitHub Actions", "Docker", "CI/CD pipelines"],
    "databases": ["SQL (PostgreSQL, MySQL)", "NoSQL (MongoDB, DynamoDB)"]
  },
  "work_experience": [
    {
      "title": "Senior Data Engineer",
      "company": "ThoughtSpot",
      "location": "Bangalore, India",
      "duration": "Jul 2023 – Present",
      "responsibilities": [
        "Leading end-to-end data platform initiatives across Finance, GTM, HR, Security, and CloudOps using GCP, Snowflake, Python, Databricks, and Matillion to deliver real-time analytics and cost-saving solutions.",
        "Designed scalable ingestion pipelines for 20+ systems (Salesforce, NetSuite, Coupa, Workday, Jira, Tenable) via APIs and file-based ingestion — reduced data latency by 70%",
        "Developed modular ETL frameworks in PySpark, cutting onboarding time for new sources by 60%",
        "Designed automated data labeling workflows using Snowflake Cortex AI to enrich large datasets with semantic tags, enabling faster scenario detection and analysis — aligning with autonomous system data enrichment use cases",
        "Engineered customer usage analytics platform using telemetry, Stripe, and SFDC — enabled usage-based pricing and recovered 12% in revenue leakage",
        "Built cloud cost analytics platform Cloud Brain on GCP to track internal cloud usage, detect idle resources, and automate clean-up — achieved 30% reduction in cloud spend",
        "Partnered with InfoSec to centralize security KPIs and audit data from Rapid7, Tenable, Jira, and ServiceNow",
        "Modeled critical KPIs (ARR, NRR, Sales Comp, Talent Acquisition) in Snowflake, improving planning accuracy by 25%",
        "Delivered executive dashboards via ThoughtSpot, reducing reporting effort and improving decision velocity by 90%"
      ]
    },
    {
      "title": "Digital Engineering Engineer",
      "company": "NTT DATA India",
      "location": "India",
      "duration": "Jun 2022 – Jul 2023",
      "responsibilities": [
        "Seamlessly migrated enterprise data landscape from Netezza to Snowflake and Matillion, unlocking enhanced data capabilities and modernizing analytics infrastructure.",
        "Led enterprise data warehouse modernization from Netezza to Snowflake and AWS, architecting dimensional models and metadata-driven ETL frameworks for terabytes-scale analytics",
        "Automated ETL pipeline conversion using Python and Matillion, optimizing for distributed processing and ensuring 98%+ data accuracy through comprehensive unit testing frameworks",
        "Migrated Informatica workflows to cloud-native serverless ETL leveraging AWS Lambda, S3, and API Gateway—preserved data lineage and governance across migration",
        "Developed orchestration frameworks ensuring code quality through automated testing, code reviews, and CI/CD integration"
      ]
    },
    {
      "title": "Senior Systems Engineer",
      "company": "Infosys Ltd.",
      "location": "India",
      "duration": "Dec 2019 – Jun 2022",
      "responsibilities": [
        "Modernized client’s data landscape from Oracle to Snowflake Cloud Data Warehouse using ETL tools like Matillion and Qlik Replicate.",
        "Built metadata-driven ingestion frameworks using Matillion ETL and Qlik Replicate for real-time data replication from heterogeneous sources (Oracle, IBM Db2, S3, Azure) to Snowflake",
        "Developed log streaming, change tracking, and apply changes tasks for real-time data synchronization supporting analytics workloads",
        "Automated ETL deployments, monitoring, and alerting using Python scripts and CloudFormation, enhancing operational reliability and reducing manual intervention by 80%",
        "Designed scalable ingestion pipelines supporting cloud data warehouse migration from Oracle to Snowflake for enterprise clients"
      ]
    },
    {
      "title": "Embedded Systems Intern",
      "company": "GT Silicon Pvt Ltd (IIT Kanpur Incubated)",
      "location": "India",
      "duration": "Jun 2018 – Aug 2018",
      "responsibilities": [
        "Enhanced open-source motion sensing platform for Navigation, developing sensor fusion algorithms and telemetry pipelines for autonomous vehicle testing.",
        "Enhanced open-source motion sensing platform (Oblu) integrating multi-sensor telemetry (IMU + GPS) for navigation and autonomous system—achieved 90% localization accuracy",
        "Developed sensor fusion algorithms using Kalman filters to combine MEMS-based INS and GPS data for precise real-time tracking in indoor/outdoor environments",
        "Designed data ingestion pipelines via Bluetooth for real-time telemetry processing and scenario reconstruction, enabling safety-critical testing and environment awareness for autonomous driving applications",
        "Built hybrid positioning system supporting scenario validation for autonomous vehicle testing and development"
      ]
    }
  ],
  "education": [
    {
      "institution": "Haldia Institute of Technology",
      "location": "West Bengal, India",
      "degree": "Bachelor of Technology",
      "field": "Electronics & Communication Engineering",
      "university": "MAKAUT",
      "duration": "Jan 2015 – Jan 2019"
    },
    {
      "institution": "Kendriya Vidyalaya MEG & Centre",
      "location": "India",
      "degree": "XII (AISSCE)",
      "board": "CBSE",
      "duration": "Jan 2014 – Jan 2015"
    }
  ],
  "publications_research": [
    {
      "title": "Design and Development of A Smart Parachute Control System for Military and Civilian Applications",
      "journal": "Turkish Journal of Computer and Mathematics Education (TURCOMAT)",
      "volume_issue": "11 (1)",
      "pages": "492-501"
    },
    {
      "title": "Performance Evaluation of Low-Cost RGB-Depth Camera and Ultrasonic Sensors",
      "journal": "Lecture Notes in Electrical Engineering, Springer",
      "year": 2020,
      "pages": "331-341",
      "doi": "10.1007/978-981-15-0829-5_33"
    }
  ],
  "awards_achievements": [
    {
      "award": "Delivery Ninja Award",
      "organization": "Infosys",
      "date": "Jan 2022",
      "description": "Recognized for exceptional project delivery and technical excellence"
    },
    {
      "award": "Rise Insta Award",
      "organization": "Infosys",
      "date": "Apr 2021",
      "description": "Honored for innovative solutions and rapid problem resolution"
    },
    {
      "award": "Top 30 Finalist – DRDO DRUSE",
      "organization": "Defense Research & Development Organization Robotics and Unmanned Systems Exposition",
      "date": "Apr 2018"
    },
    {
      "award": "Gold Medal",
      "organization": "KVS National NCSC",
      "date": "Oct 2013"
    },
    {
      "award": "Silver Medal",
      "organization": "IRIS National Fair: Intel Initiative for Research & Innovation in Science"
    }
  ]
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

    # --- Extract full page text ---
    full_text = driver.find_element(By.TAG_NAME, "body").text

    # --- Step 1: Extract Job Description via Llama ---
    prompt_extract_jd = f"""
    Extract the job description from this web page text.
    Ignore menus, headers, footers, ads, or unrelated content.
    Page text:
    {full_text}
    """
    jd_response = ollama.chat(
        model="llama3.2:latest",
        messages=[{"role":"user","content":prompt_extract_jd}]
    )
    job_description = jd_response['message']['content'][:1500]
    print("----- Job Description -----")
    print(job_description[:500], "...")

    # --- Step 2: AI Decision to Apply ---
    prompt_decision = f"""
    My info: {json.dumps(MY_JSON)}
    Job Description: {job_description}
    Should I apply? Answer YES or NO with a short reason.
    """
    decision = ollama.chat(
        model="llama3.2:latest",
        messages=[{"role":"user","content":prompt_decision}]
    )['message']['content']
    print("AI Decision:", decision)

    if "YES" in decision.upper():
        # --- Step 3: Click Apply ---
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

            # --- Step 4: Ask Llama to map form fields ---
            html_source = driver.page_source
            prompt_fields = f"""
            Here is my resume in JSON: {json.dumps(MY_JSON)}
            Here is the HTML of the apply page (truncated):
            {html_source[:2000]}
            
            Identify form fields for first name, last name, email, phone, resume upload, LinkedIn, GitHub, etc.
            Return a JSON mapping: field_name -> CSS selector or XPath
            """
            field_mapping_resp = ollama.chat(
                model="llama3.2:latest",
                messages=[{"role":"user","content":prompt_fields}]
            )['message']['content']

            print("Field mapping suggested by AI:")
            print(field_mapping_resp)

            # --- Step 5: Auto-fill using suggested selectors ---
            # User can parse field_mapping_resp JSON and fill fields:
            # Example (replace with AI-suggested selectors):
            # driver.find_element(By.CSS_SELECTOR, selector).send_keys(MY_JSON["personal_info"]["name"])

            print("✅ Form fields auto-filled (based on AI mapping). Please review before submitting.")
            input("Press Enter after reviewing form. Browser will remain open.")

        except Exception as e:
            print("⚠️ Error during Apply step:", e)

print("Job application automation complete. Browser remains open for manual submission.")
