# 🔍 Task 3: Code Review Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-API-orange.svg)](https://groq.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

An intelligent **AI-powered code review system** for Python code analysis and improvement suggestions. Built with FastAPI and Groq's advanced language models, featuring multi-round review conversations and comprehensive code analysis.

## 🌟 Features

- 🤖 **AI-Powered Reviews**: Advanced reasoning agents analyze Python code quality
- 🔄 **Multi-Round Conversations**: Iterative review process with follow-up questions
- 📊 **AST-Based Analysis**: Static code analysis for syntax and structure
- 📁 **File Upload Support**: Review entire Python files via web interface
- 🎯 **Targeted Feedback**: Specific suggestions for code improvement
- ⚡ **Fast Processing**: Optimized for quick code review turnaround
- 🌐 **Web Interface**: Clean, intuitive UI for code submission and review
- 🔍 **Detailed Analysis**: Comprehensive feedback on code quality, bugs, and best practices

## 🏗️ Architecture

```
Task_3/
├── server.py            # FastAPI web server
├── agent.py             # AI review agent logic
├── analyzer.py          # Static code analysis
├── groq_client.py       # Groq API integration
├── prompts.py           # System prompts and templates
├── index.html           # Web interface
├── requirements.txt     # Python dependencies
└── README.md            # This documentation
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Groq API key ([Get one here](https://console.groq.com))

### Installation

1. **Navigate to Task 3:**
   ```bash
   cd Task_3
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate environment:**
   ```powershell
   # Windows
   venv\Scripts\activate
   ```
   ```bash
   # macOS/Linux
   source venv/bin/activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment:**
   ```bash
   # Create .env file with your Groq API key
   echo "GROQ_API_KEY=your_api_key_here" > .env
   ```

### Running the Application

1. **Start the server:**
   ```bash
   python server.py
   ```

2. **Open in browser:**
   Visit `http://localhost:8034`

3. **Start reviewing code:**
   - Paste Python code in the text area
   - Or upload a `.py` file
   - Adjust review rounds if needed

## 🔧 How It Works

The Code Review Agent operates through multiple layers:

### 1. **Static Analysis** 📊
- **AST Parsing**: Analyzes Python syntax tree
- **Code Metrics**: Calculates complexity, line counts, etc.
- **Basic Checks**: Identifies obvious issues and patterns

### 2. **AI Review Agent** 🤖
- **Multi-Round Process**: Can perform 1-3 rounds of analysis
- **Contextual Feedback**: Understands code purpose and context
- **Improvement Suggestions**: Provides actionable recommendations
- **Conversation Flow**: Can ask clarifying questions

### 3. **Groq Integration** ⚡
- **Fast Inference**: Uses Groq's optimized models
- **Structured Prompts**: Carefully crafted prompts for consistent output
- **Error Handling**: Robust API interaction with retries

## 📋 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main web interface |
| `GET` | `/health` | Health check |
| `POST` | `/review` | Review code via text |
| `POST` | `/upload` | Review uploaded file |
| `POST` | `/analyze-only` | Static analysis only |

### Review Request Format
```json
{
  "code": "def hello():\n    print('Hello, World!')",
  "max_rounds": 2,
  "verbose": false
}
```

### Review Response Format
```json
{
  "review": "Your code looks good! Consider adding type hints...",
  "suggestions": ["Add docstring", "Use f-strings"],
  "score": 8.5,
  "rounds_completed": 2
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ Yes | - | Your Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Model to use |

### Review Parameters

- **max_rounds**: Number of review iterations (1-3)
- **verbose**: Enable detailed logging
- **file_size_limit**: 100KB max per file

## 🎨 Web Interface Features

- **Code Editor**: Syntax-highlighted code input
- **File Upload**: Drag-and-drop Python files
- **Review History**: View previous reviews
- **Export Options**: Download review reports
- **Responsive Design**: Works on all screen sizes

## 📊 Analysis Capabilities

### Static Analysis
- **Syntax Validation**: Catches Python syntax errors
- **Import Analysis**: Identifies unused imports
- **Code Complexity**: Calculates cyclomatic complexity
- **Style Checks**: PEP 8 compliance hints

### AI-Powered Review
- **Code Quality**: Overall assessment and scoring
- **Bug Detection**: Identifies potential logic errors
- **Performance**: Suggestions for optimization
- **Best Practices**: Modern Python conventions
- **Security**: Basic security vulnerability checks

## 🔍 Example Review

**Input Code:**
```python
def calc_avg(nums):
    total = 0
    for n in nums:
        total += n
    return total / len(nums)
```

**AI Review Output:**
- ✅ **Good**: Clean, readable function
- 🔄 **Suggestion**: Add type hints for better clarity
- 📝 **Improvement**: Consider using `sum()` and `len()` more explicitly
- 🎯 **Score**: 8/10

## 📚 Dependencies

- **fastapi** - Web framework
- **groq** - AI API client
- **pydantic** - Data models
- **python-dotenv** - Environment management
- **ast** - Python AST parsing
- **uvicorn** - ASGI server

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new analysis features
4. Update documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

- **Groq** for providing powerful AI models
- **FastAPI** for the robust web framework
- **Python AST** for code analysis capabilities
- Open source code review tools for inspiration

---

*Built with ❤️ for better code through AI-assisted review*