# AgeAyurveda Companion

Rule-based Ayurvedic chatbot widget for ageayurveda.com (Shopify store).

## Architecture
- **Backend**: FastAPI + PostgreSQL/SQLite at `backend/`
- **Widget**: Vanilla TypeScript + Vite IIFE bundle at `widget/` (Shadow DOM, <35KB)
- **Admin**: React + TypeScript + Tailwind at `admin/`

## Quick Start
```bash
cd backend && pip install -r requirements.txt
# Set .env from .env.example
uvicorn app.main:app --reload
```

## Key Commands
- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Widget: `cd widget && npm run dev`
- Admin: `cd admin && npm run dev`
- Create admin: `cd backend && python scripts/create_admin.py`
- Seed products: `cd backend && python scripts/seed_products.py`
- Alembic migration: `cd backend && alembic revision --autogenerate -m "description"`
- Apply migrations: `cd backend && alembic upgrade head`

## API Endpoints
All under `/api/v1/`:
- `POST /chat` and `POST /chat/stream` — Main chat (SSE streaming)
- `GET /prakriti/questions`, `POST /prakriti/submit`
- `GET /products/recommend`, `GET /products`
- `POST /leads/capture`
- `GET /widget/config`
- `POST /admin/login`, `GET /admin/dashboard`, `GET /admin/leads`
- `GET /health`

## Deployment
- Render (render.yaml blueprint): Web service ($7) + PostgreSQL ($7)
- Singapore region, 2 workers

## Key Design Decisions
- All chat responses are rule-based (static_chat.py) — no LLM APIs, no vector DB
- Product recommendations: rules-based scoring from `product_mappings.json`
- Safety: emergency detection, health disclaimers, serious condition referral
- Bilingual: auto-detect EN/HI via Devanagari script detection
