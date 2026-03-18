# LangGraph Instagram Niche Agent (HITL)

This project provides a **Python + LangGraph** agent that:

1. Selects the best niche based on a viral score.
2. Generates an Instagram post (caption + image prompt + hashtags).
3. Sends a Human-in-the-Loop (HITL) approval request over **email** or **WhatsApp**.
4. Publishes to Instagram only after approval.

## Features

- **Niche scoring engine** (`virality_score`) based on trend, competition, and audience fit.
- **LangGraph workflow** with explicit states and conditional transitions.
- **HITL gate** before posting (approve/reject path).
- **Instagram publisher adapter** (Graph API-ready structure).
- **CLI demo mode** for local testing with simulated approval.

## Project structure

- `src/instagram_langgraph_agent.py` – core LangGraph agent and integrations
- `main.py` – CLI entrypoint
- `requirements.txt` – dependencies
- `.env.example` – expected environment variables

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py --approve yes
```

## Environment variables

- `OPENAI_API_KEY` – for LLM caption generation
- `APPROVAL_CHANNEL` – `email` or `whatsapp`

### Email HITL

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `APPROVAL_FROM_EMAIL`
- `APPROVAL_TO_EMAIL`

### WhatsApp HITL (Twilio)

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM` (e.g. `whatsapp:+14155238886`)
- `TWILIO_WHATSAPP_TO`

### Instagram Graph API

- `IG_BUSINESS_ACCOUNT_ID`
- `IG_ACCESS_TOKEN`

> Note: The publisher is implemented as a clean adapter. You can switch from dry-run to live Graph API usage by setting `dry_run=False` in `InstagramPublisher`.

## HITL flow

1. Agent prepares post details.
2. It sends approval details to email/WhatsApp.
3. A human confirms approval.
4. Agent proceeds to upload only if approved.

For production, connect the approval token to a webhook/UI so approvals update the graph state asynchronously.
