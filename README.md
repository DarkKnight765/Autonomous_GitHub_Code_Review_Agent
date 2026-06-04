# 🤖 AGCRA — Autonomous GitHub Code Review Agent

An AI-powered agent that **automatically reviews every pull request** and posts structured, line-by-line review comments directly on GitHub — fully deployed and running 24/7.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen.svg)](https://autonomous-github-code-review-agent.onrender.com/health)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

🌐 **Live deployment:** `https://autonomous-github-code-review-agent.onrender.com`

---

## What It Does

- ✅ **Auto-triggers** on every new pull request via GitHub webhooks
- ✅ **Reviews code** for bugs, security vulnerabilities, and performance anti-patterns
- ✅ **Posts inline comments** line-by-line directly on the GitHub PR diff
- ✅ **Generates a quality score** (1–10) with a markdown summary comment
- ✅ **Cross-references** changes against existing codebase patterns using RAG
- ✅ **Learns from feedback** — dismissed suggestions are remembered for future PRs
- ✅ **Provider-agnostic** — works with Groq (free), Anthropic (Claude), or Google Gemini

## Live Demo

PR #1 on this repo was automatically reviewed by the agent. It found **17 real bugs** including:

| Severity | Issue | Location |
|----------|-------|----------|
| 🔴 HIGH | SQL Injection Vulnerability | `auth.py:8` |
| 🔴 HIGH | Hardcoded Secret Key + Leaked API Token | `auth.py:60` |
| 🔴 HIGH | Cryptographically Broken Hash (MD5) | `auth.py:20` |
| 🔴 HIGH | `eval()` on user input (Remote Code Execution) | `processor.py:36` |
| 🔴 HIGH | N+1 Query Pattern | `auth.py:30` |
| 🟡 MED | ZeroDivisionError | `processor.py:45` |
| + 11 more | ... | ... |

**Quality Score: 2/10** — [See the full review on PR #1 →](https://github.com/DarkKnight765/Autonomous_GitHub_Code_Review_Agent/pull/1)

---

## Architecture

```
GitHub PR opened
    │  webhook POST (HMAC-verified)
    ▼
FastAPI Webhook Server (Render)
    │
    ▼
LangGraph Pipeline
    ├── Node 1: Fetch PR diff + metadata (PyGithub)
    ├── Node 2: Fetch full file context
    ├── Node 3: RAG similarity search (ChromaDB)
    ├── Node 4: Load feedback history (SQLite)
    ├── Node 5: AI analysis per file (Groq / Anthropic / Gemini)
    ├── Node 6: Aggregate + deduplicate findings
    ├── Node 7: Generate quality score + summary
    └── Node 8: Post inline comments + summary to GitHub PR
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **AI / LLM** | Groq (llama-3.3-70b-versatile) · Anthropic Claude · Google Gemini |
| **Workflow Engine** | LangGraph (StateGraph) |
| **GitHub Integration** | PyGithub |
| **API Server** | FastAPI + Uvicorn |
| **RAG / Vector Store** | ChromaDB + SentenceTransformers (all-MiniLM-L6-v2) |
| **Feedback Storage** | SQLite |
| **Deployment** | Render (Docker) |
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
# Edit .env with your keys
```

Required variables:

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub Personal Access Token (needs `repo` scope) |
| `GITHUB_WEBHOOK_SECRET` | Random string for webhook HMAC verification |
| `GROQ_API_KEY` | Free at [console.groq.com](https://console.groq.com) |
| `LLM_PROVIDER` | `groq` · `anthropic` · `gemini` |
| `REVIEW_MODEL` | `llama-3.3-70b-versatile` (Groq default) |

### 3. Run Manually (No Webhook Needed)

```bash
# Review any PR right now
python scripts/run_review.py --repo owner/repo --pr 42

# Dry run — analyze but don't post comments
python scripts/run_review.py --repo owner/repo --pr 42 --dry-run
```

### 4. Run with Auto-Webhook (Local)

```bash
# Starts FastAPI server + ngrok tunnel in one command
python start_agent.py
# Prints your public URL — add it as a GitHub webhook
```

---

## Deployment (Cloud — Recommended)

### Deploy to Render (Free, No Credit Card)

1. Fork this repo
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub repo
4. Select **Docker** runtime (Dockerfile is included)
5. Add environment variables (see table above)
6. Click **Deploy**
7. Set the webhook URL in your GitHub repo:
   ```
   https://your-app.onrender.com/webhook
   ```

### Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

`railway.toml` is included — just connect your repo and add environment variables.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + review counter |
| `/webhook` | POST | GitHub webhook receiver (HMAC verified) |

```bash
# Check if the server is live
curl https://autonomous-github-code-review-agent.onrender.com/health
# → {"status":"healthy","service":"AGCRA","version":"0.1.0","reviews_processed":N}
```

---

## Index Your Codebase for Smarter Reviews (Optional)

```bash
# Index your repo into ChromaDB for RAG-powered context-aware reviews
python scripts/index_repo.py --path .
```

This embeds your entire codebase so the agent can find similar patterns and avoid flagging known false positives.

---

## Project Structure

```
src/
├── config.py              # Central typed configuration
├── webhook/               # FastAPI webhook listener
│   ├── app.py             # Routes + background dispatch
│   ├── security.py        # HMAC signature verification
│   └── models.py          # Pydantic webhook event models
├── github_client/         # GitHub API wrapper
│   ├── client.py          # PyGithub operations
│   └── diff_parser.py     # Unified diff parser
├── mcp_server/            # MCP server (Claude Desktop compatible)
│   └── server.py          # FastMCP + GitHub tools
├── review/                # LangGraph review pipeline
│   ├── state.py           # Pipeline state definition
│   ├── prompts.py         # LLM prompt templates
│   ├── nodes.py           # Graph node functions (provider-agnostic)
│   └── graph.py           # StateGraph wiring
├── rag/                   # ChromaDB RAG layer
│   ├── indexer.py         # Codebase indexer
│   └── retriever.py       # Pattern retriever
└── feedback/              # Feedback learning loop
    ├── store.py           # SQLite feedback storage
    └── learning.py        # Suppression logic

scripts/
├── run_review.py          # Manual PR review CLI
├── index_repo.py          # Codebase RAG indexer
└── test_mcp_server.py     # MCP server test tool

Dockerfile                 # Docker image for deployment
railway.toml               # Railway deployment config
render.yaml                # Render deployment config
start_agent.py             # One-command local startup (server + ngrok)
```

---

## Switching LLM Providers

Change the provider in `.env` — no code changes needed:

```bash
# Use Groq (free — 1M tokens/day)
LLM_PROVIDER=groq
REVIEW_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...

# Use Anthropic Claude
LLM_PROVIDER=anthropic
REVIEW_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...

# Use Google Gemini
LLM_PROVIDER=gemini
REVIEW_MODEL=gemini-2.0-flash
GEMINI_API_KEY=AIza...
```

---

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
# 34 tests passing
```

---

## License

MIT
