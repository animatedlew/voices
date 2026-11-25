.PHONY: help install build run dev api web test lint fmt clean

help: ## List targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

install: ## Install Python and frontend dependencies
	uv sync
	cd frontend && npm install

build: ## Build the frontend into frontend/dist
	cd frontend && npm run build

run: build ## Build the frontend, then serve everything on http://localhost:8000
	uv run uvicorn main:app --port 8000

api: ## Backend only, with auto-reload (port 8000)
	uv run uvicorn main:app --port 8000 --reload

web: ## Vite dev server with hot reload (port 5173, proxies /api)
	cd frontend && npm run dev

dev: ## Run api and web together for development
	$(MAKE) -j2 api web

test: ## Run backend tests
	uv run pytest

lint: ## Lint and format-check the backend, and build-check the frontend
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run build

fmt: ## Auto-format the backend
	uv run ruff check --fix .
	uv run ruff format .

clean: ## Remove build output
	rm -rf frontend/dist .pytest_cache .ruff_cache
