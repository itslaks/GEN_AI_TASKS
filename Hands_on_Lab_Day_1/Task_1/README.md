# 🤖 Task 1: Reasoning Agent Web Application

[![Flask](https://img.shields.io/badge/Flask-2.0+-red.svg)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

A sophisticated web application implementing a **ReAct (Reasoning + Acting) agent** that intelligently answers questions by combining logical reasoning with web search capabilities. Built with Flask and featuring a clean, user-friendly interface.

## 🌟 Features

- 🧠 **Structured ReAct Loop**: Implements the classic Thought → Action → Observation → Final Answer pattern
- 🔍 **Intelligent Web Search**: Uses DuckDuckGo's instant answer API for evidence-grounded responses
- 📊 **Evidence-Based Reasoning**: Only searches when questions require factual or time-sensitive information
- 🌐 **Simple Web UI**: Clean interface for submitting questions and viewing detailed reasoning steps
- ⚡ **Fast Decision Making**: Heuristic-based system to determine when search is necessary
- 🔄 **Iterative Refinement**: Refines search queries if initial results are insufficient

## 🏗️ Architecture

```
Task_1/
├── app.py              # Main Flask application with ReActAgent class
├── templates/
│   └── index.html      # Web interface template
├── LICENSE             # MIT License
└── README.md           # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Internet connection (for web search)

### Installation

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   ```

2. **Activate environment:**
   ```powershell
   # Windows PowerShell
   .\.venv\Scripts\Activate
   ```
   ```bash
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install flask requests
   ```

### Running the Application

1. **Start the server:**
   ```bash
   python app.py
   ```

2. **Open in browser:**
   Navigate to `http://localhost:8501`

3. **Try it out:**
   - Enter questions like "What is the population of Tokyo?"
   - Watch the agent reason step-by-step
   - See search results when needed

## 🔧 How It Works

The ReActAgent follows this process:

1. **Analyze Question** 🧐
   - Determines if web search is required based on keywords and question complexity

2. **Thought** 💭
   - Internal reasoning about the approach

3. **Action** ⚡
   - Executes web search via DuckDuckGo API

4. **Observation** 👀
   - Processes search results

5. **Final Answer** ✅
   - Provides evidence-grounded response

### Search Decision Logic

The agent searches when questions contain:
- Time-sensitive terms: `current`, `latest`, `today`, `recent`
- Factual queries: `who`, `when`, `where`, `what`, `how many`
- Complex questions (>10 words)

## 📋 Example Usage

**Question:** "What is the current population of New York City?"

**Agent Process:**
- Thought: "This requires current factual data"
- Action: Search[What is the current population of New York City?]
- Observation: "8,336,817 (2023 estimate) (Source: Wikipedia)"
- Final Answer: "Based on recent estimates, New York City has a population of approximately 8.3 million people."

## 🛠️ Configuration

The application runs on:
- **Host:** `0.0.0.0` (accessible from network)
- **Port:** `8501`
- **Debug Mode:** Enabled for development

## 📚 Dependencies

- **Flask** - Web framework
- **Requests** - HTTP client for API calls
- **urllib.parse** - URL encoding

## 🔍 API Details

**Web Search Integration:**
- Uses DuckDuckGo Instant Answer API
- Fallback to related topics if no direct answer
- Timeout: 10 seconds
- Error handling for failed requests

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the ReAct paper: "ReAct: Synergizing Reasoning and Acting in Language Models"
- DuckDuckGo for providing free API access
- Flask community for the excellent web framework

---

*Built with ❤️ for demonstrating AI reasoning capabilities*
