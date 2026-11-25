.PHONY: help install build run dev api ui test lint fmt clean

help: ## List targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

install: ## Install API and UI dependencies
	cd api && uv sync
	cd ui && npm install

build: ## Build the UI into ui/dist
	cd ui && npm run build

run: build ## Build the UI, then serve everything on http://localhost:8000
	cd api && uv run uvicorn main:app --port 8000

api: ## Backend only, with auto-reload (port 8000)
	cd api && uv run uvicorn main:app --port 8000 --reload

ui: ## Vite dev server with hot reload (port 5173, proxies /api)
	cd ui && npm run dev

dev: ## Run api and web together for development
	$(MAKE) -j2 api ui

test: ## Run backend tests
	cd api && uv run pytest

lint: ## Lint and format-check the backend, and build-check the UI
	cd api && uv run ruff check .
	cd api && uv run ruff format --check .
	cd ui && npm run build

fmt: ## Auto-format the backend
	cd api && uv run ruff check --fix .
	cd api && uv run ruff format .

clean: ## Remove build output
	rm -rf ui/dist api/.pytest_cache api/.ruff_cache
