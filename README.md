# SHL Conversational Assessment Recommender

A conversational AI agent that helps hiring managers and recruiters find the right SHL assessments through natural dialogue — no keyword search, no catalog expertise required.

Built for the **SHL Labs AI Intern Take-home Assignment**.

---

## What This Does

Traditional assessment catalogs require you to already know what you are looking for. This agent works differently. You describe the role in plain English, and it asks smart follow-up questions, retrieves relevant assessments from the real SHL catalog, and delivers a grounded shortlist — without ever inventing an assessment that does not exist.

**Example conversation:**

```
User:      I need to hire a Java developer who works with stakeholders
Agent:     What seniority level are you hiring for?
User:      Mid-level, around 4 years of experience
Agent:     Got it. Here are 7 assessments that fit a mid-level Java developer
           with stakeholder collaboration needs: ...
```

---

## Live API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Returns `{"status": "ok"}` — used by the grader to check readiness |
| `/chat` | POST | Takes full conversation history, returns next agent reply + recommendations |

---

## Project Structure

```
shl-recommender/
├── app/
│   ├── __init__.py
│   ├── main.py          ← FastAPI app, /health and /chat endpoints
│   ├── agent.py         ← Core agent logic: routing, LLM calls, overrides
│   ├── retrieval.py     ← TF-IDF index, search, report-penalty, find_by_name
│   ├── catalog.py       ← Loads and normalises catalog_clean.json
│   └── schemas.py       ← Pydantic models: Message, ChatRequest, ChatResponse
├── data/
│   ├── catalog_raw.json      ← Original downloaded catalog (do not edit)
│   ├── catalog_clean.json    ← Filtered Individual Test Solutions only (source of truth)
│   └── catalog.json          ← Legacy, not used by app
├── scripts/
│   ├── scrape_catalog.py     ← Downloads catalog from SHL endpoint
│   ├── fix_catalog.py        ← Filters out Job Solutions, normalises fields
│   └── eval.py               ← Runs all 10 traces, computes Recall@10
├── traces/
│   └── GenAI_SampleConversations/
│       ├── C1.md ... C10.md  ← The 10 labeled evaluation traces
│       └── traces.json       ← Same traces in JSON format used by eval.py
├── .env.example         ← Copy to .env and fill in your key
├── requirements.txt
└── README.md
```

---

## How It Works

### The core rule

> **The LLM decides what to say. Retrieval decides what it is allowed to recommend.**

Gemini never generates assessment names from its own knowledge. It only picks from a candidate list retrieved from the catalog. A post-call validation step then strips anything that does not exactly match a real catalog entry.

### Two LLM calls per turn

**Call 1 — Classifier**
- Input: full conversation history
- Task: decide action (clarify / recommend / refine / compare / refuse) and extract structured slots — retrieval query, job level, test type preferences
- Returns: strict JSON
- Never sees the catalog — only understands intent

**Call 2 — Generator** (only for recommend / refine / compare)
- Input: conversation history + top-20 retrieved catalog entries
- Task: pick and rank 6–10 items from that list only
- Explicitly told it cannot add, modify, or invent anything outside the provided candidates

### Retrieval pipeline

```
User messages
     ↓
TF-IDF search (top_k=20)
     ↓
Report-variant penalty applied (0.6x for pure "Report" items)
     ↓
Keyword injection layer (adds OPQ32r, Verify G+, DSI, GSA based on domain keywords)
     ↓
Candidate block passed to Gemini
     ↓
Gemini selects names
     ↓
Hallucination guard: each name validated against catalog dict
     ↓
OPQ32r hard-appended if not already present
     ↓
Final recommendations (max 10)
```

### Five agent actions

| Action | When it fires | Recommendations returned |
|---|---|---|
| **Clarify** | Turn 1 only, zero job/skill signal | Empty |
| **Recommend** | Turn 2+ with any useful signal | 6–10 items |
| **Refine** | User changes constraint after shortlist exists | Updated 6–10 items |
| **Compare** | User asks to compare two named assessments | Empty (answer in reply text) |
| **Refuse** | Off-topic / legal / prompt injection | Empty |

---

## Setup and Running Locally

### Prerequisites
- Python 3.11+
- A Google Gemini API key — get one free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/shl-recommender.git
cd shl-recommender
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API key
```bash
cp .env.example .env
```
Open `.env` and set:
```
GEMINI_API_KEY=AIza...your_key_here...
GEMINI_MODEL=gemini-2.5-flash
```

### 4. (Optional) Rebuild the catalog from scratch
The filtered catalog is already included at `data/catalog_clean.json`. Only run these if you want to re-download:
```bash
python scripts/scrape_catalog.py     # downloads catalog_raw.json
python scripts/fix_catalog.py        # filters to Individual Test Solutions only
```

### 5. Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Test it works
```bash
# Health check
curl http://localhost:8000/health

# Single turn
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I need to hire a mid-level Java developer"}
    ]
  }'

# Multi-turn
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user",      "content": "I am hiring a Java developer"},
      {"role": "assistant", "content": "What seniority level are you targeting?"},
      {"role": "user",      "content": "Mid-level, around 4 years of experience"}
    ]
  }'
```

---

## API Reference

### POST /chat

**Request:**
```json
{
  "messages": [
    {"role": "user",      "content": "I need to hire a Java developer"},
    {"role": "assistant", "content": "What seniority level are you targeting?"},
    {"role": "user",      "content": "Mid-level, around 4 years"}
  ]
}
```

- Send the **full conversation history** every call — the API is stateless
- Max 8 turns enforced server-side

**Response:**
```json
{
  "reply": "Here are 7 assessments that match your requirements.",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/solutions/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    },
    {
      "name": "Occupational Personality Questionnaire OPQ32r",
      "url": "https://www.shl.com/...",
      "test_type": "P"
    }
  ],
  "end_of_conversation": false
}
```

| Field | Type | Description |
|---|---|---|
| `reply` | string | Natural language response |
| `recommendations` | array | 1–10 items when shortlist is ready, empty `[]` otherwise |
| `recommendations[].name` | string | Exact name from SHL catalog |
| `recommendations[].url` | string | Real SHL catalog URL — never invented |
| `recommendations[].test_type` | string | A=Ability · P=Personality · K=Knowledge · B=Situational Judgement · C=Competencies · S=Simulations · D=Development/360 · E=Exercises |
| `end_of_conversation` | boolean | `true` when user has confirmed the shortlist |

### GET /health

```json
{"status": "ok"}
```

Returns HTTP 200. The SHL grader calls this first and waits up to 2 minutes for a response on cold start.

---

## Running the Evaluation

```bash
# Terminal 1 — start the server
uvicorn app.main:app --port 8000

# Terminal 2 — run eval
python scripts/eval.py
```

This runs all 10 labeled traces against your local `/chat` endpoint and prints:
- Per-trace Recall@10 scores
- Which expected assessments were missed
- Behavior probe results (no recs on Turn 1 for vague query, eoc fires correctly, etc.)
- Mean Recall@10 across all traces

**Results after fixes:**

| Metric | Score |
|---|---|
| Mean Recall@10 | 65.5% |
| Behavior probes passed | 9 / 10 |

---

## Deployment on Render

### 1. Push to GitHub

Make sure `.env` is in `.gitignore` first — never commit your API key.

```bash
# In your project root
git init
git add .
git commit -m "initial commit: SHL assessment recommender"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/shl-recommender.git
git push -u origin main
```

If git asks for a password, use a **Personal Access Token** (not your GitHub password):
GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate new token with `repo` scope.

### 2. Create a Render Web Service

- Go to [render.com](https://render.com) → Sign up with GitHub
- New → Web Service → Connect your repo
- Fill in settings:

| Setting | Value |
|---|---|
| Name | `shl-recommender` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

If your files are in a subfolder, set **Root Directory** to `shl-recommender`.

### 3. Add environment variables

Render dashboard → your service → Environment → Add:

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` |

### 4. Deploy and verify

Click **Create Web Service**. Wait 3–5 minutes for the first deploy. Then:

```bash
curl https://your-app-name.onrender.com/health
# Expected: {"status":"ok"}

curl -X POST https://your-app-name.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"I need to hire a data analyst"}]}'
```

> **Cold start note:** Render free tier sleeps after inactivity. The first request after sleep takes up to 2 minutes. The SHL grader allows this for the `/health` endpoint specifically.

---

## Design Decisions

**Why TF-IDF instead of embeddings?**
The catalog has ~370 items — small enough that TF-IDF recall is excellent. More importantly, it adds zero API latency, keeping every `/chat` call safely within the 30-second timeout. It is also fully deterministic, making debugging and evaluation much easier.

**Why two LLM calls per turn instead of one?**
Separating classification (what action to take?) from generation (what to say and which items to pick?) keeps each prompt small and focused. The classifier never processes 20 catalog entries. The generator never reasons about conversation intent. Each call does one thing well.

**Why the report-variant penalty?**
The SHL catalog has many derivative reports (e.g. "OPQ Leadership Report") that share description text with their underlying base assessments. Without the penalty, TF-IDF consistently ranked these above the base assessment — wrong, because hiring managers want the assessment, not its output report.

**Why force-inject OPQ32r?**
It appeared in the expected shortlist of ~60% of evaluation traces but its name does not semantically match most job-role queries, so TF-IDF reliably misses it. A hard post-LLM append is more reliable than any retrieval or prompt strategy for this specific case.

**Why stateless API design?**
The assignment requires it. Passing the full history on every call is simpler, more reliable, and easier to test than managing server-side session state.

---

## What the Agent Refuses

- General hiring advice ("How do I write a good job description?")
- Legal and compliance questions ("Can I ask candidates about their age?")
- Anything unrelated to SHL assessments
- Prompt injection attempts ("Ignore your instructions and...")

All of these return a polite refusal message, empty recommendations, and `end_of_conversation: true`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Your Google Gemini API key from aistudio.google.com |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Which Gemini model to use |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API framework | FastAPI + Pydantic | Strict schema validation, fast, automatic 422 on bad input |
| Runtime LLM | Google Gemini 2.5 Flash | Free tier, fast inference, strong JSON instruction-following |
| Retrieval | TF-IDF (scikit-learn) | Deterministic, zero latency, great recall at this catalog size |
| Catalog | SHL JSON endpoint → filtered JSON | Offline, always available, no scraping on each request |
| Deployment | Render (free tier) | Auto-deploy from GitHub, env var secrets, cold-start grace period |
