.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
       build start stop clean lint lint-backend lint-frontend test test-backend \
       db-reset docker-up docker-down setup check-deps

# --- Configuration ---
BACKEND_DIR   = backend
FRONTEND_DIR  = frontend
PYTHON        = python3
NPM           = npm
UVICORN_PORT  = 7070
FRONTEND_PORT = 4000
VENV_DIR      = $(BACKEND_DIR)/.venv
VENV_PIP      = $(VENV_DIR)/bin/pip
VENV_PYTHON   = $(VENV_DIR)/bin/python
VENV_UVICORN  = $(VENV_DIR)/bin/uvicorn

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
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r $(BACKEND_DIR)/requirements.txt
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
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r $(BACKEND_DIR)/requirements.txt

install-frontend: ## Install frontend Node.js dependencies
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	cd $(FRONTEND_DIR) && $(NPM) install

# --- Dependency Check ---

check-deps: ## Verify all backend dependencies are installed
	@echo "$(CYAN)Checking backend dependencies...$(RESET)"
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)No virtual environment found. Run 'make setup' first.$(RESET)"; \
		exit 1; \
	fi
	@$(VENV_PIP) install --quiet --dry-run -r $(BACKEND_DIR)/requirements.txt 2>/dev/null || \
		( echo "$(YELLOW)Missing dependencies detected. Installing...$(RESET)" && \
		  $(VENV_PIP) install -r $(BACKEND_DIR)/requirements.txt )
	@echo "$(GREEN)All dependencies OK.$(RESET)"

# --- Development ---

dev: check-deps ## Start both backend and frontend in development mode
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(YELLOW)No virtual environment found. Running 'make setup' first...$(RESET)"; \
		$(MAKE) setup; \
	fi
	@echo ""
	@echo "$(CYAN)Starting development servers...$(RESET)"
	@echo "  Backend  -> http://localhost:$(UVICORN_PORT)"
	@echo "  Frontend -> http://localhost:$(FRONTEND_PORT)"
	@echo ""
	@$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

dev-backend: ## Start backend dev server with hot reload
	cd $(BACKEND_DIR) && ../$(VENV_UVICORN) app.main:app --reload --port $(UVICORN_PORT)

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
	cd $(BACKEND_DIR) && ../$(VENV_UVICORN) app.main:app --host 0.0.0.0 --port $(UVICORN_PORT) --workers 4

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

db-reset: ## Reset the SQLite database
	@echo "$(CYAN)Resetting database...$(RESET)"
	rm -f $(BACKEND_DIR)/rag_pipeline.db
	@echo "$(GREEN)Database reset. It will be recreated on next server start.$(RESET)"

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

docker-up: ## Start services with Docker Compose (placeholder)
	@echo "$(CYAN)Docker support coming soon.$(RESET)"

docker-down: ## Stop Docker Compose services (placeholder)
	@echo "$(CYAN)Docker support coming soon.$(RESET)"
