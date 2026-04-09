# 🌿 AgroRAG — Agricultural Intelligence Platform

A **Retrieval-Augmented Generation (RAG)** web app that helps farmers get actionable, safe advice on crop disease, soil treatment, pest control, and seasonal planning — powered by trusted PDF documents + live weather data.

---

## 📁 Repository Structure

.
├── index.html # Single-file frontend (dark nature-themed UI)
├── app.py # FastAPI backend (RAG pipeline)
├── README.md # This file
├── .env.example # Environment variable template
└── requirements.txt # Python dependencies

---

## 🚀 Quick Start (Local)

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Clone & Install

```bash
git clone https://github.com/your-org/agrorag.git
cd agrorag
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API keys (see below)
```

### 4. Start the Backend

```bash
uvicorn app:app --reload --port 8000
```

### 5. Open the Frontend

Open `index.html` directly in your browser **or** serve it:

```bash
python -m http.server 3000
# Then open http://localhost:3000
```

> **Note:** The frontend auto-detects `localhost` and points to `http://localhost:8000`. For production, set `window.BACKEND_URL` in the HTML or configure a reverse proxy.

---

## 📄 PDF Ingestion — How It Works

The app uses a **local vector store** (FAISS + JSON). Place PDFs anywhere and upload via the UI:

1. Click the **drop zone** in the Knowledge Base panel (or drag files in)
2. Click **"Ingest & Embed PDFs"**
3. The backend: extracts text → chunks (1000 chars / 150 overlap) → embeds with `sentence-transformers` → stores in FAISS index saved to `faiss.index` + `vector_store.json`
4. On restart, the store is automatically reloaded from disk

**CLI ingestion (alternative):**

```bash
# Place PDFs in the project directory, then POST via curl:
curl -X POST http://localhost:8000/ingest \
  -F "files=@my_agri_doc.pdf" \
  -F "files=@soil_guide.pdf"
```

The FAISS index persists between runs. To reset: `DELETE /reset` or delete `faiss.index` + `vector_store.json`.

---

## 🌾 Recommended PDFs for the Knowledge Base

| #   | Title                                          | Source                                  | Covers                                                     | Why Use                                              |
| --- | ---------------------------------------------- | --------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------- |
| 1   | **FAO IPM Training Modules**                   | FAO (UN)                                | Integrated pest management, eco-friendly control           | Free, globally authoritative, practical field guides |
| 2   | **ICAR Crop Production Guides**                | Indian Council of Agricultural Research | Soil health, fertilizers, disease control for Indian crops | Official Indian govt docs, region-specific           |
| 3   | **CGIAR Climate-Smart Agriculture Sourcebook** | FAO + CGIAR                             | Climate adaptation, soil & water management                | Comprehensive, research-backed, free PDF             |
| 4   | **UC IPM Pest Management Guidelines**          | UC Davis / UCANR                        | Vegetables, fruits, field crops pest & disease             | Science-based, free, covers 100+ crops               |
| 5   | **USDA NRCS Soil Health Technical Notes**      | USDA NRCS                               | Soil organic matter, cover crops, tillage                  | Free, authoritative US govt soil science             |
| 6   | **TNAU Crop Disease Management**               | Tamil Nadu Agricultural University      | South India specific diseases, local cultivars             | Excellent for India context, regional data           |
| 7   | **CABI Crop Protection Compendium**            | CABI                                    | Disease, pest and weed management, global + regional       | Comprehensive pathogen database                      |
| 8   | **Wheat Disease ID Field Guide**               | CIMMYT / CGIAR                          | Wheat rust, blight, smut identification                    | Photo-rich, field-applicable disease ID              |

**Where to find them:**

- FAO: https://www.fao.org/documents/
- ICAR: https://icar.org.in/content/publications
- CGIAR: https://cgspace.cgiar.org/
- UC IPM: https://ipm.ucanr.edu/PMG/
- USDA NRCS: https://www.nrcs.usda.gov/
- TNAU: https://www.tnau.ac.in/agriculture/

---

## 🧠 RAG Architecture

User Query + Field Context
│
▼
Query Augmentation
(crop + symptoms appended)
│
▼
Embedding (sentence-transformers)
│
▼
FAISS Vector Search (top-5 chunks)
│
▼
Confidence Score (cosine similarity)
│
▼
LLM Answer Generation
├─ OpenAI GPT-4o-mini (if key set)
└─ Local Fallback (rule-based)
│
▼
Structured JSON Response:
summary · causes · action_plan
prevention · 7-day monitoring · citations

### Tech Choices

| Component      | Library                                  | Why                                                     |
| -------------- | ---------------------------------------- | ------------------------------------------------------- |
| Web framework  | FastAPI                                  | Async, fast, auto-docs, easy CORS                       |
| PDF extraction | pdfplumber                               | Handles tables + columns better than pypdf              |
| Embeddings     | sentence-transformers (all-MiniLM-L6-v2) | Free, local, 384-dim, excellent semantic search         |
| Vector store   | FAISS (IndexFlatIP)                      | Lightweight, file-based, production-grade               |
| LLM            | OpenAI GPT-4o-mini (optional)            | Cheap, structured JSON output; local fallback if no key |
| Weather        | OpenWeatherMap API (optional)            | Free tier sufficient                                    |

---

## 🌐 API Endpoints

| Method | Path                    | Description                                         |
| ------ | ----------------------- | --------------------------------------------------- |
| GET    | `/health`               | Backend status, model info, doc counts              |
| POST   | `/ingest`               | Upload PDFs (`multipart/form-data`, field: `files`) |
| POST   | `/ask`                  | Ask a question (`{question, context}` JSON)         |
| GET    | `/weather?location=...` | Fetch weather for location                          |
| DELETE | `/reset`                | Clear all vectors and chunks                        |

---

## ☁️ Deployment

### Option A — Vercel (Frontend) + Render/Railway (Backend)

Vercel does not support persistent disk (FAISS files) or long-running Python processes for RAG. Use it only for the static frontend.

**Frontend on Vercel:**

```bash
# 1. Push repo to GitHub
# 2. Import project in vercel.com
# 3. Set Framework Preset: Other
# 4. Set Output Directory: . (root)
# 5. Vercel serves index.html statically
# 6. In index.html, set window.BACKEND_URL = "https://your-backend.railway.app"
```

**Backend on Render (free tier):**

```bash
# 1. Create a new Web Service on render.com → connect your GitHub repo
# 2. Build command: pip install -r requirements.txt
# 3. Start command: uvicorn app:app --host 0.0.0.0 --port $PORT
# 4. Add env vars from .env.example in the Render dashboard
# 5. Use a persistent disk (Render paid) for faiss.index to survive restarts
```

---

### Option B — Azure Container Apps (Recommended for Production)

**Dockerfile** (place in repo root if adding; not committed per constraints):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps for pdfplumber
RUN apt-get update && apt-get install -y \
    libpoppler-cpp-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & push:**

```bash
# Login to Azure Container Registry
az acr login --name <your-registry>

# Build and push
docker build -t agrorag-backend:latest .
docker tag agrorag-backend:latest <your-registry>.azurecr.io/agrorag-backend:latest
docker push <your-registry>.azurecr.io/agrorag-backend:latest
```

**Deploy to Azure Container Apps:**

```bash
az containerapp create \
  --name agrorag-backend \
  --resource-group agrorag-rg \
  --image <your-registry>.azurecr.io/agrorag-backend:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --env-vars \
    OPENAI_API_KEY=secretref:openai-key \
    OPENWEATHER_API_KEY=secretref:weather-key \
    ALLOWED_ORIGINS="https://your-vercel-app.vercel.app"
```

> **Persistence:** Mount an Azure File Share to `/app` so `faiss.index` and `vector_store.json` survive container restarts.

**Azure File Share mount:**

```bash
az containerapp update \
  --name agrorag-backend \
  --resource-group agrorag-rg \
  --storage-name agrorag-storage \
  --storage-mount "/app/data"
```

---

### Option C — GitHub Actions CI/CD

Create `.github/workflows/deploy.yml` (not in the 5-file repo, but document it here):

```yaml
name: Deploy AgroRAG

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install and test
        run: |
          pip install -r requirements.txt
          python -c "import app; print('Backend imports OK')"

      - name: Login to Azure Container Registry
        uses: azure/docker-login@v1
        with:
          login-server: ${{ secrets.ACR_SERVER }}
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}

      - name: Build and push Docker image
        run: |
          docker build -t ${{ secrets.ACR_SERVER }}/agrorag-backend:${{ github.sha }} .
          docker push ${{ secrets.ACR_SERVER }}/agrorag-backend:${{ github.sha }}

      - name: Deploy to Azure Container Apps
        uses: azure/container-apps-deploy-action@v1
        with:
          resourceGroup: agrorag-rg
          containerAppName: agrorag-backend
          imageToDeploy: ${{ secrets.ACR_SERVER }}/agrorag-backend:${{ github.sha }}

      - name: Deploy frontend to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./
```

---

## 🔐 Environment Variables

See `.env.example` for the full list. Key variables:

| Variable              | Required    | Description                                               |
| --------------------- | ----------- | --------------------------------------------------------- |
| `OPENAI_API_KEY`      | Optional    | GPT-4o-mini for LLM answers; falls back to local if unset |
| `OPENWEATHER_API_KEY` | Optional    | Live weather; UI shows manual fallback if unset           |
| `EMBED_MODEL`         | Optional    | Default: `all-MiniLM-L6-v2`                               |
| `ALLOWED_ORIGINS`     | Recommended | Comma-separated CORS origins for production               |

---

## 🔒 Safety & Disclaimer

AgroRAG is an **assistive tool**, not a replacement for professional agronomic advice.

- All chemical dosage suggestions must be verified against **local product labels and regulations**
- Regional crop varieties may respond differently — always **test on a small plot first**
- Consult your **local agricultural extension officer** for confirmation
- Weather data and RAG responses are best-effort — field observation takes priority

---

## 📜 License

MIT
