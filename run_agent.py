"""
Simple runner script for the Job Application Agent
"""

import json
import sys
import os
from pathlib import Path
from job_application_agent import JobApplicationAgent, UserProfile, AIProvider
import logging
import requests


def load_config(config_path="config.json"):
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def create_user_profile(config):
    """Create UserProfile from config"""
    profile_data = config["user_profile"]

    # Convert relative paths to absolute paths
    if profile_data.get("resume_path"):
        profile_data["resume_path"] = str(Path(profile_data["resume_path"]).absolute())
    if profile_data.get("photo_path"):
        profile_data["photo_path"] = str(Path(profile_data["photo_path"]).absolute())

    return UserProfile(**profile_data)


def setup_ai_provider(config):
    """Setup AI provider from config"""
    ai_config = config["ai_config"]

    # Check for API key in environment variable as fallback (not needed for Ollama)
    if ai_config["provider"] != "ollama" and ai_config.get("api_key") == "YOUR_API_KEY":
        env_key = os.getenv(f"{ai_config['provider'].upper()}_API_KEY")
        if env_key:
            ai_config["api_key"] = env_key
        else:
            print(f"Please set your {ai_config['provider']} API key in config.json or as environment variable")
            sys.exit(1)

    # For Ollama, ensure the service is running
    if ai_config["provider"] == "ollama":
        base_url = ai_config.get("base_url", "http://localhost:11434")
        try:
            response = requests.get(f"{base_url}/api/tags")
            if response.status_code != 200:
                print(f"Error: Ollama service is not responding at {base_url}")
                print("Please ensure Ollama is running: ollama serve")
                sys.exit(1)
        except requests.ConnectionError:
            print(f"Error: Cannot connect to Ollama at {base_url}")
            print("Please start Ollama with: ollama serve")
            sys.exit(1)

    return AIProvider(
        provider=ai_config["provider"],
        api_key=ai_config.get("api_key"),
        base_url=ai_config.get("base_url"),
        model=ai_config.get("model")
    )


def main():
    """Main function to run the agent"""

    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_agent.py <job_url> [config_file]")
        print("Example: python run_agent.py https://example.com/careers/job-123")
        sys.exit(1)

    job_url = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else "config.json"

    # Load configuration
    print(f"Loading configuration from {config_file}...")
    config = load_config(config_file)

    # Create user profile
    print("Setting up user profile...")
    profile = create_user_profile(config)

    # Setup AI provider
    print("Initializing AI provider...")
    ai_provider = setup_ai_provider(config)

    # Create agent
    print("Creating job application agent...")
    agent_config = config.get("agent_config", {})
    browser_config = config.get("browser_config", {})

    agent = JobApplicationAgent(
        user_profile=profile,
        ai_provider=ai_provider,
        headless=browser_config.get("headless", False),
        debug=agent_config.get("debug_mode", True)
    )

    try:
        print(f"\nStarting application process for: {job_url}")
        print("-" * 50)

        # Apply to the job
        success = agent.apply_to_job(job_url)

        if success:
            print("\n✅ Application submitted successfully!")
            print("Check the agent_logs folder for detailed logs.")
        else:
            print("\n❌ Application failed.")
            print("Check the agent_logs folder for error details.")
            print("The agent will learn from this attempt and improve next time.")

    except KeyboardInterrupt:
        print("\n\nApplication interrupted by user.")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.exception("Unexpected error occurred")

    finally:
        print("\nCleaning up...")
        agent.close()
        print("Done!")


if __name__ == "__main__":
    main()
