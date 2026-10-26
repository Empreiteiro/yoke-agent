import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine, Base
from app.api import documents, datasets, experiments, vectorstores, providers, token_usage, collections, auth, mcp_config, chat
from app.api import agent_configs, agent_experiments
from app.api import users, traces
from app.api import decision
from app.models import saved_collection  # noqa: F401 — ensure table creation
from app.models import vectorstore_config  # noqa: F401 — ensure table creation
from app.models import api_key  # noqa: F401 — ensure table creation
from app.models import agent  # noqa: F401 — ensure agent pipeline tables
from app.models import user  # noqa: F401 — ensure users / audit_logs tables
from app.models import trace  # noqa: F401 — ensure traces / trace_spans tables
from app.models import decision as decision_models  # noqa: F401 — ensure model comparison tables
from app.core.auth import ApiKeyAuthMiddleware
from app.middleware.tracing import TracingMiddleware

logger = logging.getLogger(__name__)


def _run_migrations(engine):
    """Add missing columns to existing tables."""
    inspector = inspect(engine)
    migrations = [
        ("datasets", "error_message", "TEXT"),
        ("experiment_combinations", "error_message", "TEXT"),
        ("experiment_combinations", "total_tokens", "INTEGER DEFAULT 0"),
        ("experiment_combinations", "total_cost", "REAL DEFAULT 0.0"),
        # Latency metrics (issue #112)
        ("experiment_combinations", "avg_latency_ms", "REAL"),
        ("experiment_combinations", "p95_latency_ms", "REAL"),
        ("experiment_combinations", "avg_retrieval_ms", "REAL"),
        ("experiment_combinations", "avg_generation_ms", "REAL"),
        # Failure categorization (issue #117)
        ("experiment_combinations", "failure_summary", "TEXT"),
        # Custom metrics (issue #124)
        ("experiment_combinations", "custom_metrics", "TEXT"),
        # Multi-tenancy user ownership (issue #123)
        ("datasets", "user_id", "INTEGER"),
        ("experiments", "user_id", "INTEGER"),
        ("documents", "user_id", "INTEGER"),
        ("agent_experiments", "user_id", "INTEGER"),
        ("api_keys", "user_id", "INTEGER"),
        ("datasets", "is_benchmark", "INTEGER DEFAULT 0"),
        # Agent pipeline: scenarios refactor (input_message → objective)
        ("scenarios", "objective", "TEXT"),
        ("scenarios", "input_hint", "TEXT"),
        ("scenarios", "context", "TEXT"),
        # Agent pipeline: interaction dataset items refactor
        ("interaction_dataset_items", "objective", "TEXT"),
        ("interaction_dataset_items", "generated_input", "TEXT"),
        # External HTTP agents (issue #169)
        ("agent_configs", "agent_type", "VARCHAR(20) DEFAULT 'builtin'"),
        ("agent_configs", "http_endpoint", "VARCHAR(1024)"),
        ("agent_configs", "http_auth_header", "VARCHAR(1024)"),
        ("agent_configs", "http_timeout_seconds", "INTEGER DEFAULT 60"),
        # HTTP agent request/response templating
        ("agent_configs", "http_body_template", "TEXT"),
        ("agent_configs", "http_response_path", "VARCHAR(255)"),
        ("agent_configs", "http_tool_calls_path", "VARCHAR(255)"),
        # Decision-model providers (TypeSafe Jev / System One)
        ("providers", "supports_decision", "BOOLEAN DEFAULT FALSE"),
        ("providers", "decision_models", "JSON"),
        ("providers", "default_decision_model", "VARCHAR(100)"),
        # Model Comparison: guardrail benchmark metrics, variants, infra cost
        ("decision_model_results", "infra_cost_per_hour", "REAL"),
        ("decision_model_results", "config", "JSON"),
        ("decision_model_results", "variant", "VARCHAR(100)"),
        ("decision_model_results", "policy_hash", "VARCHAR(16)"),
        ("decision_model_results", "token_cost", "REAL"),
        ("decision_model_results", "infra_cost", "REAL"),
        ("decision_model_results", "p90_latency_ms", "REAL"),
        ("decision_model_results", "p99_latency_ms", "REAL"),
        ("decision_model_results", "latency_std_ms", "REAL"),
        ("decision_model_results", "avg_attempts", "REAL"),
        ("decision_model_results", "retried", "INTEGER DEFAULT 0"),
        ("decision_predictions", "probabilities", "JSON"),
        ("decision_predictions", "attempts", "INTEGER"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            if table in inspector.get_table_names():
                existing = [c["name"] for c in inspector.get_columns(table)]
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                    conn.commit()
                    logger.info(f"Added column {table}.{column}")

        # Backfill decision-model columns on providers created before they existed
        if "providers" in inspector.get_table_names():
            conn.execute(text("UPDATE providers SET decision_models = '[]' WHERE decision_models IS NULL"))
            conn.execute(text("UPDATE providers SET supports_decision = FALSE WHERE supports_decision IS NULL"))
            conn.commit()

        # Data migration: copy input_message → objective for existing scenarios
        if "scenarios" in inspector.get_table_names():
            existing = [c["name"] for c in inspector.get_columns("scenarios")]
            if "objective" in existing and "input_message" in existing:
                conn.execute(text(
                    "UPDATE scenarios SET objective = input_message WHERE objective IS NULL AND input_message IS NOT NULL"
                ))
                conn.commit()
        # Data migration: copy input_message → objective for existing interaction_dataset_items
        if "interaction_dataset_items" in inspector.get_table_names():
            existing = [c["name"] for c in inspector.get_columns("interaction_dataset_items")]
            if "objective" in existing and "input_message" in existing:
                conn.execute(text(
                    "UPDATE interaction_dataset_items SET objective = input_message WHERE objective IS NULL AND input_message IS NOT NULL"
                ))
                conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    # Seed built-in benchmark datasets
    from app.api.datasets import seed_benchmarks
    from app.core.database import SessionLocal
    from app.services.decision_datasets import seed_builtin_datasets
    from app.services.decision_comparison import recover_interrupted
    db = SessionLocal()
    try:
        seed_benchmarks(db)
        seed_builtin_datasets(db)
        recover_interrupted(db)
        # Seed default admin account if configured and no users exist yet
        _seed_default_admin(db)
    finally:
        db.close()
    yield


def _seed_default_admin(db):
    """Create the default admin user from env vars on first startup."""
    email = settings.default_admin_email
    password = settings.default_admin_password
    if not email or not password:
        return
    from app.models.user import User, ROLE_ADMIN
    from app.core.security import hash_password
    existing = db.query(User).first()
    if existing:
        return  # users already exist — don't overwrite
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=ROLE_ADMIN,
    )
    db.add(user)
    db.commit()
    logger.info(f"Created default admin user: {email}")


app = FastAPI(
    title="Yoke Agent",
    description="AI Quality Studio — mistake-proof your RAG pipelines and AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ApiKeyAuthMiddleware)
app.add_middleware(TracingMiddleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(mcp_config.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(vectorstores.router, prefix="/api/vectorstores", tags=["vectorstores"])
app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
app.include_router(token_usage.router, prefix="/api/token-usage", tags=["token-usage"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(agent_configs.router, prefix="/api/agent/configs", tags=["agent-configs"])
app.include_router(agent_experiments.router, prefix="/api/agent", tags=["agent-experiments"])
app.include_router(traces.router, prefix="/api/traces", tags=["traces"])
app.include_router(decision.router, prefix="/api/decision", tags=["model-comparison"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
