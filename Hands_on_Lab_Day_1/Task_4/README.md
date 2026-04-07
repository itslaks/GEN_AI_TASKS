# Customer Support Chatbot - Three Prompt Patterns

A production-ready customer support chatbot demonstrating three distinct prompt engineering patterns using Groq AI for fast, reliable inference.

## 🎯 Features

- **Three Prompt Patterns:**
  - 🔧 **ReAct Pattern**: Tool-using agent with reasoning traces
  - 🧠 **Chain-of-Thought**: Step-by-step internal reasoning with summary
  - ✨ **Self-Reflecting**: Critique and revise for polished responses

- **E-commerce Support Coverage:**
  - Order status & tracking
  - Refunds & returns
  - Subscription management
  - Billing disputes
  - Address changes
  - Product troubleshooting
  - Agent escalation

- **Fast & Efficient:**
  - Powered by Groq API (ultra-fast inference)
  - Optimized token usage
  - Real-time responses

- **Modern UI:**
  - Neon yellow theme
  - Responsive design
  - Clean, professional interface

## 📋 Prerequisites

- Python 3.8 or higher
- Groq API key (free at https://console.groq.com/keys)

## 🚀 Quick Start

### 1. Clone or Download

```bash
# If you have these files locally, navigate to the directory
cd customer-support-chatbot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:

```
GROQ_API_KEY=gsk_your_actual_api_key_here
```

**Get Your Free Groq API Key:**
1. Visit https://console.groq.com/keys
2. Sign up or log in
3. Create a new API key
4. Copy and paste it into your `.env` file

### 4. Run the Application

```bash
python app.py
```

The server will start on `http://localhost:8000`

### 5. Open in Browser

Navigate to: **http://localhost:8000**

## 🎮 How to Use

1. **Select a Pattern**: Click one of the three pattern buttons at the top
2. **Ask Questions**: Type customer support queries in the chat input
3. **Compare Responses**: Switch patterns to see how each approach handles the same query

### Example Queries

Try these sample queries to see the patterns in action:

- "I need to check the status of my order #12345"
- "I want to cancel my subscription"
- "I was charged twice for the same order"
- "My package says delivered but I didn't receive it"
- "How do I return a product?"
- "I need a refund for order #67890"

## 📁 Project Structure

```
customer-support-chatbot/
├── app.py              # FastAPI backend with three prompt patterns
├── index.html          # Modern frontend interface
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md          # This file
```

## 🔧 Configuration

### Adjust Token Usage

In `app.py`, modify the Groq API call parameters:

```python
chat_completion = client.chat.completions.create(
    model="llama-3.3-70b-versatile",  # Change model if needed
    temperature=0.3,                   # 0.0-1.0 (lower = more consistent)
    max_tokens=800,                    # Adjust response length
    top_p=0.9,                         # Nucleus sampling
)
```

### Available Groq Models

- `llama-3.3-70b-versatile` (default, best balance)
- `llama-3.1-70b-versatile` (alternative)
- `mixtral-8x7b-32768` (faster, shorter context)

## 🎨 The Three Prompt Patterns

### Pattern 1: ReAct (Reason + Act)
- **Purpose**: Tool-using agent with explicit reasoning
- **Output**: Answer + tool usage traces + next steps
- **Best for**: Complex queries requiring external data

### Pattern 2: Chain-of-Thought (CoT)
- **Purpose**: Internal step-by-step reasoning
- **Output**: Answer + step summary + next best action
- **Best for**: Queries requiring logical analysis

### Pattern 3: Self-Reflecting
- **Purpose**: Draft, critique, and revise responses
- **Output**: Polished answer + critique notes + next steps
- **Best for**: High-stakes or sensitive customer interactions

## 🔒 Security & Safety

All three prompts include:
- ✅ No full credit card or password requests
- ✅ De-escalation for angry customers
- ✅ Fraud detection signals
- ✅ Policy compliance checks
- ✅ Maximum 2 clarifying questions
- ✅ Accessibility support

## 🐛 Troubleshooting

### "GROQ_API_KEY environment variable not set"
- Make sure you created a `.env` file with your API key
- Check that the key starts with `gsk_`
- Restart the Python server after adding the key

### "Network response was not ok"
- Verify your Groq API key is valid
- Check your internet connection
- Ensure the FastAPI server is running

### Port 8000 already in use
Change the port in `app.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8001)  # Use different port
```

## 📊 Performance

- **Average Response Time**: < 2 seconds
- **Token Usage**: ~400-800 tokens per response
- **Model**: Llama 3.3 70B (optimized for speed)

## 🤝 Contributing

Feel free to:
- Add new prompt patterns
- Enhance the UI
- Add more customer support scenarios
- Optimize token usage further

## 📄 License

MIT License - feel free to use in your own projects!

## 🎓 Learning Resources

**Prompt Engineering Patterns:**
- ReAct: https://arxiv.org/abs/2210.03629
- Chain-of-Thought: https://arxiv.org/abs/2201.11903
- Self-Reflection: https://arxiv.org/abs/2303.11366

**Groq Documentation:**
- https://console.groq.com/docs/quickstart

---

**Built with ❤️ using FastAPI, Groq AI, and modern web technologies**