# Yoke Agent — AI Quality Studio

> *Poka-Yoke (ポカヨケ) — Japanese for "mistake-proofing", coined by Shigeo Shingo at Toyota. A jig or mechanism that makes it impossible to ship a worse configuration than the one you measured.*

**Yoke Agent** is an AI Quality Studio that applies the Poka-Yoke philosophy to modern AI systems. Instead of hoping you picked the right hyperparameters, prompts, retrieval strategy or agent design, Yoke Agent lets you grid-search every combination, evaluate them with reproducible metrics, and promote only the configuration that objectively wins.

It ships with three complementary workbenches on a single dashboard:

- **RAG Workbench** — Document ingestion → LLM-generated evaluation dataset → grid search over chunking, embeddings, retrieval strategies and rerankers → [RAGAS](https://docs.ragas.io/) scoring → improvement report.
- **Agent Workbench** — Agent definition (prompt, tools, MCP servers) → scenario library (tool use, decision paths, response quality, guardrails) → persona-driven simulation → G-Eval LLM-as-judge scoring → ranked leaderboard.
- **Model Comparison** — Labeled classification dataset (7 built-in sets of 1,200 rows, or your own upload) → the same sample through decision models (TypeSafe Jev and other System One endpoints) and LLM classifiers → accuracy, errors and total cost per model.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Pipeline Steps](#pipeline-steps)
- [Providers](#providers)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [RAG Hyperparameters](#rag-hyperparameters)
- [Advanced Retrieval Strategies](#advanced-retrieval-strategies)
- [RAGAS Metrics](#ragas-metrics)
- [Agent Evaluation Metrics](#agent-evaluation-metrics)
- [Model Comparison: Decision Models vs LLMs](#model-comparison-decision-models-vs-llms)
- [Cost Tracking & Flex Tier](#cost-tracking--flex-tier)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Contributing](CONTRIBUTING.md)

---

## Features

### Core platform
- **AI Chat Assistant** — Streaming chat with the default provider as the first sidebar entry, so you can ask the platform how to use itself.
- **Multi-Provider Support** — OpenAI, Anthropic, Google Gemini, Cohere, Ollama, Azure OpenAI, HuggingFace, Claude Code CLI, and OpenAI-compatible custom endpoints. Configured entirely from the Settings → Providers UI.
- **Flex Service Tier** — Opt-in ~50% discount for OpenAI (`o3`, `o4-mini`, `gpt-4.1` family) and Google Gemini (`gemini-2.5-*`, `gemini-3.x` preview) via the `service_tier=flex` parameter. Toggle per-provider in Settings.
- **Token & Cost Tracking** — Every LLM and embedding call is logged with estimated cost, including automatic flex-tier discount detection from response metadata.
- **Dark-theme UI** — Responsive, step-based dashboard with sidebar navigation.

### RAG workbench
- **Document Upload** — PDF, DOCX, TXT, Markdown; processed via LangChain loaders.
- **LLM-Powered Dataset Generation** — Generates evaluation Q&A pairs from your documents and supports JSON import of curated test sets.
- **Human-in-the-Loop Review** — Edit, add, remove, and reorder questions before locking the dataset.
- **Smart Grid Search Proposer** — An LLM inspects your collection and scenario and proposes an initial sweep; you stay in control of the final grid.
- **Advanced Retrieval Strategies** — Multi-Query RAG, Agentic RAG, HyDE, Corrective RAG (CRAG), Self-RAG, RAPTOR, and GraphRAG, all wired into the grid-search engine.
- **Multiple Vector Stores** — ChromaDB (default), Pinecone, Qdrant, pgvector, Astra DB.
- **RAGAS Evaluation** — Faithfulness, Answer Relevancy, Context Precision, Context Recall, plus optional Answer Correctness, Similarity, Entity Recall, and Noise Sensitivity.
- **Improvement Report** — LLM-generated recommendations on which configuration to ship and why.

### Agent workbench
- **Agent Definition** — Define system prompts, tools (native + MCP servers), and guardrails.
- **Persona Library** — Synthetic users with distinct communication styles and goals to stress-test agent behavior.
- **Scenario Library** — Four scenario types: `tool_use`, `decision_path`, `response_quality`, `guardrail`, each with its own rubric.
- **Simulation Engine** — Runs conversations in parallel against every grid combination, capturing full transcripts and tool invocations.
- **G-Eval LLM-as-Judge** — Scores transcripts on 14 rubric metrics (tool call accuracy, argument correctness, goal completion, path optimality, faithfulness, coherence, constraint adherence, hallucination, refusal accuracy, etc.) plus cross-cutting metrics (instruction following, persona satisfaction).
- **Deterministic Overrides** — Tool selection is scored from parsed `TOOL_CALL` invocations, not guessed from prose, so `tool_call_accuracy` is always objective.
- **Results Dashboard** — All Results table with every metric as a column, collapsible LLM-generated Improvement Report, and per-transcript drill-down.

### Model Comparison (decision models vs LLMs)
- **Decision-model providers** — TypeSafe's **Jev** (System One API) and any System One-compatible endpoint (gateways such as LiteLLM, or self-hosted open "Jev-style" models), configured in Settings → Providers next to your LLMs.
- **Built-in datasets** — Seven labeled sets of 1,200 rows each: Guardrails, Support Ticket Classification (English and pt-BR), Banking Intent Routing, Agent Tool Routing, Product Review Sentiment, and Email & SMS Threat Triage. Every set includes hard cases that borrow a neighbouring label's vocabulary.
- **Custom datasets** — Upload CSV, TSV, JSON or JSONL; columns are auto-detected (or picked in a preview), and label definitions can be edited before import.
- **Head-to-head runs** — Up to 8 models answer the same stratified sample with the same task question and label definitions, with live progress, stop and resume.
- **Results** — Total cost per model, accuracy with total / correct / errors (wrong label vs. no valid answer), error rate, cost share and cost per 1k rows, macro-F1, p50/p95 latency, per-label recall, confusion matrix, cost-vs-accuracy chart, a per-prediction explorer, and CSV export.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                          │
│                (Port 4000 → proxies /api/*)                   │
├───────────────────────────────────────────────────────────────┤
│                      FastAPI Backend                          │
│                        (Port 4040)                            │
├────────┬────────┬────────┬────────┬────────┬─────────────────┤
│ Chat   │ Docs   │Datasets│Experi- │ Agent  │ Providers /     │
│  /SSE  │        │        │ments   │Experi- │ Auth / Tokens   │
│        │        │        │        │ments   │                 │
├────────┴────────┴────────┴────────┴────────┴─────────────────┤
│                       Service Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │LangChain │ │  RAG     │ │  Agent   │ │  RAGAS / G-Eval  │ │
│  │Loaders   │ │Pipelines │ │Simulator │ │  Evaluators      │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ llm_factory (multi-provider) · token_tracker · MCP       ││
│  └──────────────────────────────────────────────────────────┘│
├───────────────────────────────────────────────────────────────┤
│         Vector Stores: Chroma / Pinecone / Qdrant / …         │
├───────────────────────────────────────────────────────────────┤
│                 SQLite (SQLAlchemy ORM)                       │
└───────────────────────────────────────────────────────────────┘
```

---

## Pipeline Steps

### RAG flow

| Step | Name | Description |
|------|------|-------------|
| 0 | **AI Chat** | Streaming assistant that explains the platform and helps you pick next steps. |
| 1 | **Upload Documents** | Upload PDF / DOCX / TXT / MD into a collection. |
| 2 | **Generate Dataset** | LLM reads the collection and proposes evaluation Q&A pairs. |
| 3 | **Review Dataset (HITL)** | Edit, add, delete, or import questions manually or via JSON. |
| 4 | **Configure Grid Search** | LLM proposes combinations; you refine any parameter. |
| 5 | **Run Experiments** | Every combination is executed and evaluated with RAGAS. |
| 6 | **View Results** | Interactive report with charts, rankings, and an LLM improvement report. |

### Agent flow

| Step | Name | Description |
|------|------|-------------|
| 1 | **Define Agent** | System prompt, tools, MCP servers, guardrails. |
| 2 | **Personas** | Synthetic user library with distinct styles and goals. |
| 3 | **Scenarios** | Test cases across `tool_use`, `decision_path`, `response_quality`, `guardrail`. |
| 4 | **Grid Search** | Sweep temperature, max turns, prompts, tool availability. |
| 5 | **Execution** | Parallel persona-vs-agent simulations with full transcript capture. |
| 6 | **Results** | All-metrics leaderboard, collapsible improvement report, per-transcript drill-down. |

---

## Providers

Configured from Settings → Providers. All credentials are stored in the backend database; the frontend never exposes API keys.

| Provider | LLM | Embeddings | Notes |
|----------|-----|------------|-------|
| **OpenAI** | ✓ | ✓ | Supports flex tier on `o3`, `o4-mini`, `gpt-4.1*`. |
| **Anthropic** | ✓ | — | Claude Opus/Sonnet/Haiku. |
| **Google (Gemini)** | ✓ | ✓ | Supports flex tier on `gemini-2.5-*` and `gemini-3.x` preview. |
| **Cohere** | ✓ | ✓ | Command-R family + embed-english/multilingual. |
| **Ollama** | ✓ | ✓ | Local models via `/api/tags` discovery. |
| **Azure OpenAI** | ✓ | ✓ | Deployment-based, with custom API version. |
| **HuggingFace** | ✓ | ✓ | Endpoint-hosted inference. |
| **Claude Code CLI** | ✓ | — | Subprocess-based; no API key needed. |
| **Custom** | ✓ | ✓ | Any OpenAI-compatible endpoint (LM Studio, vLLM, etc.). |
| **TypeSafe (Jev)** | decision | — | Decision model via the System One API (`/v1/systemone`). Input tokens only, $0.042 / 1M. |
| **System One-compatible** | decision | — | Any endpoint that speaks the System One API (gateway or self-hosted decision model). |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic v2 |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| **LLM Integration** | LangChain + native SDKs (openai, anthropic, google-genai ≥1.69.0, cohere, ollama, huggingface) |
| **Vector Stores** | ChromaDB (default), Pinecone, Qdrant, pgvector, Astra DB |
| **RAG Evaluation** | RAGAS |
| **Agent Evaluation** | Custom G-Eval rubrics + deterministic tool-call parsing |
| **MCP** | `fastmcp` for exposing/consuming MCP servers |
| **GraphRAG** | NetworkX + graspologic clustering |
| **Charts** | Recharts |
| **Icons** | Lucide React |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- At least one LLM provider (OpenAI key, or a local Ollama install, or Claude Code CLI authenticated, etc.)

### 1. Clone

```bash
git clone https://github.com/Empreiteiro/yoke-agent.git
cd yoke-agent
```

### 2. Start the dev servers

```bash
make dev
```

On the first run `make dev` prepares everything before starting: it creates `backend/.venv` (checking for Python 3.11+), installs the backend and frontend dependencies, and copies `backend/.env.example` to `backend/.env`. Later runs skip all of that and only reinstall when `backend/requirements.txt`, `frontend/package.json` or `frontend/package-lock.json` change. Use `make setup` to prepare the environment without starting the servers.

- **Backend**: http://localhost:4040 (hot reload, Swagger at `/docs`)
- **Frontend**: http://localhost:4000

Sign in with the default admin account from `backend/.env` (`DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`) and change it after the first login.

### 3. Configure a provider

Open http://localhost:4000 → Settings → Providers → **Add Provider**, pick a provider type, paste an API key (or configure local/CLI access), then Test. Once at least one provider is active you can start chatting, building collections, and running experiments.

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make dev` | Prepare the environment if needed, then start both servers for development |
| `make setup` | Prepare the environment (venv, deps, `.env`) without starting the servers |
| `make dev-backend` | Start only the backend |
| `make dev-frontend` | Start only the frontend |
| `make install` | Force a reinstall of all dependencies |
| `make build` | Build frontend for production |
| `make start` | Start both servers in production mode |
| `make lint` | Run linters (ruff + eslint) |
| `make test` | Run backend tests |
| `make db-reset` | Reset the local SQLite database (no-op when `DATABASE_URL` points at Postgres) |
| `make clean` | Remove all generated files |
| `make help` | Show all available commands |

---

## Configuration

Backend configuration lives in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./rag_pipeline.db` | SQLAlchemy database URL. Set to `postgresql://user:pass@host:5432/db` to use Postgres instead of SQLite. |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded files |
| `DEFAULT_VECTORSTORE` | `chromadb` | Default vector store provider |
| `CORS_ORIGINS` | `http://localhost:4000` | Allowed CORS origins |
| `BACKEND_URL` | `http://localhost:4040` | Used by the Next.js proxy rewrite |

Provider credentials (OpenAI, Anthropic, Google, etc.) are **not** env vars — they are stored in the DB via Settings → Providers, which lets you keep several providers side-by-side and switch between them per experiment.

Long-running endpoints (report generation, bulk evaluations) need more than the default 30 s Next.js dev-proxy timeout; `frontend/next.config.mjs` raises it to 5 minutes.

---

## RAG Hyperparameters

The grid search explores combinations of these parameters:

| Parameter | Description | Example Values |
|-----------|-------------|----------------|
| **Chunk Size** | Token/character count per chunk | `256`, `512`, `1024`, `2048` |
| **Chunk Overlap** | Overlap between consecutive chunks | `0%`, `10%`, `20%`, `30%` |
| **Chunking Strategy** | `recursive_character`, `token`, `semantic` | |
| **Embedding Model** | Model used for vector embeddings | `text-embedding-3-small`, `gemini-embedding-001`, HF / Cohere / Ollama models |
| **Embedding Dimensions** | For models that support Matryoshka truncation | `768`, `1536`, `3072` |
| **Top-K** | Documents retrieved per query | `3`, `5`, `10`, `20` |
| **Search Type** | `similarity`, `mmr`, `hybrid` (BM25 + vector) | |
| **Retrieval Strategy** | `standard`, `multi_query`, `agentic`, `hyde`, `crag`, `self_rag`, `raptor`, `graphrag` | |

An LLM proposes a starting grid based on your documents; you can add, remove or modify any axis before running.

---

## Advanced Retrieval Strategies

| Strategy | When to use |
|----------|-------------|
| **Multi-Query RAG** | Overcome vocabulary mismatch between questions and documents by retrieving with 3–5 LLM-generated paraphrases and fusing results via RRF. |
| **Agentic RAG** | Multi-hop questions where the agent should pick tools (`retrieve`, `retrieve_mmr`, `decompose_question`, `reformulate_query`, `evaluate_relevance`) dynamically. |
| **HyDE** | Complex queries where embedding a *hypothetical answer* recalls the right passages better than embedding the short question. |
| **Corrective RAG (CRAG)** | Self-correcting loop that grades relevance, reformulates, and retries until context is good enough. |
| **Self-RAG** | The LLM decides whether retrieval is needed at all, then grades docs and can switch to MMR for diversity. |
| **RAPTOR** | Documents with clear thematic hierarchy — builds a tree of clustered summaries at multiple abstraction levels. |
| **GraphRAG** | Knowledge-graph-style questions — extracts entities/relations, clusters with Leiden, and queries by community. |

---

## RAGAS Metrics

Each hyperparameter combination is evaluated with [RAGAS](https://docs.ragas.io/).

### Fixed metrics (always computed)

| Metric | Range | Description |
|--------|-------|-------------|
| **Faithfulness** | 0–1 | Factual consistency of the answer with retrieved context |
| **Answer Relevancy** | 0–1 | Relevance of the answer to the question |
| **Context Precision** | 0–1 | Signal-to-noise ratio of retrieved context |
| **Context Recall** | 0–1 | Fraction of the ground truth covered by retrieved context |

### Optional metrics (user-selectable)

| Metric | Range | Description |
|--------|-------|-------------|
| **Answer Correctness** | 0–1 | Factual accuracy vs ground truth |
| **Answer Similarity** | 0–1 | Semantic similarity to ground truth |
| **Context Entity Recall** | 0–1 | Entity coverage in retrieved context |
| **Noise Sensitivity** | 0–1 | Robustness to irrelevant context |

---

## Agent Evaluation Metrics

Transcripts are scored by an LLM-as-judge using per-scenario-type rubrics plus cross-cutting metrics. All metrics are 0–1.

| Scenario type | Metrics |
|---------------|---------|
| **tool_use** | `tool_call_accuracy` (deterministic override from parsed TOOL_CALLs), `argument_correctness` |
| **decision_path** | `goal_completion`, `path_optimality`, `step_efficiency` |
| **response_quality** | `answer_relevancy`, `faithfulness`, `coherence`, `conciseness` |
| **guardrail** | `constraint_adherence`, `hallucination_score`, `refusal_accuracy` |
| **Cross-cutting** | `instruction_following`, `persona_satisfaction` |

Aggregated results expose `{mean, median, std, min, max, count}` per metric, and an overall score is the mean of means across all metrics evaluated for each combination.

---

## Model Comparison: Decision Models vs LLMs

Decision models such as TypeSafe's Jev don't generate text. They receive a piece of **state** and a typed **question**, and return a choice with a calibrated probability for each option. Many production LLM calls are this kind of decision: routing a ticket, screening an input, classifying an intent, or picking a tool. The Model Comparison workbench measures whether a decision model can replace an LLM on *your* task, and at what cost.

**How a run works**

1. Pick a dataset and a sample (stratified by default, so the label mix is preserved).
2. Pick up to 8 models: decision models and/or LLMs from any configured provider.
3. Every model gets the **same task question and label definitions**:
   - Decision models receive them as a System One `choice` question:
     ```json
     {"model": "jev-latest", "state": "<row text>",
      "questions": {"decision": {"type": "choice", "instructions": "<task>",
                                 "criteria": {"<label>": "<definition>", "...": "..."}}}}
     ```
   - LLMs receive the same content as a prompt and must answer `{"label": "...", "confidence": ...}`. An answer that doesn't resolve to exactly one known label counts as **no answer**. The parser never guesses.
4. Predictions are stored per row, so you can drill into exactly where each model failed.

**Metrics per model**

| Metric | Meaning |
|---|---|
| Total / Correct / Errors | Rows evaluated; correct answers; errors split into *wrong label* and *no answer* (API error or an answer outside the label set) |
| Accuracy, Error rate | Correct ÷ total, Errors ÷ total |
| Macro-F1, per-label recall & precision | Class-balanced quality; where each model struggles |
| Total cost, Cost / 1k rows, Cost share, × cheapest | Measured tokens × price per 1M tokens (editable per run), and each model's share of the comparison's spend |
| Latency p50 / p95 | Per-request latency |

Prices come from the built-in table (`MODEL_PRICING`, flex-tier aware). Ollama and Claude Code are treated as free, and any other model with no known price can be priced per run in the UI (enter 0 for self-hosted). Spend is also logged to **History → Logs** under the `model_comparison` operation.

**Built-in datasets** (`backend/data/decision_datasets/`, seeded on startup)

| Dataset | Labels | Rows |
|---|---|---|
| Guardrails — Assistant Input Screening | safe, prompt_injection, jailbreak, pii_exposure, off_topic | 1,200 |
| Support Ticket Classification | billing, technical_issue, account_access, shipping_delivery, returns_refunds, product_inquiry, cancellation, feature_request | 1,200 |
| Classificação de Chamados de Suporte (pt-BR) | cobranca, problema_tecnico, acesso_conta, entrega, troca_devolucao, duvida_produto, cancelamento, sugestao | 1,200 |
| Banking Intent Routing | 10 retail-banking intents | 1,200 |
| Agent Tool Routing | web_search, calculator, calendar, send_email, weather, database_query, code_execution, no_tool | 1,200 |
| Product Review Sentiment | positive, negative, neutral, mixed | 1,200 |
| Email & SMS Threat Triage | legitimate, spam, phishing | 1,200 |

The datasets are synthetic and deterministic. All names, brands, domains and personal data are fictional, and about 20% of each set is tagged `hard`. To regenerate them after editing a spec in `backend/scripts/decision_dataset_specs/`, run:

```bash
cd backend && python scripts/generate_decision_datasets.py
```

**Custom datasets**: upload a file with a text column and a label column, for example:

```csv
text,label
"I was charged twice for my subscription this month.",billing
"The app crashes every time I open the reports page.",technical_issue
```

JSON exports from Yoke (`{"task", "labels": [{"name", "description"}], "items": [{"text", "label"}]}`) can be re-imported as-is. Label definitions matter: both decision models and LLMs are noticeably more accurate when each label has a one-line description.

---

## Cost Tracking & Flex Tier

Every LLM and embedding call goes through `app.services.token_tracker`, which:

- Records prompt/completion tokens, provider, model, experiment/combination IDs, and an estimated cost in USD.
- Knows current pricing for OpenAI (`gpt-4o*`, `gpt-4.1*`, `o3`, `o4-mini`), Anthropic (Opus/Sonnet/Haiku 3/4), Google Gemini (2.5 Pro/Flash, 2.0 Flash/Flash-Lite, 1.5 Pro/Flash, embeddings), and Cohere (Command-R, embed-*).
- Detects **flex-tier** responses from `response_metadata.service_tier` and applies a 50% discount automatically when logging cost.

Enabling flex is a single checkbox in Settings → Providers → (edit OpenAI or Google). It sets `extra_config.flex_tier = true` on the provider; `llm_factory` then:

- **OpenAI** → passes `model_kwargs={"service_tier": "flex"}` to `ChatOpenAI`.
- **Google** → uses `llm.bind(service_tier="flex")` because `ChatGoogleGenerativeAI.model_kwargs` is not forwarded; bound kwargs flow directly into `GenerateContentConfig(service_tier=...)`. Requires `google-genai >= 1.69.0`.

---

## API Reference

The backend exposes a RESTful API at `http://localhost:4040`. Interactive docs:

- **Swagger UI**: http://localhost:4040/docs
- **ReDoc**: http://localhost:4040/redoc

### Selected endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/stream` | Server-sent events chat with the default LLM |
| `GET` | `/api/providers/catalog` | Provider catalog (types, models, capabilities) |
| `POST` | `/api/providers/` | Create a provider |
| `POST` | `/api/providers/{id}/test` | Smoke-test LLM + embeddings |
| `POST` | `/api/collections/{id}/documents` | Upload documents into a collection |
| `POST` | `/api/datasets/{id}/generate` | Generate Q&A pairs with an LLM |
| `POST` | `/api/experiments/{id}/run` | Start a RAG experiment |
| `GET` | `/api/experiments/{id}/report` | RAG results + LLM improvement report |
| `POST` | `/api/agent-experiments/{id}/run` | Start an agent simulation experiment |
| `GET` | `/api/agent-experiments/{id}/results` | Agent leaderboard + per-transcript metrics |
| `GET` | `/api/token-usage/summary` | Aggregated spend by provider / model / experiment |
| `GET` | `/api/decision/datasets` | Built-in and custom comparison datasets |
| `POST` | `/api/decision/datasets/upload` | Upload a CSV / TSV / JSON / JSONL dataset (`dry_run=true` previews) |
| `GET` | `/api/decision/models` | Decision models + LLMs available for comparison, with default prices |
| `POST` | `/api/decision/comparisons/estimate` | Projected tokens and cost per model |
| `POST` | `/api/decision/comparisons` | Create and start a comparison |
| `GET` | `/api/decision/comparisons/{id}` | Leaderboard: accuracy, errors, cost, latency, per-label metrics |
| `GET` | `/api/decision/comparisons/{id}/predictions` | Per-row predictions (filter by model / outcome / label) |
| `GET` | `/api/decision/comparisons/{id}/export` | CSV with every model's prediction per row |

---

## Project Structure

```
yoke-agent/
├── backend/
│   ├── app/
│   │   ├── api/                        # FastAPI routers
│   │   │   ├── chat.py                 # Streaming chat assistant
│   │   │   ├── auth.py
│   │   │   ├── providers.py            # Provider catalog, CRUD, test, Claude Code status
│   │   │   ├── collections.py
│   │   │   ├── documents.py
│   │   │   ├── datasets.py
│   │   │   ├── experiments.py          # RAG experiments
│   │   │   ├── agent_configs.py
│   │   │   ├── agent_experiments.py    # Agent simulation experiments
│   │   │   ├── decision.py             # Model Comparison: datasets, comparisons, results
│   │   │   ├── mcp_config.py           # MCP server management
│   │   │   ├── token_usage.py
│   │   │   └── vectorstores.py
│   │   ├── core/                       # Settings, DB
│   │   ├── models/                     # SQLAlchemy ORM
│   │   ├── schemas/                    # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── llm_factory.py          # Multi-provider LLM/embedding factory
│   │   │   ├── token_tracker.py        # Token + cost logging, flex-tier aware
│   │   │   ├── claude_code_llm.py      # Claude Code CLI subprocess chat model
│   │   │   ├── document_loader.py
│   │   │   ├── dataset_generator.py
│   │   │   ├── grid_search_proposer.py
│   │   │   ├── rag_pipeline.py
│   │   │   ├── ragas_evaluator.py
│   │   │   ├── experiment_runner.py
│   │   │   ├── vectorstore_factory.py
│   │   │   ├── hyde_retriever.py
│   │   │   ├── corrective_retriever.py
│   │   │   ├── multi_query_retriever.py
│   │   │   ├── agentic_retriever.py
│   │   │   ├── raptor_indexer.py
│   │   │   ├── graphrag_pipeline.py
│   │   │   ├── agent_simulation_engine.py
│   │   │   ├── agent_generators.py
│   │   │   ├── agent_evaluator.py      # G-Eval LLM-as-judge
│   │   │   ├── agent_report_generator.py
│   │   │   ├── decision_models.py      # TypeSafe Jev / System One client
│   │   │   ├── llm_classifier.py       # LLM-as-classifier prompt + answer parser
│   │   │   ├── decision_comparison.py  # Comparison runner, sampling, metrics, pricing
│   │   │   └── decision_datasets.py    # Built-in seeding + upload parsing
│   │   └── main.py
│   ├── data/decision_datasets/         # 7 built-in comparison datasets (1,200 rows each)
│   ├── scripts/                        # Deterministic dataset generators
│   ├── tests/                          # pytest suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                # Pipeline dashboard
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Glossary.tsx            # Concepts & glossary (incl. Poka-Yoke)
│   │   │   ├── SettingsProviders.tsx   # Provider catalog UI + flex tier toggle
│   │   │   ├── Collections.tsx
│   │   │   ├── decision/               # Model Comparison: datasets, builder, results
│   │   │   └── steps/
│   │   │       ├── StepChat.tsx
│   │   │       ├── StepUpload.tsx
│   │   │       ├── StepDataset.tsx
│   │   │       ├── StepReview.tsx
│   │   │       ├── StepGridSearch.tsx
│   │   │       ├── StepExecution.tsx
│   │   │       ├── StepResults.tsx
│   │   │       ├── StepAgentDefine.tsx
│   │   │       ├── StepAgentPersonas.tsx
│   │   │       ├── StepAgentScenarios.tsx
│   │   │       ├── StepAgentGridSearch.tsx
│   │   │       ├── StepAgentExecution.tsx
│   │   │       └── StepAgentResults.tsx
│   │   └── lib/
│   │       ├── api.ts
│   │       └── utils.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.mjs
├── Makefile
├── CLAUDE.md
└── README.md
```
