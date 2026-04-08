# LangGraph Sentiment Router MVP

## Overview
This application implements a conditional routing workflow using LangGraph to analyze user queries and handle them based on sentiment. It uses Hugging Face's `distilbert-base-uncased-finetuned-sst-2-english` model. The workflow routes positive queries to an engagement branch, negative queries to an empathy branch, and neutral/uncertain queries to a clarification branch. The final response is generated using the Groq LLM API with an automatic fallback to local Ollama mistral.

## How to run
* Install dependencies via `pip install -r requirements.txt`.
* Create a `.env` file based on `.env.example` and set your `GROQ_API_KEY`.
* Ensure Ollama is running locally with the `mistral` model if you plan to rely on the fallback.
* Start the Flask application by running `python app.py`.
* Open your browser and navigate to `http://localhost:5000` to interact with the unique dark theme UI.

## Design notes
* **LangGraph Conditional Edges:** We define a single decision node `analyze_sentiment` which determines the transition `route_decision` dynamically. Edges connect from `analyze_sentiment` to `POSITIVE`, `NEGATIVE`, and `NEUTRAL` endpoints based on the sentiment output.
* **Thresholds:** A confidence threshold of 0.6 is applied. If the sentiment analyzer scores below 0.6, or runtime issues arise (like missing text or model exceptions), the system gracefully routes to the `NEUTRAL` clarification branch as a safe default.
* **State Management:** The Graph uses a strict `WorkflowState` object to store metrics, route data, the original query, and eventual NLP response.
