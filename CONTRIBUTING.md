# Contributing

Thank you for your interest in contributing to the RAG Optimization Pipeline! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork and set up the project:
   ```bash
   git clone https://github.com/<your-username>/rag-optimization-pipeline.git
   cd rag-optimization-pipeline
   make setup
   ```
3. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
4. Start the development servers:
   ```bash
   make dev
   ```

## Development Workflow

1. Make your changes with atomic, descriptive commits
2. Ensure all linters pass:
   ```bash
   make lint
   ```
3. Run the test suite:
   ```bash
   make test
   ```
4. Push your branch and open a Pull Request with a clear description

## Conventions

### Language

- All PRs, commit messages, and documentation must be in **English**

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) prefixes:

| Prefix     | Usage                                      |
|------------|------------------------------------------- |
| `feat:`    | New feature                                |
| `fix:`     | Bug fix                                    |
| `chore:`   | Maintenance, dependency updates            |
| `docs:`    | Documentation only                         |
| `refactor:`| Code restructuring without behavior change |
| `test:`    | Adding or updating tests                   |

### Backend

- Follow **FastAPI** patterns with **Pydantic** schemas for validation
- New services go in `backend/app/services/`
- New API routes go in `backend/app/api/`
- Database models go in `backend/app/models/`
- Schemas (request/response) go in `backend/app/schemas/`

### Frontend

- Uses **Next.js 14 App Router** with client components
- Components go in `frontend/src/components/`
- Step-specific components go in `frontend/src/components/steps/`
- Use Tailwind CSS for styling — follow the existing theme token system (`text-primary`, `bg-surface-100`, `text-accent`, etc.)
- Use [Lucide React](https://lucide.dev/) for icons

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Reference related issues (e.g., `Closes #42`)
- Ensure CI checks pass before requesting review
