#!/usr/bin/env python3
"""
Test script for the customer support chatbot
Verifies that all components are properly set up
"""

import os
import sys

def test_imports():
    """Test that all required packages are installed"""
    print("Testing imports...")
    try:
        import fastapi
        import uvicorn
        import groq
        import pydantic
        print("✅ All required packages are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def test_env():
    """Test that environment variables are set"""
    print("\nTesting environment variables...")
    
    # Try to load from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not installed, skipping .env file loading")
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY not set")
        print("Create a .env file with: GROQ_API_KEY=your_key_here")
        print("Get your key from: https://console.groq.com/keys")
        return False
    
    if api_key == "your_groq_api_key_here":
        print("❌ GROQ_API_KEY is still the placeholder value")
        print("Replace it with your actual API key from https://console.groq.com/keys")
        return False
    
    print(f"✅ GROQ_API_KEY is set ({api_key[:10]}...)")
    return True

def test_groq_connection():
    """Test connection to Groq API"""
    print("\nTesting Groq API connection...")
    try:
        from groq import Groq
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("❌ Cannot test API without key")
            return False
        
        client = Groq(api_key=api_key)
        
        # Simple test request
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Say 'OK' if you can read this"}],
            model="llama-3.3-70b-versatile",
            max_tokens=10
        )
        
        if response.choices[0].message.content:
            print("✅ Successfully connected to Groq API")
            return True
        else:
            print("❌ Received empty response from Groq API")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to Groq API: {e}")
        print("Check that your API key is valid")
        return False

def test_files():
    """Test that all required files exist"""
    print("\nTesting file structure...")
    required_files = [
        "app.py",
        "index.html",
        "requirements.txt",
        "README.md",
        ".env.example"
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ Missing: {file}")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 50)
    print("Customer Support Chatbot - Setup Test")
    print("=" * 50)
    
    tests = [
        test_files(),
        test_imports(),
        test_env(),
        test_groq_connection()
    ]
    
    print("\n" + "=" * 50)
    if all(tests):
        print("✅ ALL TESTS PASSED!")
        print("=" * 50)
        print("\nYou're ready to run the application:")
        print("  python app.py")
        print("\nThen open: http://localhost:8000")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 50)
        print("\nPlease fix the issues above before running the app.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
