# RAG Optimization Pipeline

An end-to-end platform for optimizing Retrieval-Augmented Generation (RAG) pipelines through systematic hyperparameter grid search and [RAGAS](https://docs.ragas.io/) evaluation.

Upload your documents, generate evaluation datasets, configure RAG hyperparameters, run experiments, and get a comprehensive report showing the best configuration — all from a single dashboard.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Pipeline Steps](#pipeline-steps)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Hyperparameters](#hyperparameters)
- [RAGAS Metrics](#ragas-metrics)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Document Upload** — Upload PDF, DOCX, TXT, and Markdown files for analysis
- **AI-Powered Dataset Generation** — LLM analyzes documents and generates evaluation Q&A pairs
- **Human-in-the-Loop (HITL)** — Review, edit, add, or import evaluation questions before proceeding
- **Smart Grid Search Proposal** — LLM analyzes your scenario and proposes optimal hyperparameter combinations
- **Customizable Hyperparameters** — Tune chunk size, overlap, embedding models, top-K, search type, and more
- **RAGAS Evaluation** — Industry-standard metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall
- **Multiple Vector Stores** — ChromaDB (default), Pinecone, Weaviate, Qdrant, Milvus support
- **Visual Reports** — Radar charts, bar charts, sortable tables, and CSV export for results
- **Dark Theme UI** — Modern, responsive interface built with Next.js and Tailwind CSS

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│              (Port 3000 → proxies /api/*)                │
├─────────────────────────────────────────────────────────┤
│                   FastAPI Backend                        │
│                     (Port 8000)                          │
├──────────┬──────────┬──────────┬───────────────────────┤
│ Document │ Dataset  │   Grid   │   Experiment          │
│  Upload  │   Gen    │  Search  │   Runner              │
├──────────┴──────────┴──────────┴───────────────────────┤
│                  Service Layer                          │
│  ┌────────────┐ ┌──────────┐ ┌──────────────────────┐  │
│  │  LangChain │ │ ChromaDB │ │   RAGAS Evaluator    │  │
│  │  Loaders   │ │ / Others │ │                      │  │
│  └────────────┘ └──────────┘ └──────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              SQLite (SQLAlchemy ORM)                     │
└─────────────────────────────────────────────────────────┘
```

---

## Pipeline Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | **Upload Documents** | Upload one or more documents (PDF, DOCX, TXT, MD) for analysis |
| 2 | **Generate Dataset** | LLM reads documents and generates evaluation Q&A pairs automatically |
| 3 | **Review Dataset (HITL)** | Human reviews, edits, deletes, or adds questions manually or via JSON import |
| 4 | **Configure Grid Search** | LLM proposes hyperparameter combinations; user can add/modify parameters |
| 5 | **Run Experiments** | Each combination is executed and evaluated with RAGAS metrics |
| 6 | **View Results** | Interactive report with charts, rankings, and the best configuration highlighted |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS |
| **LLM Integration** | LangChain, OpenAI API |
| **Vector Stores** | ChromaDB (default), Pinecone, Weaviate, Qdrant, Milvus |
| **Evaluation** | RAGAS framework |
| **Charts** | Recharts |
| **Icons** | Lucide React |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key (or compatible LLM provider)

### 1. Clone the repository

```bash
git clone https://github.com/Empreiteiro/rag-optimization-pipeline.git
cd rag-optimization-pipeline
```

### 2. Run setup (creates venv, installs everything)

```bash
make setup
```

### 3. Configure your API key

```bash
# Edit the .env file created by setup
nano backend/.env

# Set your OpenAI API key:
# OPENAI_API_KEY=sk-your-key-here
```

### 4. Start developing

```bash
make dev
```

This starts both servers:
- **Backend**: http://localhost:7070 (with hot reload)
- **Frontend**: http://localhost:4000

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make setup` | First-time setup: venv, deps, .env |
| `make dev` | Start both servers for development |
| `make dev-backend` | Start only the backend |
| `make dev-frontend` | Start only the frontend |
| `make install` | Install all dependencies |
| `make build` | Build frontend for production |
| `make start` | Start both servers in production mode |
| `make lint` | Run linters (ruff + eslint) |
| `make test` | Run backend tests |
| `make db-reset` | Reset the SQLite database |
| `make clean` | Remove all generated files |
| `make help` | Show all available commands |

---

## Configuration

All backend configuration is managed via environment variables in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `DATABASE_URL` | `sqlite:///./rag_pipeline.db` | SQLAlchemy database URL |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded files |
| `DEFAULT_LLM_MODEL` | `gpt-4o-mini` | LLM model for dataset generation |
| `DEFAULT_EMBEDDING_MODEL` | `text-embedding-3-small` | Default embedding model |
| `DEFAULT_VECTORSTORE` | `chromadb` | Default vector store provider |
| `CORS_ORIGINS` | `http://localhost:4000` | Allowed CORS origins |

---

## Hyperparameters

The grid search explores combinations of these RAG pipeline parameters:

| Parameter | Description | Example Values |
|-----------|-------------|----------------|
| **Chunk Size** | Token count per text chunk | `256`, `512`, `1024`, `2048` |
| **Chunk Overlap** | Overlap between consecutive chunks (%) | `0%`, `10%`, `20%`, `30%` |
| **Embedding Model** | Model used to generate vector embeddings | `text-embedding-3-small`, `text-embedding-3-large`, HuggingFace models |
| **Top-K** | Number of documents retrieved per query | `3`, `5`, `10`, `20` |
| **Search Type** | Retrieval strategy | `similarity` (vector), `mmr` (Max Marginal Relevance), `hybrid` (vector + BM25) |

The LLM analyzes your documents and proposes an initial grid. You can then add, remove, or modify any parameter values before running the experiment.

---

## RAGAS Metrics

Each hyperparameter combination is evaluated using these [RAGAS](https://docs.ragas.io/) metrics:

### Fixed Metrics (always computed)

| Metric | Range | Description |
|--------|-------|-------------|
| **Faithfulness** | 0–1 | How factually consistent is the answer with the retrieved context |
| **Answer Relevancy** | 0–1 | How relevant is the answer to the question |
| **Context Precision** | 0–1 | How precise is the retrieved context (signal-to-noise ratio) |
| **Context Recall** | 0–1 | How much of the ground truth is covered by the retrieved context |

### Optional Metrics (user-selectable)

| Metric | Range | Description |
|--------|-------|-------------|
| **Answer Correctness** | 0–1 | Factual accuracy of the answer vs ground truth |
| **Answer Similarity** | 0–1 | Semantic similarity between answer and ground truth |
| **Context Entity Recall** | 0–1 | Entity coverage in retrieved context |
| **Noise Sensitivity** | 0–1 | Robustness to irrelevant context |

---

## API Reference

The backend exposes a RESTful API at `http://localhost:7070`. Full interactive documentation is available at:

- **Swagger UI**: http://localhost:7070/docs
- **ReDoc**: http://localhost:7070/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload documents |
| `GET` | `/api/documents` | List all documents |
| `POST` | `/api/datasets` | Create a new dataset |
| `POST` | `/api/datasets/{id}/generate` | Generate Q&A pairs with LLM |
| `PUT` | `/api/datasets/{id}/items/{item_id}` | Edit a dataset item |
| `POST` | `/api/datasets/{id}/import` | Import items from JSON |
| `POST` | `/api/datasets/{id}/approve` | Approve dataset for experiments |
| `POST` | `/api/experiments` | Create an experiment |
| `PUT` | `/api/experiments/{id}/grid` | Configure grid search parameters |
| `POST` | `/api/experiments/{id}/run` | Start experiment execution |
| `GET` | `/api/experiments/{id}/report` | Get results report |
| `GET` | `/api/vectorstores` | List supported vector stores |

---

## Project Structure

```
rag-optimization-pipeline/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers
│   │   │   ├── documents.py        # Document upload & management
│   │   │   ├── datasets.py         # Dataset CRUD, generation, import
│   │   │   ├── experiments.py      # Experiment CRUD, grid config, run
│   │   │   └── vectorstores.py     # Vector store listing & config
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings (env vars)
│   │   │   └── database.py         # SQLAlchemy engine & session
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── document.py
│   │   │   ├── dataset.py
│   │   │   └── experiment.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── document.py
│   │   │   ├── dataset.py
│   │   │   └── experiment.py
│   │   ├── services/               # Business logic
│   │   │   ├── document_loader.py  # LangChain document loaders
│   │   │   ├── dataset_generator.py # LLM-powered Q&A generation
│   │   │   ├── grid_search_proposer.py # LLM grid search proposal
│   │   │   ├── rag_pipeline.py     # RAG pipeline execution
│   │   │   ├── ragas_evaluator.py  # RAGAS metric evaluation
│   │   │   ├── experiment_runner.py # Orchestrates experiment runs
│   │   │   └── vectorstore_factory.py # Vector store factory pattern
│   │   └── main.py                 # FastAPI application entry point
│   ├── requirements.txt
│   ├── .env.example
│   └── .gitignore
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # Root layout with dark theme
│   │   │   ├── page.tsx            # Main pipeline dashboard
│   │   │   └── globals.css         # Tailwind + custom styles
│   │   ├── components/
│   │   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   │   ├── PipelineHeader.tsx  # Step indicator header
│   │   │   └── steps/
│   │   │       ├── StepUpload.tsx      # Step 1: Document upload
│   │   │       ├── StepDataset.tsx     # Step 2: Dataset generation
│   │   │       ├── StepReview.tsx      # Step 3: HITL review
│   │   │       ├── StepGridSearch.tsx  # Step 4: Grid search config
│   │   │       ├── StepExecution.tsx   # Step 5: Experiment runner
│   │   │       └── StepResults.tsx     # Step 6: Results dashboard
│   │   └── lib/
│   │       ├── api.ts              # API client functions
│   │       └── utils.ts            # Utility helpers
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   └── postcss.config.mjs
├── Makefile                        # Development & build commands
├── CLAUDE.md                       # AI assistant instructions
└── README.md                       # This file
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make atomic, descriptive commits
4. Ensure all linters pass: `make lint`
5. Open a Pull Request with a clear description

### Conventions

- All PRs and documentation in **English**
- Backend follows **FastAPI** patterns with **Pydantic** schemas
- Frontend uses **Next.js App Router** with client components
- Commits should be atomic and use conventional commit prefixes (`feat:`, `fix:`, `chore:`, etc.)

---

## License

MIT
