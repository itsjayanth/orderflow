# Orderflow

WhatsApp-based ordering system for independent restaurants: customers browse, order, and pay entirely inside a WhatsApp chat; a merchant web dashboard shows and manages orders in real time.

See `docs/project-brief.txt` for the product brief, `ARCHITECTURE.md` for the system design, and `TECH_STACK.md` for stack decisions and repo layout.

## Getting started

```bash
# Backend (FastAPI)
cd backend && uv sync && cp .env.example .env
uv run uvicorn app:app --app-dir src --reload --port 8000

# Frontend (React + Vite), in a second shell
cd frontend && npm install && cp .env.example .env
npm run dev
```

Backend: http://localhost:8000/docs · Frontend: http://localhost:5173
