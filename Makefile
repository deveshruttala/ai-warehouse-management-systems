.DEFAULT_GOAL := help
PY ?= python3.12
VENV := .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: help setup setup-cv backend frontend test lint clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv, install backend + frontend deps
	$(PY) -m venv $(VENV)
	$(VENV_PIP) install -U pip
	$(VENV_PIP) install -r backend/requirements.txt
	cd frontend && npm install

setup-cv: ## (Optional) install YOLO/OpenCV deps for real CCTV
	$(VENV_PIP) install -r backend/requirements-cv.txt

backend: ## Run the API + pipeline (http://localhost:8000)
	cd backend && ../$(VENV_PY) -m uvicorn app.main:app --reload --port 8000

frontend: ## Run the dashboard dev server (http://localhost:5173)
	cd frontend && npm run dev

test: ## Run the backend test suite
	cd backend && ../$(VENV_PY) -m pytest -q

clean: ## Remove venv, node_modules, db and caches
	rm -rf $(VENV) frontend/node_modules frontend/dist backend/*.db backend/.pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

docker-up: ## Build & run the full stack via Docker (dashboard :8080)
	docker compose up --build

docker-down: ## Stop the Docker stack
	docker compose down
