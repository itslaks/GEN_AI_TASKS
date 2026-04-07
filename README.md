# GEN_AI Projects Collection 🚀

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](#contributing)

A curated collection of AI-powered web applications demonstrating modern Python frameworks, API integrations, and intelligent agents. Each project is self-contained and showcases different aspects of generative AI and reasoning systems.

## 📋 Table of Contents

- [Overview](#overview)
- [Tasks](#tasks)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## 🌟 Overview

This repository contains four distinct AI projects, each focusing on different AI capabilities:

- **Reasoning Agents** with web search integration
- **Mathematical Problem Solving** using Chain-of-Thought prompting
- **Code Analysis and Review** automation
- **Future AI Applications** (Task 4 - in development)

All projects are built with production-ready practices, including proper error handling, logging, and user-friendly interfaces.

## 🛠️ Tasks

### 1. 🤖 Reasoning Agent Web App (`Task_1/`)
[![Flask](https://img.shields.io/badge/Flask-2.0+-red.svg)](https://flask.palletsprojects.com/)

A Flask-based web application implementing a ReAct (Reasoning + Acting) agent that answers questions using web search when needed. Features evidence-grounded responses with structured reasoning steps.

**Key Features:**
- 🔍 Intelligent web search using DuckDuckGo API
- 🧠 Structured ReAct loop (Thought → Action → Observation → Answer)
- 🌐 Simple web interface for question submission
- ⚡ Fast, heuristic-based search decision making

[View Task 1 README](Task_1/README.md) | [Demo](http://localhost:8501)

---

### 2. 🧮 Math CoT Solver (`Task_2/`)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-API-orange.svg)](https://groq.com/)

A FastAPI-powered math problem solver using Chain-of-Thought (CoT) prompting with Groq's LLaMA models. Provides step-by-step solutions with verification.

**Key Features:**
- ➗ Multi-step math problem solving
- 🧠 Chain-of-Thought prompting for accurate reasoning
- 🔄 Automatic verification and sanity checks
- 🎨 Neon dark-themed responsive UI
- ⚡ Real-time API responses

[View Task 2 README](Task_2/README.md) | [Demo](http://localhost:5500)

---

### 3. 🔍 Code Review Agent (`Task_3/`)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-API-orange.svg)](https://groq.com/)

An AI-powered code review system for Python code using advanced reasoning agents. Analyzes code quality, suggests improvements, and provides detailed feedback.

**Key Features:**
- 📝 Automated Python code analysis
- 🤖 Multi-round review conversations
- 📊 AST-based static analysis
- 🔄 File upload support
- 📈 Detailed improvement suggestions

[View Task 3 README](Task_3/README.md) | [Demo](http://localhost:8034)

---

### 4. ❓ Future Project (`Task_4/`)
*Coming Soon - New AI Application*

## 📋 Prerequisites

- **Python 3.8+** - All projects require modern Python
- **Virtual Environment** - Isolated dependencies per project
- **API Keys** - Required for Tasks 2 & 3 (Groq API)
- **Web Browser** - For accessing the web interfaces

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd GEN_AI
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Navigate to each task and follow its setup instructions**

## 💻 Usage

Each task runs independently. Start by navigating to the task folder and following the README instructions:

```bash
# Example for Task 1
cd Task_1
pip install -r requirements.txt
python app.py
```

Then open the provided localhost URL in your browser.

## 🤝 Contributing

Contributions are welcome! 🎉

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code follows the existing style and includes appropriate tests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Groq](https://groq.com/) for providing fast AI inference
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Flask](https://flask.palletsprojects.com/) for the lightweight web framework
- Open source community for inspiration and tools

---

*Built with ❤️ using Python and modern AI technologies*</content>
<parameter name="filePath">L:\GEN_AI\README.md