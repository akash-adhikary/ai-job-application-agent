# AI Job Application Agent 🤖

An intelligent automation agent that applies to jobs on your behalf using Selenium and AI. The agent dynamically understands job portals, handles authentication, fills forms, and learns from each application.

## Features

- **Dynamic Portal Understanding**: Uses AI to analyze any job portal's structure
- **Smart Authentication**: Handles login/signup flows automatically
- **Intelligent Form Filling**: AI-powered field mapping matches your data to form fields
- **Learning System**: Remembers successful strategies for each portal
- **Multi-AI Support**: Works with OpenAI, Anthropic, Google Gemini, or Ollama
- **Anti-Detection**: Human-like typing patterns and browser fingerprinting
- **Error Recovery**: Automatic retry mechanism with configurable attempts
- **File Uploads**: Automatically uploads resume and photo when needed

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ai-job-application-agent-main
```

2. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Install Chrome WebDriver**:
```bash
# The webdriver-manager package handles this automatically
# Or manually download from: https://chromedriver.chromium.org/
```

## Configuration

Edit `config.json` with your information:

```json
{
  "user_profile": {
    "email": "your.email@example.com",
    "password": "your_password",
    "first_name": "Your",
    "last_name": "Name",
    "phone": "+1234567890",
    "linkedin_url": "https://linkedin.com/in/yourprofile",
    "resume_path": "path/to/resume.pdf",
    "photo_path": "path/to/photo.jpg",
    ...
  },
  "ai_config": {
    "provider": "ollama",  // or "openai", "anthropic", "gemini"
    "api_key": "",         // Not needed for Ollama
    "model": "gpt-oss:120B-cloud",
    "base_url": "http://localhost:11434"
  }
}
```

## AI Provider Setup

### Using Ollama (Local AI)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve

# Pull a model
ollama pull gpt-oss:120B-cloud
# Or use smaller models: llama2, mistral, neural-chat
```

### Using OpenAI
```bash
# Set API key in config.json or environment
export OPENAI_API_KEY="your-api-key"
```

### Using Anthropic (Claude)
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Using Google Gemini
```bash
export GEMINI_API_KEY="your-api-key"
```

## Usage

### Basic Usage
```bash
python run_agent.py <job_url>
```

### Examples
```bash
# Apply to a specific job
python run_agent.py https://careers.example.com/software-engineer

# Use custom config file
python run_agent.py https://jobs.site.com/position/123 custom_config.json
```

### Batch Applications
```python
# Create a script for multiple applications
from job_application_agent import JobApplicationAgent, UserProfile, AIProvider
import json

# Load config
with open('config.json') as f:
    config = json.load(f)

# Setup
profile = UserProfile(**config['user_profile'])
ai = AIProvider(**config['ai_config'])
agent = JobApplicationAgent(profile, ai)

# Apply to multiple jobs
job_urls = [
    "https://example1.com/job/123",
    "https://example2.com/careers/456",
    "https://example3.com/apply/789"
]

for url in job_urls:
    success = agent.apply_to_job(url)
    print(f"{url}: {'✅ Success' if success else '❌ Failed'}")

agent.close()
```

## How It Works

1. **Page Analysis**: Agent visits the job URL and uses AI to understand the page
2. **Authentication**: Detects and handles login/signup requirements
3. **Form Detection**: Identifies all form fields using AI + Selenium
4. **Field Mapping**: AI maps your profile data to correct form fields
5. **Form Filling**: Fills forms with human-like typing patterns
6. **File Upload**: Uploads resume and photo when detected
7. **Submission**: Finds and clicks submit button
8. **Learning**: Saves successful strategy for future use

## File Structure

```
ai-job-application-agent-main/
├── job_application_agent.py  # Main agent implementation
├── run_agent.py              # CLI runner script
├── config.json               # Your configuration
├── requirements.txt          # Python dependencies
├── agent_memory.json         # Learning system storage (auto-created)
├── agent_logs/              # Application logs (auto-created)
└── README.md                # This file
```

## Logging

Logs are saved in `agent_logs/` directory with timestamps:
- `agent_20240115_143022.log` - Detailed debug information
- Screenshots on failure (if enabled in config)

## Memory System

The agent learns from each application and stores patterns in `agent_memory.json`:

```json
{
  "successful_patterns": {
    "careers.example.com": [{
      "timestamp": "2024-01-15T14:30:22",
      "strategy": { /* field mappings and steps */ }
    }]
  },
  "failed_patterns": { /* errors for improvement */ },
  "field_mappings": { /* learned field associations */ }
}
```

## Advanced Configuration

### Browser Settings
```json
"browser_config": {
  "headless": false,        // Set true to run in background
  "window_size": "1920,1080",
  "user_agent": "Mozilla/5.0...",
  "implicit_wait": 10,
  "page_load_timeout": 30
}
```

### Agent Settings
```json
"agent_config": {
  "max_retries": 3,         // Retry attempts on failure
  "retry_delay": 5,         // Seconds between retries
  "debug_mode": true,       // Verbose logging
  "save_screenshots": true, // Capture screenshots on error
  "log_level": "INFO"       // INFO, DEBUG, WARNING, ERROR
}
```

## Troubleshooting

### Ollama Connection Error
```bash
# Ensure Ollama is running
ollama serve

# Check if model is available
ollama list
```

### Selenium WebDriver Issues
```bash
# Update Chrome
# WebDriver manager should auto-download matching version
# Or manually specify in code:
from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(ChromeDriverManager().install())
```

### Form Not Filling Correctly
1. Check `agent_logs/` for detailed errors
2. Run with `headless: false` to watch the process
3. Increase `retry_delay` in config
4. Clear `agent_memory.json` to reset learned patterns

### AI Response Errors
- For Ollama: Try a different model (mistral, llama2)
- Increase timeout values in browser_config
- Check API keys for cloud providers

## Security Notes

⚠️ **Important Security Considerations**:
- Never commit `config.json` with real credentials
- Use environment variables for sensitive data
- Store passwords securely (consider using keyring library)
- Review agent actions in non-headless mode first
- Be cautious with sites that have anti-bot measures

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/improvement`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/improvement`)
5. Create Pull Request

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is for educational purposes. Always comply with website terms of service and use responsibly. The authors are not responsible for any misuse or violations of website policies.

## Support

- Report issues: [GitHub Issues](https://github.com/yourusername/repo/issues)
- Documentation: [Wiki](https://github.com/yourusername/repo/wiki)
- Email: your.email@example.com

---

**Note**: This agent is a powerful automation tool. Use it ethically and in accordance with all applicable laws and website terms of service.
