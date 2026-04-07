#!/bin/bash

echo "=================================================="
echo "Customer Support Chatbot - Quick Start"
echo "=================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo ""
    echo "📝 IMPORTANT: Edit the .env file and add your Groq API key!"
    echo "   Get your free key from: https://console.groq.com/keys"
    echo ""
    echo "   After adding your key, run this script again or run:"
    echo "   python app.py"
    echo ""
    exit 0
fi

# Run tests
echo "🧪 Running setup tests..."
python3 test_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🚀 Starting the application..."
    echo ""
    echo "Opening in browser: http://localhost:8000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    
    # Try to open browser (works on macOS and some Linux systems)
    (sleep 2 && (open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null)) &
    
    # Start the server
    python3 app.py
else
    echo ""
    echo "❌ Setup test failed. Please fix the issues above."
    exit 1
fi
