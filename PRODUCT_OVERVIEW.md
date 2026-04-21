# Yoke Agent — Product Overview

> **Source document for the marketing website.** Covers positioning, features, advantages, and honest limitations, written in a tone suitable for landing-page copy, product pages, and sales collateral.

---

## 1. What is Yoke Agent?

**Yoke Agent is an AI Quality Studio.** It turns the guesswork of "is this prompt / chunk size / retrieval strategy / agent configuration actually good?" into a reproducible, measurable, grid-search workflow — so you only ever ship the configuration that objectively won.

The name comes from **Poka-Yoke** (ポカヨケ), the Japanese manufacturing principle coined by Shigeo Shingo at Toyota meaning "mistake-proofing". In a factory, a poka-yoke is a jig that physically prevents a defective part from leaving the line. Yoke Agent is that jig, applied to AI systems: it makes it impossible to ship a worse configuration than the one you measured.

It does this through two complementary workbenches on a single dashboard:

- **RAG Workbench** — Document ingestion → LLM-generated evaluation dataset → grid-search over chunking, embeddings, retrieval strategies, and rerankers → RAGAS scoring → improvement report.
- **Agent Workbench** — Agent definition (prompt, tools, MCP servers) → persona + scenario library → parallel simulations → G-Eval LLM-as-judge scoring → ranked leaderboard.

### Who it's for

| Audience | What they get |
|---|---|
| **AI / ML engineers** | A systematic way to tune RAG pipelines and agents instead of vibe-checking prompts in a notebook. |
| **Applied scientists** | Reproducible experiments with full token/cost tracking and per-transcript drill-down. |
| **Product teams shipping LLM features** | Confidence that the version going to production is the one that scored best on faithfulness, tool-use accuracy, and guardrails. |
| **Solo developers / indie hackers** | A local, self-hosted studio that works against Ollama, Claude Code CLI, or any OpenAI-compatible endpoint. |

### The core promise

> *Don't ship what you hope works. Ship what you measured.*

---

## 2. Main Features

### 2.1 Platform

- **AI Chat Assistant** — A streaming chat with your default provider is the first sidebar entry, so you can ask the platform how to use itself.
- **Multi-Provider Support** — OpenAI, Anthropic, Google Gemini, Cohere, Ollama, Azure OpenAI, HuggingFace, Claude Code CLI, and any OpenAI-compatible custom endpoint (LM Studio, vLLM, etc.). Keys are stored in the backend database, never exposed to the frontend, and multiple providers can run side-by-side.
- **Flex Service Tier** — Opt-in ~50% discount for OpenAI (`o3`, `o4-mini`, `gpt-4.1` family) and Google Gemini (`gemini-2.5-*`, `gemini-3.x` preview), toggled per-provider.
- **Token & Cost Tracking** — Every LLM and embedding call is logged with estimated USD cost, including automatic flex-tier discount detection.
- **OpenTelemetry tracing** — Production-grade observability via OTLP export.
- **Multi-tenancy & Authentication** — Workspace isolation with first-class auth.
- **Dark-theme, step-based dashboard** — Responsive UI designed around a guided pipeline, not a blank canvas.

### 2.2 RAG Workbench

- **Document upload** — PDF, DOCX, TXT, Markdown; ingested via LangChain loaders.
- **LLM-powered dataset generation** — Generates evaluation Q&A pairs directly from your documents. Supports JSON import for curated test sets.
- **Human-in-the-Loop review** — Edit, add, remove, and reorder questions before locking the dataset.
- **Smart Grid Search Proposer** — An LLM inspects your collection and scenario, then proposes an initial sweep. You keep final control.
- **Advanced retrieval strategies** — Multi-Query RAG, Agentic RAG, HyDE, Corrective RAG (CRAG), Self-RAG, RAPTOR, and GraphRAG, all wired into the grid-search engine.
- **Multiple vector stores** — ChromaDB (default), Pinecone, Qdrant, pgvector, Astra DB.
- **Rerankers** — Pluggable reranking stage in the pipeline.
- **RAGAS evaluation** — Faithfulness, Answer Relevancy, Context Precision, Context Recall, plus optional Answer Correctness, Similarity, Entity Recall, and Noise Sensitivity.
- **Custom evaluation metrics** — Define your own metrics via a hook, in addition to RAGAS defaults.
- **Failure categorization & error analysis** — Fine-grained breakdown of *why* a run failed, not just that it did.
- **LLM-generated Improvement Report** — Plain-language recommendation on which configuration to ship and why.

### 2.3 Agent Workbench

- **Agent Definition** — System prompts, tools (native + MCP servers), and guardrails.
- **Persona Library** — Synthetic users with distinct communication styles and goals to stress-test agent behavior.
- **Scenario Library** — Four scenario types, each with its own rubric: `tool_use`, `decision_path`, `response_quality`, `guardrail`.
- **Simulation Engine** — Runs conversations in parallel against every grid combination, capturing full transcripts and tool invocations.
- **G-Eval LLM-as-Judge** — Scores transcripts on 14 rubric metrics (tool call accuracy, argument correctness, goal completion, path optimality, faithfulness, coherence, constraint adherence, hallucination, refusal accuracy, and more) plus cross-cutting metrics (instruction following, persona satisfaction).
- **Deterministic overrides** — Tool selection is scored from parsed `TOOL_CALL` invocations, not guessed from prose, so `tool_call_accuracy` is always objective.
- **Results Dashboard** — All-metrics leaderboard table, collapsible LLM-generated improvement report, and per-transcript drill-down.

### 2.4 Developer surface

- **REST API** — Fully documented at `/docs` (Swagger) and `/redoc`.
- **Python / FastAPI backend** + **Next.js 14 frontend** — Familiar stack, easy to extend.
- **MCP support** — Both exposing and consuming MCP servers via `fastmcp`.
- **CLI tooling** — `yoke-agent/cli` for scripted workflows.
- **Docker Compose** — One-command local bring-up.

---

## 3. Advantages

### 3.1 Scientific, not anecdotal
Every configuration claim is backed by a reproducible grid search and a numeric score. You stop arguing about which prompt "feels better" and start comparing `0.87` against `0.82`.

### 3.2 Two disciplines, one studio
RAG tuning and agent evaluation normally live in separate tools (or separate notebooks on separate laptops). Yoke Agent unifies them, with shared providers, shared cost tracking, and a shared improvement-report format.

### 3.3 Provider-agnostic by design
Nine provider types supported out of the box, including fully local options (Ollama, LM Studio via custom endpoint) and CLI-based options (Claude Code) that need no API key. Switch providers per experiment to benchmark models objectively.

### 3.4 Built-in cost governance
Token + cost tracking is not a bolt-on — it is the default code path. Flex-tier detection means you automatically get the ~50% discount logged when the provider returns it, with no manual bookkeeping.

### 3.5 State-of-the-art retrieval, not just naive RAG
Seven advanced strategies (HyDE, CRAG, Self-RAG, RAPTOR, GraphRAG, Multi-Query, Agentic) ship built in and are first-class grid-search axes. Most competitors stop at "chunk size and top-k".

### 3.6 Human-in-the-loop where it matters
LLMs propose (datasets, grids, reports) — humans approve. The philosophy is "LLM as a fast junior analyst", not "LLM as an unchecked oracle".

### 3.7 Objective tool-use scoring
Agent tool calls are parsed deterministically from `TOOL_CALL` invocations in the transcript, so accuracy scoring never depends on a judge LLM's interpretation of prose. This is a real differentiator vs. pure LLM-as-judge setups.

### 3.8 Self-hosted, no data egress
Your documents, questions, and transcripts stay on your infrastructure. Only the LLM calls themselves leave, to providers you explicitly configure.

### 3.9 Production observability
OpenTelemetry + OTLP export means runs can be piped into existing observability stacks (Grafana, Honeycomb, Datadog) without custom glue.

### 3.10 Open-source and extensible
MIT-licensed, Pydantic schemas, clean FastAPI routers, pluggable retrievers, custom-metrics hook. The code is meant to be read and forked.

---

## 4. Disadvantages & Honest Limitations

A product page without trade-offs is marketing, not a product page. These are the real constraints.

### 4.1 Self-hosted only
There is no managed cloud offering. Teams that want a "sign up and start evaluating" experience will need to run it themselves (Docker Compose or `make dev`). No SaaS plan, no SSO-integrated hosted tier, no hands-off upgrades.

### 4.2 SQLite is the default storage
Great for local development and solo users; not the right choice for large teams with concurrent writers, high-volume experiments, or strict backup requirements. Moving to Postgres is supported by the SQLAlchemy layer but is a deliberate operational step, not a toggle.

### 4.3 Evaluation quality is bounded by the judge LLM
Both RAGAS metrics and G-Eval rubrics rely on an LLM-as-judge. Known consequences:
- Judge bias can leak into scores (favoring verbose answers, or the judge's own provider's style).
- Cheap judges produce noisier scores; strong judges (GPT-5, Opus, Gemini 3) cost real money.
- Relative rankings across a grid are generally trustworthy; absolute scores are not a ground truth.
The deterministic `tool_call_accuracy` override mitigates this for agent tool use, but most other metrics remain judge-dependent.

### 4.4 Grid-search cost can scale aggressively
A 4×3×4×3 grid is 144 runs; with 20 evaluation questions that is 2,880 LLM calls *before* counting the judge. Flex-tier pricing and cost tracking help, but users are responsible for scoping their own sweeps. The platform does not enforce a spending cap by default.

### 4.5 Stack requirements
Python 3.11+ and Node.js 18+ are hard requirements. Python 3.13 compatibility is recent; older enterprise environments stuck on 3.9/3.10 cannot run it as-is.

### 4.6 UI is dark-theme only
Light-mode users and accessibility contexts that require high-contrast light themes are not served out of the box.

### 4.7 Vector-store breadth means setup complexity
Five vector-store options sounds great until you have to pick one. ChromaDB is the sensible default, but to use Pinecone / Qdrant / pgvector / Astra at scale you own the provisioning, indexing, and operational cost.

### 4.8 GraphRAG and RAPTOR are heavy
These strategies are powerful but computationally expensive on large corpora (clustering, summary-tree construction). Expect long first-run indexing times and significant memory on mid-sized datasets.

### 4.9 Agent simulations are synthetic
Personas are LLM-driven synthetic users, not real ones. They surface a lot of real-world failure modes — but they do not replace actual user testing, and they can under-represent the long tail of human oddness.

### 4.10 Young project, fast-moving surface
The README, features, and migration paths change between releases (recent additions: multi-tenancy, OTel tracing, custom metrics, failure categorization). Teams that need API stability guarantees should pin versions and read release notes before upgrading.

---

## 5. At a glance

| Dimension | Yoke Agent |
|---|---|
| **Category** | AI Quality Studio (RAG + Agent evaluation) |
| **License** | Open source (see `LICENSE`) |
| **Deployment** | Self-hosted (Docker Compose or `make dev`) |
| **Backend** | Python 3.11+ · FastAPI · SQLAlchemy · Pydantic v2 |
| **Frontend** | Next.js 14 · React 18 · TypeScript · Tailwind |
| **Default storage** | SQLite (Postgres supported via `DATABASE_URL`) |
| **Providers** | OpenAI · Anthropic · Google Gemini · Cohere · Azure OpenAI · Ollama · HuggingFace · Claude Code CLI · Custom OpenAI-compatible |
| **Vector stores** | ChromaDB · Pinecone · Qdrant · pgvector · Astra DB |
| **RAG evaluation** | RAGAS (4 fixed + 4 optional metrics) + custom metrics hook |
| **Agent evaluation** | G-Eval rubrics (14 metrics) + deterministic tool-call parsing |
| **Observability** | OpenTelemetry / OTLP |
| **Multi-tenancy** | Yes, with auth |

---

## 6. Taglines (pick-list for website copy)

- *Mistake-proof your AI. Ship only the configuration that won.*
- *Grid-search your way to a RAG pipeline you can defend with numbers.*
- *Stop vibe-checking prompts. Start measuring agents.*
- *One studio, two workbenches, zero guesswork.*
- *Poka-Yoke for AI: the jig that makes shipping a worse config impossible.*

---

## 7. Where to go next

- **Installation:** see `README.md` → Quick Start
- **Contributing:** see `CONTRIBUTING.md`
- **API docs:** `http://localhost:4040/docs` after running `make dev`
- **Glossary (in-app):** Sidebar → Glossary, including the Poka-Yoke entry
