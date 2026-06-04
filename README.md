# 🤖 AGCRA — Autonomous GitHub Code Review Agent

An MCP-powered AI agent that automatically reviews every pull request and posts structured, line-by-line review comments on GitHub.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What It Does

- ✅ **Connects** to your GitHub repository via a custom-built MCP server  
- ✅ **Triggers automatically** every time a new pull request is opened  
- ✅ **Reviews code** for bugs, security vulnerabilities, and performance anti-patterns  
- ✅ **Cross-references** changes against existing codebase patterns using RAG over your repo  
- ✅ **Posts structured** line-by-line review comments directly on the GitHub PR  
- ✅ **Learns from feedback** — dismissed suggestions are remembered for future PRs  
- ✅ **Generates a summary** comment with overall quality score and top 3 concerns  

## Architecture

```
GitHub PR Event
    │ webhook POST
    ▼
FastAPI Listener ──► HMAC Signature Verification
    │
    ▼
PyGithub: Fetch Diff + Metadata
    │
    ▼
ChromaDB: RAG Similarity Search (optional)
    │
    ▼
LangGraph Pipeline
    ├── Plan Review (split into chunks)
    ├── Claude Analysis (via Anthropic SDK)
    ├── Aggregate Findings
    └── Score + Summarize
    │
    ▼
Post Results via GitHub API
    ├── Inline review comments (per finding)
    └── Summary comment (quality score + top concerns)
    │
    ▼
Feedback Store (SQLite)
    └── Learn from dismissed suggestions
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Agent Runtime | Claude (via Anthropic SDK) |
| MCP Server | FastMCP (Model Context Protocol) |
| GitHub Integration | PyGithub |
| Workflow Engine | LangGraph (StateGraph) |
| RAG / Vector Store | ChromaDB + SentenceTransformers |
| API Server | FastAPI + Uvicorn |
| Feedback Storage | SQLite |
| Language | Python 3.12+ |

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-username/agcra.git
cd agcra
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your keys:
#   GITHUB_TOKEN=ghp_...
#   ANTHROPIC_API_KEY=sk-ant-...
#   GITHUB_WEBHOOK_SECRET=your-secret
```

### 3. Start the Webhook Server

```bash
python -m src.webhook.app
# Server starts at http://0.0.0.0:8000
```

### 4. Expose via ngrok (for local development)

```bash
ngrok http 8000
# Copy the ngrok URL and set it as your GitHub webhook URL
```

### 5. Configure GitHub Webhook

1. Go to your repo → Settings → Webhooks → Add webhook
2. **Payload URL:** `https://your-ngrok-url.ngrok.io/webhook`
3. **Content type:** `application/json`
4. **Secret:** same as `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events:** select "Pull requests"

### 6. (Optional) Index Codebase for RAG

```bash
python scripts/index_repo.py --path /path/to/your/repo
```

### 7. Test Manually

```bash
# Review a specific PR without webhooks
python scripts/run_review.py --repo owner/repo --pr 42

# Dry run (analyze but don't post comments)
python scripts/run_review.py --repo owner/repo --pr 42 --dry-run
```

## MCP Server (Standalone)

The MCP server can be used independently with Claude Code or Claude Desktop:

```bash
# Run the MCP server
python -m src.mcp_server.server

# Test tools locally
python scripts/test_mcp_server.py --tool get_pr_diff --repo owner/repo --pr 1
python scripts/test_mcp_server.py --tool list_pr_files --repo owner/repo --pr 1
```

### Claude Desktop Configuration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "github-reviewer": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/path/to/agcra"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `get_pr_diff` | Fetch the complete diff for a PR |
| `get_pr_metadata` | Get PR title, author, branches, stats |
| `get_file_content` | Read a file at a specific ref |
| `list_pr_files` | List all files changed in a PR |
| `post_review_comment` | Post an inline comment on a diff line |
| `post_pr_summary` | Post a summary comment on the PR |
| `search_codebase` | RAG search for similar patterns |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + review counter |
| `/webhook` | POST | GitHub webhook receiver |

## Project Structure

```
src/
├── config.py              # Central configuration
├── webhook/               # FastAPI webhook listener
│   ├── app.py             # Routes + background dispatch
│   ├── security.py        # HMAC signature verification
│   └── models.py          # Pydantic webhook models
├── github_client/         # GitHub API wrapper
│   ├── client.py          # PyGithub operations
│   └── diff_parser.py     # Unified diff parser
├── mcp_server/            # Custom MCP server
│   └── server.py          # FastMCP + GitHub tools
├── review/                # LangGraph review pipeline
│   ├── state.py           # Pipeline state definition
│   ├── prompts.py         # Claude prompt templates
│   ├── nodes.py           # Graph node functions
│   └── graph.py           # StateGraph wiring
├── rag/                   # ChromaDB RAG layer
│   ├── indexer.py         # Codebase indexer
│   └── retriever.py       # Pattern retriever
└── feedback/              # Feedback learning loop
    ├── store.py           # SQLite feedback storage
    └── learning.py        # Suppression logic
```

## How the Review Pipeline Works

1. **Fetch Diff** — Gets PR metadata and file changes from GitHub API
2. **Fetch File Context** — Reads full file content for surrounding context
3. **Query RAG** — Finds similar patterns in the indexed codebase
4. **Load Feedback** — Retrieves previously dismissed suggestion patterns
5. **Review Chunks** — Sends each file diff to Claude with full context
6. **Aggregate Findings** — Deduplicates, filters by severity, caps at limit
7. **Generate Summary** — Creates a polished markdown summary with quality score
8. **Post Results** — Posts inline comments + summary to the GitHub PR

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

MIT
