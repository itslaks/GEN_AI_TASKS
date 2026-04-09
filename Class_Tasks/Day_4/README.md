# DataPulse · Data Extraction Agent

Turn unstructured text into clean structured data — JSON, CSV, or TXT — powered by GPT-4o-mini and Flask.

## Features

- **One-click extraction** from any freeform text
- **Output formats**: JSON (syntax-highlighted), CSV, TXT
- **Fields**: `name`, `item`, `quantity`, `price`, `date` (ISO-8601), `currency` (ISO-4217), `confidence`
- **Observability**: `request_id`, `latency_ms`, `model`, `token` usage in every response
- **Dark, vibrant UI** with animated backgrounds, field pills, and download support

## Quickstart

```bash
# 1. Clone / download files into a directory
# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env → set OPENAI_API_KEY

# 4. Run
python app.py
# → http://localhost:5000
```

## API

### `POST /extract`

**Request**
```json
{ "text": "John bought 3 laptops for ₹50,000 each on Jan 5, 2024" }
```

**Response**
```json
{
  "data": {
    "name": "John",
    "item": "laptops",
    "quantity": 3,
    "price": 50000,
    "date": "2024-01-05",
    "currency": "INR",
    "confidence": 0.97
  },
  "request_id": "b3f1a2c4-...",
  "latency_ms": 430,
  "model": "gpt-4o-mini-2024-07-18",
  "tokens": 118
}
```

**Response headers**
```
X-Request-Id: b3f1a2c4-...
```

## Currency Normalization

| Input         | Output |
|---------------|--------|
| ₹, Rs, INR    | INR    |
| $, USD        | USD    |
| €, EUR        | EUR    |
| £, GBP        | GBP    |

Missing fields are always `null` — never guessed.

## Files

| File             | Purpose                        |
|------------------|--------------------------------|
| `app.py`         | Flask backend + OpenAI call    |
| `index.html`     | Standalone frontend UI         |
| `requirements.txt` | Python dependencies          |
| `.env.example`   | Environment variable template  |
| `README.md`      | This file                      |

## Keyboard Shortcut

`Ctrl + Enter` (or `Cmd + Enter`) triggers extraction from the textarea.
