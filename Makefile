# Makefile for Home Inventory Tracker

APP_NAME := home-app
DEPLOYMENT := $(APP_NAME)
IMAGE := fogcat5/$(APP_NAME)
NAMESPACE := default
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
PYTHON = $(VENV)/bin/python
SRC_DIR := scripts
TAG := latest
VENV = venv

.PHONY: all build push deploy logs shell test coverage open-coverage clean

all: spell lint format test build

dev: $(VENV)/bin/activate

$(VENV)/bin/activate:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "⬆️  Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "📦 Installing required packages..."
	$(PIP) install fastapi python-multipart uvicorn pillow openai jinja2 dotenv
	$(PIP) install -r requirements.txt

build:
	docker build -t $(IMAGE):$(TAG) . --load

run-local: build
	docker run -it --rm -p 8000:8000 -e NOLOGIN=1 tracker-app

push:
	docker push $(IMAGE):$(TAG)

deploy:
	kubectl rollout restart deployment $(DEPLOYMENT) -n $(NAMESPACE)

logs:
	kubectl logs -l app=$(APP_NAME) --tail=100 -n $(NAMESPACE)

shell:
	kubectl exec -it deploy/$(DEPLOYMENT) -n $(NAMESPACE) -- /bin/bash

apply-secrets:
	kubectl apply -f k8s/secrets.yaml

describe:
	kubectl describe deployment $(DEPLOYMENT) -n $(NAMESPACE)

tag:
	@read -p "Enter tag version: " version; \
	docker tag $(IMAGE):latest $(IMAGE):$$version; \
	docker push $(IMAGE):$$version

# 🧪 Tests

coverage:
	$(PYTEST) --cov=scripts --cov-report=term-missing --cov-report=html

open-coverage:
	xdg-open htmlcov/index.ht

# Run tests with coverage
test:
	pytest --cov=$(SRC_DIR) --cov-report=term-missing --cov-fail-under=85

# Run pylint (warnings only)
lint:
	pylint $(SRC_DIR) --fail-under=8.5 || true

# Check spelling (ignoring common noise)
spell:
	codespell . --skip="venv,htmlcov,.venv,*.db,*.jpg,*.png,*.sqlite3" --ignore-words-list="nd"

# Run Ruff lint + formatter
format:
	echo "docformatter"
	docformatter --in-place --wrap-summaries 80 --wrap-descriptions 80 -r $(SRC_DIR) --exclude venv
	echo "ruff check"
	ruff check $(SRC_DIR)
	echo "ruff format"
	ruff format $(SRC_DIR)

format-fix:
	ruff format --fix $(SRC_DIR)

pre-commit:
	pre-commit run --all-files -v
