# 🧮 Task 2: Math CoT Solver

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-API-orange.svg)](https://groq.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

A powerful **Chain-of-Thought (CoT) math problem solver** built with FastAPI and Groq's lightning-fast LLaMA models. Features a stunning neon dark-themed frontend and provides step-by-step mathematical reasoning with automatic verification.

## 🌟 Features

- ➗ **Advanced Math Solving**: Handles multi-step algebraic, calculus, and complex mathematical problems
- 🧠 **Chain-of-Thought Prompting**: Leverages CoT for accurate, step-by-step reasoning
- 🔄 **Automatic Verification**: Built-in sanity checks via substitution and alternate methods
- 🎨 **Neon Dark UI**: Beautiful, responsive interface with cyberpunk aesthetics
- ⚡ **Real-time Responses**: Fast API responses powered by Groq's optimized inference
- 📱 **Mobile Friendly**: Responsive design works on all devices
- 🔒 **Error Handling**: Robust error handling with retries and timeouts

## 🏗️ Architecture

```
Task_2/
├── main.py              # FastAPI backend with Groq integration
├── index.html           # Single-file neon dark frontend
├── requirements.txt     # Python dependencies
└── README.md            # This documentation
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Groq API key ([Get one here](https://console.groq.com))

### Installation

1. **Navigate to Task 2:**
   ```bash
   cd Task_2
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
   # Copy and edit .env file
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

### Running the Application

**Option 1: Combined (Recommended)**
```bash
# Backend serves frontend automatically
uvicorn main:app --reload --port 8000
```
Then visit: `http://localhost:8000`

**Option 2: Separate Servers**
```bash
# Terminal 1 - Backend
uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend
python -m http.server 5500
# OR
npx serve .
```
Then visit: `http://localhost:5500`

## 🔧 How Chain-of-Thought Works

The system uses a carefully crafted prompt that instructs the LLM to:

1. **Internal Reasoning** 🧠
   - Reason step-by-step in a hidden scratchpad
   - Never expose raw chain-of-thought to users

2. **Structured Output** 📋
   - Returns clean JSON with three key fields:
     - `final_answer`: The mathematical result
     - `step_summary`: 2-6 user-friendly bullet points
     - `verification`: Sanity check confirmation

3. **Quality Assurance** ✅
   - Automatic verification via substitution
   - Alternate solution methods when applicable

### Example Interaction

**Problem:** "Solve: 2x + 3 = 7"

**Internal CoT (Hidden):**
- Subtract 3: 2x = 4
- Divide by 2: x = 2
- Verify: 2(2) + 3 = 7 ✓

**User Sees:**
- **Final Answer:** x = 2
- **Steps:** 
  - Subtract 3 from both sides: 2x = 4
  - Divide both sides by 2: x = 2
- **Verification:** Substituting x=2: 2(2)+3=7, which equals 7 ✓

## 📋 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the main application |
| `GET` | `/health` | Health check endpoint |
| `POST` | `/solve` | Solve math problem |

### Solve Request Format
```json
{
  "problem": "Solve for x: 2x + 5 = 13"
}
```

### Solve Response Format
```json
{
  "final_answer": "x = 4",
  "step_summary": [
    "Subtract 5 from both sides: 2x = 8",
    "Divide both sides by 2: x = 4"
  ],
  "verification": "Substituting x=4: 2(4)+5=13 ✓"
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ Yes | - | Your Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Model to use |
| `TIMEOUT_SECONDS` | No | `30` | API timeout |
| `MAX_RETRIES` | No | `2` | Retry attempts |

### `.env` Example
```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

## 📚 Dependencies

- **fastapi** - Modern web framework
- **httpx** - Async HTTP client
- **pydantic** - Data validation
- **python-dotenv** - Environment management
- **uvicorn** - ASGI server

## 🎨 UI Features

- **Neon Glow Effects**: Cyberpunk-inspired design
- **Responsive Layout**: Works on desktop and mobile
- **Real-time Feedback**: Loading states and error messages
- **Clean Typography**: Easy-to-read math formatting
- **Dark Theme**: Easy on the eyes for long sessions

## 🔍 Error Handling

- **Timeout Protection**: 30-second API timeouts
- **Retry Logic**: Automatic retries with exponential backoff
- **JSON Validation**: Ensures proper response format
- **User-Friendly Messages**: Clear error messages for users

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure code follows existing patterns
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🙏 Acknowledgments

- **Groq** for providing blazing-fast AI inference
- **FastAPI** for the excellent async web framework
- **Chain-of-Thought Research** for the reasoning methodology
- Open source community for inspiration

---

*Built with ❤️ for mathematical excellence and AI-powered education*

---

## API Reference

### `GET /health`
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### `POST /solve`
```bash
curl -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"problem": "A train travels 300 km at 60 km/h. How long does it take?"}'
```

Response:
```json
{
  "final_answer": "5 hours",
  "step_summary": [
    "Identify the formula: Time = Distance ÷ Speed",
    "Substitute values: Time = 300 ÷ 60",
    "Calculate: Time = 5 hours"
  ],
  "verification": "Check: 60 km/h × 5 h = 300 km ✓"
}
```

---

## UI Notes

| Element             | Color           | Purpose                          |
|---------------------|-----------------|----------------------------------|
| Input border/label  | `#00ffe7` cyan  | Problem entry focus              |
| Final Answer        | `#00ffe7` cyan  | Bold neon answer highlight       |
| Step numbered pills | `#bf5fff` violet| Color-coded reasoning steps      |
| Verification        | `#ffb830` amber | Sanity check, distinct accent    |
| Error messages      | `#ff4a6e` red   | Warning neon for failures        |

- Background grid texture + gradient glow cards for depth.
- Fonts: **Syne** (display) + **Space Mono** (code/labels).
- Ctrl+Enter submits the problem.
- Example pill buttons for quick testing.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `GROQ_API_KEY not configured` | Set key in `.env` and restart backend |
| `Cannot reach the backend` | Ensure uvicorn is running on port 8000 |
| `LLM returned non-JSON` | Rare; retry the request |
| CORS error in browser | Backend CORS is open (`*`); check URL matches `localhost:8000` |
| Groq rate limit (429) | Free tier limit; wait a few seconds and retry |
