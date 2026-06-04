# 🤖 AGCRA — Autonomous GitHub Code Review Agent

An AI-powered agent that **automatically reviews every pull request** and posts structured, line-by-line security and quality findings directly on GitHub — fully deployed and running 24/7.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Live Demo](https://img.shields.io/badge/demo-live%20on%20Render-brightgreen.svg)](https://autonomous-github-code-review-agent.onrender.com/health)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by Groq](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3%2070B-orange.svg)](https://console.groq.com)

🌐 **Live:** `https://autonomous-github-code-review-agent.onrender.com`

---

## What It Does

Every time a pull request is opened on a connected repository, AGCRA:

1. **Fetches** the PR diff and full file context via GitHub API
2. **Analyzes** the code using LLaMA 3.3 70B (via Groq) for bugs, security issues, and anti-patterns
3. **Posts** inline review comments at the exact lines with issues
4. **Summarizes** with an overall quality score (1–10) and top concerns
5. **Learns** from dismissed feedback to avoid repeat false positives

## Live Demo

**PR #4** on this repo was reviewed automatically by AGCRA within 60 seconds of opening. It found **20+ security issues** in a realistic e-commerce order management module:

| Severity | Issue | File:Line |
|----------|-------|-----------|
| 🔴 HIGH | Hardcoded production DB credentials + API keys | `order_manager.py:13` |
| 🔴 HIGH | SQL Injection in `get_order()` via string concatenation | `order_manager.py:22` |
| 🔴 HIGH | Shell injection via `subprocess.run(shell=True)` | `order_manager.py:40` |
| 🔴 HIGH | `pickle.loads()` on untrusted input (Remote Code Execution) | `order_manager.py:62` |
| 🔴 HIGH | Directory traversal in `export_orders()` | `order_manager.py:73` |
| 🔴 HIGH | MD5 for credit card hashing (cryptographically broken) | `order_manager.py:45` |
| 🟡 MED | N+1 query pattern in `get_all_orders()` | `order_manager.py:50` |
| 🟡 MED | Resource leak — DB connections never closed | `order_manager.py:22` |
| 🟡 MED | ZeroDivisionError in `apply_discount()` | `order_manager.py:67` |
| + more | ... | ... |

**Quality Score: 2/10** → [See the full review on PR #4 →](https://github.com/DarkKnight765/Autonomous_GitHub_Code_Review_Agent/pull/4)

---

## Architecture

```
PR opened on GitHub
    │  webhook POST (HMAC-verified)
    ▼
FastAPI Webhook Server (Render — always on)
    │  background task dispatched
    ▼
LangGraph Pipeline
    ├── Node 1: Fetch PR diff + metadata (PyGithub)
    ├── Node 2: Fetch full file content for context
    ├── Node 3: AI analysis per file (Groq LLaMA 3.3 70B)
    ├── Node 4: Load feedback history (SQLite)
    ├── Node 5: Aggregate + deduplicate findings
    ├── Node 6: Generate quality score + summary
    └── Node 7: Post inline comments + summary to GitHub PR
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **AI / LLM** | [Groq](https://console.groq.com) (llama-3.3-70b-versatile) · Anthropic Claude · Google Gemini |
| **Workflow Engine** | LangGraph (StateGraph) |
| **GitHub Integration** | PyGithub |
| **API Server** | FastAPI + Uvicorn |
| **Feedback Storage** | SQLite |
| **Deployment** | Render (Docker, free tier) |
| **Keep-Alive** | GitHub Actions cron (every 10 min) |
| **Language** | Python 3.12+ |

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/DarkKnight765/Autonomous_GitHub_Code_Review_Agent.git
cd Autonomous_GitHub_Code_Review_Agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Fill in your keys
```

Minimum required variables:

| Variable | Where to get it |
|----------|----------------|
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) — needs `repo` scope |
| `GITHUB_WEBHOOK_SECRET` | Any random string: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GROQ_API_KEY` | Free at [console.groq.com](https://console.groq.com) — 1M tokens/day |
| `LLM_PROVIDER` | `groq` |
| `TARGET_REPO` | `owner/repo-name` |

### 3. Run Manually (No Webhook Needed)

```bash
# Review any PR immediately
python scripts/run_review.py --repo owner/repo --pr 42

# Dry run — analyze but don't post comments
python scripts/run_review.py --repo owner/repo --pr 42 --dry-run
```

### 4. Run Locally with Auto-Webhook

```bash
# Starts FastAPI server + ngrok tunnel in one command
python start_agent.py
# Prints your public webhook URL — add it to GitHub repo settings
```

---

## Cloud Deployment (Free)

### Deploy to Render

> **Free tier, no credit card required. Always-on via GitHub Actions keep-alive.**

1. Fork this repo
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub fork → select **Docker** runtime
4. Add environment variables (see table above)
5. Deploy → set the webhook URL in your GitHub repo:
   ```
   https://your-app.onrender.com/webhook
   ```
6. Enable **GitHub Actions** in your fork (already configured in `.github/workflows/keep_alive.yml`)

> The `keep_alive.yml` workflow pings your Render server every 10 minutes to prevent free-tier sleep.

### Why the Slim Docker Image?

The production `Dockerfile` uses `requirements-prod.txt` which **excludes** `chromadb` and `sentence-transformers` to stay within Render's 512MB free tier RAM limit.  
For local development with full RAG support, use `pip install -r requirements.txt`.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + reviews processed counter |
| `/webhook` | POST | GitHub webhook receiver (HMAC-verified) |

```bash
# Check live server
curl https://autonomous-github-code-review-agent.onrender.com/health
# → {"status":"healthy","service":"AGCRA","version":"0.1.0","reviews_processed":N}
```

---

## Switching LLM Providers

Change in `.env` — no code changes needed:

```bash
# Groq (default — free, 1M tokens/day)
LLM_PROVIDER=groq
REVIEW_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...

# Anthropic Claude
LLM_PROVIDER=anthropic
REVIEW_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...

# Google Gemini
LLM_PROVIDER=gemini
REVIEW_MODEL=gemini-2.0-flash
GEMINI_API_KEY=AIza...
```

---

## (Optional) RAG-Powered Context-Aware Reviews

Index your codebase so the agent can cross-reference similar patterns:

```bash
# Requires full requirements: pip install -r requirements.txt
python scripts/index_repo.py --path .
# → Indexes 37+ files, 99+ chunks into ChromaDB
```

RAG is automatically disabled in cloud deployments (no chroma_db directory) to save memory.

---

## Project Structure

```
src/
├── config.py              # Central typed configuration (pydantic)
├── webhook/               # FastAPI webhook listener
│   ├── app.py             # Routes + HMAC-verified background dispatch
│   ├── security.py        # Webhook signature verification
│   └── models.py          # Pydantic GitHub event models
├── github_client/         # GitHub API wrapper
│   ├── client.py          # PyGithub operations
│   └── diff_parser.py     # Unified diff parser
├── mcp_server/            # MCP server (Claude Desktop compatible)
│   └── server.py          # FastMCP + GitHub tools
├── review/                # LangGraph review pipeline
│   ├── state.py           # ReviewState TypedDict
│   ├── prompts.py         # LLM prompt templates
│   ├── nodes.py           # Node functions (provider-agnostic)
│   └── graph.py           # StateGraph wiring
├── rag/                   # ChromaDB RAG (local dev only)
│   ├── indexer.py         # Codebase indexer
│   └── retriever.py       # Similarity search
└── feedback/              # Feedback learning loop
    ├── store.py            # SQLite dismissed suggestions store
    └── learning.py         # Suppression logic

scripts/
├── run_review.py           # Manual PR review CLI
├── index_repo.py           # RAG codebase indexer
└── test_mcp_server.py      # MCP tool tester

.github/workflows/
└── keep_alive.yml          # Cron: ping Render every 10 min

Dockerfile                  # Slim production image (no chromadb)
requirements.txt            # Full deps (local dev + RAG)
requirements-prod.txt       # Slim deps (cloud deployment)
start_agent.py              # One-command local startup (server + ngrok)
```

---

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## License

MIT
