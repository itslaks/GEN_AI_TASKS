# 🧠 Enterprise Knowledge Copilot

A production-ready RAG (Retrieval-Augmented Generation) system over internal company documents, featuring hybrid search, RBAC, cost monitoring, and full observability — all on free/OSS infrastructure.

---

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENTERPRISE KNOWLEDGE COPILOT                         │
└─────────────────────────────────────────────────────────────────────────────┘

  Browser (index.html)
       │
       │  fetch() / REST API
       ▼
  ┌────────────────────────────────────────────────────────────┐
  │                  Flask App  (app.py)                        │
  │                                                            │
  │  GET /           → serve index.html                        │
  │  GET /health     → system health JSON                      │
  │  GET /metrics    → Prometheus text format                  │
  │  POST /api/query → hybrid retrieve + LLM synthesis         │
  │  POST /api/ingest→ chunk + embed + upload (admin only)     │
  │  GET /api/logs   → structured log ring buffer              │
  │  GET /api/metrics-json → metrics snapshot                  │
  │                                                            │
  │  ┌───────────────┐   ┌──────────────────────────────────┐  │
  │  │  RBAC Filter  │   │   Cost Estimator                 │  │
  │  │  role_permissions│  │   estimate_tokens() × price     │  │
  │  │  → allowed_roles│  │   persist in MetricsStore        │  │
  │  └───────────────┘   └──────────────────────────────────┘  │
  │                                                            │
  │  ┌──────────────────────────────────────────────────────┐  │
  │  │                Hybrid Retrieval                       │  │
  │  │                                                      │  │
  │  │  query ──► get_embedding() ──► VectorizedQuery       │  │
  │  │         ──► BM25 search_text                         │  │
  │  │         ──► Azure AI Search hybrid endpoint          │  │
  │  │         ──► RRF fusion: 1/(k+rank_bm25) +           │  │
  │  │                         1/(k+rank_vector)            │  │
  │  │         ──► RBAC filter: allowed_roles filter        │  │
  │  │         ──► top-K chunks returned                    │  │
  │  └──────────────────────────────────────────────────────┘  │
  │                                                            │
  │  ┌──────────────────────────────────────────────────────┐  │
  │  │                LLM Synthesis                          │  │
  │  │                                                      │  │
  │  │  context = build_context(chunks)                     │  │
  │  │  try: OpenAI GPT-4o-mini  ──► answer                 │  │
  │  │  except: Mistral (local)  ──► answer                 │  │
  │  │  fallback: demo answer                               │  │
  │  └──────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────┘
          │                           │
          ▼                           ▼
  ┌───────────────┐         ┌──────────────────┐
  │  Azure AI     │         │  OpenAI API       │
  │  Search       │         │  (LLM + Embeds)   │
  │  (Free F0)    │         │                  │
  └───────────────┘         └──────────────────┘
                                     │ (fallback)
                            ┌─────────────────┐
                            │  Local Mistral   │
                            │  via Ollama /    │
                            │  llama.cpp       │
                            └─────────────────┘
```

---

## Quick Start (How to Run)

### 1. Clone / place the 5 files

```
project/
├── app.py
├── index.html
├── README.md
├── .env.example
└── requirements.txt
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 4. (Optional) Set up local Mistral fallback

```bash
# Using Ollama (free, OSS)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral
ollama serve          # starts on http://localhost:11434
```

### 5. Run in demo mode (no Azure / OpenAI needed)

```bash
python app.py
# Open http://localhost:5000
```

### 6. Run in full mode

```bash
# Ensure .env has AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, OPENAI_API_KEY
python app.py
```

---

## Azure AI Search Setup

### Create a free index

1. Go to [portal.azure.com](https://portal.azure.com) → Create Azure AI Search → choose **Free (F0)** tier.
2. Note the **Endpoint** and generate an **Admin API Key**.
3. Set these in `.env`.
4. The index schema is auto-created on first ingest via `ensure_index()`.

### Index Schema

| Field           | Type             | Notes                                  |
|-----------------|------------------|----------------------------------------|
| chunk_id        | String (key)     | Stable ID: `{doc_uuid}-{chunk_n:04d}` |
| document_id     | String           | UUID-v5 of filename                    |
| filename        | String           | Original filename, filterable          |
| last_modified   | String (ISO8601) | Sortable                               |
| allowed_roles   | Collection(String)| Filterable — RBAC enforcement         |
| content         | String           | Full-text searchable (en.microsoft)    |
| content_vector  | Collection(Single)| 1536-dim for ada-002                  |

### Vector Configuration

- **Algorithm**: HNSW (`m=4`, `efConstruction=400`) — free, built into Azure AI Search
- **Dimensions**: 1536 (text-embedding-ada-002) — configurable via `OPENAI_EMBEDDING_MODEL`
- **Profile**: `hnsw-profile` mapped to the vector field

### Semantic Configuration (optional)

Semantic ranking re-ranks BM25+vector results using a cross-encoder. Enabled automatically if the index includes `semantic-config`.

---

## Environment Variables

| Variable                  | Default                              | Description                              |
|---------------------------|--------------------------------------|------------------------------------------|
| AZURE_SEARCH_ENDPOINT     | —                                    | Azure AI Search HTTPS endpoint           |
| AZURE_SEARCH_KEY          | —                                    | Admin or query API key                   |
| AZURE_SEARCH_INDEX        | knowledge-copilot                    | Index name                               |
| OPENAI_API_KEY            | —                                    | OpenAI API key                           |
| OPENAI_CHAT_MODEL         | gpt-4o-mini                          | Chat model (cheapest capable option)     |
| OPENAI_EMBEDDING_MODEL    | text-embedding-ada-002               | Embedding model                          |
| MISTRAL_ENDPOINT          | http://localhost:11434/api/chat      | Local Mistral/Ollama endpoint            |
| MISTRAL_MODEL             | mistral                              | Model name for local server              |
| ADMIN_TOKEN               | demo-admin-secret                    | Bearer token for ingest endpoint         |
| TOP_K_RESULTS             | 5                                    | Number of chunks to retrieve             |
| VECTOR_WEIGHT             | 0.6                                  | Weight for vector score in fusion        |
| KEYWORD_WEIGHT            | 0.4                                  | Weight for BM25 score in fusion          |
| CHUNK_SIZE                | 512                                  | Words per chunk                          |
| CHUNK_OVERLAP             | 64                                   | Overlap words between chunks             |
| OPENAI_PRICE_IN_PER_1M   | 0.15                                 | USD per 1M input tokens                  |
| OPENAI_PRICE_OUT_PER_1M  | 0.60                                 | USD per 1M output tokens                 |
| OPENAI_PRICE_EMB_PER_1M  | 0.10                                 | USD per 1M embedding tokens              |
| PORT                      | 5000                                 | Flask listen port                        |
| FLASK_DEBUG               | false                                | Enable Flask debug mode                  |

---

## RBAC — How It Works

### Role Hierarchy

```
admin    → public + internal + confidential + restricted   (+ can ingest)
manager  → public + internal + confidential
analyst  → public + internal
viewer   → public
guest    → public
```

### Enforcement Flow

1. **UI**: User selects role from dropdown (demo mode). In production, replace with JWT/OAuth claim.
2. **API**: `POST /api/query` receives `{"query": "...", "role": "analyst"}`.
3. **Filter construction**: Flask maps role → `allowed_doc_groups` list.
4. **Azure filter**: OData filter applied at query time:
   ```
   allowed_roles/any(r: r eq 'public') or allowed_roles/any(r: r eq 'internal')
   ```
5. **Documents not matching** the filter are never returned — enforced server-side.
6. **Ingest** gate: `POST /api/ingest` checks `X-User-Role: admin` header **and** `Authorization: Bearer ADMIN_TOKEN`.

### Extending RBAC

To add a new role (e.g. `executive`):
```python
ROLE_PERMISSIONS["executive"] = {
    "can_ingest": False,
    "allowed_doc_groups": ["public", "internal", "confidential", "executive-only"]
}
```
Tag documents at ingest time with `allowed_roles: ["executive-only"]`.

---

## Hybrid Search — How Scoring Works

### BM25 (Keyword)

Azure AI Search uses the Okapi BM25 formula internally for full-text matching. It scores based on term frequency (TF), inverse document frequency (IDF), and document length normalization.

### Vector Similarity

HNSW approximate nearest-neighbor search over 1536-dimensional embeddings. Returns cosine similarity score.

### Reciprocal Rank Fusion (RRF)

Azure AI Search natively fuses both ranking lists:

```
RRF_score(d) = Σ_r  1 / (k + rank_r(d))

where:
  k    = 60  (standard constant — dampens top-rank advantage)
  r    ∈ { keyword_ranking, vector_ranking }
  rank = position of document d in that ranking list
```

**Example** (k=60):
```
Document A: BM25 rank 1, vector rank 3
  RRF = 1/(60+1) + 1/(60+3) = 0.01639 + 0.01587 = 0.03226

Document B: BM25 rank 5, vector rank 1
  RRF = 1/(60+5) + 1/(60+1) = 0.01538 + 0.01639 = 0.03177
```
Document A wins by a small margin — good keyword AND vector match beats single-mode dominance.

### Configurable weights

`VECTOR_WEIGHT` and `KEYWORD_WEIGHT` allow you to bias the fusion. These map to Azure's `weight` parameter on `VectorizedQuery` for semantic boosting when combined with Azure Semantic Ranker.

---

## Cost Monitoring

### Methodology

1. **Token counting**: Uses `estimate_tokens(text) = ceil(len(text)/4)` — approximates GPT tokenization (average 4 chars/token). For exact counts, install `tiktoken` (free/OSS) and replace the heuristic.
2. **Cost formula**:
   ```
   cost = (tokens_in / 1M) × PRICE_IN
        + (tokens_out / 1M) × PRICE_OUT
        + (embed_tokens / 1M) × PRICE_EMB
   ```
3. **Storage**: In-memory `MetricsStore`. Totals persist for the process lifetime. Restart clears counts. For persistence: write to a local JSON file or SQLite (add to app.py — no extra files needed).
4. **Per-role breakdown**: Each request increments a per-role bucket in `MetricsStore.per_role`.

### Limitations

- Heuristic token counts may be off by ±15%.
- Actual OpenAI usage is authoritative — check your dashboard.
- No currency conversion or tax included.
- Embedding costs at ingest are tracked separately (`embed_cost_usd` in ingest response).

### Cost Dashboard (UI)

Visible in the left sidebar. Shows: total cost, last-request cost, tokens in/out, per-role breakdown table. Auto-refreshes every 30 seconds.

---

## Observability

### Structured Logging

All logs are emitted as JSON to stdout:
```json
{
  "timestamp": "2024-11-01T12:00:00.000Z",
  "level": "INFO",
  "message": "Query completed",
  "request_id": "a1b2c3d4",
  "role": "analyst",
  "retrieval_ms": 145.2,
  "llm_ms": 820.5,
  "provider": "openai",
  "tokens_in": 1240,
  "tokens_out": 312,
  "cost_usd": 0.000372,
  "demo_mode": false
}
```

Pipe to any log aggregator: `python app.py 2>&1 | your-log-shipper`

### Log Ring Buffer

Last 200 log entries kept in-memory. Access via:
```
GET /api/logs → { "logs": [...], "total_buffered": N }
```
The UI streams and displays the last 50 entries in the Observability panel.

### Prometheus Metrics

```
GET /metrics
```
Returns Prometheus text format. Scrape with any Prometheus-compatible system (Prometheus, Grafana, VictoriaMetrics — all free/OSS).

Available metrics:
- `copilot_requests_total` — counter
- `copilot_errors_total` — counter
- `copilot_avg_retrieval_ms` — gauge
- `copilot_avg_llm_ms` — gauge
- `copilot_tokens_in_total` — counter
- `copilot_tokens_out_total` — counter
- `copilot_cost_usd_total` — counter
- `copilot_openai_calls` — counter
- `copilot_mistral_calls` — counter

### OpenTelemetry Note

Full OTEL was replaced with structured JSON logging + Prometheus scraping (both free/OSS) to avoid adding a collector dependency. To add OTEL: `pip install opentelemetry-sdk opentelemetry-exporter-otlp` and wrap `hybrid_retrieve` / `synthesize` with `tracer.start_as_current_span(...)`.

### Health Check

```
GET /health
```
Returns JSON with Azure Search and OpenAI status. Use as a readiness probe in Docker/Kubernetes.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Demo mode, no Azure results | `AZURE_SEARCH_ENDPOINT` not set | Set env vars, restart |
| OpenAI errors, Mistral fallback | Invalid `OPENAI_API_KEY` or quota exceeded | Check key/billing |
| Mistral not responding | Ollama not running | `ollama serve` |
| Ingest returns 403 | Wrong role or token | Use `X-User-Role: admin` + correct `ADMIN_TOKEN` |
| Empty results for a role | Role not permitted for those docs | Check `allowed_roles` on documents |
| High token estimates | Long context | Reduce `TOP_K_RESULTS` or `CHUNK_SIZE` |
| Index not found | First run, Azure not yet indexed | Call `/api/ingest` first |

---

## Security Notes (Production)

1. **Replace demo RBAC** with proper JWT validation (e.g. `flask-jwt-extended`, Azure AD / Entra ID tokens).
2. **Rotate `ADMIN_TOKEN`** — never use `demo-admin-secret` in production.
3. **Use Azure Managed Identity** instead of API keys when deployed on Azure.
4. **Enable HTTPS** — run behind a reverse proxy (nginx, Caddy — both free/OSS).
5. **Rate limiting** — add `flask-limiter` (free/OSS) to prevent abuse.
6. **Input validation** — sanitize query length and file content on ingest.
7. **Audit log** — route JSON logs to an immutable store (Azure Log Analytics free tier).
8. **Never log full document content** — only log chunk_ids and snippets.

---

## Free Source Substitutions

| Original intent | Free substitute used | Reason |
|-----------------|----------------------|--------|
| Paid tokenizer (tiktoken requires pinned install) | `ceil(len/4)` heuristic | Zero dependency; ±15% accuracy acceptable for cost estimation |
| Azure Semantic Ranker (paid add-on) | HNSW vector + BM25 hybrid with RRF | Achieves comparable quality; built into free Azure AI Search tier |
| OpenTelemetry collector (infra overhead) | Structured JSON logs + Prometheus text | Simpler, zero extra services, scrape-compatible |
| Paid log aggregation | In-memory ring buffer + stdout JSON | Developer-friendly; pipe to any OSS aggregator |
| Azure Key Vault (paid) | `.env` file + python-dotenv | Sufficient for dev; swap to Key Vault in production |
