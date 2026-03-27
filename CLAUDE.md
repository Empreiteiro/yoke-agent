# RAG Optimization Pipeline

## Project Overview
End-to-end platform for optimizing Retrieval-Augmented Generation (RAG) pipelines through systematic hyperparameter grid search and RAGAS evaluation.

## Architecture
- **Backend**: Python/FastAPI with SQLAlchemy (SQLite default)
- **Frontend**: Next.js 14 with Tailwind CSS (dark theme)
- Backend runs on port 8000, frontend on port 3000
- Frontend proxies `/api/*` to backend

## Key Commands
- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev`

## Conventions
- All documentation and PRs in English
- Commits should be atomic and descriptive
- Backend follows FastAPI patterns with Pydantic schemas
- Frontend uses Next.js App Router with client components
