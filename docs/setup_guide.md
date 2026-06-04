# 🔧 AGCRA Setup Guide — Getting Your API Keys

Follow these 3 steps to get everything you need. Total time: ~10 minutes.

---

## Step 1: GitHub Personal Access Token (FREE)

### What you need: A token with `repo` scope

1. **Go to:** https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Fill in:
   - **Note:** `AGCRA Code Review Bot`
   - **Expiration:** 90 days (or custom)
   - **Scopes:** Check ✅ `repo` (this gives full control of private repositories — needed to read PRs and post comments)
4. Click **"Generate token"**
5. **COPY THE TOKEN IMMEDIATELY** — you won't see it again!
   - It starts with `ghp_...`

### Also create a Webhook Secret:
- Open a terminal and run:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
- Save this value — you'll use it as `GITHUB_WEBHOOK_SECRET`

---

## Step 2: Anthropic API Key (PAID — has free trial credits)

### What you need: An API key for Claude

1. **Go to:** https://console.anthropic.com/
2. **Sign up** or **log in** with your Google/email
3. Once logged in, go to: https://console.anthropic.com/settings/keys
4. Click **"Create Key"**
5. Name it: `AGCRA`
6. **COPY THE KEY** — starts with `sk-ant-...`

> **Cost info:** Claude Sonnet costs ~$3/million input tokens. A typical PR review uses ~5K-20K tokens. So reviewing 100 PRs costs roughly $0.50-$2.00. They give free credits on signup.

---

## Step 3: Install ngrok (FREE)

### What it does: Exposes your local server to the internet so GitHub can send webhooks

### Option A — Install via npm (easiest on Windows):
```bash
npm install -g ngrok
```

### Option B — Download directly:
1. **Go to:** https://ngrok.com/download
2. Sign up for a free account
3. Download the Windows version
4. Unzip and add to your PATH

### After installing:
```bash
# Authenticate (one-time, use your auth token from ngrok dashboard)
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN

# Start the tunnel (run this after starting the webhook server)
ngrok http 8000
```

---

## Step 4: Configure Your .env File

Once you have all 3 values, create your `.env` file:

```bash
cd "d:\PROJECTS __ DEV\Autonomous_GitHub_Code_Review_Agent(AGCRA)"
copy .env.example .env
```

Then edit `.env` and fill in:

```env
GITHUB_TOKEN=ghp_your_actual_token_here
GITHUB_WEBHOOK_SECRET=your_generated_hex_secret
ANTHROPIC_API_KEY=sk-ant-your_actual_key_here
TARGET_REPO=your-username/your-repo-name
```

---

## Step 5: Set Up the GitHub Webhook

1. Go to your target repo on GitHub
2. **Settings** → **Webhooks** → **Add webhook**
3. Fill in:
   - **Payload URL:** `https://YOUR-NGROK-URL.ngrok-free.app/webhook`
   - **Content type:** `application/json`
   - **Secret:** paste your `GITHUB_WEBHOOK_SECRET` value
   - **Events:** select **"Let me select individual events"** → check **"Pull requests"**
4. Click **"Add webhook"**

---

## Quick Verification

After completing setup, test that everything works:

```bash
# 1. Start the server
python -m src.webhook.app

# 2. In another terminal, start ngrok
ngrok http 8000

# 3. Test the health endpoint
curl http://localhost:8000/health

# 4. Open a PR on your repo — the agent should trigger automatically!
```
