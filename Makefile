.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
       build start stop clean lint lint-backend lint-frontend test test-backend \
       db-reset docker-up docker-down setup check-deps \
       sync-cli-client cli-install cli-uninstall

# --- Configuration ---
BACKEND_DIR   = backend
FRONTEND_DIR  = frontend
PYTHON        = python3
NPM           = npm
UVICORN_PORT  = 4040
FRONTEND_PORT = 4000
VENV_DIR      = $(BACKEND_DIR)/.venv
VENV_PIP      = $(VENV_DIR)/bin/pip
VENV_PYTHON   = $(VENV_DIR)/bin/python
VENV_UVICORN  = $(VENV_DIR)/bin/uvicorn
UV            = $(shell command -v uv 2>/dev/null)
PIP_INSTALL   = $(if $(UV),$(UV) pip install --python $(VENV_PYTHON),$(VENV_PIP) install)

# Colors
CYAN  = \033[36m
GREEN = \033[32m
YELLOW = \033[33m
RESET = \033[0m

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)RAG Optimization Pipeline$(RESET)"
	@echo "========================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# --- Setup & Install ---

setup: ## First-time setup: create venv, install all deps, copy .env
	@echo "$(CYAN)Setting up project...$(RESET)"
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP_INSTALL) --upgrade pip
	$(PIP_INSTALL) -r $(BACKEND_DIR)/requirements.txt
	cd $(FRONTEND_DIR) && $(NPM) install
	@if [ ! -f $(BACKEND_DIR)/.env ]; then \
		cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env; \
		echo "$(GREEN)Created $(BACKEND_DIR)/.env from .env.example$(RESET)"; \
		echo "$(YELLOW)>>> Edit $(BACKEND_DIR)/.env and add your OPENAI_API_KEY$(RESET)"; \
	fi
	@echo ""
	@echo "$(GREEN)Setup complete! Run 'make dev' to start developing.$(RESET)"

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend Python dependencies (uses venv)
	@echo "$(CYAN)Installing backend dependencies...$(RESET)"
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)Virtual environment not found. Creating...$(RESET)"; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	$(PIP_INSTALL) --upgrade pip
	$(PIP_INSTALL) -r $(BACKEND_DIR)/requirements.txt

install-frontend: ## Install frontend Node.js dependencies
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) install

# --- Dependency Check ---

check-deps: ## Verify and install all backend dependencies
	@echo "$(CYAN)Checking backend dependencies...$(RESET)"
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)No virtual environment found. Run 'make setup' first.$(RESET)"; \
		exit 1; \
	fi
	@$(PIP_INSTALL) --quiet -r $(BACKEND_DIR)/requirements.txt
	@echo "$(GREEN)All dependencies OK.$(RESET)"

# --- Development ---

dev: check-deps ## Start both backend and frontend in development mode
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)No virtual environment found. Running 'make setup' first...$(RESET)"; \
		$(MAKE) setup; \
	fi
	@# Kill any stale processes on our ports
	@-lsof -ti:$(UVICORN_PORT) | xargs kill -9 2>/dev/null || true
	@-lsof -ti:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null || true
	@echo ""
	@echo "$(CYAN)Starting development servers...$(RESET)"
	@echo "  Backend  -> http://localhost:$(UVICORN_PORT)"
	@echo "  Frontend -> http://localhost:$(FRONTEND_PORT)"
	@echo ""
	@$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

dev-backend: ## Start backend dev server with hot reload
	cd $(BACKEND_DIR) && ../$(VENV_UVICORN) app.main:app --reload --port $(UVICORN_PORT) --loop asyncio

dev-frontend: ## Start frontend dev server
	cd $(FRONTEND_DIR) && $(NPM) run dev

# --- Production ---

build: ## Build frontend for production
	@echo "$(CYAN)Building frontend...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) run build

start: ## Start both servers in production mode
	@echo "$(CYAN)Starting production servers...$(RESET)"
	@$(MAKE) start-backend & $(MAKE) start-frontend & wait

start-backend: ## Start backend in production mode
	cd $(BACKEND_DIR) && ../$(VENV_UVICORN) app.main:app --host 0.0.0.0 --port $(UVICORN_PORT) --workers 4 --loop asyncio

start-frontend: ## Start frontend in production mode
	cd $(FRONTEND_DIR) && $(NPM) run start

# --- Quality ---

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend Python code
	@echo "$(CYAN)Linting backend...$(RESET)"
	cd $(BACKEND_DIR) && ../$(VENV_PYTHON) -m ruff check . || true

lint-frontend: ## Lint frontend TypeScript code
	@echo "$(CYAN)Linting frontend...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) run lint

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	@echo "$(CYAN)Running backend tests...$(RESET)"
	cd $(BACKEND_DIR) && ../$(VENV_PYTHON) -m pytest -v || true

# --- Database ---

db-reset: ## Reset the local SQLite database (no-op when DATABASE_URL points at Postgres)
	@DB_URL=$$(grep -E '^DATABASE_URL=' $(BACKEND_DIR)/.env 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'); \
	if [ -n "$$DB_URL" ] && ! echo "$$DB_URL" | grep -q '^sqlite:'; then \
		echo "$(YELLOW)DATABASE_URL=$$DB_URL is not SQLite — drop/recreate your Postgres DB manually.$(RESET)"; \
	else \
		echo "$(CYAN)Resetting database...$(RESET)"; \
		rm -f $(BACKEND_DIR)/rag_pipeline.db; \
		echo "$(GREEN)Database reset. It will be recreated on next server start.$(RESET)"; \
	fi

# --- Cleanup ---

clean: ## Remove all generated files (node_modules, venv, db, uploads, .next)
	@echo "$(CYAN)Cleaning up...$(RESET)"
	rm -rf $(FRONTEND_DIR)/node_modules
	rm -rf $(FRONTEND_DIR)/.next
	rm -rf $(BACKEND_DIR)/.venv
	rm -rf $(BACKEND_DIR)/__pycache__
	rm -rf $(BACKEND_DIR)/uploads
	rm -f  $(BACKEND_DIR)/rag_pipeline.db
	find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean!$(RESET)"

# --- Docker (future) ---

docker-up: ## Start services with Docker Compose
	@echo "$(CYAN)Starting Docker containers...$(RESET)"
	docker compose up --build -d
	@echo ""
	@echo "$(GREEN)Services running:$(RESET)"
	@echo "  Backend  -> http://localhost:4040"
	@echo "  Frontend -> http://localhost:4000"

docker-down: ## Stop Docker Compose services
	docker compose down

docker-logs: ## View Docker container logs
	docker compose logs -f

DOCKER_USER = empreiteiro
DOCKER_BACKEND = $(DOCKER_USER)/rag-studio-backend
DOCKER_FRONTEND = $(DOCKER_USER)/rag-studio-frontend
DOCKER_TAG ?= latest

docker-publish: ## Build and push images to Docker Hub (DOCKER_TAG=v0.1.0)
	@echo "$(CYAN)Building and pushing Docker images...$(RESET)"
	docker build -t $(DOCKER_BACKEND):$(DOCKER_TAG) -t $(DOCKER_BACKEND):latest ./backend
	docker build -t $(DOCKER_FRONTEND):$(DOCKER_TAG) -t $(DOCKER_FRONTEND):latest ./frontend
	docker push $(DOCKER_BACKEND):$(DOCKER_TAG)
	docker push $(DOCKER_BACKEND):latest
	docker push $(DOCKER_FRONTEND):$(DOCKER_TAG)
	docker push $(DOCKER_FRONTEND):latest
	@echo "$(GREEN)Published:$(RESET)"
	@echo "  $(DOCKER_BACKEND):$(DOCKER_TAG)"
	@echo "  $(DOCKER_FRONTEND):$(DOCKER_TAG)"

# --- CLI ---

CLI_DIR             = cli
CANONICAL_CLIENT    = $(BACKEND_DIR)/yoke_client.py
VENDORED_CLIENT     = $(CLI_DIR)/yoke_cli/client.py

sync-cli-client: ## Regenerate cli/yoke_cli/client.py from backend/yoke_client.py
	@$(PYTHON) $(CLI_DIR)/scripts/sync_client.py

cli-install: ## Install the yoke CLI locally via pipx (editable)
	@echo "$(CYAN)Installing yoke-cli via pipx...$(RESET)"
	pipx install --force --editable ./$(CLI_DIR)
	@echo "$(GREEN)✓ Installed. Run 'yoke --help' to get started.$(RESET)"

cli-uninstall: ## Uninstall the yoke CLI from pipx
	pipx uninstall yoke-cli
